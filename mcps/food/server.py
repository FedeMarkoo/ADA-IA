"""Food & Shopping MCP Server."""

import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.food.shopping import ShoppingManager
from mcps.food.recipes import RecipeManager
from mcps.food.inventory import InventoryManager


def get_db(db_path: str = "memory.db") -> sqlite3.Connection:
    conn = sqlite3.connect(str(Path(db_path).expanduser()))
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
    CREATE TABLE IF NOT EXISTS food_inventory (
      id INTEGER PRIMARY KEY, item TEXT UNIQUE NOT NULL, quantity REAL NOT NULL DEFAULT 0,
      unit TEXT, minimum REAL NOT NULL DEFAULT 0, category TEXT, expires_at TEXT,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS food_budgets (
      period TEXT PRIMARY KEY, amount REAL NOT NULL, spent REAL NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT 'ARS', notes TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS food_meal_plan (
      id INTEGER PRIMARY KEY, plan_date TEXT NOT NULL, meal TEXT NOT NULL,
      recipe_name TEXT, servings INTEGER, estimated_cost REAL, notes TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(plan_date, meal)
    );
    """)
    conn.commit()
    return conn


def create_food_server(db_path: str = "memory.db") -> StdioMCPServer:
    server = StdioMCPServer("food", "1.0.0")

    def shopping_handler(args: Dict[str, Any]) -> Dict[str, Any]:
        with get_db(args.get("db_path", db_path)) as conn:
            return ShoppingManager.handle(conn, args)

    def recipes_handler(args: Dict[str, Any]) -> Dict[str, Any]:
        with get_db(args.get("db_path", db_path)) as conn:
            return RecipeManager.handle(conn, args)

    def inventory_handler(args: Dict[str, Any]) -> Dict[str, Any]:
        with get_db(args.get("db_path", db_path)) as conn:
            return InventoryManager.handle(conn, args)

    server.register_tool(
        name="food.shopping",
        description="Gestiona la lista de compras del supermercado (agregar, listar, marcar como comprado, eliminar).",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "complete", "remove", "clear_completed"], "default": "list"},
                "item": {"type": "string", "description": "Nombre del producto"},
                "quantity": {"type": "string", "description": "Cantidad"},
                "unit": {"type": "string", "description": "Unidad de medida (kg, gr, lts, un)"},
                "category": {"type": "string", "description": "Categoría (Verdulería, Carnicería, Almacén)"},
            },
        },
        handler=shopping_handler,
        risk_level="safe",
    )

    server.register_tool(
        name="food.recipes",
        description="Consulta y administra el recetario personal de comidas e ingredientes.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "get", "add", "delete"], "default": "list"},
                "name": {"type": "string", "description": "Nombre de la receta"},
                "ingredients": {"type": "array", "items": {"type": "string"}, "description": "Lista de ingredientes"},
            },
        },
        handler=recipes_handler,
        risk_level="safe",
    )

    server.register_tool(
        name="food.inventory",
        description="Supervisa el stock de alimentos en la alacena y alerta sobre faltantes (low_stock).",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "set", "low_stock", "delete"], "default": "list"},
                "item": {"type": "string", "description": "Nombre del alimento"},
                "quantity": {"type": "number", "description": "Cantidad disponible"},
                "minimum": {"type": "number", "description": "Stock mínimo de alerta"},
            },
        },
        handler=inventory_handler,
        risk_level="safe",
    )

    return server


if __name__ == "__main__":
    srv = create_food_server()
    srv.run()
