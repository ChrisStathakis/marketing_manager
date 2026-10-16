"""Seed the development database with a realistic demo dataset.

- All writes go through the ORM. Dates are generated relative to *today* so the
  dashboard, calendar and reports always look current.
- Deterministic: a fixed random seed keeps the numbers stable across re-runs.
- Guarded: refuses to run when data already exists unless --reset is passed.
- --reset deletes rows ONLY for the models seeded here (campaigns, channels,
  content, metrics, spend, products, orders, tasks, suggestions). Users and
  saved integration API keys (IntegrationCredential) are never touched.
"""
import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ads.models import AdSpend
from campaigns.models import Campaign
from channels.models import Channel
from content.models import ContentItem
from plans.models import Task
from results.models import DailyMetric
from shop.models import OrderRef, Product
from suggestions.models import Suggestion
from suggestions.services import campaign_snapshot


class Command(BaseCommand):
    help = (
        "Create demo campaigns, channels, content, metrics, ad spend, products, "
        "orders, tasks and suggestions (development only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data first. Never touches users or saved API keys.",
        )
        parser.add_argument(
            "--owner",
            help="Username that will own the demo campaigns (default: first user).",
        )

    def handle(self, *args, **options):
        owner = self._resolve_owner(options.get("owner"))
        if self._has_data() and not options["reset"]:
            raise CommandError(
                "Demo data already exists. Re-run with --reset to rebuild it "
                "(users and saved API keys are kept)."
            )

        self.rng = random.Random(42)
        self.today = timezone.localdate()

        with transaction.atomic():
            if options["reset"]:
                self._reset()
            counts = self._seed_all(owner)

        self.stdout.write(self.style.SUCCESS(f"Demo data ready (owner: {owner.username})."))
        for label, count in counts.items():
            self.stdout.write(f"  {label:<12} {count}")

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _resolve_owner(username):
        user_model = get_user_model()
        if username:
            try:
                return user_model.objects.get(username=username)
            except user_model.DoesNotExist as exc:
                raise CommandError(f"User {username!r} does not exist.") from exc
        owner = user_model.objects.order_by("id").first()
        if owner is None:
            raise CommandError("No user exists yet — run createsuperuser first.")
        return owner

    @staticmethod
    def _has_data():
        return Campaign.objects.exists() or Channel.objects.exists() or Product.objects.exists()

    @staticmethod
    def _reset():
        # Deliberately NOT deleting users or IntegrationCredential (saved API keys).
        for model in (AdSpend, DailyMetric, ContentItem, OrderRef, Task, Suggestion, Product, Campaign, Channel):
            model.objects.all().delete()

    def _seed_all(self, owner):
        channels = self._channels()
        campaigns = self._campaigns(owner)
        self._performance(campaigns, channels)
        self._content(campaigns, channels)
        self._products()
        self._orders(campaigns)
        self._tasks_and_suggestions(campaigns)
        return {
            "channels": Channel.objects.count(),
            "campaigns": Campaign.objects.count(),
            "metrics": DailyMetric.objects.count(),
            "ad spend": AdSpend.objects.count(),
            "content": ContentItem.objects.count(),
            "products": Product.objects.count(),
            "orders": OrderRef.objects.count(),
            "tasks": Task.objects.count(),
            "suggestions": Suggestion.objects.count(),
        }

    def _channels(self):
        specs = {
            "instagram": ("Instagram", "instagram", "@basket.co"),
            "tiktok": ("TikTok", "tiktok", "@basket.co"),
            "facebook": ("Facebook Ads", "facebook", "Basket Shop"),
            "google": ("Google Ads", "google", "basket-shop"),
            "newsletter": ("Newsletter", "other", "Basket Shop Newsletter"),
        }
        return {
            key: Channel.objects.create(name=name, channel_type=channel_type, handle=handle)
            for key, (name, channel_type, handle) in specs.items()
        }

    def _campaigns(self, owner):
        def make(key, name, objective, budget, status, start, end, utm):
            campaign = Campaign.objects.create(
                name=name,
                objective=objective,
                budget=budget,
                status=status,
                start_date=self.today + timedelta(days=start),
                end_date=self.today + timedelta(days=end),
                utm_campaign=utm,
                owner=owner,
            )
            return key, campaign

        specs = [
            ("easter", "Easter Baskets Launch", "Drive pre-orders for the large Easter basket bundle.",
             "1500.00", "completed", -78, -42, "easter-baskets-launch"),
            ("spring", "Spring Retargeting", "Bring back visitors who added a basket but did not check out.",
             "800.00", "active", -30, 15, "spring-retargeting"),
            ("always_on", "Always-on Brand Search", "Keep brand search and remarketing running all season.",
             "600.00", "active", -90, 60, "always-on-brand"),
            ("corporate", "Corporate Gifts (B2B)", "Pilot outreach for bulk orders of corporate gift baskets.",
             "400.00", "paused", -20, 25, "corporate-gifts-b2b"),
            ("mothers", "Mother's Day VIP Baskets", "Premium basket with a handwritten card, limited to 100 boxes.",
             "900.00", "planned", 12, 40, "mothers-day-vip"),
            ("picnic", "Summer Picnic Sets", "Bundle push for picnic sets ahead of the warm weekends.",
             "700.00", "planned", 20, 65, "summer-picnic-sets"),
            ("fall", "Fall Preview Teaser", "Tease the fall collection to warm up the audience.",
             "250.00", "draft", 45, 75, "fall-preview-teaser"),
        ]
        return dict(make(*spec) for spec in specs)

    def _performance(self, campaigns, channels):
        """Daily metrics + ad spend, kept consistent: metric.spend == sum of AdSpend rows."""
        windows = [
            # campaign, channels, start offset, end offset, base orders/day, avg order value, target ROAS, zero-order spend hint
            (campaigns["easter"], ("instagram", "facebook"), -78, -42, 3.1, 52.0, 3.2, 30.0),
            (campaigns["spring"], ("instagram", "google"), -30, 0, 2.2, 46.0, 3.6, 18.0),
            (campaigns["always_on"], ("google", "facebook"), -90, 0, 1.6, 44.0, 4.2, 14.0),
            (campaigns["corporate"], ("facebook",), -20, -6, 0.7, 88.0, 2.6, 20.0),
        ]
        for campaign, channel_keys, start, end, base_orders, aov, target_roas, spend_hint in windows:
            for offset in range(start, end + 1):
                day = self.today + timedelta(days=offset)
                weekend = 1.3 if day.weekday() >= 5 else 1.0
                orders = max(0, round(self.rng.gauss(base_orders, base_orders * 0.4) * weekend))
                revenue = round(orders * aov * self.rng.uniform(0.88, 1.12), 2)
                if revenue:
                    spend = round(revenue / target_roas * self.rng.uniform(0.8, 1.2), 2)
                else:
                    spend = round(spend_hint * self.rng.uniform(0.6, 0.9), 2)

                remaining_spend, remaining_orders = spend, orders
                clicks_total = impressions_total = 0
                for index, key in enumerate(channel_keys):
                    if index == len(channel_keys) - 1:
                        channel_spend, channel_orders = round(remaining_spend, 2), remaining_orders
                    else:
                        channel_spend = round(spend * 0.6, 2)
                        channel_orders = int(orders * 0.6)
                        remaining_spend = round(remaining_spend - channel_spend, 2)
                        remaining_orders -= channel_orders
                    impressions = int(channel_spend * self.rng.uniform(55, 105))
                    clicks = int(impressions * self.rng.uniform(0.01, 0.03))
                    clicks_total += clicks
                    impressions_total += impressions
                    AdSpend.objects.create(
                        campaign=campaign, channel=channels[key], date=day,
                        spend=channel_spend, impressions=impressions,
                        clicks=clicks, conversions=channel_orders,
                    )

                ctr = round(clicks_total / impressions_total * 100, 2) if impressions_total else 0
                roas = round(revenue / spend, 2) if spend else 0
                DailyMetric.objects.create(
                    campaign=campaign, date=day, revenue=revenue,
                    orders=orders, spend=spend, ctr=ctr, roas=roas,
                )

    def _content(self, campaigns, channels):
        utm = {
            "instagram": ("instagram", "social"),
            "tiktok": ("tiktok", "social"),
            "facebook": ("facebook", "paid"),
            "newsletter": ("newsletter", "email"),
        }
        items = [
            ("easter", "instagram", "Easter basket pre-orders are open",
             "The large Easter basket is back — pre-order today and we ship the week before Palm Sunday.",
             -74, 10, "published"),
            ("easter", "newsletter", "Inside the Easter basket",
             "What goes into the large basket this year, and why we changed the chocolate supplier.",
             -60, 9, "published"),
            ("easter", "facebook", "Last call for Easter delivery slots",
             "Only a few delivery slots left before the holidays. Order by Thursday.",
             -50, 18, "published"),
            ("spring", "instagram", "Still thinking about that basket?",
             "Your basket is one tap away. Free delivery over €50 this week only.",
             -24, 11, "published"),
            ("spring", "facebook", "10% off if you finish your basket",
             "Retargeting push for cart abandoners — code FINISH10.",
             -20, 17, "published"),
            ("spring", "tiktok", "Packing a spring basket in 30s",
             "ASMR-style packing video with the spring mini basket.",
             -12, 20, "published"),
            ("always_on", "newsletter", "April news from the basket studio",
             "New ribbons, a bigger picnic set, and one small apology.",
             -10, 8, "published"),
            ("spring", "facebook", "Cart recovery push — weekend",
             "Weekend reminder ad with the picnic set as the upsell.",
             1, 9, "scheduled"),
            ("spring", "instagram", "Retargeting creative B — customer story",
             "Short testimonial video from a repeat customer.",
             2, 10, "scheduled"),
            ("mothers", "instagram", "Mother's Day VIP basket drop",
             "Limited to 100 boxes with a handwritten card. Set your reminder.",
             3, 10, "scheduled"),
            ("mothers", "newsletter", "Reserve a VIP basket before they sell out",
             "Early access for subscribers — the VIP basket usually sells out in days.",
             5, 8, "scheduled"),
            ("always_on", "facebook", "Reminder ad copy refresh",
             "Swap the reminder copy to the picnic season angle.",
             6, 14, "scheduled"),
            ("mothers", "facebook", "Gift the good kind of flowers",
             "Carousel: VIP basket, spring mini, and the new ribbon set.",
             7, 12, "scheduled"),
            ("picnic", "instagram", "Picnic season opens",
             "First look at the picnic set for two, with the new wicker handles.",
             9, 10, "scheduled"),
            ("picnic", "tiktok", "3 picnic baskets under €60",
             "Quick comparison video across the three picnic options.",
             11, 19, "scheduled"),
            ("picnic", "newsletter", "Picnic recipes with your basket",
             "Three recipes that fit exactly in the picnic set.",
             14, 8, "draft"),
            ("fall", "instagram", "Fall collection teaser",
             "Moody first frame of the fall collection (no prices yet).",
             40, 10, "draft"),
            ("fall", "tiktok", "Fall unboxing script",
             "Draft script — needs the new fall basket sample first.",
             None, None, "draft"),
        ]
        for campaign_key, channel_key, title, copy, offset, hour, status in items:
            campaign = campaigns[campaign_key]
            channel = channels[channel_key]
            source, medium = utm[channel_key]
            publish_at = None
            if offset is not None:
                day = self.today + timedelta(days=offset)
                publish_at = timezone.make_aware(datetime.combine(day, time(hour, 0)))
            ContentItem.objects.create(
                campaign=campaign,
                channel=channel,
                title=title,
                copy=copy,
                link=(
                    f"https://shop.example.com/collections/{campaign.utm_campaign}"
                    f"?utm_source={source}&utm_medium={medium}&utm_campaign={campaign.utm_campaign}"
                ),
                utm_source=source,
                utm_medium=medium,
                utm_campaign=campaign.utm_campaign,
                publish_at=publish_at,
                status=status,
            )

    def _products(self):
        specs = [
            ("SKU-1001", "Easter Basket — Large", "89.00", "https://shop.example.com/products/easter-basket-large"),
            ("SKU-1002", "Easter Basket — Mini", "39.00", "https://shop.example.com/products/easter-basket-mini"),
            ("SKU-1003", "Spring Mini Basket", "29.00", "https://shop.example.com/products/spring-mini-basket"),
            ("SKU-1004", "Picnic Set for Two", "69.00", "https://shop.example.com/products/picnic-set-two"),
            ("SKU-1005", "Corporate Gift Basket", "120.00", "https://shop.example.com/products/corporate-gift-basket"),
            ("SKU-1006", "Mother's Day VIP Basket", "99.00", "https://shop.example.com/products/mothers-day-vip"),
        ]
        for external_id, name, price, url in specs:
            Product.objects.create(external_id=external_id, name=name, price=price, url=url)

    def _orders(self, campaigns):
        # campaign, utm source, utm medium, min days ago, max days ago (kept inside each campaign window)
        pool = [
            (campaigns["easter"], "instagram", "social", 42, 76),
            (campaigns["easter"], "facebook", "paid", 42, 76),
            (campaigns["spring"], "instagram", "social", 1, 30),
            (campaigns["spring"], "google", "cpc", 1, 30),
            (campaigns["always_on"], "google", "cpc", 1, 89),
            (campaigns["always_on"], "facebook", "paid", 1, 89),
        ]
        for index in range(25):
            campaign, source, medium, min_ago, max_ago = self.rng.choice(pool)
            ordered_at = timezone.now() - timedelta(
                days=self.rng.randint(min_ago, max_ago),
                hours=self.rng.randint(0, 21),
                minutes=self.rng.randint(0, 59),
            )
            OrderRef.objects.create(
                external_id=f"ORD-{24000 + index}",
                campaign=campaign,
                utm_source=source,
                utm_medium=medium,
                utm_campaign=campaign.utm_campaign,
                total=round(self.rng.uniform(28, 132), 2),
                ordered_at=ordered_at,
            )

    def _tasks_and_suggestions(self, campaigns):
        spring_task = Task.objects.create(
            campaign=campaigns["spring"],
            title="Set up retargeting audience v2",
            notes="Exclude buyers from the last 30 days; include product viewers and cart abandoners.",
            due_date=self.today + timedelta(days=2),
        )
        Task.objects.create(
            campaign=campaigns["easter"],
            title="Archive Easter campaign assets",
            notes="Move creatives and copy into the shared drive.",
            due_date=self.today - timedelta(days=35),
            done=True,
        )
        Task.objects.create(
            campaign=campaigns["easter"],
            title="Refresh Easter ad creatives",
            notes="UGC versions outperformed studio shots — brief 2 more.",
            due_date=self.today - timedelta(days=50),
            done=True,
        )
        Task.objects.create(
            campaign=campaigns["always_on"],
            title="Book newsletter slots for May",
            notes="Two slots: picnic launch and Mother's Day reminder.",
            due_date=self.today + timedelta(days=6),
        )
        Task.objects.create(
            campaign=campaigns["mothers"],
            title="Approve Mother's Day VIP copy",
            notes="Legal check on the 'limited to 100 boxes' claim, then schedule.",
            due_date=self.today + timedelta(days=4),
        )
        Task.objects.create(
            campaign=campaigns["picnic"],
            title="Brief photographer for picnic shots",
            notes="Needs: top-down shot, two-person picnic scene, wicker handle close-up.",
            due_date=self.today + timedelta(days=8),
        )
        Task.objects.create(
            campaign=campaigns["corporate"],
            title="Review corporate outreach list",
            notes="Confirm the 20 pilot companies before unpausing.",
            due_date=self.today + timedelta(days=5),
        )
        Task.objects.create(
            title="Update UTM naming convention",
            notes="Align channel/source names across ads and newsletter links.",
            due_date=self.today + timedelta(days=10),
        )

        ai_suggestion = Suggestion.objects.create(
            campaign=campaigns["spring"],
            kind="ai",
            title="AI next steps",
            text=(
                "1) Test a 48-hour cart-recovery flow on Instagram. "
                "2) Shift 15% of budget to Google while ROAS holds above 3.5. "
                "3) Refresh creative B with the testimonial cut."
            ),
            input_snapshot=campaign_snapshot(campaigns["spring"]),
            accepted=True,
        )
        spring_task.suggestion = ai_suggestion
        spring_task.save(update_fields=["suggestion"])

        for spec in [
            ("spring", "rule", "Scale winners",
             "ROAS has held above target for two weeks. Increase budget ~20% on the best ad set, keep frequency under 3."),
            ("spring", "rule", "Refresh creative",
             "CTR is trending down week over week. Test a new hook on the top channel this week."),
            ("always_on", "rule", "Hold steady",
             "Metrics healthy. Keep cadence, log results daily, review again in 3 days."),
            ("corporate", "rule", "Fix targeting/landing",
             "Spend with very few conversions. Check the B2B audience list and the wholesale landing page load time."),
            ("picnic", "rule", "Plan next 7 days",
             "No content scheduled yet for launch week. Draft 3 posts (unboxing, comparison, recipe) and schedule them."),
        ]:
            campaign_key, kind, title, text = spec
            Suggestion.objects.create(
                campaign=campaigns[campaign_key],
                kind=kind,
                title=title,
                text=text,
                input_snapshot=campaign_snapshot(campaigns[campaign_key]),
            )
