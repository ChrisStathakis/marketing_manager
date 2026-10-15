from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """PageNumberPagination with an opt-in ?page_size= (capped at 500).

    List pages use the default 20 via the browsing UI; tables that should show
    a whole dataset (campaign detail results/tasks) request a larger page.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500
