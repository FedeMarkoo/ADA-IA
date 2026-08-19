"""Persistent shopping list and recipe book for ADA.

The capability is deliberately small and local-first.  Telegram and the web
interface pass the same structured payload to it, so neither adapter owns
food-related business logic.
"""
import json
import re
import sqlite3
from pathlib import Path


def _db(args):
    path = args.get("db_path") or args.get("config", {}).get("db_path") or "memory.db"
    return sqlite3.connect(str(Path(path).expanduser()))


def _ensure(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS food_shopping (
      id INTEGER PRIMARY KEY, item TEXT NOT NULL, quantity TEXT, unit TEXT,
      category TEXT, priority TEXT DEFAULT 'normal', status TEXT DEFAULT 'pending',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS food_recipes (
      id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, ingredients TEXT NOT NULL,
      steps TEXT, servings INTEGER, tags TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()


def _seed_profile(conn, path):
    """Import recipe sections from the user's markdown profile once.

    The profile remains the source document; INSERT OR IGNORE makes this safe
    to run on every request and preserves later edits made through ADA.
    """
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
        ingredients = [line.strip()[2:].strip() for line in ingredient_block.group(1).splitlines() if line.strip().startswith("-")]
        if ingredients:
            conn.execute("INSERT OR IGNORE INTO food_recipes(name,ingredients,steps,tags) VALUES (?,?,?,?)", (name.strip(), json.dumps(ingredients, ensure_ascii=False), body.strip(), "perfil_fede"))
    conn.commit()


def _shopping(conn, args):
    action = args.get("action", "list")
    if action == "add":
        cur = conn.execute("SELECT id FROM food_shopping WHERE lower(item)=lower(?) AND status='pending'", (args["item"],))
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE food_shopping SET quantity=COALESCE(?, quantity), unit=COALESCE(?, unit), updated_at=CURRENT_TIMESTAMP WHERE id=?", (args.get("quantity"), args.get("unit"), row[0]))
            item_id = row[0]
        else:
            item_id = conn.execute("INSERT INTO food_shopping(item,quantity,unit,category,priority) VALUES (?,?,?,?,?)", (args["item"], args.get("quantity"), args.get("unit"), args.get("category"), args.get("priority", "normal"))).lastrowid
        conn.commit()
        return {"ok": True, "action": "added", "id": item_id, "item": args["item"]}
    if action in {"check", "cancel", "remove"}:
        item = args.get("item", "").strip()
        row = conn.execute("SELECT id,item FROM food_shopping WHERE lower(item)=lower(?) ORDER BY id DESC LIMIT 1", (item,)).fetchone()
        if not row:
            return {"ok": False, "error": "item_not_found", "item": item}
        if action == "remove":
            conn.execute("DELETE FROM food_shopping WHERE id=?", (row[0],))
        else:
            conn.execute("UPDATE food_shopping SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", ("bought" if action == "check" else "cancelled", row[0]))
        conn.commit()
        return {"ok": True, "action": action, "item": row[1]}
    rows = conn.execute("SELECT id,item,quantity,unit,category,priority,status FROM food_shopping WHERE status=? ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END,id", ("pending",)).fetchall()
    return {"ok": True, "items": [dict(zip(("id","item","quantity","unit","category","priority","status"), row)) for row in rows]}


def _recipes(conn, args):
    action = args.get("action", "list")
    if action == "save":
        name = args["name"].strip()
        ingredients = [x.strip() for x in re.split(r"[,;\n]", args.get("ingredients", "")) if x.strip()]
        conn.execute("INSERT INTO food_recipes(name,ingredients,steps,servings,tags) VALUES (?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET ingredients=excluded.ingredients,steps=excluded.steps,servings=excluded.servings,tags=excluded.tags,updated_at=CURRENT_TIMESTAMP", (name, json.dumps(ingredients, ensure_ascii=False), args.get("steps", ""), args.get("servings"), args.get("tags", "")))
        conn.commit()
        return {"ok": True, "action": "saved", "name": name, "ingredients": ingredients}
    rows = conn.execute("SELECT name,ingredients,steps,servings,tags FROM food_recipes ORDER BY name").fetchall()
    recipes = [{"name": r[0], "ingredients": json.loads(r[1]), "steps": r[2], "servings": r[3], "tags": r[4]} for r in rows]
    if action == "get":
        wanted = args.get("name", "").lower()
        recipes = [r for r in recipes if r["name"].lower() == wanted or wanted in r["name"].lower()]
    if action == "suggest":
        available = {x.strip().lower() for x in args.get("available", "").split(",") if x.strip()}
        recipes.sort(key=lambda r: sum(any(x in a or a in x for a in available) for x in r["ingredients"]), reverse=True)
    return {"ok": True, "recipes": recipes}


def run(args):
    conn = _db(args)
    try:
        _ensure(conn)
        _seed_profile(conn, args.get("config", {}).get("food_profile"))
        if args.get("action") == "recipe_to_shopping":
            recipe = _recipes(conn, {"action": "get", "name": args.get("name", "")}).get("recipes", [])
            if not recipe:
                return {"ok": False, "error": "recipe_not_found"}
            added = [_shopping(conn, {"action": "add", "item": ingredient}) for ingredient in recipe[0]["ingredients"]]
            return {"ok": True, "action": "recipe_to_shopping", "name": recipe[0]["name"], "added": len(added)}
        return _shopping(conn, args) if args.get("domain") == "shopping" else _recipes(conn, args)
    finally:
        conn.close()
