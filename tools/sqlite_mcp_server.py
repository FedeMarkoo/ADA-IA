#!/usr/bin/env python3
"""
SQLite Model Context Protocol (MCP) Server for Antigravity.
Implements the standard MCP JSON-RPC 2.0 protocol over stdio to query and manage SQLite databases.
"""

import sys
import json
import sqlite3
import os
from pathlib import Path

DEFAULT_DB_PATH = os.environ.get("SQLITE_DEFAULT_DB", "data/ada.db")


def _resolve_db_path(db_path: str = None) -> str:
    """Resolve database path with fallback to default project database."""
    if db_path and db_path.strip():
        resolved = Path(db_path).resolve()
    else:
        resolved = Path(DEFAULT_DB_PATH).resolve()
    return str(resolved)


def _get_connection(db_path: str, readonly: bool = False) -> sqlite3.Connection:
    """Open SQLite connection with row factory."""
    if readonly:
        uri_path = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri_path, uri=True, timeout=10.0)
    else:
        conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# Tool Handlers
# =============================================================================

def handle_sqlite_read_query(args: dict) -> str:
    """Execute a SELECT query and return rows."""
    query = args.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query parameter is required"})

    db_path = _resolve_db_path(args.get("db_path"))
    if not Path(db_path).exists():
        return json.dumps({"error": f"Database file not found: {db_path}"})

    params = args.get("parameters", [])
    max_rows = args.get("max_rows", 100)

    try:
        conn = _get_connection(db_path, readonly=True)
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchmany(max_rows)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        results = [dict(row) for row in rows]
        total_fetched = len(results)
        conn.close()

        return json.dumps({
            "database": db_path,
            "columns": columns,
            "total_rows": total_fetched,
            "rows": results
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e), "query": query, "database": db_path})


def handle_sqlite_write_query(args: dict) -> str:
    """Execute INSERT, UPDATE, DELETE, or DDL statements."""
    query = args.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query parameter is required"})

    db_path = _resolve_db_path(args.get("db_path"))
    params = args.get("parameters", [])

    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = _get_connection(db_path, readonly=False)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        rows_affected = cursor.rowcount
        last_row_id = cursor.lastrowid
        conn.close()

        return json.dumps({
            "success": True,
            "database": db_path,
            "rows_affected": rows_affected,
            "last_insert_rowid": last_row_id
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "query": query, "database": db_path})


def handle_sqlite_list_tables(args: dict) -> str:
    """List all tables, views, and row counts in a database."""
    db_path = _resolve_db_path(args.get("db_path"))
    if not Path(db_path).exists():
        return json.dumps({"error": f"Database file not found: {db_path}"})

    try:
        conn = _get_connection(db_path, readonly=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        )
        tables = []
        for row in cursor.fetchall():
            t_name = row["name"]
            t_type = row["type"]
            count = 0
            if t_type == "table":
                try:
                    c2 = conn.cursor()
                    c2.execute(f"SELECT COUNT(*) FROM \"{t_name}\";")
                    count = c2.fetchone()[0]
                except Exception:
                    count = -1
            tables.append({
                "name": t_name,
                "type": t_type,
                "row_count": count
            })
        conn.close()

        return json.dumps({
            "database": db_path,
            "total_tables": len(tables),
            "tables": tables
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "database": db_path})


def handle_sqlite_describe_table(args: dict) -> str:
    """Show schema, columns, data types, and indexes of a table."""
    table_name = args.get("table_name", "").strip()
    if not table_name:
        return json.dumps({"error": "table_name parameter is required"})

    db_path = _resolve_db_path(args.get("db_path"))
    if not Path(db_path).exists():
        return json.dumps({"error": f"Database file not found: {db_path}"})

    try:
        conn = _get_connection(db_path, readonly=True)
        cursor = conn.cursor()

        # Columns
        cursor.execute(f"PRAGMA table_info(\"{table_name}\");")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": bool(row["notnull"]),
                "dflt_value": row["dflt_value"],
                "pk": bool(row["pk"])
            })

        # Foreign keys
        cursor.execute(f"PRAGMA foreign_key_list(\"{table_name}\");")
        foreign_keys = [dict(row) for row in cursor.fetchall()]

        # Indexes
        cursor.execute(f"PRAGMA index_list(\"{table_name}\");")
        indexes = [dict(row) for row in cursor.fetchall()]

        # DDL SQL
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        sql_row = cursor.fetchone()
        create_sql = sql_row["sql"] if sql_row else None

        conn.close()

        return json.dumps({
            "database": db_path,
            "table_name": table_name,
            "create_sql": create_sql,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "indexes": indexes
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "table_name": table_name, "database": db_path})


