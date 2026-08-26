"""Shopping list manager with categorization and status tracking."""

import sqlite3
from typing import Any, Dict


class ShoppingManager:
    """Manages grocery shopping list in SQLite."""

    @staticmethod
    def handle(conn: sqlite3.Connection, args: Dict[str, Any]) -> Dict[str, Any]:
        action = args.get("action", "list")
        if action == "add":
            item = args.get("item", "").strip()
            if not item:
                return {"error": "item_required"}
            cur = conn.execute(
                "SELECT id FROM food_shopping WHERE lower(item)=lower(?) AND status='pending'", (item,)
            )
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE food_shopping SET quantity=COALESCE(?, quantity), unit=COALESCE(?, unit), updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (args.get("quantity"), args.get("unit"), row[0]),
                )
                item_id = row[0]
            else:
                cur = conn.execute(
                    "INSERT INTO food_shopping(item,quantity,unit,category,priority) VALUES (?,?,?,?,?)",
                    (
                        item,
                        args.get("quantity"),
                        args.get("unit"),
                        args.get("category"),
                        args.get("priority", "normal"),
                    ),
                )
                item_id = cur.lastrowid
            conn.commit()
            return {"ok": True, "action": "add", "id": item_id, "item": item}

        elif action in {"complete", "check", "comprar"}:
            item = args.get("item")
            item_id = args.get("id")
            if item_id:
                conn.execute(
                    "UPDATE food_shopping SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (item_id,),
                )
            elif item:
                conn.execute(
                    "UPDATE food_shopping SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE lower(item)=lower(?) AND status='pending'",
                    (item,),
                )
            conn.commit()
            return {"ok": True, "action": "complete", "item": item or item_id}

        elif action == "remove":
            item = args.get("item")
            item_id = args.get("id")
            if item_id:
                conn.execute("DELETE FROM food_shopping WHERE id=?", (item_id,))
            elif item:
                conn.execute("DELETE FROM food_shopping WHERE lower(item)=lower(?)", (item,))
            conn.commit()
            return {"ok": True, "action": "remove", "item": item or item_id}

        elif action == "clear_completed":
            cur = conn.execute("DELETE FROM food_shopping WHERE status='completed'")
            conn.commit()
            return {"ok": True, "action": "clear_completed", "deleted": cur.rowcount}

        status_filter = args.get("status", "pending")
        query = "SELECT id, item, quantity, unit, category, priority, status FROM food_shopping"
        params = []
        if status_filter != "all":
            query += " WHERE status=?"
            params.append(status_filter)
        query += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, category, item"

        rows = conn.execute(query, params).fetchall()
        items = [
            {
                "id": r[0],
                "item": r[1],
                "quantity": r[2],
                "unit": r[3],
                "category": r[4],
                "priority": r[5],
                "status": r[6],
            }
            for r in rows
        ]
        return {"ok": True, "action": "list", "total": len(items), "items": items}
