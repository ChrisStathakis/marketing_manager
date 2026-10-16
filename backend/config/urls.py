from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from ads.views import AdSpendViewSet
from campaigns.views import CampaignViewSet
from channels.views import ChannelViewSet
from config.dashboard import health, public_config, summary
from config.registration import RegisterView
from content.views import ContentItemViewSet
from integrations.views import integration_detail, integration_list
from plans.views import TaskViewSet
from results.views import DailyMetricViewSet
from shop.views import OrderRefViewSet, ProductViewSet
from suggestions.views import SuggestionViewSet

router = DefaultRouter()
router.register("campaigns", CampaignViewSet)
router.register("channels", ChannelViewSet)
router.register("content", ContentItemViewSet)
router.register("spend", AdSpendViewSet)
router.register("metrics", DailyMetricViewSet)
router.register("tasks", TaskViewSet)
router.register("suggestions", SuggestionViewSet)
router.register("products", ProductViewSet)
router.register("orders", OrderRefViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/dashboard/summary/", summary),
    path("api/health/", health),
    path("api/config/", public_config),
    path("api/integrations/", integration_list),
    path("api/integrations/<slug:provider>/", integration_detail),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", RegisterView.as_view(), name="register"),
]

# Django admin branding.
admin.site.site_header = "Social Media Manager"
admin.site.site_title = "Social Media Manager"
