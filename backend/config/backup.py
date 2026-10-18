"""Backup & restore helpers.

Two formats are supported:

* **JSON business data** — every business model (campaigns, channels, content,
  results, ad spend, tasks, suggestions, products, orders, saved growth cards,
  post performance, experiments and GA4 traffic snapshots) is serialized to a
  plain dict. Users, passwords and
  stored API keys are deliberately *excluded*.
  ``Campaign.owner`` is written as a username so a restore can map it even when
  the backup is loaded into an instance with different user ids.

* **SQLite database file** — a consistent snapshot of ``db.sqlite3`` (users and
  encrypted credentials included). Only available with the SQLite backend.

Restores replace the existing data: the JSON path wipes and reloads the
business tables, the database-file path overwrites ``db.sqlite3`` after taking
a safety copy.
"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

User = get_user_model()

FORMAT = "marketing-manager-backup"
FORMAT_VERSION = 1
SQLITE_MAGIC = b"SQLite format 3\x00"

# Ordered so every row's foreign keys already exist when it is inserted.
# (Reverse this order when deleting.) Only business data — never auth users.
BUSINESS_MODELS = [
    "channels.Channel",
    "campaigns.Campaign",
    "shop.Product",
    "shop.OrderRef",
    "content.ContentItem",
    "ads.AdSpend",
    "results.DailyMetric",
    "suggestions.Suggestion",
    "plans.Task",
    "growth.StatCard",
    "growth.PostPerformance",
    "growth.GrowthExperiment",
    "growth.TrafficSnapshot",
]


class BackupError(ValueError):
    """A backup file could not be read or applied."""


def _business_models():
    return [django_apps.get_model(label) for label in BUSINESS_MODELS]


def _serialize() -> tuple[dict, dict]:
    data: dict[str, list] = {}
    counts: dict[str, int] = {}
    for label in BUSINESS_MODELS:
        model = django_apps.get_model(label)
        rows = []
        for obj in model._default_manager.all().order_by("pk"):
            record: dict = {"pk": obj.pk}
            for field in model._meta.concrete_fields:
                if field.primary_key:
                    continue
                value = field.value_from_object(obj)
                if field.is_relation and field.related_model == User:
                    # Reference the user by username, not pk.
                    record[field.name] = getattr(obj, field.name).username if value else None
                    continue
                if field.is_relation:
                    record[field.name] = value  # target primary key
                    continue
                record[field.name] = value
            rows.append(record)
        data[label] = rows
        counts[label] = len(rows)
    return data, counts


def build_backup() -> dict:
    data, counts = _serialize()
    return {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "exported_at": timezone.now().isoformat(),
        "counts": counts,
        "data": data,
    }


def _reset_sequences():
    """Realign auto-increment sequences after inserting explicit primary keys."""
    reset_sql = getattr(connection.ops, "sequence_reset_sql", None)
    if reset_sql is None:
        return
    statements = reset_sql(no_style(), _business_models())
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


@transaction.atomic
def restore(payload: dict) -> dict:
    """Replace all business data with the contents of a JSON backup."""
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise BackupError("That file is not a Marketing Manager backup.")
    if payload.get("version") != FORMAT_VERSION:
        raise BackupError(f"Unsupported backup version: {payload.get('version')!r}.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BackupError("The backup file has no data section.")

    users = {user.username: user for user in User.objects.all()}

    prepared: list[tuple] = []
    for label in BUSINESS_MODELS:
        model = django_apps.get_model(label)
        records = data.get(label, [])
        if not isinstance(records, list):
            raise BackupError(f"Malformed backup: {label} is not a list.")
        prepared.append((label, model, records))

    # Replace everything: clear business tables, then load the backup back in.
    for label in reversed(BUSINESS_MODELS):
        django_apps.get_model(label)._default_manager.all().delete()

    counts: dict[str, int] = {}
    for label, model, records in prepared:
        for record in records:
            if not isinstance(record, dict) or "pk" not in record:
                raise BackupError(f"Malformed backup row for {label}.")
            field_values: dict = {}
            auto_values: dict = {}
            for field in model._meta.concrete_fields:
                if field.primary_key or field.name not in record:
                    continue
                value = record[field.name]
                if field.is_relation and field.related_model == User:
                    owner = users.get(value) if value else None
                    field_values[field.attname] = owner.pk if owner else None
                    continue
                if field.is_relation:
                    field_values[field.attname] = value
                    continue
                python_value = None if value is None else field.to_python(value)
                if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
                    # auto_now* would be overwritten on save; reapply afterwards.
                    auto_values[field.attname] = python_value
                else:
                    field_values[field.name] = python_value
            obj = model._default_manager.create(pk=record["pk"], **field_values)
            if auto_values:
                model._default_manager.filter(pk=obj.pk).update(**auto_values)
        counts[label] = len(records)

    _reset_sequences()
    return counts


def sqlite_snapshot_bytes() -> bytes:
    """Return a consistent copy of the SQLite database as bytes.

    Built from Django's live connection (via ``iterdump``) so in-memory
    databases used by the test runner work as well as an on-disk file. The
    SQLite backup API is avoided because it can deadlock on a shared-cache
    in-memory database with an open transaction.
    """
    handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    handle.close()
    try:
        connection.ensure_connection()
        destination = sqlite3.connect(handle.name)
        try:
            for statement in connection.connection.iterdump():
                destination.execute(statement)
            destination.commit()
        finally:
            destination.close()
        with open(handle.name, "rb") as file:
            return file.read()
    finally:
        try:
            os.remove(handle.name)
        except OSError:
            pass


def _table_names(path: str) -> set:
    con = sqlite3.connect(path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        con.close()
    return {row[0] for row in rows}


def restore_database_file(raw: bytes) -> None:
    """Replace ``db.sqlite3`` with an uploaded database file (SQLite only).

    A timestamped copy of the previous database is kept next to it so a bad
    upload can be recovered. The caller should restart the server afterwards.
    """
    if connection.vendor != "sqlite":
        raise BackupError("Restoring a database file is only available with SQLite.")
    if not raw.startswith(SQLITE_MAGIC):
        raise BackupError("That file is not a SQLite database.")

    db_path = Path(settings.DATABASES["default"]["NAME"])
    handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    handle.write(raw)
    handle.close()
    try:
        con = sqlite3.connect(handle.name)
        try:
            result = con.execute("PRAGMA integrity_check").fetchone()
        finally:
            con.close()
        if not result or result[0] != "ok":
            raise BackupError("The uploaded database file is corrupt.")
        if "django_migrations" not in _table_names(handle.name):
            raise BackupError("That SQLite file does not look like a Marketing Manager database.")

        if db_path.exists():
            stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(db_path, f"{db_path}.bak-{stamp}")

        # Close Django's handles so the file can be replaced (notably on Windows),
        # and drop stale WAL/SHM sidecars that would shadow the new file.
        connection.close()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{db_path}{suffix}")
            if sidecar.exists():
                try:
                    sidecar.unlink()
                except OSError:
                    pass
        os.replace(handle.name, db_path)
        handle = None
    finally:
        if handle is not None:
            try:
                os.remove(handle.name)
            except OSError:
                pass


__all__ = [
    "BackupError",
    "FORMAT",
    "SQLITE_MAGIC",
    "build_backup",
    "restore",
    "restore_database_file",
    "sqlite_snapshot_bytes",
]
