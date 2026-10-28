from datetime import date, timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from content.models import ContentItem
from plans.models import Task

from .models import Campaign
from .serializers import CampaignSerializer


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.select_related("playbook").all()
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "owner", "playbook"]
    search_fields = ["name", "objective", "utm_campaign", "round_label"]
    ordering_fields = ["created_at", "start_date", "budget", "name"]

    def perform_create(self, serializer):
        if not serializer.validated_data.get("owner"):
            serializer.save(owner=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Clone a campaign and shift its calendar to a new start date.

        The playbook run is the normal way to start fresh; this is for the case
        where someone has edited the calendar by hand and wants the same shape
        next month without rebuilding it.
        """
        source = self.get_object()
        payload = request.data if isinstance(request.data, dict) else {}
        raw_start = payload.get("start_date")
        try:
            new_start = (
                date.fromisoformat(str(raw_start))
                if raw_start
                else (source.start_date or timezone.localdate())
            )
        except (TypeError, ValueError):
            return Response({"detail": "start_date must be an ISO date."}, status=400)

        delta = new_start - (source.start_date or new_start)
        new_end = source.end_date + delta if source.end_date else None
        name = (payload.get("name") or f"{source.name} — copy").strip()
        utm = (payload.get("utm_campaign") or source.utm_campaign).strip()
        clone = Campaign.objects.create(
            name=name,
            objective=source.objective,
            budget=source.budget,
            status="planned",
            playbook=source.playbook,
            round_label=payload.get("round_label") or source.round_label,
            locales=source.locales,
            platforms=source.platforms,
            start_date=new_start,
            end_date=new_end,
            utm_campaign=utm,
            landing_path=source.landing_path,
            owner=request.user if not source.owner else source.owner,
        )

        copied_items = 0
        for item in source.items.select_related("channel").all():
            ContentItem.objects.create(
                campaign=clone,
                channel=item.channel,
                card_set=item.card_set,
                title=item.title,
                copy=item.copy,
                asset_url=item.asset_url,
                link=item.link.replace(source.utm_campaign, utm) if source.utm_campaign and item.link else item.link,
                utm_source=item.utm_source,
                utm_medium=item.utm_medium,
                utm_campaign=utm,
                utm_content=item.utm_content,
                locale=item.locale,
                format=item.format,
                content_kind=item.content_kind,
                thread=item.thread,
                notes=item.notes,
                publish_at=item.publish_at + delta if item.publish_at else None,
                status="scheduled" if item.publish_at else item.status,
            )
            copied_items += 1

        copied_tasks = 0
        for task in source.tasks.all():
            Task.objects.create(
                campaign=clone,
                title=task.title,
                notes=task.notes,
                due_date=task.due_date + delta if task.due_date else None,
                done=False,
            )
            copied_tasks += 1

        serializer = self.get_serializer(clone)
        return Response(
            {
                **serializer.data,
                "copied_items": copied_items,
                "copied_tasks": copied_tasks,
                "shift_days": delta.days,
            },
            status=201,
        )
