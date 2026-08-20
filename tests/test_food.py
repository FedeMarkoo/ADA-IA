import tempfile
import unittest
from pathlib import Path

from ada.application.agent import Agent
from ada.capabilities.data.food import run
from ada.infrastructure.persistence.sqlite import Memory


class FoodTests(unittest.TestCase):
    def test_persists_shopping_and_recipes(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "food.db")
            self.assertTrue(
                run(
                    {
                        "db_path": db,
                        "domain": "shopping",
                        "action": "add",
                        "item": "leche",
                        "quantity": "2",
                        "unit": "litros",
                    }
                )["ok"]
            )
            self.assertEqual(run({"db_path": db, "domain": "shopping", "action": "list"})["items"][0]["item"], "leche")
            run(
                {
                    "db_path": db,
                    "domain": "recipes",
                    "action": "save",
                    "name": "Tortilla",
                    "ingredients": "huevo, papa, cebolla",
                }
            )
            result = run({"db_path": db, "action": "recipe_to_shopping", "name": "Tortilla"})
            self.assertEqual(result["added"], 3)

    def test_agent_parses_food_requests_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = Agent({"engine_provider": "unknown", "db_path": str(Path(directory) / "memory.db")})
            self.assertEqual(agent.parse_prompt("qué puedo comer mañana?")["action"], "food")
            self.assertTrue(agent.parse_prompt("qué puedo comer mañana?")["advisor"])

    def test_seeds_recipes_from_markdown_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "perfil.md"
            profile.write_text(
                "## 3.1 Hamburguesas caseras\n### Ingredientes\n- carne picada\n- sal\n\n### Freezer\n- Muy buena\n",
                encoding="utf-8",
            )
            db = str(Path(directory) / "food.db")
            result = run(
                {"db_path": db, "config": {"food_profile": str(profile)}, "domain": "recipes", "action": "list"}
            )
            self.assertEqual(result["recipes"][0]["name"], "Hamburguesas caseras")

    def test_ai_prompts_are_dynamic_in_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "memory.db"))
            self.assertTrue(memory.router_actions())
            memory.upsert_prompt_template("router", "PEDIDO: {text}")
            self.assertEqual(memory.prompt_template("router"), "PEDIDO: {text}")
            schema = memory.json_schema("food_reply")
            self.assertIn("reply", schema["properties"])
            memory.upsert_json_schema("food_reply", {"type": "object", "properties": {"reply": {"type": "string"}}})
            self.assertEqual(memory.json_schema("food_reply")["type"], "object")

    def test_inventory_budget_and_weekly_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "food.db")
            self.assertTrue(
                run(
                    {
                        "db_path": db,
                        "domain": "inventory",
                        "action": "add",
                        "item": "arroz",
                        "quantity": 2,
                        "minimum": 1,
                    }
                )["ok"]
            )
            self.assertEqual(
                run({"db_path": db, "domain": "inventory", "action": "use", "item": "arroz", "quantity": 1})[
                    "quantity"
                ],
                1.0,
            )
            self.assertEqual(
                run({"db_path": db, "domain": "budget", "action": "set", "period": "2026-08", "amount": 10000})[
                    "budget"
                ]["amount"],
                10000,
            )
            run({"db_path": db, "domain": "budget", "action": "spend", "period": "2026-08", "amount": 1200})
            self.assertEqual(run({"db_path": db, "domain": "budget", "action": "list"})["budgets"][0]["spent"], 1200)
            self.assertTrue(
                run(
                    {
                        "db_path": db,
                        "domain": "planning",
                        "action": "set",
                        "plan_date": "2026-08-24",
                        "meal": "cena",
                        "recipe_name": "Tortilla",
                    }
                )["ok"]
            )
            self.assertEqual(
                len(run({"db_path": db, "domain": "planning", "action": "list", "week": "2026-08-24"})["plan"]), 1
            )


if __name__ == "__main__":
    unittest.main()
