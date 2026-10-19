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


class StatCard(models.Model):
    """A rendered share image plus the numbers it was built from."""

    KIND_CHOICES = [
        ("player", "Player card"),
        ("comparison", "Player comparison"),
        ("metric", "Metric of the day"),
        ("round_recap", "Round recap"),
        ("matchup", "Team matchup"),
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
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default="x")
    title = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to=card_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["kind"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return self.title or f"{self.get_kind_display()} ({self.format})"


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
    url = models.URLField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    impressions = models.PositiveIntegerField(default=0)
    engagements = models.PositiveIntegerField(default=0, help_text="Likes + upvotes + saves + shares.")
    comments = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at", "-created_at"]
        indexes = [models.Index(fields=["platform"]), models.Index(fields=["posted_at"])]

    def __str__(self):
        return f"{self.get_platform_display()} — {self.posted_at:%Y-%m-%d}" if self.posted_at else self.get_platform_display()

    @property
    def engagement_rate(self) -> float | None:
        return round(self.engagements / self.impressions, 4) if self.impressions else None

    @property
    def click_rate(self) -> float | None:
        return round(self.clicks / self.impressions, 4) if self.impressions else None


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
    sessions = models.PositiveIntegerField(default=0)
    engaged_sessions = models.PositiveIntegerField(default=0)
    users = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-sessions"]
        constraints = [
            models.UniqueConstraint(fields=["date", "source", "medium"], name="growth_traffic_unique_day_source"),
        ]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["source"])]

    def __str__(self):
        return f"{self.date} · {self.source} ({self.sessions} sessions)"

    @property
    def engagement_rate(self) -> float | None:
        return round(self.engaged_sessions / self.sessions, 4) if self.sessions else None


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
