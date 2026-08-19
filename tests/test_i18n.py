import unittest

from ada.interfaces.i18n import normalize_language, tr


class I18nTests(unittest.TestCase):
    def test_language_fallback_and_translation(self):
        self.assertEqual(normalize_language("en-US"), "en")
        self.assertEqual(normalize_language("pt"), "es")
        self.assertEqual(tr("greeting", "en"), "Hi, how can I help you?")


if __name__ == "__main__":
    unittest.main()
