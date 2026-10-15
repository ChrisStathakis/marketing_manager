import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AdSpend
from .serializers import AdSpendSerializer


class AdSpendViewSet(viewsets.ModelViewSet):
    queryset = AdSpend.objects.select_related("campaign", "channel").all()
    serializer_class = AdSpendSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "channel", "date"]
    ordering_fields = ["date", "spend"]

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
                campaign_id = int(row.get("campaign") or row.get("campaign_id") or 0)
                channel_id = row.get("channel") or row.get("channel_id") or None
                obj, was_created = AdSpend.objects.update_or_create(
                    campaign_id=campaign_id,
                    channel_id=int(channel_id) if channel_id else None,
                    date=row["date"],
                    defaults={
                        "spend": row.get("spend") or 0,
                        "impressions": row.get("impressions") or 0,
                        "clicks": row.get("clicks") or 0,
                        "conversions": row.get("conversions") or 0,
                    },
                )
                created += 1 if was_created else 0
                updated += 0 if was_created else 1
            except Exception:
                continue
        return Response({"created": created, "updated": updated})
