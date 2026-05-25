# MCP-Based ETL QA Validation Tool

**Author:** Satish Panchumarthy  
**GitHub:** [github.com/panchumarthy](https://github.com/panchumarthy)  
**Stack:** Python · MCP (Model Context Protocol) · Claude AI · Microsoft SQL Server

---

## What This Is

An AI-powered ETL data quality validation agent built on Anthropic's
**Model Context Protocol (MCP)**. Instead of writing SQL validation scripts
manually, you describe what you want to validate in plain English — Claude
autonomously calls the right tools, queries SQL Server, analyzes results,
and returns a structured QA report.

```
You: "Validate today's securities pipeline run"
         ↓
   Claude Agent (Anthropic API)
         ↓  (MCP protocol)
   QA MCP Server (Python)
         ↓
   SQL Server (local)
         ↓
   Full QA Report: row counts, missing records,
   duplicates, nulls — all in one response
```

---

## QA Tools Exposed via MCP

| Tool | What It Does |
|---|---|
| `list_tables` | Discover available tables |
| `get_table_schema` | Inspect columns, types, nullability |
| `row_count_check` | Compare source vs target counts |
| `null_check` | Find NULL values across columns |
| `duplicate_check` | Find duplicate records by key |
| `source_target_reconciliation` | LEFT ANTI JOIN — find dropped records |
| `data_type_validation` | Validate numeric/date/length formats |
| `referential_integrity_check` | Find orphaned foreign key records |
| `generate_qa_report` | Full pipeline validation in one call |

---

## Setup

### Prerequisites

- Python 3.10+
- Microsoft SQL Server (local) with SSMS
- ODBC Driver 17 for SQL Server
- Anthropic API key

### Step 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Set up the demo database

Open **SQL Server Management Studio (SSMS)**, connect to your local instance,
open `scripts/setup_sqlserver.sql` and run it.

This creates the `ETL_QA_Demo` database with:
- `securities_source` — 50 trades (Broadridge-style data)
- `securities_target` — same data with **intentional defects**:
  - 3 records dropped (trade IDs 1005, 1010, 1015)
  - 1 duplicate record (trade ID 1001)
  - 1 NULL broker_code (trade 1003)
  - 1 wrong trade_amount (trade 1007)
- `orders_source` / `orders_target` — second pipeline with 2 dropped records
- `customers` — lookup table (with 1 orphaned FK in orders)

### Step 3 — Set your Anthropic API key

**Windows:**
```cmd
set ANTHROPIC_API_KEY=your-api-key-here
```

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### Step 4 — Update the connection string (if needed)

Edit `src/qa_agent.py` — find `DEFAULT_CONNECTION` near the top:

```python
DEFAULT_CONNECTION = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"          # ← change if your server name is different
    "DATABASE=ETL_QA_Demo;"
    "Trusted_Connection=yes"     # ← Windows auth; or use UID=sa;PWD=... for SQL auth
)
```

---

## Running the Agent

### Interactive mode (recommended for demo)

```bash
cd mcp-qa-tool
python src/qa_agent.py
```

Then type natural language queries:

```
> Validate today's pipeline run between securities_source and securities_target
> Check for NULL values in the securities_target table
> Find any duplicate trades in securities_target
> Run a full QA report on the securities pipeline
> Check referential integrity between orders_source and customers
> List all available tables
```

### Single query mode

```bash
python src/qa_agent.py --query "Run a full QA report on the securities pipeline"
```

---

## Example Output

```
> Validate today's pipeline run between securities_source and securities_target

🤖 Agent thinking...
────────────────────────────────────────────────────
🔧 Calling tool: generate_qa_report
   Result: ❌ FAILED: row_count, reconciliation, duplicates_in_target

## ETL QA Validation Report — securities pipeline

**Overall Status: ❌ PIPELINE FAILED**

| Check | Status | Detail |
|---|---|---|
| Row Count | ❌ FAIL | Source: 50 · Target: 48 · Missing: 2 |
| Reconciliation | ❌ FAIL | 3 records in source missing from target |
| Duplicates in Target | ❌ FAIL | 1 duplicate group found (trade_id 1001) |
| NULL Key Check | ✅ PASS | No NULL trade_ids |

**Issues Found:**
1. **Dropped Records**: Trades 1005, 1010, 1015 are in source but not in target
2. **Duplicate Load**: Trade 1001 was loaded twice into target
3. **Count Mismatch**: 2 net difference (3 dropped - 1 duplicate)

**Recommended Next Steps:**
- Investigate ETL filter logic for trades 1005/1010/1015
- Check for duplicate detection logic in the load process
- Review AUTOSYS job logs for any partial re-runs
```

---

## Architecture

```
mcp-qa-tool/
├── src/
│   ├── qa_mcp_server.py   # MCP server — exposes SQL tools to Claude
│   └── qa_agent.py        # Claude agent — orchestrates tool calls
├── scripts/
│   └── setup_sqlserver.sql  # Demo database with intentional defects
├── requirements.txt
└── README.md
```

**How MCP works here:**

1. `qa_agent.py` starts `qa_mcp_server.py` as a subprocess
2. They communicate over `stdio` using the MCP protocol
3. Claude receives the list of available tools
4. Claude decides which tools to call based on your query
5. Tool calls go through MCP → Python → pyodbc → SQL Server
6. Results return to Claude → Claude synthesizes the final report

---

## Interview Talking Points

> *"I built an MCP-based QA agent where Claude autonomously orchestrates
> multiple database validation checks — row counts, LEFT ANTI JOINs for
> dropped records, duplicate detection, and referential integrity — all
> triggered by a plain English query. The MCP server exposes each check as
> a discrete tool, and Claude decides which tools to call and in what order
> based on the validation objective. This is the same reconciliation logic
> I applied manually at Wells Fargo, but now driven by an AI agent."*

---

## Skills Demonstrated

- **MCP (Model Context Protocol)** — tool server design and client integration
- **Agentic AI** — Claude orchestrating multi-step validation autonomously  
- **ETL Data Quality** — real reconciliation patterns (count checks, anti joins, null checks)
- **Python** — async MCP server, pyodbc, Anthropic SDK
- **SQL Server** — schema design, complex queries, window functions
- **Data Engineering** — source-to-target validation methodology
