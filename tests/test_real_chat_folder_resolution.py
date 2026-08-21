import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ada.application.services.web_chat import WebChatService
from ada.application.services.folder_resolver import FolderResolver
from ada.infrastructure.persistence.sqlite import Memory


class RealChatFolderResolutionTests(unittest.TestCase):
    @staticmethod
    def _filesystem_agent(base, calls):
        class FakeAgent:
            cfg = {"base_dir": str(base), "allowed_roots": [str(base)], "folder_resolver_timeout": 1}
            mem = None

            def parse_prompt(self, text):
                raise AssertionError("Una consulta local de carpetas no debe invocar el router/modelo")

            def decide_and_run(self, task):
                calls.append(task)
                folder = Path(task["payload"]["dir"])
                dirs = sorted(str(path) for path in folder.iterdir() if path.is_dir())
                return {"result": {"ok": True, "action": "list_dirs", "dir": str(folder), "dirs": dirs, "count": len(dirs)}}

        return FakeAgent()

    def test_user_phrases_resolve_against_configured_drive_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            sofia = base / "Eventos" / "Fotos Sofia"
            sofia.mkdir(parents=True)

            calls = []

            class FakeAgent:
                cfg = {"base_dir": str(base), "allowed_roots": [str(base)]}

                def parse_prompt(self, text):
                    return {"action": "list_files", "complexity": 1}

                def decide_and_run(self, task):
                    calls.append(task)
                    return {"result": {"action": "list_files", "dir": task["payload"].get("dir"), "files": [], "count": 0}}

            service = WebChatService(FakeAgent(), FakeAgent.cfg)
            state = SimpleNamespace(conversation=[], pending_action=None)
            response, status = service.handle("cual es la ruta de las fotos de Sofia", state, "es")

            self.assertEqual(status, 200)
            self.assertEqual(response["reply"], f"La ruta es {sofia}.")
            self.assertEqual(calls, [])
            self.assertNotIn("Pictures", response["path"])

    def test_colloquial_user_phrase_resolves_without_model_or_pictures_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            sofia = base / "Fotos" / "Eventos Sociales" / "2026-08-08 - XV Sofia"
            sofia.mkdir(parents=True)

            class FakeAgent:
                cfg = {"base_dir": str(base), "allowed_roots": [str(base)]}
                mem = None

                def parse_prompt(self, text):
                    raise AssertionError("La frase coloquial debe usar el resolver local")

                def decide_and_run(self, task):
                    raise AssertionError("Resolver una ruta no debe ejecutar una capability")

            service = WebChatService(FakeAgent(), FakeAgent.cfg)
            state = SimpleNamespace(conversation=[], pending_action=None, pending_path_action=None, current_path=None)
            response, status = service.handle(
                "che ada, donde estan las fotos de sofia? no me acuerdo la carpeta",
                state,
                "es",
            )

            self.assertEqual(status, 200)
            self.assertEqual(response["reply"], f"La ruta es {sofia}.")
            self.assertEqual(Path(state.current_path), sofia)

            response, status = service.handle(
                "me refiero a las del cumple de 15 de sofia, las tengo en google drive, buscame la carpeta exacta",
                state,
                "es",
            )
            self.assertEqual(status, 200)
            self.assertEqual(response["reply"], f"La ruta es {sofia}.")

    def test_count_photo_followup_resolves_direct_child_from_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            sofia = base / "Fotos" / "Eventos Sociales" / "2026-08-08 - XV Sofia"
            originals = sofia / "Originales"
            originals.mkdir(parents=True)
            for name in ("uno.jpg", "dos.NEF", "tres.png"):
                (originals / name).write_bytes(b"test")
            (originals / "notas.txt").write_text("no es una foto", encoding="utf-8")

            class FakeAgent:
                cfg = {"base_dir": str(base), "allowed_roots": [str(base)]}
                mem = None

                def parse_prompt(self, text):
                    raise AssertionError("El seguimiento debe resolverse localmente")

                def decide_and_run(self, task):
                    payload = task["payload"]
                    extensions = {value.lower() for value in payload.get("extensions", [])}
                    files = [
                        str(path) for path in Path(payload["dir"]).iterdir()
                        if path.is_file() and (not extensions or path.suffix.lower() in extensions)
                    ]
                    return {"result": {"ok": True, "action": "list_files", "dir": payload["dir"], "files": files, "count": len(files)}}

            service = WebChatService(FakeAgent(), FakeAgent.cfg)
            state = SimpleNamespace(conversation=[], pending_action=None, pending_path_action=None, current_path=None)
            service.handle("cual es la ruta de las fotos de sofia?", state, "es")
            response, status = service.handle("y cuantas fotos hay en originales?", state, "es")

            self.assertEqual(status, 200)
            self.assertEqual(response["reply"], f"Hay 3 fotos en {originals}.")
            self.assertEqual(Path(state.current_path), originals)

    def test_root_phrase_uses_configured_drive_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            base.mkdir(parents=True)
            calls = []

            class FakeAgent:
                cfg = {"base_dir": str(base), "allowed_roots": [str(base)]}

                def parse_prompt(self, text):
                    return {"action": "list_dirs", "complexity": 1}

                def decide_and_run(self, task):
                    calls.append(task)
                    return {"result": {"action": "list_dirs", "dir": task["payload"].get("dir"), "dirs": [], "count": 0}}

            service = WebChatService(FakeAgent(), FakeAgent.cfg)
            state = SimpleNamespace(conversation=[], pending_action=None)
            response, status = service.handle("que carpetas tenes en tu root", state, "es")

            self.assertEqual(status, 200)
            self.assertEqual(Path(calls[0]["payload"]["dir"]), base)

    def test_real_followups_keep_folder_context_without_calling_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            events = base / "Fotos" / "Eventos Sociales"
            (events / "Sofia").mkdir(parents=True)
            (events / "Cumpleaños").mkdir()
            calls = []
            agent = self._filesystem_agent(base, calls)
            service = WebChatService(agent, agent.cfg)
            state = SimpleNamespace(conversation=[], pending_action=None, pending_path_action=None, current_path=None)

            first, _ = service.handle("quiero saber que carpetas tengo en gdrive", state, "es")
            second, _ = service.handle("hay una carpeta que sea fotos ahi?", state, "es")
            third, _ = service.handle("y que carpetas tiene adentro de fotos?", state, "es")
            fourth, _ = service.handle("que carpetas hay en eventos sociales?", state, "es")

            self.assertIn("Fotos", first["reply"])
            self.assertEqual(second["reply"], f"Sí, hay una carpeta Fotos en {base / 'Fotos'}.")
            self.assertEqual(Path(calls[2]["payload"]["dir"]), base / "Fotos")
            self.assertEqual(Path(calls[3]["payload"]["dir"]), events)
            self.assertIn(str(events / "Sofia"), fourth["reply"])
            self.assertEqual(Path(state.current_path), events)

    def test_discovered_folders_are_resolved_from_persistent_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            sofia = base / "Fotos" / "Eventos Sociales" / "2026-08-08 - XV Sofia"
            sofia.mkdir(parents=True)
            memory = Memory(str(Path(tmp) / "memory.db"))
            memory.index_folders(sofia.parent, [sofia])
            memory.save_folder_context("web-session", str(sofia.parent))

            result = FolderResolver({"base_dir": str(base)}, memory).resolve("las fotos de sofia")

            self.assertEqual(result["status"], "resolved")
            self.assertEqual(result["source"], "folder_index")
            self.assertEqual(Path(result["path"]), sofia)
            self.assertEqual(memory.get_folder_context("web-session"), str(sofia.parent))
            memory.close()

    def test_stale_folder_index_is_not_reported_as_an_existing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "GoogleDrive"
            base.mkdir()
            missing = base / "Fotos" / "Originales"
            memory = Memory(str(Path(tmp) / "memory.db"))
            memory.index_folders(missing.parent, [missing])

            result = FolderResolver({"base_dir": str(base)}, memory).resolve("fotos en originales")

            self.assertEqual(result["status"], "none")
            self.assertEqual(result["reason"], "stale_index")
            self.assertIn(str(missing), result["stale_paths"])
            memory.close()


if __name__ == "__main__":
    unittest.main()
