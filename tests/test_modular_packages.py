"""Unit tests for the dedicated Ollama client and ModelCatalog / MCPManager."""

from unittest.mock import MagicMock, patch
from ada.ollama.client import OllamaClient
from ada.models.catalog import ModelCatalog
from ada.mcps.manager import MCPManager


def test_ollama_client_health():
    client = OllamaClient(endpoint="http://127.0.0.1:11434")
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        health = client.health()
        assert health["online"] is True
        assert health["status_code"] == 200


def test_ollama_client_list_models():
    client = OllamaClient()
    fake_json = b'{"models": [{"name": "llama3.2:3b", "size": 2000000000, "details": {"format": "gguf", "parameter_size": "3B"}}]}'
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_json
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        models = client.list_models()
        assert len(models) == 1
        assert models[0]["name"] == "llama3.2:3b"
        assert "details" in models[0]
        assert models[0]["details"]["parameter_size"] == "3B"


def test_model_catalog_and_roles():
    catalog = ModelCatalog({"model_catalog": [{"name": "custom:7b", "min_ram_gb": 4, "roles": ["chat"]}]})
    items = catalog.get_catalog()
    assert len(items) == 1
    assert items[0]["name"] == "custom:7b"
    assert "hardware_fit" in items[0]
    roles = catalog.get_roles()
    assert "chat" in roles
    assert "vision" in roles


def test_mcp_manager_tools_and_toggling():
    manager = MCPManager()
    servers = manager.list_servers()
    assert len(servers) >= 3

    tools = manager.list_tools()
    assert len(tools) >= 5
    fs_tool = manager.get_tool("filesystem.list_files")
    assert fs_tool is not None
    assert fs_tool["enabled"] is True

    toggled = manager.toggle_tool("filesystem.list_files", False)
    assert toggled is True
    assert manager.get_tool("filesystem.list_files")["enabled"] is False
