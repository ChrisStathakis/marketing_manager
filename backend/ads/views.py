import csv
import io

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.csv_import import import_response, run_import

from .filters import AdSpendFilter
from .models import AdSpend
from .serializers import AdSpendImportRowSerializer, AdSpendSerializer

EXPORT_COLUMNS = ["campaign", "channel", "date", "spend", "impressions", "clicks", "conversions"]


class AdSpendViewSet(viewsets.ModelViewSet):
    queryset = AdSpend.objects.select_related("campaign", "channel").all()
    serializer_class = AdSpendSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = AdSpendFilter
    ordering_fields = ["date", "spend"]

    SPEND_FIELDS = ("spend", "impressions", "clicks", "conversions")

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            text = upload.read().decode("utf-8-sig")
        except Exception:
            return Response({"detail": "unreadable file."}, status=status.HTTP_400_BAD_REQUEST)

        def apply_row(row):
            _, was_created = AdSpend.objects.update_or_create(
                campaign=row["campaign"],
                channel=row.get("channel"),
                date=row["date"],
                defaults={
                    **{field: row[field] for field in self.SPEND_FIELDS},
                    "source": AdSpend.SOURCE_MANUAL,
                },
            )
            return was_created

        created, updated, errors = run_import(
            csv.DictReader(io.StringIO(text)), AdSpendImportRowSerializer, apply_row
        )
        return Response(import_response(created, updated, errors))

    @action(detail=False, methods=["get"], url_path="export-csv")
    def export_csv(self, request):
        """Export the filtered spend rows as an import-compatible CSV."""
        queryset = self.filter_queryset(self.get_queryset()).order_by("date", "campaign_id", "channel_id")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="spend.csv"'
        writer = csv.writer(response)
        writer.writerow(EXPORT_COLUMNS)
        for row in queryset.iterator():
            writer.writerow(
                [
                    row.campaign_id,
                    row.channel_id or "",
                    row.date.isoformat(),
                    row.spend,
                    row.impressions,
                    row.clicks,
                    row.conversions,
                ]
            )
        return response
