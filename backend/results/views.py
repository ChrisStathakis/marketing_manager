import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.csv_import import import_response, run_import

from .models import DailyMetric
from .serializers import DailyMetricSerializer, MetricImportRowSerializer


class DailyMetricViewSet(viewsets.ModelViewSet):
    queryset = DailyMetric.objects.select_related("campaign").all()
    serializer_class = DailyMetricSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "date"]
    ordering_fields = ["date", "revenue", "spend"]

    METRIC_FIELDS = ("revenue", "orders", "spend", "ctr", "roas")

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
            _, was_created = DailyMetric.objects.update_or_create(
                campaign=row["campaign"],
                date=row["date"],
                defaults={field: row[field] for field in self.METRIC_FIELDS},
            )
            return was_created

        created, updated, errors = run_import(
            csv.DictReader(io.StringIO(text)), MetricImportRowSerializer, apply_row
        )
        return Response(import_response(created, updated, errors))
