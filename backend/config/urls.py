from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from ads.views import AdSpendViewSet
from campaigns.views import CampaignViewSet
from channels.views import ChannelViewSet
from config.backup_views import backup_database, backup_export, backup_restore
from config.dashboard import health, public_config, summary
from config.registration import RegisterView
from content.views import ContentAssetViewSet, ContentItemViewSet
from google_sync.views import sync_google_analytics, sync_google_search_console
from growth.views import (
    BoostViewSet,
    CaptionDraftView,
    CardPreviewView,
    CardSetViewSet,
    GrowthExperimentViewSet,
    GrowthInsightsView,
    GrowthMetaView,
    GrowthPlayersView,
    GrowthReportView,
    GrowthSearchConsoleView,
    GrowthSuggestView,
    GrowthTeamsView,
    GrowthTrafficSyncView,
    GrowthTrafficView,
    HashtagSetViewSet,
    InstagramAnalysisView,
    InstagramCommentListView,
    InstagramExportView,
    InstagramPostViewSet,
    InstagramTestView,
    KpiTargetViewSet,
    PlanSeedView,
    PlaybookViewSet,
    PostPerformanceViewSet,
    StatCardViewSet,
)
from integrations.views import integration_detail, integration_list
from plans.views import TaskViewSet
from results.views import DailyMetricViewSet
from shop.views import OrderRefViewSet, ProductViewSet
from suggestions.views import SuggestionViewSet

router = DefaultRouter()
router.register("campaigns", CampaignViewSet)
router.register("channels", ChannelViewSet)
router.register("content", ContentItemViewSet)
router.register("content-assets", ContentAssetViewSet)
router.register("spend", AdSpendViewSet)
router.register("metrics", DailyMetricViewSet)
router.register("tasks", TaskViewSet)
router.register("suggestions", SuggestionViewSet)
router.register("products", ProductViewSet)
router.register("orders", OrderRefViewSet)
router.register("cards", StatCardViewSet)
router.register("card-sets", CardSetViewSet)
router.register("performance", PostPerformanceViewSet)
router.register("experiments", GrowthExperimentViewSet)
router.register("playbooks", PlaybookViewSet)
router.register("kpi-targets", KpiTargetViewSet)
router.register("boosts", BoostViewSet)
router.register("hashtag-sets", HashtagSetViewSet)
router.register("growth/instagram/posts", InstagramPostViewSet, basename="instagram-posts")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/dashboard/summary/", summary),
    path("api/health/", health),
    path("api/config/", public_config),
    path("api/integrations/", integration_list),
    path("api/integrations/google-analytics/sync/", sync_google_analytics),
    path("api/integrations/google-search-console/sync/", sync_google_search_console),
    path("api/integrations/<slug:provider>/", integration_detail),
    path("api/backup/export/", backup_export, name="backup_export"),
    path("api/backup/database/", backup_database, name="backup_database"),
    path("api/backup/restore/", backup_restore, name="backup_restore"),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", RegisterView.as_view(), name="register"),
    # Organic growth studio.
    path("api/growth/meta/", GrowthMetaView.as_view()),
    path("api/growth/players/", GrowthPlayersView.as_view()),
    path("api/growth/teams/", GrowthTeamsView.as_view()),
    path("api/growth/suggest/", GrowthSuggestView.as_view()),
    path("api/growth/cards/preview/", CardPreviewView.as_view()),
    path("api/growth/captions/", CaptionDraftView.as_view()),
    path("api/growth/plan/", PlanSeedView.as_view()),
    path("api/growth/report/", GrowthReportView.as_view()),
    path("api/growth/insights/", GrowthInsightsView.as_view()),
    path("api/growth/traffic/", GrowthTrafficView.as_view()),
    path("api/growth/traffic/sync/", GrowthTrafficSyncView.as_view()),
    path("api/growth/search-console/", GrowthSearchConsoleView.as_view()),
    # Instagram audience research (comments on public posts).
    path("api/growth/instagram/comments/", InstagramCommentListView.as_view()),
    path("api/growth/instagram/analysis/", InstagramAnalysisView.as_view()),
    path("api/growth/instagram/export/", InstagramExportView.as_view()),
    path("api/growth/instagram/test/", InstagramTestView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Django admin branding.
admin.site.site_header = "Social Media Manager"
admin.site.site_title = "Social Media Manager"
