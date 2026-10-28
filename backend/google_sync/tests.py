"""Tests for the GA4 → DailyMetric sync.

The Google side is faked at the ``urlopen`` boundary (the same trick the OpenAI
tests use), so the whole chain runs for real: service-account JWT signing, the
urllib transport, report parsing, campaign matching and the DB upsert.
"""
import json
import os
import base64
import urllib.error
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest import mock

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APITestCase

from campaigns.models import Campaign
from integrations.crypto import encrypt
from integrations.models import IntegrationCredential
from integrations.services import set_credential
from results.models import DailyMetric

from . import ga4, search_console
from .services import DEFAULT_WINDOW_DAYS, SyncNotConfigured, resolve_window, sync_ga4

SYNC_URL = "/api/integrations/google-analytics/sync/"
PROPERTY_ID = "123456789"


def make_service_account() -> tuple:
    """A structurally valid (throwaway) service-account key file + its public key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    info = {
        "type": "service_account",
        "project_id": "demo",
        "private_key_id": "key-id",
        "private_key": pem,
        "client_email": "sync-bot@demo.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return info, key.public_key()


def service_account_json() -> str:
    return json.dumps(make_service_account()[0])


def report_row(day: str, campaign: str, revenue: str, orders: str) -> dict:
    return {
        "dimensionValues": [{"value": day}, {"value": campaign}],
        "metricValues": [{"value": revenue}, {"value": orders}],
    }


class FakeHTTPResponse:
    """Just enough of an ``http.client.HTTPResponse`` for urllib callers."""

    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self.data = json.dumps(payload).encode()
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.data


class GoogleStubMixin:
    """Route ``urlopen`` to a canned token response and a canned GA4 report."""

    def setUp(self):
        super().setUp()
        self.requests = []
        env = mock.patch.dict(
            os.environ,
            {"GOOGLE_ANALYTICS_CREDENTIALS": "", "GOOGLE_ANALYTICS_PROPERTY_ID": ""},
        )
        env.start()
        self.addCleanup(env.stop)

    def stub_google(self, rows: list[dict], token: str = "ya29.test"):
        def fake_urlopen(request, timeout=None):
            url = request.full_url
            if url.startswith("https://oauth2.googleapis.com/token"):
                return FakeHTTPResponse({"access_token": token, "expires_in": 3600})
            if ":runReport" in url:
                self.requests.append({"url": url, "body": json.loads(request.data.decode())})
                return FakeHTTPResponse({"rows": rows})
            raise AssertionError(f"unexpected URL: {url}")

        return mock.patch("urllib.request.urlopen", side_effect=fake_urlopen)

    def configure(self, property_id: str = PROPERTY_ID, credentials: str | None = None):
        set_credential(
            "google-analytics",
            values={"credentials_json": credentials or service_account_json()},
            config={"property_id": property_id},
        )


class ParseReportTests(APITestCase):
    def test_parses_dimensions_metrics_and_dates(self):
        rows = ga4.parse_report({"rows": [report_row("20261010", "spring", "120.505", "4")]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-10-10")
        self.assertEqual(rows[0]["campaign"], "spring")
        self.assertEqual(rows[0]["revenue"], Decimal("120.505"))
        self.assertEqual(rows[0]["orders"], 4)

    def test_skips_unparseable_dates_and_short_rows(self):
        payload = {
            "rows": [
                report_row("not-a-date", "spring", "1", "1"),
                {"dimensionValues": [{"value": "20261010"}], "metricValues": []},
                report_row("20261010", "spring", "1", "1"),
            ]
        }
        self.assertEqual([row["date"] for row in ga4.parse_report(payload)], ["2026-10-10"])

    def test_empty_report(self):
        self.assertEqual(ga4.parse_report({}), [])


class AccessTokenTests(APITestCase):
    def test_jwt_is_signed_with_the_service_account_key(self):
        info, public_key = make_service_account()
        token = ga4.signed_jwt(info, "https://oauth2.googleapis.com/token", now=1_000)

        header_b64, claims_b64, signature_b64 = token.split(".")
        signature = base64.urlsafe_b64decode(signature_b64 + "=" * (-len(signature_b64) % 4))
        # Raises InvalidSignature if the signature does not match.
        public_key.verify(
            signature,
            f"{header_b64}.{claims_b64}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        def decode(segment: str) -> dict:
            return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))

        self.assertEqual(decode(header_b64)["alg"], "RS256")
        self.assertEqual(decode(header_b64)["kid"], "key-id")
        claims = decode(claims_b64)
        self.assertEqual(claims["iss"], "sync-bot@demo.iam.gserviceaccount.com")
        self.assertEqual(claims["aud"], "https://oauth2.googleapis.com/token")
        self.assertEqual(claims["scope"], "https://www.googleapis.com/auth/analytics.readonly")
        self.assertEqual(claims["exp"] - claims["iat"], 3600)

    def test_jwt_accepts_search_console_scopes(self):
        info, _ = make_service_account()
        token = ga4.signed_jwt(
            info,
            "https://oauth2.googleapis.com/token",
            now=1_000,
            scopes=search_console.SCOPES,
        )
        _, claims_b64, _ = token.split(".")
        claims = json.loads(base64.urlsafe_b64decode(claims_b64 + "=" * (-len(claims_b64) % 4)))
        self.assertEqual(claims["scope"], "https://www.googleapis.com/auth/webmasters.readonly")

    def test_access_token_exchanges_the_jwt(self):
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["body"] = request.data.decode()
            return FakeHTTPResponse({"access_token": "ya29.token", "expires_in": 3600})

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            token = ga4._access_token(service_account_json())

        self.assertEqual(token, "ya29.token")
        self.assertEqual(captured["url"], "https://oauth2.googleapis.com/token")
        self.assertIn("grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer", captured["body"])
        self.assertIn("assertion=", captured["body"])

    def test_invalid_json_is_reported(self):
        with self.assertRaises(ga4.GA4Error):
            ga4._access_token("not json")

    def test_incomplete_credentials_are_reported(self):
        with self.assertRaises(ga4.GA4Error) as ctx:
            ga4._access_token(json.dumps({"type": "service_account"}))
        self.assertIn("incomplete", str(ctx.exception))

    def test_broken_private_key_is_reported(self):
        info, _ = make_service_account()
        info["private_key"] = "-----BEGIN PRIVATE KEY-----\nnope\n-----END PRIVATE KEY-----"
        with self.assertRaises(ga4.GA4Error) as ctx:
            ga4._access_token(json.dumps(info))
        self.assertIn("PEM", str(ctx.exception))

    def test_auth_failure_is_wrapped(self):
        creds = service_account_json()
        with mock.patch("urllib.request.urlopen", side_effect=OSError("boom")):
            with self.assertRaises(ga4.GA4Error):
                ga4._access_token(creds)

    def test_rejected_credentials_include_the_status(self):
        error = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
        error.read = lambda: b'{"error": "invalid_grant"}'
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ga4.GA4Error) as ctx:
                ga4._access_token(service_account_json())
        self.assertIn("400", str(ctx.exception))
        self.assertIn("invalid_grant", str(ctx.exception))


class SearchConsoleClientTests(APITestCase):
    def test_normalizes_pages_for_campaign_matching(self):
        self.assertEqual(
            search_console.normalize_page_path("https://www.catchandstats.com/team/?utm_source=x"),
            "/team",
        )
        self.assertEqual(search_console.normalize_page_path("https://catchandstats.com"), "/")
        self.assertEqual(
            search_console.normalize_page_path("https://catchandstats.com/a/b/"),
            "/a/b",
        )

    def test_parses_totals_pages_and_queries(self):
        payload = {
            "rows": [
                {
                    "keys": ["2026-10-10"],
                    "clicks": 12,
                    "impressions": 300,
                    "ctr": 0.04,
                    "position": 4.2,
                }
            ]
        }
        total = search_console.parse_rows(payload, "total")[0]
        self.assertEqual(total["date"], date(2026, 10, 10))
        self.assertEqual(total["clicks"], 12)
        self.assertEqual(total["page_path"], "")

        page = search_console.parse_rows(
            {
                "rows": [
                    {
                        "keys": ["2026-10-10", "https://catchandstats.com/team/?utm_source=x"],
                        "clicks": "7",
                        "impressions": "90",
                        "ctr": "0.0778",
                        "position": "2.5",
                    }
                ]
            },
            "page",
        )[0]
        self.assertEqual(page["page_path"], "/team")
        self.assertEqual(page["page_url"], "https://catchandstats.com/team/?utm_source=x")

        query = search_console.parse_rows(
            {"rows": [{"keys": ["2026-10-10", "euroleague top 8"], "clicks": 1}]},
            "query",
        )[0]
        self.assertEqual(query["query"], "euroleague top 8")
        self.assertEqual(query["impressions"], 0)

    def test_query_encodes_the_property_and_posts_dimensions(self):
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode())
            return FakeHTTPResponse({"rows": []})

        with mock.patch.object(search_console, "_access", return_value="token"):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                search_console.query(
                    "{}",
                    "sc-domain:catchandstats.com",
                    date(2026, 10, 1),
                    date(2026, 10, 10),
                    ["date", "page"],
                )

        self.assertIn("sc-domain%3Acatchandstats.com", captured["url"])
        self.assertTrue(captured["url"].endswith("/searchAnalytics/query"))
        self.assertEqual(captured["body"]["startDate"], "2026-10-01")
        self.assertEqual(captured["body"]["endDate"], "2026-10-10")
        self.assertEqual(captured["body"]["dimensions"], ["date", "page"])
        self.assertEqual(captured["body"]["dataState"], "all")

    def test_fetch_snapshot_asks_for_totals_pages_and_queries(self):
        calls = []

        def fake_rows(credentials, site_url, start, end, dimensions, **kwargs):
            calls.append(dimensions)
            return []

        with mock.patch.object(search_console, "_fetch_rows", side_effect=fake_rows):
            rows = search_console.fetch_snapshot(
                "{}", "sc-domain:catchandstats.com", date(2026, 10, 1), date(2026, 10, 10)
            )

        self.assertEqual(rows, [])
        self.assertEqual(calls, [["date"], ["date", "page"], ["date", "query"]])


class ResolveWindowTests(APITestCase):
    def test_default_window_is_seven_days_inclusive(self):
        start, end = resolve_window(None, today=date(2026, 10, 17))
        self.assertEqual(start, date(2026, 10, 11))
        self.assertEqual(end, date(2026, 10, 17))
        self.assertEqual(DEFAULT_WINDOW_DAYS, 7)

    def test_out_of_range_windows_are_clamped(self):
        self.assertEqual(resolve_window(0, today=date(2026, 10, 17))[0], date(2026, 10, 17))
        self.assertEqual(resolve_window(9999, today=date(2026, 10, 17))[0], date(2025, 10, 18))
        self.assertEqual(resolve_window("garbage", today=date(2026, 10, 17))[0], date(2026, 10, 11))


class SyncGa4Tests(GoogleStubMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.matched = Campaign.objects.create(name="Spring Retargeting", utm_campaign="spring-retargeting")

    def test_sync_creates_matches_and_reports_unmatched(self):
        rows = [
            report_row("20261010", "spring-retargeting", "120.505", "4"),
            report_row("20261010", "(not set)", "10", "1"),
            report_row("20261011", "Winter Baskets", "5", "1"),
        ]
        self.configure()
        with self.stub_google(rows):
            result = sync_ga4()

        self.assertEqual(result.created, 1)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 2)
        self.assertEqual(result.rows, 3)
        self.assertEqual(result.unmatched, ["Winter Baskets"])

        metric = DailyMetric.objects.get(campaign=self.matched, date="2026-10-10")
        self.assertEqual(metric.revenue, Decimal("120.51"))  # rounded to cents
        self.assertEqual(metric.orders, 4)
        self.assertEqual(metric.source, DailyMetric.SOURCE_GA4)

    def test_resync_is_idempotent_and_keeps_spend(self):
        DailyMetric.objects.create(
            campaign=self.matched, date="2026-10-10", revenue="0.00", orders=0,
            spend="30.00", ctr=1.5, roas=0.0,
        )
        self.configure()
        rows = [report_row("20261010", "spring-retargeting", "120.50", "4")]
        with self.stub_google(rows):
            first = sync_ga4()
            second = sync_ga4()

        self.assertEqual((first.created, first.updated), (0, 1))
        self.assertEqual((second.created, second.updated), (0, 1))
        self.assertEqual(DailyMetric.objects.count(), 1)

        metric = DailyMetric.objects.get()
        self.assertEqual(metric.revenue, Decimal("120.50"))
        self.assertEqual(metric.spend, Decimal("30.00"))  # GA4 never moves spend
        self.assertEqual(metric.ctr, 1.5)
        self.assertAlmostEqual(metric.roas, 4.02)

    def test_campaign_match_is_case_insensitive(self):
        rows = [report_row("20261012", "SPRING-Retargeting ", "7", "1")]
        self.configure()
        with self.stub_google(rows):
            result = sync_ga4()
        self.assertEqual(result.created, 1)
        self.assertTrue(DailyMetric.objects.filter(campaign=self.matched, date="2026-10-12").exists())

    def test_request_targets_the_configured_property_and_window(self):
        self.configure()
        with self.stub_google([]):
            result = sync_ga4(days=3, today=date(2026, 10, 17))
        self.assertEqual(result.start, "2026-10-15")
        self.assertEqual(result.end, "2026-10-17")
        self.assertEqual(len(self.requests), 1)
        self.assertIn(f"/properties/{PROPERTY_ID}:runReport", self.requests[0]["url"])
        self.assertEqual(
            self.requests[0]["body"]["dateRanges"],
            [{"startDate": "2026-10-15", "endDate": "2026-10-17"}],
        )
        self.assertEqual(
            [d["name"] for d in self.requests[0]["body"]["dimensions"]],
            ["date", "sessionCampaignName"],
        )

    def test_missing_credentials_raise(self):
        with self.assertRaises(SyncNotConfigured):
            sync_ga4()

    def test_missing_property_id_raises(self):
        set_credential("google-analytics", values={"credentials_json": service_account_json()})
        with self.assertRaises(SyncNotConfigured) as ctx:
            sync_ga4()
        self.assertIn("property ID", str(ctx.exception))

    def test_env_fallback_is_used(self):
        rows = [report_row("20261010", "spring-retargeting", "9", "1")]
        with mock.patch.dict(
            os.environ,
            {
                "GOOGLE_ANALYTICS_CREDENTIALS": service_account_json(),
                "GOOGLE_ANALYTICS_PROPERTY_ID": PROPERTY_ID,
            },
        ):
            with self.stub_google(rows):
                result = sync_ga4()
        self.assertEqual(result.created, 1)

    def test_api_error_is_wrapped(self):
        self.configure()
        error = urllib.error.HTTPError("url", 403, "Forbidden", {}, None)
        error.read = lambda: b'{"error": "permission denied"}'
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ga4.GA4Error) as ctx:
                sync_ga4()
        self.assertIn("403", str(ctx.exception))


class SyncEndpointTests(GoogleStubMixin, APITestCase):
    def setUp(self):
        super().setUp()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="boss", password="pw123456", is_staff=True)
        self.user = user_model.objects.create_user(username="viewer", password="pw123456")
        self.campaign = Campaign.objects.create(name="Spring", utm_campaign="spring-retargeting")

    def test_requires_authentication(self):
        self.assertEqual(self.client.post(SYNC_URL).status_code, 401)

    def test_requires_staff(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(SYNC_URL).status_code, 403)

    def test_unconfigured_returns_clear_error(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(SYNC_URL)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("not configured", r.data["detail"])

    def test_rejects_bad_days(self):
        self.client.force_authenticate(self.admin)
        for value in ("abc", 0, 4000):
            r = self.client.post(SYNC_URL, {"days": value}, format="json")
            self.assertEqual(r.status_code, 400, r.content)

    def test_sync_reports_counts_and_records_timestamp(self):
        self.configure()
        self.client.force_authenticate(self.admin)
        rows = [
            report_row("20261010", "spring-retargeting", "40.00", "2"),
            report_row("20261010", "unknown-brand", "1", "1"),
        ]
        with self.stub_google(rows):
            r = self.client.post(SYNC_URL, {"days": 5}, format="json")

        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["unmatched"], ["unknown-brand"])
        self.assertIsNotNone(r.data["last_synced_at"])

        credential = IntegrationCredential.objects.get(provider="google-analytics")
        self.assertIsNotNone(credential.last_synced_at)
        self.assertEqual(credential.last_sync_error, "")

    def test_api_failure_is_recorded_and_reported(self):
        self.configure()
        self.client.force_authenticate(self.admin)
        error = urllib.error.HTTPError("url", 500, "Server Error", {}, None)
        error.read = lambda: b"kaboom"
        with mock.patch("urllib.request.urlopen", side_effect=error):
            r = self.client.post(SYNC_URL)

        self.assertEqual(r.status_code, 502, r.content)
        credential = IntegrationCredential.objects.get(provider="google-analytics")
        self.assertIn("500", credential.last_sync_error)
        self.assertIsNone(credential.last_synced_at)


class SyncCommandTests(GoogleStubMixin, APITestCase):
    def setUp(self):
        super().setUp()
        Campaign.objects.create(name="Spring", utm_campaign="spring-retargeting")

    def test_command_syncs_and_reports(self):
        self.configure()
        out = StringIO()
        with self.stub_google([report_row("20261010", "spring-retargeting", "5", "1")]):
            call_command("sync_google", "--days", "3", stdout=out)
        self.assertIn("1 created", out.getvalue())
        self.assertEqual(DailyMetric.objects.count(), 1)

    def test_command_fails_clearly_when_unconfigured(self):
        with self.assertRaises(CommandError):
            call_command("sync_google", stdout=StringIO())

    def test_command_warns_about_unmatched_campaigns(self):
        self.configure()
        out = StringIO()
        with self.stub_google([report_row("20261010", "nope", "5", "1")]):
            call_command("sync_google", stdout=out)
        self.assertIn("Unmatched campaigns: nope", out.getvalue())


class CredentialStorageTests(APITestCase):
    """The GA4 entry stores a JSON blob plus non-secret config."""

    def test_secrets_and_config_are_stored_separately(self):
        raw = service_account_json()
        credential = set_credential(
            "google-analytics", values={"credentials_json": raw}, config={"property_id": PROPERTY_ID}
        )
        self.assertEqual(credential.config, {"property_id": PROPERTY_ID})
        self.assertNotIn(raw, credential.key_encrypted)
        # The hint is the service account email, so you can tell which key is set.
        self.assertEqual(credential.key_hint, "sync-bot@demo.iam.gserviceaccount.com")

    def test_config_only_update_keeps_the_stored_key(self):
        raw = service_account_json()
        set_credential("google-analytics", values={"credentials_json": raw})
        credential = set_credential("google-analytics", config={"property_id": "987"})
        self.assertEqual(credential.config, {"property_id": "987"})
        self.assertEqual(credential.key_hint, "sync-bot@demo.iam.gserviceaccount.com")

    def test_malformed_credentials_still_get_a_sane_hint(self):
        credential = set_credential("google-analytics", values={"credentials_json": "x" * 40})
        self.assertEqual(credential.key_hint, "xxxx")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            set_credential("nope", values={"key": "x" * 20})

    def test_unreadable_stored_key_falls_back_to_env(self):
        IntegrationCredential.objects.create(
            provider="google-analytics", key_encrypted="not-a-token"
        )
        with mock.patch.dict(
            os.environ,
            {"GOOGLE_ANALYTICS_CREDENTIALS": "{}", "GOOGLE_ANALYTICS_PROPERTY_ID": ""},
        ):
            from integrations.services import get_credential_secrets

            self.assertEqual(
                get_credential_secrets("google-analytics"), {"credentials_json": "{}"}
            )
