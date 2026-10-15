import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.csv_import import import_response, run_import

from .models import AdSpend
from .serializers import AdSpendImportRowSerializer, AdSpendSerializer


class AdSpendViewSet(viewsets.ModelViewSet):
    queryset = AdSpend.objects.select_related("campaign", "channel").all()
    serializer_class = AdSpendSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "channel", "date"]
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
                defaults={field: row[field] for field in self.SPEND_FIELDS},
            )
            return was_created

        created, updated, errors = run_import(
            csv.DictReader(io.StringIO(text)), AdSpendImportRowSerializer, apply_row
        )
        return Response(import_response(created, updated, errors))
