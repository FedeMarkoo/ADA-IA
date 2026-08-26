"""Pantry inventory and low-stock management."""

import sqlite3
from typing import Any, Dict


class InventoryManager:
    """Manages pantry items, quantities, minimum stock, and usage."""

    @staticmethod
    def handle(conn: sqlite3.Connection, args: Dict[str, Any]) -> Dict[str, Any]:
        action = args.get("action", "list")
        if action in {"add", "set"}:
            item = args.get("item", "").strip()
            if not item:
                return {"error": "item_required"}
            qty = float(args.get("quantity", 0))
            min_stock = float(args.get("minimum", 0))
            unit = args.get("unit")
            category = args.get("category")
            expires_at = args.get("expires_at")

            cur = conn.execute("SELECT quantity FROM food_inventory WHERE lower(item)=lower(?)", (item,))
            row = cur.fetchone()
            if row and action == "add":
                new_qty = row[0] + qty
                conn.execute(
                    "UPDATE food_inventory SET quantity=?, minimum=COALESCE(?, minimum), updated_at=CURRENT_TIMESTAMP WHERE lower(item)=lower(?)",
                    (new_qty, min_stock or None, item),
                )
                conn.commit()
                return {"ok": True, "action": "add", "item": item, "quantity": new_qty}
            else:
                conn.execute(
                    """INSERT INTO food_inventory(item, quantity, unit, minimum, category, expires_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(item) DO UPDATE SET
                         quantity = excluded.quantity,
                         unit = COALESCE(excluded.unit, food_inventory.unit),
                         minimum = COALESCE(excluded.minimum, food_inventory.minimum),
                         category = COALESCE(excluded.category, food_inventory.category),
                         expires_at = COALESCE(excluded.expires_at, food_inventory.expires_at),
                         updated_at = CURRENT_TIMESTAMP""",
                    (item, qty, unit, min_stock, category, expires_at),
                )
                conn.commit()
                return {"ok": True, "action": action, "item": item, "quantity": qty}

        elif action == "use":
            item = args.get("item", "").strip()
            qty = float(args.get("quantity", 1))
            cur = conn.execute("SELECT quantity FROM food_inventory WHERE lower(item)=lower(?)", (item,))
            row = cur.fetchone()
            if not row:
                return {"error": "item_not_found", "item": item}
            new_qty = max(0.0, row[0] - qty)
            conn.execute(
                "UPDATE food_inventory SET quantity=?, updated_at=CURRENT_TIMESTAMP WHERE lower(item)=lower(?)",
                (new_qty, item),
            )
            conn.commit()
            return {"ok": True, "action": "use", "item": item, "quantity": new_qty}

        elif action == "low_stock":
            rows = conn.execute(
                "SELECT id, item, quantity, unit, minimum, category FROM food_inventory WHERE quantity <= minimum ORDER BY item"
            ).fetchall()
            items = [
                {"id": r[0], "item": r[1], "quantity": r[2], "unit": r[3], "minimum": r[4], "category": r[5]}
                for r in rows
            ]
            return {"ok": True, "action": "low_stock", "total": len(items), "items": items}

        elif action == "delete":
            item = args.get("item", "").strip()
            conn.execute("DELETE FROM food_inventory WHERE lower(item)=lower(?)", (item,))
            conn.commit()
            return {"ok": True, "action": "delete", "item": item}

        rows = conn.execute(
            "SELECT id, item, quantity, unit, minimum, category, expires_at FROM food_inventory ORDER BY category, item"
        ).fetchall()
        items = [
            {
                "id": r[0],
                "item": r[1],
                "quantity": r[2],
                "unit": r[3],
                "minimum": r[4],
                "category": r[5],
                "expires_at": r[6],
            }
            for r in rows
        ]
        return {"ok": True, "action": "list", "total": len(items), "items": items}
