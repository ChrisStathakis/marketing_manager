"""Models for organic growth work: shareable stat cards, post results, experiments.

Nothing here touches ad spend. A "campaign" is reused as the container for a
content series (for example "EuroLeague 2026-27 organic"), and `ContentItem` /
`Task` stay the calendar and to-do list.
"""

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone


def card_upload_path(instance, filename):
    stamp = timezone.now()
    extension = (filename.rsplit(".", 1)[-1] or "png").lower()
    return f"growth/cards/{stamp:%Y/%m}/{uuid4().hex}.{extension}"


#: Shared between playbook slots, content items and performance rows. "Photo
#: carousel" is TikTok's still-image format; "thread" is an X post that ships as
#: several tweets. Keeping the vocabulary in one place means a slot can be
#: turned into a calendar entry without a translation table.
CONTENT_FORMAT_CHOICES = [
    ("post", "Feed post"),
    ("carousel", "Carousel"),
    ("reel", "Reel / short video"),
    ("story", "Story"),
    ("thread", "Thread"),
    ("photo_carousel", "Photo carousel"),
    ("short", "Short video"),
    ("text_post", "Text post"),
    ("video", "Video"),
    ("other", "Other"),
]

LOCALE_CHOICES = [
    ("en", "English"),
    ("el", "Greek"),
    ("tr", "Turkish"),
    ("sr", "Serbian"),
    ("lt", "Lithuanian"),
]

KPI_METRIC_CHOICES = [
    ("impressions", "Impressions"),
    ("reach", "Reach"),
    ("engagements", "Engagements"),
    ("saves", "Saves"),
    ("shares", "Shares"),
    ("comments", "Comments"),
    ("profile_visits", "Profile visits"),
    ("clicks", "Link clicks"),
    ("signups", "Signups"),
    ("upvote_ratio", "Reddit upvote ratio"),
    ("sessions", "GA4 sessions"),
    ("search_clicks", "Google Search clicks"),
    ("search_impressions", "Google Search impressions"),
    ("search_ctr", "Google Search CTR"),
    ("spend", "Paid spend"),
]

PLAYBOOK_PLATFORM_CHOICES = [
    ("x", "X / Twitter"),
    ("instagram", "Instagram"),
    ("reddit", "Reddit"),
    ("tiktok", "TikTok"),
    ("facebook", "Facebook"),
    ("linkedin", "LinkedIn"),
    ("youtube", "YouTube"),
    ("telegram", "Telegram"),
    ("other", "Other"),
]


class StatCard(models.Model):
    """A rendered share image plus the numbers it was built from."""

    KIND_CHOICES = [
        ("player", "Player card"),
        ("comparison", "Player comparison"),
        ("metric", "Metric of the day"),
        ("round_recap", "Round recap"),
        ("matchup", "Team matchup"),
        ("team", "Team card"),
        ("team_delta", "Team season delta"),
        ("top8", "Top 8 table"),
    ]
    FORMAT_CHOICES = [
        ("x", "X / Twitter — 1600×900"),
        ("instagram", "Instagram — 1080×1350"),
        ("story", "Story / TikTok — 1080×1920"),
        ("reddit", "Reddit — 1200×1200"),
        ("og", "Open Graph — 1200×630"),
    ]

    campaign = models.ForeignKey(
        "campaigns.Campaign", null=True, blank=True, on_delete=models.SET_NULL, related_name="stat_cards"
    )
    card_set = models.ForeignKey(
        "growth.CardSet", null=True, blank=True, on_delete=models.SET_NULL, related_name="slides"
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default="x")
    title = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to=card_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return self.title or f"{self.get_kind_display()} ({self.format})"


