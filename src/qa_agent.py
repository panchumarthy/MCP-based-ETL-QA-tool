"""
Claude QA Agent
================
Uses the Anthropic API to let Claude autonomously call MCP tools,
validate your SQL Server ETL pipeline in plain English, and save
a professional HTML report for every run.

Usage:
    python qa_agent.py
    python qa_agent.py --query "Validate today's pipeline run"

Author : Satish Panchumarthy
GitHub : github.com/panchumarthy
"""

import argparse
import asyncio
import json
import os
import sys
import webbrowser

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from report_generator import generate_html_report


# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_CONNECTION = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=ETL_QA_Demo;"
    "Trusted_Connection=yes"
)

SYSTEM_PROMPT = f"""You are an expert ETL QA Data Engineer and Data Analyst.
You have access to tools that connect to a SQL Server database and run
data quality validation checks.

Connection string to use for all tool calls:
{DEFAULT_CONNECTION}

Your job is to:
1. Understand what the user wants to validate
2. Call the appropriate MCP tools (you can call multiple tools in sequence)
3. Analyze the results
4. Provide a clear, structured QA report with PASS/FAIL status for each check
5. Highlight any data issues found and suggest root causes

Always start with list_tables if you don't know what tables exist.
For full pipeline validation, use generate_qa_report for efficiency.
For targeted checks, use individual tools like row_count_check, null_check, etc.

Format your final report clearly with:
- Overall Pipeline Status (PASS/FAIL)
- Individual check results
- Issues found (if any)
- Recommended next steps

When you call generate_qa_report, always include the full JSON result
in your response so it can be saved to an HTML report.
"""

BANNER = """
╔══════════════════════════════════════════════════════════╗
║        MCP-Based ETL QA Validation Agent                 ║
║        Powered by Claude + SQL Server                    ║
║        Reports saved to: reports/                        ║
║        github.com/panchumarthy                           ║
╚══════════════════════════════════════════════════════════╝
Type your validation request in plain English.
Examples:
  > Run a full QA report on the securities pipeline
  > Validate today's pipeline run between source and target
  > Check for NULL values in the orders table
  > Find any duplicate records in securities_target
  > Check referential integrity between orders_source and customers
  > List all available tables
Type 'exit' to quit.
"""


# ── MCP → Anthropic Tool Converter ───────────────────────────────────────────
def mcp_tool_to_anthropic(tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.inputSchema,
    }


# ── Agent Loop ────────────────────────────────────────────────────────────────
async def run_agent(user_query: str, session: ClientSession, client: anthropic.Anthropic):
    """Run one agentic loop and auto-save HTML report if QA report data found."""

    tools_response = await session.list_tools()
    tools = [mcp_tool_to_anthropic(t) for t in tools_response.tools]
    messages = [{"role": "user", "content": user_query}]

    print(f"\n🤖 Agent thinking...\n{'─' * 60}")

    all_tool_results = {}

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        for block in response.content:
            if hasattr(block, "text") and block.text:
                print(block.text)

        if response.stop_reason == "end_turn":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                print(f"\n🔧 Calling tool: {tool_name}")
                print(f"   Args: {json.dumps({k: v for k, v in tool_input.items() if k != 'connection_string'}, indent=2)}")

                result = await session.call_tool(tool_name, tool_input)
                result_text = result.content[0].text if result.content else "{}"

                try:
                    result_json = json.loads(result_text)
                    all_tool_results[tool_name] = result_json
                    status = result_json.get("status") or result_json.get("overall_status", "")
                    if status:
                        icon = "✅" if "PASS" in str(status) else "❌"
                        print(f"   Result: {icon} {status}")
                except Exception:
                    pass

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    print(f"\n{'─' * 60}")

    # ── Auto-save HTML report ─────────────────────────────────────────────────
    report_data = None

    if "generate_qa_report" in all_tool_results:
        report_data = all_tool_results["generate_qa_report"]

    elif any(k in all_tool_results for k in ["null_check", "duplicate_check",
                                               "source_target_reconciliation",
                                               "row_count_check"]):
        report_data = {
            "report": "ETL QA Partial Validation Report",
            "generated_at": __import__('datetime').datetime.now().isoformat(),
            "source_table": "N/A",
            "target_table": "N/A",
            "overall_status": "See individual checks below",
            "summary": f"{len(all_tool_results)} check(s) completed.",
            "checks": {}
        }

        if "row_count_check" in all_tool_results:
            r = all_tool_results["row_count_check"]
            report_data["source_table"] = r.get("source_table", "N/A")
            report_data["target_table"] = r.get("target_table", "N/A")
            report_data["checks"]["row_count"] = {
                "status": r.get("status"),
                "source": r.get("source_count", 0),
                "target": r.get("target_count", 0),
                "difference": r.get("difference", 0)
            }

        if "source_target_reconciliation" in all_tool_results:
            r = all_tool_results["source_target_reconciliation"]
            report_data["checks"]["reconciliation"] = {
                "status": r.get("status"),
                "missing_records": r.get("total_missing", 0)
            }

        if "duplicate_check" in all_tool_results:
            r = all_tool_results["duplicate_check"]
            report_data["checks"]["duplicates_in_target"] = {
                "status": r.get("status"),
                "duplicate_groups": r.get("duplicate_groups", 0)
            }

        if "null_check" in all_tool_results:
            r = all_tool_results["null_check"]
            report_data["checks"]["null_key_check"] = {
                "status": r.get("overall_status"),
                "null_key_count": r.get("failed_columns", 0)
            }

        statuses = [v.get("status", "") if isinstance(v, dict) else "" for v in report_data["checks"].values()]
        all_pass = all("PASS" in str(s) for s in statuses)
        report_data["overall_status"] = "✅ ALL CHECKS PASSED" if all_pass else "❌ FAILED"
        report_data["summary"] = ("All checks passed." if all_pass
                                   else f"{sum(1 for s in statuses if 'FAIL' in str(s))} check(s) failed.")

    if report_data:
        report_path = generate_html_report(report_data)
        abs_path = os.path.abspath(report_path)
        print(f"\n📊 HTML Report saved  →  {abs_path}")
        print(f"   Opening in browser automatically...")
        webbrowser.open(f"file:///{abs_path.replace(os.sep, '/')}")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main(initial_query: str = None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set.")
        print("   Set it with: export ANTHROPIC_API_KEY=your-key-here")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    server_params = StdioServerParameters(
        command="python",
        args=["src/qa_mcp_server.py"],
        env=None,
    )

    print(BANNER)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ MCP QA Server connected\n")

            if initial_query:
                await run_agent(initial_query, session, client)
            else:
                while True:
                    try:
                        query = input("\n> ").strip()
                        if not query:
                            continue
                        if query.lower() in ("exit", "quit", "q"):
                            print("Goodbye!")
                            break
                        await run_agent(query, session, client)
                    except KeyboardInterrupt:
                        print("\nGoodbye!")
                        break
                    except Exception as e:
                        print(f"❌ Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude MCP QA Agent for SQL Server")
    parser.add_argument("--query", type=str, help="Run a single query non-interactively")
    args = parser.parse_args()
    asyncio.run(main(args.query))
