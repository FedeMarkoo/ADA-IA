import json
import tempfile
import unittest
from pathlib import Path

from ada.config import load_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_validation_rejects_unknown_web_framework(self):
        with self.assertRaises(ValueError):
            validate_config({"web_framework": "unknown"})

    def test_validation_accepts_model_catalog_shapes(self):
        config = validate_config({"model_catalog": {"small": {"min_ram_gb": 2}}})
        self.assertEqual(config["model_catalog"]["small"]["min_ram_gb"], 2)

    def test_validation_rejects_non_boolean_memory_encryption(self):
        with self.assertRaises(ValueError):
            validate_config({"memory_encryption": "yes"})

    def test_validation_rejects_invalid_runtime_types(self):
        with self.assertRaises(ValueError):
            validate_config({"adaptive_models": "yes"})
        with self.assertRaises(ValueError):
            validate_config({"photo_executor": "fork"})
        with self.assertRaises(ValueError):
            validate_config({"cpu_limit_percent": 0})
        with self.assertRaises(ValueError):
            validate_config({"chat_workers": 0})

    def test_load_config_does_not_trust_vscode_mcp_servers_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".vscode").mkdir()
            (root / ".vscode" / "mcp.json").write_text(
                json.dumps({"servers": {"github": {"type": "stdio", "command": "npx", "args": ["-y", "x"]}}}),
                encoding="utf-8",
            )
            config = load_config(project_root=root)
        self.assertEqual(config["mcp_servers"], {})

    def test_load_config_imports_vscode_mcp_servers_after_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".vscode").mkdir()
            (root / ".vscode" / "mcp.json").write_text(
                json.dumps({"servers": {"github": {"type": "stdio", "command": "npx", "args": ["-y", "x"]}}}),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(json.dumps({"trust_workspace_mcp": True}), encoding="utf-8")
            config = load_config(path=config_path, project_root=root)
        self.assertEqual(config["mcp_servers"]["github"]["command"], "npx")

    def test_load_config_prefers_inline_mcp_servers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({"mcpServers": {"local": {"command": "python"}}}), encoding="utf-8")
            config = load_config(path=config_path, project_root=root)
        self.assertEqual(config["mcp_servers"]["local"]["command"], "python")

    def test_validation_rejects_non_boolean_workspace_mcp_trust(self):
        with self.assertRaises(ValueError):
            validate_config({"trust_workspace_mcp": "yes"})


if __name__ == "__main__":
    unittest.main()
