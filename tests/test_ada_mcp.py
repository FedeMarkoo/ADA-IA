"""Unit tests for ADA MCP server (tools/ada_mcp_server.py)."""

import json
import unittest
from unittest.mock import MagicMock, patch

import tools.ada_mcp_server as mcp_server


class TestAdaMcpServer(unittest.TestCase):
    """Test suite for ADA MCP Server tools and JSON-RPC dispatching."""

    def test_tools_list_completeness(self):
        """Verify that all expected tools are registered with schemas and handlers."""
        tool_names = {t["name"] for t in mcp_server.TOOLS}
        expected_tools = {
            # System & Core
            "ada_status",
            "ada_core_state",
            "ada_activity",
            "ada_restart_agent",
            # Chat & Conversation
            "ada_chat",
            "ada_conversation_get",
            "ada_conversation_clear",
            "ada_action_confirm",
            "ada_action_cancel",
            "ada_debug_toggle",
            "ada_debug_events",
            # Models & Ollama
            "ada_ollama_status",
            "ada_ollama_list_models",
            "ada_ollama_load_model",
            "ada_ollama_unload_model",
            "ada_ollama_preload_all",
            "ada_ollama_delete_model",
            "ada_ollama_show_model",
            "ada_ollama_memory_estimate",
            "ada_ollama_memory_calibrate",
            "ada_ollama_config_get",
            "ada_ollama_config_set",
            "ada_models_catalog_list",
            "ada_models_catalog_upsert",
            "ada_models_catalog_delete",
            "ada_models_policy_get",
            "ada_models_policy_set",
            "ada_models_benchmark",
            "ada_models_benchmark_prompts",
            # MCPs
            "ada_mcp_list_servers",
            "ada_mcp_list_tools",
            "ada_mcp_server_action",
            "ada_mcp_restart_all",
            # Healthcheck & Doctor
            "ada_healthcheck_diagnose",
            "ada_healthcheck_auto_heal",
            "ada_healthcheck_fix",
            "ada_healthcheck_prompts_list",
            "ada_healthcheck_prompt_create",
            "ada_healthcheck_run_batch",
            "ada_healthcheck_batch_status",
            "ada_healthcheck_batch_cancel",
            "ada_healthcheck_history",
            "ada_healthcheck_latest",
            # Vault
            "ada_vault_list_keys",
            "ada_vault_set_key",
            "ada_vault_delete_key",
            "ada_telegram_test",
            # System, Triggers, Memory, Updates & Telegram
            "ada_memory_stats",
            "ada_memory_refiner_run",
            "ada_audit_log",
            "ada_triggers_list",
            "ada_trigger_toggle",
            "ada_trigger_status",
            "ada_presence_get",
            "ada_presence_set",
            "ada_presence_history",
            "ada_telegram_service_status",
            "ada_telegram_service_toggle",
            "ada_telegram_service_config",
            "ada_telegram_service_logs",
            "ada_update_status",
            "ada_update_check",
            "ada_update_apply",
            "ada_send_event",
            # Monitoring (Prometheus & Grafana)
            "ada_monitoring_status",
            "ada_monitoring_action",
        }
        for tool in expected_tools:
            self.assertIn(tool, tool_names, f"Missing tool: {tool}")
            self.assertIn(tool, mcp_server.TOOL_MAP)
            self.assertTrue(callable(mcp_server.TOOL_MAP[tool]["handler"]))
            self.assertIn("inputSchema", mcp_server.TOOL_MAP[tool])

    @patch("tools.ada_mcp_server._opener.open")
    def test_ada_status_tool(self, mock_open):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"identity": {"version": "3.0.0"}, "agent_enabled": True}).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_response

        res_str = mcp_server.handle_ada_status({})
        res = json.loads(res_str)
        self.assertEqual(res.get("identity", {}).get("version"), "3.0.0")

    @patch("tools.ada_mcp_server._opener.open")
    def test_ada_chat_tool(self, mock_open):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"reply": "Hola, ¿en qué puedo ayudarte?", "status": "completed"}).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_response

        res_str = mcp_server.handle_ada_chat({"message": "hola", "lang": "es"})
        res = json.loads(res_str)
        self.assertEqual(res.get("reply"), "Hola, ¿en qué puedo ayudarte?")

    def test_ada_chat_validation(self):
        res_str = mcp_server.handle_ada_chat({})
        res = json.loads(res_str)
        self.assertIn("error", res)

    @patch("tools.ada_mcp_server._opener.open")
    def test_ada_ollama_tools(self, mock_open):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"models": [{"name": "llama3.2:3b"}], "running": []}).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_response

        res_str = mcp_server.handle_ada_ollama_list_models({})
        res = json.loads(res_str)
        self.assertEqual(len(res.get("models")), 1)

    @patch("tools.ada_mcp_server._opener.open")
    def test_ada_mcp_server_action(self, mock_open):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True, "server": "filesystem", "status": "restarted"}).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_response

        res_str = mcp_server.handle_ada_mcp_server_action({"name": "filesystem", "action": "restart"})
        res = json.loads(res_str)
        self.assertTrue(res.get("ok"))

    @patch("tools.ada_mcp_server._opener.open")
    def test_ada_healthcheck_tools(self, mock_open):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"overall_status": "healthy", "score": 100, "items": []}).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_response

        res_str = mcp_server.handle_ada_healthcheck_diagnose({})
        res = json.loads(res_str)
        self.assertEqual(res.get("overall_status"), "healthy")

    @patch("tools.ada_mcp_server._opener.open")
    def test_ada_vault_tools(self, mock_open):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"ok": True, "keys": ["telegram_bot_token"]}).encode("utf-8")
        mock_open.return_value.__enter__.return_value = mock_response

        res_str = mcp_server.handle_ada_vault_list_keys({})
        res = json.loads(res_str)
        self.assertIn("telegram_bot_token", res.get("keys"))

    @patch("tools.ada_mcp_server._opener.open")
    def test_offline_error_handling(self, mock_open):
        import urllib.error
        mock_open.side_effect = urllib.error.URLError("Connection refused")

        res_str = mcp_server.handle_ada_status({})
        res = json.loads(res_str)
        self.assertTrue(res.get("error"))
        self.assertTrue(res.get("offline"))
        self.assertIn("No se pudo conectar a ADA", res.get("message"))


if __name__ == "__main__":
    unittest.main()
