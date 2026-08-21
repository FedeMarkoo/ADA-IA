"""Food and shopping capability bridge delegating directly to mcps.food."""

from typing import Any, Dict
from mcps.food.shopping import ShoppingManager
from mcps.food.recipes import RecipeManager
from mcps.food.inventory import InventoryManager
from mcps.food.budget import BudgetManager
from mcps.food.planner import PlannerManager
from mcps.food.server import get_db


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    domain = args.get("domain") or args.get("section")
    action = args.get("action", "list")
    if not domain:
        if action == "recipe_to_shopping":
            domain = "recipes"
        else:
            domain = "shopping"

    db_path = args.get("db_path") or args.get("config", {}).get("db_path")
    with get_db(db_path) as conn:
        cfg = args.get("config") or {}
        profile_path = args.get("profile") or cfg.get("food_profile") or cfg.get("profile")
        RecipeManager.seed_profile(conn, profile_path)

        if domain == "shopping":
            result = ShoppingManager.handle(conn, args)
        elif domain == "recipes":
            result = RecipeManager.handle(conn, args)
        elif domain == "inventory":
            result = InventoryManager.handle(conn, args)
        elif domain == "budget":
            result = BudgetManager.handle(conn, args)
        elif domain in {"planning", "meal_plan", "planner"}:
            result = PlannerManager.handle(conn, args)
        else:
            return {"error": "unknown_domain", "domain": domain}
        if isinstance(result, dict):
            result.setdefault("domain", domain)
        return result
