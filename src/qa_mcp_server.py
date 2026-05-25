"""
MCP-Based ETL QA Validation Server
====================================
Exposes SQL Server QA validation tools to Claude via MCP protocol.
Claude can autonomously run reconciliation, null checks, duplicate
checks, and generate discrepancy reports against SQL Server.

Author : Satish Panchumarthy
GitHub : github.com/panchumarthy
"""

import json
import sys
import logging
from datetime import datetime
from typing import Any

import pyodbc
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger(__name__)

# ── MCP Server ────────────────────────────────────────────────────────────────
server = Server("etl-qa-validator")


# ── DB Connection ─────────────────────────────────────────────────────────────
def get_connection(connection_string: str) -> pyodbc.Connection:
    """Return a pyodbc connection. Raises on failure."""
    return pyodbc.connect(connection_string, timeout=10)


def execute_query(connection_string: str, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT and return rows as list-of-dicts."""
    conn = get_connection(connection_string)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def scalar(connection_string: str, sql: str, params: tuple = ()) -> Any:
    """Execute a scalar query and return the single value."""
    rows = execute_query(connection_string, sql, params)
    if rows:
        return list(rows[0].values())[0]
    return None


# ── Tool: List Tables ─────────────────────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_tables",
            description=(
                "List all user tables in a SQL Server database. "
                "Use this first to discover what tables are available."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {
                        "type": "string",
                        "description": (
                            "pyodbc connection string. Example: "
                            "'DRIVER={ODBC Driver 17 for SQL Server};"
                            "SERVER=localhost;DATABASE=ETL_QA_Demo;Trusted_Connection=yes'"
                        )
                    }
                },
                "required": ["connection_string"]
            }
        ),
        Tool(
            name="get_table_schema",
            description="Get column names, data types, and nullability for a table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "table_name": {"type": "string", "description": "Table name (no schema prefix needed)"}
                },
                "required": ["connection_string", "table_name"]
            }
        ),
        Tool(
            name="row_count_check",
            description=(
                "Compare row counts between source and target tables. "
                "Returns counts and flags a PASS/FAIL with the difference."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "source_table": {"type": "string"},
                    "target_table": {"type": "string"},
                    "filter_clause": {
                        "type": "string",
                        "description": "Optional WHERE clause applied to both tables, e.g. \"load_date = '2026-05-21'\""
                    }
                },
                "required": ["connection_string", "source_table", "target_table"]
            }
        ),
        Tool(
            name="null_check",
            description=(
                "Check for NULL values in one or more columns of a table. "
                "Returns null counts per column and flags columns that exceed a threshold."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "table_name": {"type": "string"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of column names to check. Pass empty list [] to check ALL columns."
                    },
                    "null_threshold_pct": {
                        "type": "number",
                        "description": "Flag columns where null% exceeds this value. Default 0 (any null = FAIL).",
                        "default": 0
                    }
                },
                "required": ["connection_string", "table_name", "columns"]
            }
        ),
        Tool(
            name="duplicate_check",
            description=(
                "Find duplicate records in a table based on a key column or set of columns. "
                "Returns duplicate groups with counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "table_name": {"type": "string"},
                    "key_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns that together form the unique key."
                    }
                },
                "required": ["connection_string", "table_name", "key_columns"]
            }
        ),
        Tool(
            name="source_target_reconciliation",
            description=(
                "Perform a full source-to-target reconciliation using a LEFT ANTI JOIN. "
                "Identifies records present in source but missing from target. "
                "This is the core ETL validation check."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "source_table": {"type": "string"},
                    "target_table": {"type": "string"},
                    "join_key": {
                        "type": "string",
                        "description": "Column name used to match source and target rows."
                    },
                    "max_rows_returned": {
                        "type": "integer",
                        "description": "Max missing rows to return (default 50).",
                        "default": 50
                    }
                },
                "required": ["connection_string", "source_table", "target_table", "join_key"]
            }
        ),
        Tool(
            name="data_type_validation",
            description=(
                "Validate that column values conform to expected formats. "
                "Checks dates, numerics, and string lengths."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "table_name": {"type": "string"},
                    "validations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "check_type": {
                                    "type": "string",
                                    "enum": ["is_numeric", "is_date", "max_length", "min_value", "max_value"]
                                },
                                "threshold": {"type": "string", "description": "Value for max_length / min_value / max_value checks"}
                            }
                        },
                        "description": "List of column validation rules."
                    }
                },
                "required": ["connection_string", "table_name", "validations"]
            }
        ),
        Tool(
            name="referential_integrity_check",
            description=(
                "Check that all foreign key values in a child table exist in the parent table. "
                "Catches orphaned records that violate referential integrity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "child_table": {"type": "string"},
                    "child_column": {"type": "string"},
                    "parent_table": {"type": "string"},
                    "parent_column": {"type": "string"}
                },
                "required": ["connection_string", "child_table", "child_column", "parent_table", "parent_column"]
            }
        ),
        Tool(
            name="generate_qa_report",
            description=(
                "Run a full QA validation suite (row count + null + duplicate + reconciliation) "
                "on a source/target table pair and return a structured JSON report. "
                "Use this for end-to-end pipeline validation in one call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {"type": "string"},
                    "source_table": {"type": "string"},
                    "target_table": {"type": "string"},
                    "join_key": {"type": "string"},
                    "key_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to use for duplicate check."
                    }
                },
                "required": ["connection_string", "source_table", "target_table", "join_key", "key_columns"]
            }
        ),
    ]


# ── Tool Implementations ──────────────────────────────────────────────────────
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments)
    except Exception as e:
        log.exception(f"Tool '{name}' failed")
        result = {"status": "ERROR", "error": str(e)}
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


async def _dispatch(name: str, args: dict) -> dict:
    conn = args["connection_string"]

    if name == "list_tables":
        rows = execute_query(conn, """
            SELECT TABLE_SCHEMA, TABLE_NAME,
                   (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
                    WHERE c.TABLE_NAME = t.TABLE_NAME
                      AND c.TABLE_SCHEMA = t.TABLE_SCHEMA) AS column_count
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        return {"tables": rows, "total": len(rows)}

    elif name == "get_table_schema":
        table = args["table_name"]
        rows = execute_query(conn, """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                   CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """, (table,))
        return {"table": table, "columns": rows, "column_count": len(rows)}

    elif name == "row_count_check":
        src = args["source_table"]
        tgt = args["target_table"]
        flt = args.get("filter_clause", "")
        where = f" WHERE {flt}" if flt else ""

        src_count = scalar(conn, f"SELECT COUNT(*) FROM {src}{where}")
        tgt_count = scalar(conn, f"SELECT COUNT(*) FROM {tgt}{where}")
        diff = src_count - tgt_count
        status = "PASS" if diff == 0 else "FAIL"

        return {
            "check": "row_count",
            "status": status,
            "source_table": src,
            "target_table": tgt,
            "source_count": src_count,
            "target_count": tgt_count,
            "difference": diff,
            "filter": flt or "none",
            "message": (
                f"✅ Counts match: {src_count:,} rows" if status == "PASS"
                else f"❌ {abs(diff):,} records {'missing from target' if diff > 0 else 'extra in target'}"
            )
        }

    elif name == "null_check":
        table = args["table_name"]
        cols = args.get("columns", [])
        threshold = args.get("null_threshold_pct", 0)

        # If no columns specified, get all
        if not cols:
            schema_rows = execute_query(conn, """
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION
            """, (table,))
            cols = [r["COLUMN_NAME"] for r in schema_rows]

        total = scalar(conn, f"SELECT COUNT(*) FROM {table}")
        results = []
        for col in cols:
            null_count = scalar(conn, f"SELECT COUNT(*) FROM {table} WHERE [{col}] IS NULL")
            null_pct = round((null_count / total * 100), 2) if total > 0 else 0
            status = "FAIL" if null_pct > threshold else "PASS"
            results.append({
                "column": col,
                "null_count": null_count,
                "null_pct": null_pct,
                "status": status
            })

        failed = [r for r in results if r["status"] == "FAIL"]
        return {
            "check": "null_check",
            "table": table,
            "total_rows": total,
            "threshold_pct": threshold,
            "overall_status": "FAIL" if failed else "PASS",
            "failed_columns": len(failed),
            "results": results
        }

    elif name == "duplicate_check":
        table = args["table_name"]
        keys = args["key_columns"]
        key_str = ", ".join(f"[{k}]" for k in keys)

        dupes = execute_query(conn, f"""
            SELECT {key_str}, COUNT(*) AS duplicate_count
            FROM {table}
            GROUP BY {key_str}
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
        """)
        return {
            "check": "duplicate_check",
            "table": table,
            "key_columns": keys,
            "status": "FAIL" if dupes else "PASS",
            "duplicate_groups": len(dupes),
            "total_duplicate_rows": sum(d["duplicate_count"] for d in dupes),
            "duplicates": dupes[:20],
            "message": (
                "✅ No duplicates found" if not dupes
                else f"❌ {len(dupes)} duplicate key groups found"
            )
        }

    elif name == "source_target_reconciliation":
        src = args["source_table"]
        tgt = args["target_table"]
        key = args["join_key"]
        limit = args.get("max_rows_returned", 50)

        missing = execute_query(conn, f"""
            SELECT TOP {limit} s.*
            FROM {src} s
            LEFT JOIN {tgt} t ON s.[{key}] = t.[{key}]
            WHERE t.[{key}] IS NULL
        """)
        missing_count = scalar(conn, f"""
            SELECT COUNT(*)
            FROM {src} s
            LEFT JOIN {tgt} t ON s.[{key}] = t.[{key}]
            WHERE t.[{key}] IS NULL
        """)
        return {
            "check": "source_target_reconciliation",
            "source_table": src,
            "target_table": tgt,
            "join_key": key,
            "status": "FAIL" if missing_count > 0 else "PASS",
            "total_missing": missing_count,
            "sample_missing_records": missing,
            "message": (
                "✅ All source records found in target" if missing_count == 0
                else f"❌ {missing_count:,} records in source are MISSING from target"
            )
        }

    elif name == "data_type_validation":
        table = args["table_name"]
        validations = args["validations"]
        results = []

        for v in validations:
            col = v["column"]
            check = v["check_type"]
            threshold = v.get("threshold")

            if check == "is_numeric":
                bad = scalar(conn, f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE TRY_CAST([{col}] AS FLOAT) IS NULL
                      AND [{col}] IS NOT NULL
                """)
                results.append({"column": col, "check": check,
                                 "invalid_count": bad,
                                 "status": "PASS" if bad == 0 else "FAIL"})

            elif check == "is_date":
                bad = scalar(conn, f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE TRY_CAST([{col}] AS DATE) IS NULL
                      AND [{col}] IS NOT NULL
                """)
                results.append({"column": col, "check": check,
                                 "invalid_count": bad,
                                 "status": "PASS" if bad == 0 else "FAIL"})

            elif check == "max_length":
                bad = scalar(conn, f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE LEN(CAST([{col}] AS VARCHAR(MAX))) > {threshold}
                """)
                results.append({"column": col, "check": check,
                                 "max_length": threshold, "violations": bad,
                                 "status": "PASS" if bad == 0 else "FAIL"})

            elif check in ("min_value", "max_value"):
                op = "<" if check == "min_value" else ">"
                bad = scalar(conn, f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE TRY_CAST([{col}] AS FLOAT) {op} {threshold}
                """)
                results.append({"column": col, "check": check,
                                 "threshold": threshold, "violations": bad,
                                 "status": "PASS" if bad == 0 else "FAIL"})

        failed = [r for r in results if r["status"] == "FAIL"]
        return {
            "check": "data_type_validation",
            "table": table,
            "overall_status": "FAIL" if failed else "PASS",
            "results": results
        }

    elif name == "referential_integrity_check":
        child_tbl = args["child_table"]
        child_col = args["child_column"]
        parent_tbl = args["parent_table"]
        parent_col = args["parent_column"]

        orphans = execute_query(conn, f"""
            SELECT TOP 50 c.[{child_col}]
            FROM {child_tbl} c
            LEFT JOIN {parent_tbl} p ON c.[{child_col}] = p.[{parent_col}]
            WHERE p.[{parent_col}] IS NULL
              AND c.[{child_col}] IS NOT NULL
        """)
        orphan_count = scalar(conn, f"""
            SELECT COUNT(*)
            FROM {child_tbl} c
            LEFT JOIN {parent_tbl} p ON c.[{child_col}] = p.[{parent_col}]
            WHERE p.[{parent_col}] IS NULL
              AND c.[{child_col}] IS NOT NULL
        """)
        return {
            "check": "referential_integrity",
            "child_table": child_tbl,
            "child_column": child_col,
            "parent_table": parent_tbl,
            "parent_column": parent_col,
            "status": "FAIL" if orphan_count > 0 else "PASS",
            "orphan_count": orphan_count,
            "sample_orphans": orphans,
            "message": (
                "✅ All foreign keys are valid" if orphan_count == 0
                else f"❌ {orphan_count:,} orphaned records in {child_tbl}"
            )
        }

    elif name == "generate_qa_report":
        src = args["source_table"]
        tgt = args["target_table"]
        key = args["join_key"]
        key_cols = args["key_columns"]

        timestamp = datetime.now().isoformat()
        checks = {}

        # 1. Row count
        src_count = scalar(conn, f"SELECT COUNT(*) FROM {src}")
        tgt_count = scalar(conn, f"SELECT COUNT(*) FROM {tgt}")
        diff = src_count - tgt_count
        checks["row_count"] = {
            "status": "PASS" if diff == 0 else "FAIL",
            "source": src_count,
            "target": tgt_count,
            "difference": diff
        }

        # 2. Reconciliation
        missing_count = scalar(conn, f"""
            SELECT COUNT(*) FROM {src} s
            LEFT JOIN {tgt} t ON s.[{key}] = t.[{key}]
            WHERE t.[{key}] IS NULL
        """)
        checks["reconciliation"] = {
            "status": "PASS" if missing_count == 0 else "FAIL",
            "missing_records": missing_count
        }

        # 3. Duplicates in target
        key_str = ", ".join(f"[{k}]" for k in key_cols)
        dupe_groups = scalar(conn, f"""
            SELECT COUNT(*) FROM (
                SELECT {key_str}, COUNT(*) AS cnt
                FROM {tgt}
                GROUP BY {key_str}
                HAVING COUNT(*) > 1
            ) d
        """)
        checks["duplicates_in_target"] = {
            "status": "PASS" if dupe_groups == 0 else "FAIL",
            "duplicate_groups": dupe_groups
        }

        # 4. Null check on key column in target
        null_count = scalar(conn, f"SELECT COUNT(*) FROM {tgt} WHERE [{key}] IS NULL")
        checks["null_key_check"] = {
            "status": "PASS" if null_count == 0 else "FAIL",
            "null_key_count": null_count
        }

        all_pass = all(c["status"] == "PASS" for c in checks.values())
        failed_checks = [k for k, v in checks.items() if v["status"] == "FAIL"]

        return {
            "report": "ETL QA Validation Report",
            "generated_at": timestamp,
            "source_table": src,
            "target_table": tgt,
            "overall_status": "✅ ALL CHECKS PASSED" if all_pass else f"❌ FAILED: {', '.join(failed_checks)}",
            "checks": checks,
            "summary": (
                f"All {len(checks)} checks passed. Pipeline is healthy."
                if all_pass
                else f"{len(failed_checks)} of {len(checks)} checks failed. Investigation required."
            )
        }

    else:
        return {"error": f"Unknown tool: {name}"}


# ── Entry Point ───────────────────────────────────────────────────────────────
async def main():
    log.info("ETL QA MCP Server starting...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
