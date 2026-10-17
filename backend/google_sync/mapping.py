"""Match external report rows (GA4, later Google Ads) to Campaign rows.

Attribution in this app is UTM-based everywhere (orders carry ``utm_*``), so
GA4's ``sessionCampaignName`` is matched against ``Campaign.utm_campaign``,
case-insensitively. Rows that match nothing are collected and reported back
instead of being dropped silently.
"""
IGNORED_CAMPAIGN_VALUES = {
    "",
    "(not set)",
    "(direct)",
    "(referral)",
    "(none)",
    "(organic)",
    "not set",
    "null",
}


def normalize(value: object) -> str:
    """Case/whitespace-insensitive campaign key."""
    return str(value or "").strip().casefold()


def is_ignored(campaign_name: object) -> bool:
    """True for GA4 placeholders that never map to a campaign."""
    return normalize(campaign_name) in IGNORED_CAMPAIGN_VALUES


def campaign_index(campaigns=None) -> dict:
    """``normalize(utm_campaign) -> Campaign``; first campaign wins a tie."""
    if campaigns is None:
        from campaigns.models import Campaign

        campaigns = Campaign.objects.all()
    index: dict = {}
    for campaign in campaigns:
        key = normalize(campaign.utm_campaign)
        if key and key not in index:
            index[key] = campaign
    return index
