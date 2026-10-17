"""Backup & restore API.

* Export (any authenticated user) — JSON business data, or the SQLite file.
* Restore (staff only) — replace all data from a JSON or SQLite backup file.
"""
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from . import backup as ops


def _stamp() -> str:
    return timezone.localdate().isoformat()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def backup_export(request):
    """Stream every business model as a JSON file (no users or API keys)."""
    payload = ops.build_backup()
    body = json.dumps(payload, cls=DjangoJSONEncoder, indent=2)
    response = HttpResponse(body, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="marketing-backup-{_stamp()}.json"'
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def backup_database(request):
    """Stream a consistent snapshot of the SQLite database file."""
    if connection.vendor != "sqlite":
        return Response(
            {"detail": "Database file download is only available with SQLite. Use the JSON export instead."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    body = ops.sqlite_snapshot_bytes()
    response = HttpResponse(body, content_type="application/x-sqlite3")
    response["Content-Disposition"] = f'attachment; filename="marketing-db-{_stamp()}.sqlite3"'
    return response


@api_view(["POST"])
@permission_classes([IsAdminUser])
def backup_restore(request):
    """Replace all data from an uploaded JSON backup or SQLite database file."""
    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "Attach a backup file under the 'file' field."}, status=status.HTTP_400_BAD_REQUEST)
    if str(request.data.get("confirm", "")).lower() != "replace":
        return Response(
            {"detail": "Send confirm=replace to replace the existing data."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw = upload.read()
    if raw.startswith(ops.SQLITE_MAGIC):
        try:
            ops.restore_database_file(raw)
        except ops.BackupError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "kind": "database",
                "detail": "Database replaced. The previous database was kept as a .bak file; restart the server.",
            }
        )

    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Response(
            {"detail": "That file is neither a JSON backup nor a SQLite database."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        counts = ops.restore(payload)
    except ops.BackupError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"kind": "json", "restored": counts, "detail": "All data replaced from the JSON backup."})
