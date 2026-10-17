import json
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from campaigns.models import Campaign
from suggestions.services import llm_suggestions

from .crypto import decrypt, encrypt
from .models import IntegrationCredential

URL = "/api/integrations/"


class IntegrationCredentialTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username="owner", password="pw123456", is_staff=True
        )
        self.user = user_model.objects.create_user(username="viewer", password="pw123456")
        # Deterministic env: no OPENAI_API_KEY unless a test sets it.
        env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def entry(self, provider: str) -> dict:
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        matches = [item for item in r.data if item["id"] == provider]
        self.assertEqual(len(matches), 1, f"{provider} missing from {[i['id'] for i in r.data]}")
        return matches[0]

    def test_anonymous_is_rejected(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 401, r.content)

    def test_any_authenticated_user_can_read_status(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual({item["id"] for item in r.data}, {"openai", "google-analytics"})
        entry = self.entry("openai")
        self.assertFalse(entry["configured"])
        self.assertIsNone(entry["source"])
        self.assertFalse(entry["stored"])
        # Status shape: docs metadata + flags, and no secret field.
        for field in ("label", "summary", "env_var", "where_to_get", "steps", "security_note"):
            self.assertIn(field, entry)
        self.assertNotIn("key", entry)

    def test_non_staff_cannot_write(self):
        self.client.force_authenticate(self.user)
        r = self.client.put(f"{URL}openai/", {"key": "sk-test-1234567890"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        r = self.client.delete(f"{URL}openai/")
        self.assertEqual(r.status_code, 403, r.content)

    def test_admin_stores_key_encrypted_and_value_never_returns(self):
        self.client.force_authenticate(self.admin)
        raw = "sk-test-abcdefghijklmnop"
        r = self.client.put(f"{URL}openai/", {"key": raw}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["configured"])
        self.assertEqual(r.data["source"], "database")
        self.assertEqual(r.data["key_hint"], "mnop")
        self.assertNotIn(raw, json.dumps(r.data, default=str))

        credential = IntegrationCredential.objects.get(provider="openai")
        self.assertNotEqual(credential.key_encrypted, raw)
        self.assertNotIn(raw, credential.key_encrypted)
        self.assertEqual(decrypt(credential.key_encrypted), raw)

        listing = self.client.get(URL)
        self.assertNotIn(raw, json.dumps(listing.data, default=str))
        self.assertEqual(self.entry("openai")["updated_by"], "owner")
        self.assertIsNotNone(self.entry("openai")["updated_at"])

    def test_short_or_unknown_are_rejected(self):
        self.client.force_authenticate(self.admin)
        short = self.client.put(f"{URL}openai/", {"key": "sk-short"}, format="json")
        self.assertEqual(short.status_code, 400, short.content)
        unknown = self.client.put(f"{URL}not-a-provider/", {"key": "sk-test-1234567890"}, format="json")
        self.assertEqual(unknown.status_code, 404, unknown.content)

    def test_env_fallback_and_database_precedence(self):
        self.client.force_authenticate(self.user)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-000000000000"}):
            entry = self.entry("openai")
            self.assertTrue(entry["configured"])
            self.assertEqual(entry["source"], "env")
            self.assertIsNone(entry["key_hint"])

            IntegrationCredential.objects.create(
                provider="openai", key_encrypted=encrypt("sk-db-00000000000000"), key_hint="0000"
            )
            self.assertEqual(self.entry("openai")["source"], "database")

    def test_delete_falls_back_to_env(self):
        self.client.force_authenticate(self.admin)
        IntegrationCredential.objects.create(
            provider="openai", key_encrypted=encrypt("sk-db-00000000000000"), key_hint="0000"
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-111111111111"}):
            r = self.client.delete(f"{URL}openai/")
            self.assertEqual(r.status_code, 200, r.content)
            self.assertTrue(r.data["configured"])
            self.assertEqual(r.data["source"], "env")
        self.assertFalse(IntegrationCredential.objects.filter(provider="openai").exists())

    def test_unreadable_stored_key_is_reported(self):
        IntegrationCredential.objects.create(
            provider="openai", key_encrypted=encrypt("sk-db-00000000000000"), key_hint="0000"
        )
        self.client.force_authenticate(self.user)
        with override_settings(SECRET_KEY="rotated-secret"):
            entry = self.entry("openai")
        self.assertFalse(entry["configured"])
        self.assertTrue(entry["stored"])
        self.assertTrue(entry["stored_unreadable"])


class GoogleAnalyticsCredentialTests(APITestCase):
    """The GA4 entry uses the generic fields/config API shape."""

    GA4_URL = f"{URL}google-analytics/"
    CREDENTIALS = json.dumps(
        {
            "type": "service_account",
            "project_id": "demo",
            "private_key": "-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----",
            "client_email": "sync-bot@demo.iam.gserviceaccount.com",
        }
    )
    PAYLOAD = {"fields": {"credentials_json": CREDENTIALS}, "config": {"property_id": "123456789"}}

    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="boss", password="pw123456", is_staff=True)
        env = mock.patch.dict(
            os.environ,
            {"GOOGLE_ANALYTICS_CREDENTIALS": "", "GOOGLE_ANALYTICS_PROPERTY_ID": ""},
        )
        env.start()
        self.addCleanup(env.stop)

    def test_listing_exposes_field_metadata_and_blank_config(self):
        self.client.force_authenticate(self.admin)
        entry = next(item for item in self.client.get(URL).data if item["id"] == "google-analytics")
        self.assertEqual([f["name"] for f in entry["fields"]], ["credentials_json"])
        self.assertTrue(entry["fields"][0]["secret"])
        self.assertEqual([f["name"] for f in entry["config_fields"]], ["property_id"])
        self.assertEqual(entry["config"], {})
        self.assertFalse(entry["configured"])

    def test_admin_saves_fields_and_config(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(self.GA4_URL, self.PAYLOAD, format="json")
        self.assertEqual(r.status_code, 200, r.content)

        self.assertTrue(r.data["configured"])
        self.assertEqual(r.data["config"], {"property_id": "123456789"})
        # The service-account email is surfaced as a hint; the key itself never is.
        self.assertEqual(r.data["key_hint"], "sync-bot@demo.iam.gserviceaccount.com")
        self.assertNotIn(self.CREDENTIALS, json.dumps(r.data, default=str))

        credential = IntegrationCredential.objects.get(provider="google-analytics")
        self.assertEqual(credential.config, {"property_id": "123456789"})
        # One secret field is stored as a plain string; several as a JSON object.
        self.assertEqual(decrypt(credential.key_encrypted), self.CREDENTIALS)

    def test_configured_needs_the_property_id_too(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(
            self.GA4_URL, {"fields": {"credentials_json": self.CREDENTIALS}}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.data["configured"])
        self.assertTrue(r.data["stored"])

    def test_property_id_alone_is_rejected(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(self.GA4_URL, {"config": {"property_id": "123"}}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_config_only_update_keeps_the_key(self):
        self.client.force_authenticate(self.admin)
        self.client.put(self.GA4_URL, self.PAYLOAD, format="json")
        before = IntegrationCredential.objects.get(provider="google-analytics").key_encrypted

        r = self.client.put(self.GA4_URL, {"config": {"property_id": "999"}}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["config"], {"property_id": "999"})

        after = IntegrationCredential.objects.get(provider="google-analytics")
        self.assertEqual(after.key_encrypted, before)

    def test_missing_required_config_is_rejected(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(
            self.GA4_URL,
            {"fields": {"credentials_json": self.CREDENTIALS}, "config": {"property_id": ""}},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("property ID", r.data["detail"])

    def test_clearing_a_required_setting_is_refused_and_keeps_the_stored_value(self):
        """Regression: an empty setting must not silently wipe the stored config."""
        self.client.force_authenticate(self.admin)
        self.client.put(self.GA4_URL, self.PAYLOAD, format="json")

        r = self.client.put(self.GA4_URL, {"config": {"property_id": ""}}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

        entry = next(item for item in self.client.get(URL).data if item["id"] == "google-analytics")
        self.assertEqual(entry["config"], {"property_id": "123456789"})
        self.assertTrue(entry["configured"])

    def test_required_setting_may_come_from_the_env(self):
        self.client.force_authenticate(self.admin)
        with mock.patch.dict(os.environ, {"GOOGLE_ANALYTICS_PROPERTY_ID": "777"}):
            r = self.client.put(
                self.GA4_URL, {"fields": {"credentials_json": self.CREDENTIALS}}, format="json"
            )
            self.assertEqual(r.status_code, 200, r.content)
            self.assertTrue(r.data["configured"])
            self.assertEqual(r.data["config"], {"property_id": "777"})
        self.assertEqual(IntegrationCredential.objects.get(provider="google-analytics").config, {})

    def test_short_credentials_are_rejected(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(self.GA4_URL, {"fields": {"credentials_json": "short"}}, format="json")
        self.assertEqual(r.status_code, 400, r.content)

    def test_legacy_key_shape_is_refused_for_multi_field_providers(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(self.GA4_URL, {"key": "x" * 40}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("fields", r.data["detail"])

    def test_env_fallback_populates_config(self):
        self.client.force_authenticate(self.admin)
        with mock.patch.dict(os.environ, {"GOOGLE_ANALYTICS_PROPERTY_ID": "555"}):
            entry = next(item for item in self.client.get(URL).data if item["id"] == "google-analytics")
        self.assertEqual(entry["config"], {"property_id": "555"})

    def test_sync_status_fields_start_empty(self):
        self.client.force_authenticate(self.admin)
        self.client.put(self.GA4_URL, self.PAYLOAD, format="json")
        entry = next(item for item in self.client.get(URL).data if item["id"] == "google-analytics")
        self.assertIsNone(entry["last_synced_at"])
        self.assertEqual(entry["last_sync_error"], "")

    def test_non_staff_cannot_save(self):
        self.client.force_authenticate(get_user_model().objects.create_user(username="v", password="pw123456"))
        r = self.client.put(self.GA4_URL, self.PAYLOAD, format="json")
        self.assertEqual(r.status_code, 403, r.content)


class LlmKeyPrecedenceTests(APITestCase):
    """llm_suggestions picks the key as: explicit argument > stored > env."""

    def setUp(self):
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="100.00")
        env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def _authorization(self, api_key=None):
        response_body = json.dumps({"choices": [{"message": {"content": "step one"}}]}).encode()
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = response_body
            out = llm_suggestions(self.campaign, api_key=api_key)
        self.assertEqual(out["text"], "step one")
        return urlopen.call_args[0][0].get_header("Authorization")

    def test_explicit_key_beats_stored_and_env(self):
        IntegrationCredential.objects.create(
            provider="openai", key_encrypted=encrypt("sk-db-00000000000000"), key_hint="0000"
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-000000000000"}):
            self.assertEqual(self._authorization(api_key="sk-explicit-00000000"), "Bearer sk-explicit-00000000")

    def test_stored_credential_beats_env(self):
        IntegrationCredential.objects.create(
            provider="openai", key_encrypted=encrypt("sk-db-00000000000000"), key_hint="0000"
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-000000000000"}):
            self.assertEqual(self._authorization(), "Bearer sk-db-00000000000000")

    def test_env_used_when_nothing_stored(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-000000000000"}):
            self.assertEqual(self._authorization(), "Bearer sk-env-000000000000")

    def test_missing_key_raises(self):
        with self.assertRaises(RuntimeError):
            llm_suggestions(self.campaign)
