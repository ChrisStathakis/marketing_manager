import django_filters

from .models import Task


class TaskFilter(django_filters.FilterSet):
    """Supports calendar range queries: ?due_date__gte=...&due_date__lte=..."""

    due_date__gte = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date__lte = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Task
        fields = ["campaign", "done", "suggestion"]
