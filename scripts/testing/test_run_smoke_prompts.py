import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("run-smoke-prompts.py")
SPEC = importlib.util.spec_from_file_location("smoke_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SmokeRunnerTest(unittest.TestCase):
    def test_default_database_path_is_relative_to_repository(self):
        with patch.dict(MODULE.os.environ, {}, clear=True):
            expected = Path(MODULE.__file__).resolve().parents[2] / "../ada-data/db/ada.sqlite"
            self.assertEqual(MODULE.database_path(None), expected.resolve())

    def test_rejects_non_positive_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "ada.sqlite"
            MODULE.seed_prompts(database, Path(__file__).with_name("smoke-prompts.json"))
            self.assertEqual(MODULE.load_prompts(database, 0), [])

    def test_seed_and_load_prompts_from_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "db" / "ada.sqlite"
            seed = Path(directory) / "prompts.json"
            seed.write_text(
                json.dumps([{"id": "one", "name": "One", "prompt": "Prompt one"}]),
                encoding="utf-8",
            )

            self.assertEqual(MODULE.seed_prompts(database, seed), 1)
            self.assertEqual(
                MODULE.load_prompts(database, 3),
                [{"id": "one", "name": "One", "prompt": "Prompt one"}],
            )
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM smoke_prompts").fetchone()[0],
                    1,
                )

    def test_only_enabled_prompts_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "ada.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute(MODULE.CREATE_PROMPTS_TABLE)
                connection.executemany(
                    "INSERT INTO smoke_prompts(id, name, prompt, enabled) VALUES (?, ?, ?, ?)",
                    [("enabled", "Enabled", "yes", 1), ("disabled", "Disabled", "no", 0)],
                )
            self.assertEqual(
                [item["id"] for item in MODULE.load_prompts(database, 3)], ["enabled"]
            )


if __name__ == "__main__":
    unittest.main()
