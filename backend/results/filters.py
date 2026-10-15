import django_filters

from .models import DailyMetric


class DailyMetricFilter(django_filters.FilterSet):
    """Supports reporting ranges: ?date__gte=...&date__lte=..."""

    date__gte = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date__lte = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = DailyMetric
        fields = ["campaign", "date"]
