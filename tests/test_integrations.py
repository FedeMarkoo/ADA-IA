import unittest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from ada.infrastructure.integrations.gmail import draft as gmail_draft
from ada.infrastructure.integrations.gmail import send as gmail_send
from ada.infrastructure.integrations.mcp import MCPClient
from ada.infrastructure.integrations.instagram_graph import publish as graph_publish
from ada.infrastructure.integrations.instagram import publish as instagram_publish
from ada.interfaces.voice import FasterWhisperSTT, PiperTTS


class IntegrationTests(unittest.TestCase):
    def test_mcp_timeout_does_not_wait_for_a_hung_server(self):
        client = MCPClient([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.05)
        with self.assertRaises(TimeoutError):
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

    def test_gmail_draft_is_a_confirmed_real_operation(self):
        preview = gmail_draft({}, "a@b.com", "s", "b")
        self.assertEqual(preview["error"], "confirmation_required")
        self.assertEqual(preview["preview"]["subject"], "s")

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
