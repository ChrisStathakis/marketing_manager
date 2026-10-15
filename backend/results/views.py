import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DailyMetric
from .serializers import DailyMetricSerializer


class DailyMetricViewSet(viewsets.ModelViewSet):
    queryset = DailyMetric.objects.select_related("campaign").all()
    serializer_class = DailyMetricSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "date"]
    ordering_fields = ["date", "revenue", "spend"]

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            text = upload.read().decode("utf-8-sig")
        except Exception:
            return Response({"detail": "unreadable file."}, status=status.HTTP_400_BAD_REQUEST)
        reader = csv.DictReader(io.StringIO(text))
        created = updated = 0
        for row in reader:
            try:
                obj, was_created = DailyMetric.objects.update_or_create(
                    campaign_id=int(row.get("campaign") or row.get("campaign_id") or 0),
                    date=row["date"],
                    defaults={
                        "revenue": row.get("revenue") or 0,
                        "orders": row.get("orders") or 0,
                        "spend": row.get("spend") or 0,
                        "ctr": row.get("ctr") or 0,
                        "roas": row.get("roas") or 0,
                    },
                )
                created += 1 if was_created else 0
                updated += 0 if was_created else 1
            except Exception:
                continue
        return Response({"created": created, "updated": updated})
