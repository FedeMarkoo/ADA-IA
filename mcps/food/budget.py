"""Food budget management and expense tracking."""

import sqlite3
from typing import Any, Dict, List, Optional


class BudgetManager:
    """Manages food budgets and expense limits per period."""

    @staticmethod
    def handle(conn: sqlite3.Connection, args: Dict[str, Any]) -> Dict[str, Any]:
        action = args.get("action", "list")
        if action == "set":
            period = args.get("period", "").strip()
            amount = float(args.get("amount", 0))
            currency = args.get("currency", "ARS")
            notes = args.get("notes", "")
            conn.execute(
                """INSERT INTO food_budgets(period, amount, spent, currency, notes, updated_at)
                   VALUES (?, ?, 0, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(period) DO UPDATE SET
                     amount = excluded.amount,
                     currency = excluded.currency,
                     notes = excluded.notes,
                     updated_at = CURRENT_TIMESTAMP""",
                (period, amount, currency, notes),
            )
            conn.commit()
            return {
                "ok": True,
                "action": "set",
                "budget": {"period": period, "amount": amount, "spent": 0.0, "currency": currency, "notes": notes},
            }

        elif action in {"spend", "add_expense"}:
            period = args.get("period", "").strip()
            amount = float(args.get("amount", 0))
            cur = conn.execute("SELECT amount, spent, currency FROM food_budgets WHERE period=?", (period,))
            row = cur.fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO food_budgets(period, amount, spent, currency) VALUES (?, ?, ?, ?)",
                    (period, amount, amount, "ARS"),
                )
                new_spent = amount
            else:
                new_spent = row[1] + amount
                conn.execute("UPDATE food_budgets SET spent=?, updated_at=CURRENT_TIMESTAMP WHERE period=?", (new_spent, period))
            conn.commit()
            return {"ok": True, "action": "spend", "period": period, "spent": new_spent}

        rows = conn.execute("SELECT period, amount, spent, currency, notes FROM food_budgets ORDER BY period DESC").fetchall()
        budgets = [
            {"period": r[0], "amount": r[1], "spent": r[2], "currency": r[3], "notes": r[4]}
            for r in rows
        ]
        return {"ok": True, "action": "list", "total": len(budgets), "budgets": budgets}
