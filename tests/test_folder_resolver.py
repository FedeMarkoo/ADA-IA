from pathlib import Path
import tempfile
import unittest

from ada.application.services.folder_resolver import FolderResolver


class TestFolderResolver(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        (self.base_path / "Fotos").mkdir(parents=True, exist_ok=True)
        (self.base_path / "Fotos" / "Cumpleaños_15").mkdir(parents=True, exist_ok=True)
        (self.base_path / "Documentos").mkdir(parents=True, exist_ok=True)

        self.config = {
            "base_dir": str(self.base_path),
            "folder_probe_timeout": 1.0,
            "folder_resolver_timeout": 2.0,
        }
        self.resolver = FolderResolver(self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalize(self):
        norm = FolderResolver._normalize("¡Hola! ¿Dónde están las Fótos?")
        self.assertEqual(norm, "hola donde estan las fotos")

    def test_resolve_root(self):
        res = self.resolver.resolve("carpeta raiz de google drive")
        self.assertEqual(res.get("status"), "resolved")
        self.assertEqual(res.get("path"), str(self.base_path.resolve()))

    def test_resolve_label(self):
        res = self.resolver.resolve_label("Fotos")
        self.assertEqual(res.get("status"), "resolved")
        self.assertEqual(Path(res.get("path")).name, "Fotos")


if __name__ == "__main__":
    unittest.main()