class CardSet(models.Model):
    """An ordered group of slides, usually one carousel.

    The rendered PNGs live on ``StatCard`` rows because the card library can
    already list, preview and delete them; this model only records that they
    belong together and what the set was built from.
    """

    campaign = models.ForeignKey(
        "campaigns.Campaign", null=True, blank=True, on_delete=models.SET_NULL, related_name="card_sets"
    )
    kind = models.CharField(max_length=20, choices=StatCard.KIND_CHOICES, default="top8")
    format = models.CharField(max_length=20, choices=StatCard.FORMAT_CHOICES, default="instagram")
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Playbook(models.Model):
    """A reusable content series. A run creates a Campaign and its calendar.

    Nothing about a playbook is tied to a particular month: every slot stores a
    *day offset* and a time, and ``run`` combines those with the start date the
    operator chooses. That is what makes "run it again for the next round" a
    data-entry action rather than a code change.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    default_locales = models.JSONField(default=list, blank=True)
    default_platforms = models.JSONField(default=list, blank=True)
    is_seeded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PlaybookSlot(models.Model):
    """One planned post inside a playbook, positioned by day offset, not date."""

    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE, related_name="slots")
    order = models.PositiveIntegerField(default=0)
    day_offset = models.PositiveIntegerField(default=0, help_text="Days after the run's start date.")
    time = models.TimeField(default="12:00")
    platform = models.CharField(max_length=20, choices=PLAYBOOK_PLATFORM_CHOICES, default="x")
    format = models.CharField(max_length=20, choices=CONTENT_FORMAT_CHOICES, default="post")
    content_kind = models.CharField(max_length=20, choices=StatCard.KIND_CHOICES, blank=True)
    locales = models.JSONField(default=list, blank=True, help_text="Empty means the run's selected locales.")
    title_template = models.CharField(max_length=255)
    brief = models.TextField(blank=True)
    utm_content_template = models.CharField(max_length=160, blank=True)
    asset_required = models.BooleanField(default=False)
    paid_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_task_only = models.BooleanField(default=False, help_text="Create a to-do but no calendar post.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["playbook", "order"])]

    def __str__(self):
        return f"{self.playbook} · day {self.day_offset} · {self.title_template}"


class KpiTarget(models.Model):
    """A target the run is judged against, not just an after-the-fact actual."""

    campaign = models.ForeignKey(
        "campaigns.Campaign", on_delete=models.CASCADE, related_name="kpi_targets"
    )
    metric = models.CharField(max_length=30, choices=KPI_METRIC_CHOICES)
    target = models.FloatField()
    window_start = models.DateField(null=True, blank=True)
    window_end = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["metric", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "metric", "window_start", "window_end"],
                name="growth_kpi_unique_target_window",
            ),
        ]

    def __str__(self):
        return f"{self.campaign} · {self.get_metric_display()} ≥ {self.target:g}"


class Boost(models.Model):
    """A planned or running paid boost. Spend lives here; results in AdSpend."""

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("running", "Running"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    campaign = models.ForeignKey(
        "campaigns.Campaign", null=True, blank=True, on_delete=models.SET_NULL, related_name="boosts"
    )
    content_item = models.ForeignKey(
        "content.ContentItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="boosts"
    )
    platform = models.CharField(max_length=20, choices=PLAYBOOK_PLATFORM_CHOICES, default="instagram")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    objective = models.CharField(max_length=120, blank=True, help_text="e.g. profile visits, link clicks, signups.")
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    targeting = models.JSONField(default=dict, blank=True)
    cpa_target = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_platform_display()} boost · {self.campaign or 'no campaign'}"


class HashtagSet(models.Model):
    """A named, reusable tag bank so a run does not retype 12 hashtags."""

    name = models.CharField(max_length=120)
    locale = models.CharField(max_length=8, choices=LOCALE_CHOICES, default="en")
    platform = models.CharField(max_length=20, choices=PLAYBOOK_PLATFORM_CHOICES, blank=True)
    tags = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "locale"]

    def __str__(self):
        return f"{self.name} ({self.locale})"


class PostPerformance(models.Model):
    """What one published post actually did.

    Kept separate from `results.DailyMetric` on purpose: that model is about
    money per campaign, this one is about reach per post.
    """

    PLATFORM_CHOICES = [
        ("x", "X / Twitter"),
        ("reddit", "Reddit"),
        ("instagram", "Instagram"),
        ("tiktok", "TikTok"),
        ("facebook", "Facebook"),
        ("linkedin", "LinkedIn"),
        ("youtube", "YouTube"),
        ("telegram", "Telegram"),
        ("discord", "Discord"),
        ("other", "Other"),
    ]

    campaign = models.ForeignKey(
        "campaigns.Campaign", null=True, blank=True, on_delete=models.SET_NULL, related_name="post_performance"
    )
    content_item = models.ForeignKey(
        "content.ContentItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance"
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default="x")
    #: Which card the post came from, so the report can say which *kind* works.
    kind = models.CharField(max_length=20, choices=StatCard.KIND_CHOICES, blank=True)
    #: The metric the post was built around (``consistency_score``, ``ts_pct``, …).
    metric_key = models.CharField(max_length=60, blank=True)
    format = models.CharField(max_length=20, choices=CONTENT_FORMAT_CHOICES, blank=True)
    locale = models.CharField(max_length=8, choices=LOCALE_CHOICES, blank=True)
    utm_content = models.CharField(max_length=160, blank=True)
    url = models.URLField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    impressions = models.PositiveIntegerField(default=0)
    reach = models.PositiveIntegerField(default=0)
    engagements = models.PositiveIntegerField(default=0, help_text="Likes + upvotes + saves + shares.")
    saves = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    profile_visits = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    signups = models.PositiveIntegerField(default=0)
    upvote_ratio = models.FloatField(
        null=True, blank=True, help_text="Reddit's upvote ratio, 0–1 (e.g. 0.92 for 92%)."
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at", "-created_at"]
        indexes = [
            models.Index(fields=["platform"]),
            models.Index(fields=["posted_at"]),
            models.Index(fields=["format"]),
            models.Index(fields=["locale"]),
        ]

    def __str__(self):
        return f"{self.get_platform_display()} — {self.posted_at:%Y-%m-%d}" if self.posted_at else self.get_platform_display()

    @property
    def engagement_rate(self) -> float | None:
        return round(self.engagements / self.impressions, 4) if self.impressions else None

    @property
    def click_rate(self) -> float | None:
        return round(self.clicks / self.impressions, 4) if self.impressions else None

    @property
    def save_rate(self) -> float | None:
        return round(self.saves / self.impressions, 4) if self.impressions else None

    @property
    def share_rate(self) -> float | None:
        return round(self.shares / self.impressions, 4) if self.impressions else None


class GrowthExperiment(models.Model):
    """A hook/format test, so wins are repeated instead of remembered."""

    STATUS_CHOICES = [
        ("idea", "Idea"),
        ("running", "Running"),
        ("done", "Done"),
        ("abandoned", "Abandoned"),
    ]

    name = models.CharField(max_length=255)
    hypothesis = models.TextField(blank=True)
    metric = models.CharField(max_length=120, blank=True, help_text="What decides the winner, e.g. click rate on X.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="idea")
    result = models.TextField(blank=True)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class TrafficSnapshot(models.Model):
    """One day of GA4 sessions for one traffic source.

    This is the other half of the growth picture: `PostPerformance` says what
    was published, this says what actually arrived on the site. A source with
    impressions but no sessions is a post that did not travel.
    """

    date = models.DateField()
    source = models.CharField(max_length=120, help_text="GA4 sessionSource, e.g. x, reddit, google.")
    medium = models.CharField(max_length=120, blank=True)
    campaign = models.CharField(max_length=160, blank=True, help_text="GA4 sessionCampaignName (utm_campaign).")
    content = models.CharField(max_length=160, blank=True, help_text="GA4 sessionManualAdContent (utm_content).")
    sessions = models.PositiveIntegerField(default=0)
    engaged_sessions = models.PositiveIntegerField(default=0)
    users = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-sessions"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "source", "medium", "campaign", "content"],
                name="growth_traffic_unique_day_source",
            ),
        ]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["source"]), models.Index(fields=["campaign"])]

    def __str__(self):
        return f"{self.date} · {self.source} ({self.sessions} sessions)"

    @property
    def engagement_rate(self) -> float | None:
        return round(self.engaged_sessions / self.sessions, 4) if self.sessions else None


class SearchConsoleSnapshot(models.Model):
    """One Search Console row for a date, site total, page or query.

    Search Console has no UTM/campaign dimension. Campaigns therefore join to
    it through the canonical paths of the pages they link to; the report labels
    those numbers as *assisted search*, not causal attribution.
    """

    SCOPE_CHOICES = [
        ("total", "Site total"),
        ("page", "Page"),
        ("query", "Query"),
    ]

    date = models.DateField()
    site_url = models.CharField(max_length=255, help_text="Exact Search Console property.")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    page_url = models.URLField(max_length=2000, blank=True)
    page_path = models.CharField(max_length=1000, blank=True)
    query = models.CharField(max_length=500, blank=True)
    clicks = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    ctr = models.FloatField(default=0, help_text="Fraction, e.g. 0.052 for 5.2%.")
    position = models.FloatField(default=0)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-clicks"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "site_url", "scope", "page_path", "query"],
                name="growth_searchconsole_unique_row",
            ),
        ]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["page_path"]),
            models.Index(fields=["query"]),
        ]

    def __str__(self):
        subject = self.page_path or self.query or self.get_scope_display()
        return f"{self.date} · {subject} ({self.clicks} clicks)"


class InstagramTrackedPost(models.Model):
    """A public Instagram post whose commenters we collect (research only).

    Stored separately from `PostPerformance`: that one is about *reach* for the
    posts we publish, this one is about *who* engaged on someone else's post.
    Nothing here is published to Instagram.
    """

    STATUS_CHOICES = [
        ("pending", "Not fetched yet"),
        ("ok", "Fetched"),
        ("error", "Last fetch failed"),
    ]

    url = models.URLField(max_length=500)
    shortcode = models.CharField(max_length=64, unique=True)
    media_pk = models.BigIntegerField(help_text="Numeric media id decoded from the shortcode.")
    owner_username = models.CharField(max_length=150, blank=True)
    caption = models.TextField(blank=True)
    comment_count = models.PositiveIntegerField(
        default=0, help_text="How many comments Instagram reports, as last seen."
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    error = models.TextField(blank=True)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"@{self.owner_username} · {self.shortcode}" if self.owner_username else self.shortcode


class InstagramComment(models.Model):
    """One commenter and their text on a tracked post.

    Unique per ``(post, comment_pk)`` so re-running a scrape is idempotent and
    only the text/likes are refreshed.
    """

    post = models.ForeignKey(InstagramTrackedPost, on_delete=models.CASCADE, related_name="comments")
    comment_pk = models.CharField(max_length=40)
    author_username = models.CharField(max_length=150)
    author_pk = models.CharField(max_length=40, blank=True)
    author_full_name = models.CharField(max_length=255, blank=True)
    text = models.TextField(blank=True)
    commented_at = models.DateTimeField(null=True, blank=True)
    like_count = models.PositiveIntegerField(default=0, help_text="Likes on this comment.")
    child_count = models.PositiveIntegerField(default=0, help_text="Replies to this comment.")
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-commented_at", "-fetched_at"]
        constraints = [
            models.UniqueConstraint(fields=["post", "comment_pk"], name="growth_ig_unique_comment"),
        ]
        indexes = [models.Index(fields=["author_username"])]

    def __str__(self):
        return f"@{self.author_username}: {self.text[:40]}"
