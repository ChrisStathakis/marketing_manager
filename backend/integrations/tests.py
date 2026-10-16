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

    def test_anonymous_is_rejected(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 401, r.content)

    def test_any_authenticated_user_can_read_status(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data), 1)
        entry = r.data[0]
        self.assertEqual(entry["id"], "openai")
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
        self.assertEqual(listing.data[0]["updated_by"], "owner")
        self.assertIsNotNone(listing.data[0]["updated_at"])

    def test_short_or_unknown_are_rejected(self):
        self.client.force_authenticate(self.admin)
        short = self.client.put(f"{URL}openai/", {"key": "sk-short"}, format="json")
        self.assertEqual(short.status_code, 400, short.content)
        unknown = self.client.put(f"{URL}not-a-provider/", {"key": "sk-test-1234567890"}, format="json")
        self.assertEqual(unknown.status_code, 404, unknown.content)

    def test_env_fallback_and_database_precedence(self):
        self.client.force_authenticate(self.user)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-000000000000"}):
            r = self.client.get(URL)
            self.assertTrue(r.data[0]["configured"])
            self.assertEqual(r.data[0]["source"], "env")
            self.assertIsNone(r.data[0]["key_hint"])

            IntegrationCredential.objects.create(
                provider="openai", key_encrypted=encrypt("sk-db-00000000000000"), key_hint="0000"
            )
            r = self.client.get(URL)
            self.assertEqual(r.data[0]["source"], "database")

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
            r = self.client.get(URL)
        entry = r.data[0]
        self.assertFalse(entry["configured"])
        self.assertTrue(entry["stored"])
        self.assertTrue(entry["stored_unreadable"])


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
