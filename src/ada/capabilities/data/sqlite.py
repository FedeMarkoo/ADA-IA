"""Read-only SQLite tool for ADA's local knowledge and photo catalogues."""

import os
import sqlite3
from pathlib import Path


def _open_readonly(path):
    database = Path(os.path.expanduser(str(path))).resolve()
    if not database.exists():
        raise FileNotFoundError(f"database not found: {database}")
    uri = f"file:{database}?mode=ro"
    return sqlite3.connect(uri, uri=True), database


def run(args):
    action = str(args.get("action", "status")).lower()
    conn, database = _open_readonly(args.get("db"))
    try:
        if action in {"status", "summary", "resumen", "estado"}:
            summary = conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(total),0), COALESCE(SUM(buenas),0),
                       COALESCE(SUM(rechazadas),0), COALESCE(SUM(eliminadas),0),
                       COALESCE(SUM(movidas),0), COALESCE(SUM(jpg),0),
                       COALESCE(SUM(jpg_asociados),0), COALESCE(SUM(videos),0),
                       COALESCE(SUM(editables),0), COALESCE(SUM(otros),0)
                FROM carpetas
            """
            ).fetchone()
            states = conn.execute(
                "SELECT estado, COUNT(*) FROM carpetas GROUP BY estado ORDER BY COUNT(*) DESC"
            ).fetchall()
            formats = conn.execute(
                'SELECT COALESCE(formato, "Sin formato"), COUNT(*) FROM colecciones GROUP BY formato ORDER BY COUNT(*) DESC'
            ).fetchall()
            return {
                "ok": True,
                "tool": "sqlite",
                "action": "status",
                "db": str(database),
                "summary": {
                    "carpetas": summary[0],
                    "total": summary[1],
                    "buenas": summary[2],
                    "rechazadas": summary[3],
                    "eliminadas": summary[4],
                    "movidas": summary[5],
                    "jpg": summary[6],
                    "jpg_asociados": summary[7],
                    "videos": summary[8],
                    "editables": summary[9],
                    "otros": summary[10],
                },
                "estados": [{"estado": row[0], "cantidad": row[1]} for row in states],
                "formatos": [{"formato": row[0], "colecciones": row[1]} for row in formats],
            }
        if action in {"report", "reporte", "photo_report", "reporte_fotos"}:
            summary = conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(total),0), COALESCE(SUM(buenas),0),
                       COALESCE(SUM(rechazadas),0), COALESCE(SUM(eliminadas),0),
                       COALESCE(SUM(movidas),0), COALESCE(SUM(jpg),0),
                       COALESCE(SUM(jpg_asociados),0), COALESCE(SUM(videos),0),
                       COALESCE(SUM(editables),0), COALESCE(SUM(otros),0)
                FROM carpetas
            """
            ).fetchone()
            rows = conn.execute(
                """
                SELECT c.formato, c.contexto, c.fecha, c.contenido, cc.ruta,
                       COALESCE(f.total, 0), COALESCE(f.buenas, 0),
                       COALESCE(f.rechazadas, 0), COALESCE(f.eliminadas, 0),
                       COALESCE(f.jpg, 0), COALESCE(f.jpg_asociados, 0),
                       COALESCE(f.videos, 0), COALESCE(f.editables, 0), COALESCE(f.otros, 0)
                FROM colecciones c
                JOIN coleccion_carpetas cc ON cc.coleccion_id=c.id
                LEFT JOIN carpetas f ON f.ruta=cc.ruta
                ORDER BY c.formato, c.contexto, c.fecha, c.contenido, cc.ruta
            """
            ).fetchall()
            formats = {}
            collections = []
            for row in rows:
                item = {
                    "formato": row[0] or "Sin formato",
                    "contexto": row[1],
                    "fecha": row[2],
                    "contenido": row[3],
                    "ruta": row[4],
                    "total": row[5],
                    "buenas": row[6],
                    "rechazadas": row[7],
                    "eliminadas": row[8],
                    "jpg": row[9],
                    "jpg_asociados": row[10],
                    "videos": row[11],
                    "editables": row[12],
                    "otros": row[13],
                }
                collections.append(item)
                group = formats.setdefault(
                    item["formato"],
                    {"colecciones": 0, "carpetas": 0, "total": 0, "buenas": 0, "rechazadas": 0, "eliminadas": 0},
                )
                group["colecciones"] += 1
                group["carpetas"] += 1
                for key in ("total", "buenas", "rechazadas", "eliminadas"):
                    group[key] += item[key]
                for key in ("jpg", "jpg_asociados", "videos", "editables", "otros"):
                    group[key] = group.get(key, 0) + item[key]
            unassigned = conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(f.total),0), COALESCE(SUM(f.buenas),0),
                       COALESCE(SUM(f.rechazadas),0), COALESCE(SUM(f.eliminadas),0)
                FROM carpetas f
                LEFT JOIN coleccion_carpetas cc ON cc.ruta=f.ruta
                WHERE cc.ruta IS NULL
            """
            ).fetchone()
            if unassigned[0]:
                formats["Sin colección"] = {
                    "colecciones": 0,
                    "carpetas": unassigned[0],
                    "total": unassigned[1],
                    "buenas": unassigned[2],
                    "rechazadas": unassigned[3],
                    "eliminadas": unassigned[4],
                    "jpg": 0,
                    "jpg_asociados": 0,
                    "videos": 0,
                    "editables": 0,
                    "otros": 0,
                }
            return {
                "ok": True,
                "tool": "sqlite",
                "action": "report",
                "db": str(database),
                "summary": {
                    "carpetas": summary[0],
                    "total": summary[1],
                    "buenas": summary[2],
                    "rechazadas": summary[3],
                    "eliminadas": summary[4],
                    "movidas": summary[5],
                    "jpg": summary[6],
                    "jpg_asociados": summary[7],
                    "videos": summary[8],
                    "editables": summary[9],
                    "otros": summary[10],
                },
                "formatos": [{"formato": key, **value} for key, value in formats.items()],
                "collections": collections,
            }
        if action in {"structure", "estructura", "folders", "carpetas"}:
            rows = conn.execute(
                """
                SELECT c.formato, c.contexto, c.fecha, c.contenido, cc.ruta
                FROM colecciones c JOIN coleccion_carpetas cc ON cc.coleccion_id=c.id
                ORDER BY c.formato, c.contexto, c.fecha, c.contenido
            """
            ).fetchall()
            return {
                "ok": True,
                "tool": "sqlite",
                "action": "structure",
                "db": str(database),
                "count": len(rows),
                "collections": [
                    {"formato": row[0], "contexto": row[1], "fecha": row[2], "contenido": row[3], "ruta": row[4]}
                    for row in rows
                ],
            }
        return {"error": f"unsupported sqlite action: {action}", "tool": "sqlite"}
    finally:
        conn.close()
