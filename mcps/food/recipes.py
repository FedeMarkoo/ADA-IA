"""Recipe management and profile auto-seeding engine."""

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class RecipeManager:
    """Manages recipe repository and ingredients."""

    @staticmethod
    def seed_profile(conn: sqlite3.Connection, path: Optional[str]) -> None:
        """Seed initial recipes from user profile markdown if available."""
        if not path:
            return
        profile = Path(path).expanduser()
        if not profile.is_file():
            return
        text = profile.read_text(encoding="utf-8")
        sections = re.findall(r"^##\s+3\.\d+\s+(.+?)\n(.*?)(?=^##\s+3\.\d+\s+|\Z)", text, re.M | re.S)
        for name, body in sections:
            ingredient_block = re.search(r"^###\s+Ingredientes\s*\n(.*?)(?=^###\s+|\Z)", body, re.M | re.S)
            if not ingredient_block:
                continue
            ingredients = [
                line.strip()[2:].strip() for line in ingredient_block.group(1).splitlines() if line.strip().startswith("-")
            ]
            if ingredients:
                conn.execute(
                    "INSERT OR IGNORE INTO food_recipes(name,ingredients,steps,tags) VALUES (?,?,?,?)",
                    (name.strip(), json.dumps(ingredients, ensure_ascii=False), body.strip(), "perfil_fede"),
                )
        conn.commit()

    @staticmethod
    def handle(conn: sqlite3.Connection, args: Dict[str, Any]) -> Dict[str, Any]:
        action = args.get("action", "list")
        if action in {"add", "save"}:
            name = args.get("name", "").strip()
            if not name:
                return {"error": "name_required"}
            raw_ing = args.get("ingredients", [])
            if isinstance(raw_ing, list):
                ingredients = [str(x).strip() for x in raw_ing if str(x).strip()]
            elif isinstance(raw_ing, str):
                ingredients = [x.strip() for x in raw_ing.split(",") if x.strip()]
            else:
                ingredients = [str(raw_ing).strip()]

            cur = conn.execute(
                "INSERT OR REPLACE INTO food_recipes(name, ingredients, steps, servings, tags, updated_at) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (
                    name,
                    json.dumps(ingredients, ensure_ascii=False),
                    args.get("steps", ""),
                    args.get("servings", 2),
                    args.get("tags", ""),
                ),
            )
            conn.commit()
            return {"ok": True, "action": action, "id": cur.lastrowid, "name": name, "ingredients": ingredients}

        elif action == "get":
            name = args.get("name", "").strip()
            row = conn.execute(
                "SELECT id, name, ingredients, steps, servings, tags FROM food_recipes WHERE lower(name) LIKE lower(?)",
                (f"%{name}%",),
            ).fetchone()
            if not row:
                return {"error": "recipe_not_found", "name": name}
            try:
                ingredients_list = json.loads(row[2])
            except Exception:
                ingredients_list = [row[2]]
            return {
                "ok": True,
                "recipe": {
                    "id": row[0],
                    "name": row[1],
                    "ingredients": ingredients_list,
                    "steps": row[3],
                    "servings": row[4],
                    "tags": row[5],
                },
            }

        elif action in {"recipe_to_shopping", "to_shopping"}:
            name = args.get("name", "").strip()
            row = conn.execute(
                "SELECT ingredients FROM food_recipes WHERE lower(name) LIKE lower(?)",
                (f"%{name}%",),
            ).fetchone()
            if not row:
                return {"error": "recipe_not_found", "name": name}
            try:
                ingredients = json.loads(row[0])
            except Exception:
                ingredients = [x.strip() for x in row[0].split(",") if x.strip()]

            added_count = 0
            for ing in ingredients:
                cur = conn.execute(
                    "SELECT id FROM food_shopping WHERE lower(item)=lower(?) AND status='pending'", (ing,)
                )
                if not cur.fetchone():
                    conn.execute("INSERT INTO food_shopping(item, category, priority) VALUES (?, ?, ?)", (ing, "Receta", "normal"))
                    added_count += 1
            conn.commit()
            return {"ok": True, "action": "recipe_to_shopping", "recipe": name, "added": added_count}

        elif action == "delete":
            name = args.get("name", "").strip()
            conn.execute("DELETE FROM food_recipes WHERE lower(name)=lower(?)", (name,))
            conn.commit()
            return {"ok": True, "action": "delete", "name": name}

        query = "SELECT id, name, ingredients, servings, tags FROM food_recipes"
        tag_filter = args.get("tag")
        params = []
        if tag_filter:
            query += " WHERE tags LIKE ?"
            params.append(f"%{tag_filter}%")
        query += " ORDER BY name"

        rows = conn.execute(query, params).fetchall()
        recipes = []
        for r in rows:
            try:
                ings = json.loads(r[2])
            except Exception:
                ings = []
            recipes.append({"id": r[0], "name": r[1], "ingredients_count": len(ings), "servings": r[3], "tags": r[4]})
        return {"ok": True, "action": "list", "total": len(recipes), "recipes": recipes}
