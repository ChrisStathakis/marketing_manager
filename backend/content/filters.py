import django_filters

from .models import ContentItem


class ContentItemFilter(django_filters.FilterSet):
    """Supports calendar range queries: ?publish_at__gte=...&publish_at__lte=..."""

    publish_at__gte = django_filters.DateTimeFilter(field_name="publish_at", lookup_expr="gte")
    publish_at__lte = django_filters.DateTimeFilter(field_name="publish_at", lookup_expr="lte")

    class Meta:
        model = ContentItem
        fields = ["campaign", "channel", "status", "locale", "format", "content_kind", "card_set"]
