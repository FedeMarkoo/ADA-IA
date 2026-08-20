import unittest
from unittest.mock import patch

from ada.capabilities.system import gmail


class GmailMCPTests(unittest.TestCase):
    def test_search_uses_google_gmail_mcp(self):
        with patch.object(gmail.MCPClient) as client_cls:
            client_cls.return_value.call.return_value = {"ok": True}

            result = gmail.run({"action": "search", "query": "from:cliente@example.com"})

            self.assertEqual(result, {"ok": True})
            client_cls.assert_called_once_with(
                {
                    "type": "http",
                    "url": "https://gmailmcp.googleapis.com/mcp/v1",
                    "headers": {"Authorization": "Bearer ${env:GMAIL_MCP_ACCESS_TOKEN}"},
                }
            )
            client_cls.return_value.call.assert_called_once_with(
                tool="search_threads",
                arguments={"query": "from:cliente@example.com"},
            )

    def test_create_draft_requires_explicit_confirmation(self):
        with patch.object(gmail.MCPClient) as client_cls:
            result = gmail.run({"action": "create_draft", "arguments": {"subject": "Test"}})

            self.assertEqual(result["error"], "confirmation_required")
            client_cls.assert_not_called()

    def test_create_draft_calls_mcp_after_confirmation(self):
        with patch.object(gmail.MCPClient) as client_cls:
            client_cls.return_value.call.return_value = {"draft": "123"}

            result = gmail.run(
                {
                    "action": "create_draft",
                    "confirm": True,
                    "arguments": {"subject": "Test", "body": "Hola"},
                }
            )

            self.assertEqual(result, {"draft": "123"})
            client_cls.return_value.call.assert_called_once_with(
                tool="create_draft",
                arguments={"subject": "Test", "body": "Hola"},
            )


if __name__ == "__main__":
    unittest.main()
