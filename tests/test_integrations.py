import os
import unittest
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from ada.infrastructure.integrations.gmail import draft as gmail_draft
from ada.infrastructure.integrations.gmail import send as gmail_send
from ada.infrastructure.integrations.mcp import MCPClient
from ada.infrastructure.integrations.instagram_graph import publish as graph_publish
from ada.infrastructure.integrations.instagram import publish as instagram_publish
from ada.interfaces.voice import FasterWhisperSTT, PiperTTS


class IntegrationTests(unittest.TestCase):
    def test_mcp_timeout_does_not_wait_for_a_hung_server(self):
        client = MCPClient([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.05)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            client.call(list_only=True)
        self.assertLess(time.monotonic() - started, 1)

    def test_mcp_timeout_does_not_block_on_partial_line(self):
        script = 'import sys,time; sys.stdout.write(\'{\\"jsonrpc\\":\\"2.0\\"}\'); sys.stdout.flush(); time.sleep(2)'
        client = MCPClient([sys.executable, "-c", script], timeout=0.05)
        with self.assertRaises(TimeoutError):
            client.call(list_only=True)

    def test_mcp_accepts_vscode_stdio_command_args_env_and_cwd(self):
        script = (
            "import json,os,sys; "
            "print(json.dumps({'jsonrpc':'2.0','id':1,'result':{}}),flush=True); "
            "print(json.dumps({'jsonrpc':'2.0','id':2,'result':{'tools':[{'name':'hello'}]}}),flush=True); "
            "line=sys.stdin.readline(); "
            "print(json.dumps({'jsonrpc':'2.0','id':3,'result':{'content':[{'text':os.environ['ADA_MCP_TEST']+sys.argv[1]}]}}),flush=True)"
        )
        with patch.dict(os.environ, {"ADA_MCP_ARG": "-embedded"}):
            client = MCPClient(
                {
                    "type": "stdio",
                    "command": sys.executable,
                    "args": ["-c", script, "${env:ADA_MCP_ARG}"],
                    "env": {"ADA_MCP_TEST": "ok"},
                    "cwd": str(Path.cwd()),
                }
            )
            result = client.call(tool="hello", arguments={})
        self.assertEqual(result["tool"], "hello")
        self.assertEqual(result["result"]["content"][0]["text"], "ok-embedded")

    def test_mcp_http_uses_streamable_http_style_session(self):
        payloads = [
            (b'{"result":{}}', "session-1"),
            (b"{}", None),
            (b'{"result":{"tools":[{"name":"hello"}]}}', None),
            (b'{"result":{"content":[{"text":"ok"}]}}', None),
        ]
        contexts = []
        for body, session_id in payloads:
            response = MagicMock()
            response.headers.get.side_effect = lambda key, sid=session_id: (
                sid if key == "Mcp-Session-Id" else "application/json"
            )
            response.read.return_value = body
            context = MagicMock()
            context.__enter__.return_value = response
            contexts.append(context)
        with patch("ada.infrastructure.integrations.mcp.urllib.request.urlopen", side_effect=contexts):
            client = MCPClient({"type": "http", "url": "https://example.test/mcp"})
            result = client.call(tool="hello", arguments={})
        self.assertEqual(result["result"]["content"][0]["text"], "ok")

    def test_mcp_http_rejects_cleartext_remote_endpoints(self):
        client = MCPClient({"type": "http", "url": "http://example.test/mcp"})
        with self.assertRaises(ValueError):
            client.call(list_only=True)

    def test_graph_publisher_requires_configuration_and_confirmation(self):
        preview = graph_publish({}, "https://example.com/photo.jpg", "caption")
        self.assertEqual(preview["error"], "confirmation_required")
        missing = graph_publish({}, "https://example.com/photo.jpg", "caption", confirm=True)
        self.assertEqual(missing["error"], "instagram_graph_not_configured")

    def test_optional_voice_adapters_fail_with_actionable_messages(self):
        with self.assertRaises(RuntimeError):
            FasterWhisperSTT().transcribe("/tmp/missing.wav")
        with self.assertRaises(RuntimeError):
            PiperTTS().synthesize("hola", "/tmp/out.wav")

    def test_gmail_still_previews_before_oauth(self):
        self.assertEqual(gmail_send({}, "a@b.com", "s", "b")["error"], "confirmation_required")

    def test_gmail_draft_does_not_require_send_confirmation(self):
        with patch("ada.infrastructure.integrations.gmail._mcp_call", return_value={"ok": True}) as call:
            result = gmail_draft({"gmail_backend": "mcp"}, "a@b.com", "s", "b")
        self.assertTrue(result["ok"])
        self.assertEqual(result["preview"]["subject"], "s")
        call.assert_called_once()

    def test_instagram_persists_profile_and_passes_it_to_puppeteer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "photo.jpg"
            script = root / "publish.js"
            image.write_bytes(b"image")
            script.write_text("", encoding="utf-8")
            with patch("ada.infrastructure.integrations.instagram.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = "ok"
                run.return_value.stderr = ""
                result = instagram_publish(
                    {
                        "instagram_publish_script": str(script),
                        "instagram_profile_dir": str(root / "profile"),
                        "allowed_roots": [str(root)],
                    },
                    str(image),
                    "caption",
                    confirm=True,
                )
            self.assertTrue(result["ok"])
            self.assertIn("--user-data-dir", run.call_args.args[0])
            self.assertTrue(Path(result["profile_dir"]).is_dir())


if __name__ == "__main__":
    unittest.main()
