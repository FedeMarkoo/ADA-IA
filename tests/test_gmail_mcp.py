import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ada.capabilities.registry import load_capabilities
from ada.infrastructure.integrations import gmail


class GmailMCPTests(unittest.TestCase):
    @staticmethod
    def _config(url="https://gmailmcp.googleapis.com/mcp/v1"):
        return {
            "gmail_backend": "mcp",
            "gmail_mcp_server": "gmail",
            "gmail_mcp_allowed_hosts": ["gmailmcp.googleapis.com"],
            "mcp_servers": {"gmail": {"type": "http", "url": url}},
        }

    def test_registry_keeps_one_canonical_gmail_surface(self):
        capabilities = load_capabilities(strict=True)
        self.assertNotIn("gmail", capabilities)
        self.assertIn("gmail_read", capabilities)
        self.assertIn("gmail_draft", capabilities)
        self.assertIn("gmail_send", capabilities)

    def test_read_uses_configured_google_mcp_backend(self):
        client = MagicMock()
        client.call.return_value = {"result": {"threads": []}}
        with patch.object(gmail, "_gmail_mcp_client", return_value=client):
            result = gmail.read(self._config(), query="from:cliente@example.com", limit=7)
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "mcp")
        client.call.assert_called_once_with(
            tool="search_threads",
            arguments={
                "query": "from:cliente@example.com",
                "pageSize": 7,
                "view": "THREAD_VIEW_MINIMAL",
            },
        )

    def test_create_draft_uses_mcp_without_send_confirmation(self):
        client = MagicMock()
        client.call.return_value = {"result": {"id": "draft-123"}}
        with patch.object(gmail, "_gmail_mcp_client", return_value=client):
            result = gmail.draft(self._config(), "a@example.com", "Asunto", "Hola")
        self.assertTrue(result["ok"])
        self.assertEqual(result["preview"]["subject"], "Asunto")
        client.call.assert_called_once_with(
            tool="create_draft",
            arguments={"to": ["a@example.com"], "subject": "Asunto", "body": "Hola"},
        )

    def test_send_remains_the_confirmation_boundary(self):
        result = gmail.send(self._config(), "a@example.com", "Asunto", "Hola")
        self.assertEqual(result["error"], "confirmation_required")

    def test_mcp_client_uses_config_url_and_refreshed_credential_token(self):
        config = self._config()
        config["gmail_mcp_timeout"] = 30
        config["mcp_servers"]["gmail"]["headers"] = {"X-Client": "ADA"}
        with (
            patch.object(gmail, "_credentials", return_value=SimpleNamespace(token="fresh-token")),
            patch.object(gmail, "MCPClient") as client_class,
        ):
            gmail._gmail_mcp_client(config, [gmail.READ_SCOPE])
        client_class.assert_called_once_with(
            {
                "type": "http",
                "url": "https://gmailmcp.googleapis.com/mcp/v1",
                "headers": {"X-Client": "ADA", "Authorization": "Bearer fresh-token"},
            },
            timeout=30.0,
        )

    def test_mcp_client_rejects_non_https_or_unlisted_hosts_before_loading_token(self):
        for url in (
            "http://gmailmcp.googleapis.com/mcp/v1",
            "https://evil.example/mcp",
            "https://user:secret@gmailmcp.googleapis.com/mcp/v1",
        ):
            with self.subTest(url=url), patch.object(gmail, "_credentials") as credentials:
                with self.assertRaises(RuntimeError):
                    gmail._gmail_mcp_client(self._config(url), [gmail.READ_SCOPE])
                credentials.assert_not_called()

    def test_expired_access_token_is_refreshed_and_persisted(self):
        class FakeCredentials:
            expired = True
            refresh_token = "refresh-token"
            token = "expired-token"

            def refresh(self, request):
                self.request = request
                self.expired = False
                self.token = "fresh-token"

        credentials = FakeCredentials()
        request = object()
        with (
            patch.object(gmail, "_load_credentials", return_value=(credentials, None)),
            patch.object(gmail, "_refresh_request", return_value=request),
            patch.object(gmail, "_save_credentials") as save,
        ):
            result = gmail._credentials({}, [gmail.READ_SCOPE])
        self.assertIs(result, credentials)
        self.assertIs(credentials.request, request)
        save.assert_called_once_with({}, credentials, None)

    def test_encrypted_credential_configuration_requires_a_key_before_oauth(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ADA_CREDENTIAL_KEY"):
                gmail.authenticate({"gmail_credential_name": "gmail_oauth"})


if __name__ == "__main__":
    unittest.main()
