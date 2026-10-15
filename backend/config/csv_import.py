"""Shared CSV import helpers.

Imports validate every row through a DRF serializer instead of trusting the
file: bad rows are reported back with their line number and skipped, good rows
are applied one at a time inside their own transaction so one failure cannot
poison the rest of the import.
"""
from django.db import transaction

# CSV headers that should be treated as aliases of the canonical field name.
COLUMN_ALIASES = {
    "campaign_id": "campaign",
    "channel_id": "channel",
}


def clean_row(row: dict) -> dict:
    """Normalize a DictReader row: lowercase/strip keys, drop blank values."""
    data = {}
    for key, value in row.items():
        if key is None:  # extra columns with no header
            continue
        name = COLUMN_ALIASES.get(key.strip().lower(), key.strip().lower())
        if value is None:
            continue
        value = value.strip()
        if value == "":
            continue
        data[name] = value
    return data


def format_errors(errors) -> str:
    """Flatten DRF serializer errors into one human-readable string."""
    parts = []
    for field, messages in errors.items():
        if isinstance(messages, (list, tuple)):
            text = "; ".join(str(m) for m in messages)
        else:
            text = str(messages)
        label = "" if field == "non_field_errors" else f"{field}: "
        parts.append(f"{label}{text}")
    return " | ".join(parts) or "invalid row"


def _is_blank(raw: dict) -> bool:
    return all(v is None or not str(v).strip() for v in raw.values())


def run_import(reader, row_serializer_cls, apply_row):
    """Validate and apply CSV rows.

    ``apply_row(validated_data)`` must return True when a new object was
    created and False when an existing row was updated.

    Returns ``(created, updated, errors)`` where errors is a list of
    ``{"row": <line number>, "error": <message>}`` (line 1 is the header).
    """
    created = updated = 0
    errors = []
    for row_num, raw in enumerate(reader, start=2):
        if raw is None or _is_blank(raw):
            continue
        ser = row_serializer_cls(data=clean_row(raw))
        if not ser.is_valid():
            errors.append({"row": row_num, "error": format_errors(ser.errors)})
            continue
        try:
            with transaction.atomic():
                was_created = apply_row(ser.validated_data)
        except Exception as exc:  # DB-level failure (FK race, constraint, ...)
            errors.append({"row": row_num, "error": str(exc)})
            continue
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated, errors


def import_response(created: int, updated: int, errors: list[dict]) -> dict:
    return {
        "created": created,
        "updated": updated,
        "error_count": len(errors),
        "errors": errors,
    }
