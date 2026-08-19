import unittest

from src.ada.infrastructure.integrations.gmail import send as gmail_send
from src.ada.infrastructure.integrations.instagram_graph import publish as graph_publish
from src.ada.interfaces.voice import FasterWhisperSTT, PiperTTS


class IntegrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
