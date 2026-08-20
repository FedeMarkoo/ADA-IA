"""Meal planning and weekly schedule engine."""

import sqlite3
from typing import Any, Dict, List, Optional


class PlannerManager:
    """Manages weekly meal plans and scheduled recipes."""

    @staticmethod
    def handle(conn: sqlite3.Connection, args: Dict[str, Any]) -> Dict[str, Any]:
        action = args.get("action", "list")
        if action == "set":
            plan_date = args.get("plan_date", "").strip()
            meal = args.get("meal", "").strip()
            recipe_name = args.get("recipe_name", "").strip()
            servings = int(args.get("servings", 2))
            cost = float(args.get("estimated_cost", 0)) if args.get("estimated_cost") else None
            notes = args.get("notes", "")

            conn.execute(
                """INSERT INTO food_meal_plan(plan_date, meal, recipe_name, servings, estimated_cost, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(plan_date, meal) DO UPDATE SET
                     recipe_name = excluded.recipe_name,
                     servings = excluded.servings,
                     estimated_cost = excluded.estimated_cost,
                     notes = excluded.notes,
                     updated_at = CURRENT_TIMESTAMP""",
                (plan_date, meal, recipe_name, servings, cost, notes),
            )
            conn.commit()
            return {"ok": True, "action": "set", "plan_date": plan_date, "meal": meal, "recipe_name": recipe_name}

        elif action == "delete":
            plan_date = args.get("plan_date", "").strip()
            meal = args.get("meal", "").strip()
            conn.execute("DELETE FROM food_meal_plan WHERE plan_date=? AND meal=?", (plan_date, meal))
            conn.commit()
            return {"ok": True, "action": "delete"}

        query = "SELECT id, plan_date, meal, recipe_name, servings, estimated_cost, notes FROM food_meal_plan"
        params = []
        week = args.get("week")
        if week:
            query += " WHERE plan_date >= ? AND plan_date <= date(?, '+6 days')"
            params.extend([week, week])
        query += " ORDER BY plan_date, meal"

        rows = conn.execute(query, params).fetchall()
        plan = [
            {
                "id": r[0],
                "plan_date": r[1],
                "meal": r[2],
                "recipe_name": r[3],
                "servings": r[4],
                "estimated_cost": r[5],
                "notes": r[6],
            }
            for r in rows
        ]
        return {"ok": True, "action": "list", "total": len(plan), "plan": plan}