def handle_sqlite_explain_query(args: dict) -> str:
    """Run EXPLAIN QUERY PLAN on an SQL statement."""
    query = args.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query parameter is required"})

    db_path = _resolve_db_path(args.get("db_path"))
    if not Path(db_path).exists():
        return json.dumps({"error": f"Database file not found: {db_path}"})

    try:
        conn = _get_connection(db_path, readonly=True)
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN QUERY PLAN {query}")
        plan = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return json.dumps({
            "database": db_path,
            "query": query,
            "plan": plan
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "query": query, "database": db_path})


# =============================================================================
# Tool Definitions Metadata
# =============================================================================

TOOLS = [
    {
        "name": "sqlite_read_query",
        "description": "Execute a SELECT query against an SQLite database and return matching rows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SELECT SQL query to execute"},
                "db_path": {"type": "string", "description": "Path to the SQLite database file (default: data/ada.db or project DB)"},
                "parameters": {"type": "array", "description": "Optional parameterized query parameters list"},
                "max_rows": {"type": "integer", "description": "Maximum number of rows to return (default: 100)"}
            },
            "required": ["query"]
        },
        "handler": handle_sqlite_read_query
    },
    {
        "name": "sqlite_write_query",
        "description": "Execute INSERT, UPDATE, DELETE, or DDL queries (CREATE/ALTER/DROP) on an SQLite database with commit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL statement to execute (INSERT/UPDATE/DELETE/CREATE/etc.)"},
                "db_path": {"type": "string", "description": "Path to the SQLite database file"},
                "parameters": {"type": "array", "description": "Optional parameters list"}
            },
            "required": ["query"]
        },
        "handler": handle_sqlite_write_query
    },
    {
        "name": "sqlite_list_tables",
        "description": "List all tables and views in an SQLite database along with their current row counts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {"type": "string", "description": "Path to the SQLite database file"}
            }
        },
        "handler": handle_sqlite_list_tables
    },
    {
        "name": "sqlite_describe_table",
        "description": "Get detailed schema definition, column data types, primary keys, foreign keys, and indexes for a table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table to describe"},
                "db_path": {"type": "string", "description": "Path to the SQLite database file"}
            },
            "required": ["table_name"]
        },
        "handler": handle_sqlite_describe_table
    },
    {
        "name": "sqlite_explain_query",
        "description": "Explain the query execution plan (EXPLAIN QUERY PLAN) for query optimization and index analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The SQL query to analyze"},
                "db_path": {"type": "string", "description": "Path to the SQLite database file"}
            },
            "required": ["query"]
        },
        "handler": handle_sqlite_explain_query
    }
]

TOOL_MAP = {t["name"]: t for t in TOOLS}


# =============================================================================
# JSON-RPC 2.0 Protocol Loop
# =============================================================================

def send_response(response: dict):
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            req = json.loads(raw_line)
        except Exception as e:
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "antigravity-sqlite-mcp",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            })
        elif method == "notifications/initialized" or method == "initialized":
            pass
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            tool_list = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"]
                }
                for t in TOOLS
            ]
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tool_list
                }
            })
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in TOOL_MAP:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
                })
            else:
                try:
                    result_text = TOOL_MAP[tool_name]["handler"](tool_args)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result_text
                                }
                            ]
                        }
                    })
                except Exception as e:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "isError": True,
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Error executing {tool_name}: {e}"
                                }
                            ]
                        }
                    })
        else:
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                })


if __name__ == "__main__":
    main()
