"""Zetaris federated-SQL tool — the agent's data layer.

Exposed to the agent and to the Nemotron planner as a real tool:

  tool = ZetarisFederatedTool()
  result = tool.run("SELECT ... FROM NY_TAXI.yellow_taxi ...")
  context = tool.ground(question, result, recalled_memory)

`ground` joins the federated result set with the agent's recalled memories in
one context block with explicit provenance labels, so the generator can cite
whether a statement came from Zetaris data or from memory. The tool is
mockable offline: any object with a compatible `query(sql)` method can stand
in for ZetarisClient when the platform is down (see tests/test_zetaris.py).
"""
import time

from zetaris_client import ZetarisClient, ZetarisUnavailable

# Catalog hint the planner reasons over when deciding which SQL to federate.
# Tables come from the platform's registered sample datasets (NY_TAXI, TPCDS_DB).
CATALOG_HINT = (
    "Zetaris Lightning federated catalog (sample datasets): "
    "NY_TAXI (CSV) with tables customers, trips, yellow_taxi, taxi_zones, payment_type, "
    "vendor, rate_code, trip_distances, pickup_locations, dropoff_locations and more; "
    "TPCDS_DB (Parquet, TPC-DS schema) with tables store_sales, item, date_dim, "
    "customer, store, household_demographics, promotion, web_sales and more. "
    "SQL dialect: Spark SQL. Fully qualify tables as DATABASE.table."
)

TOOL_NAME = "zetaris_federated_sql"
TOOL_DESCRIPTION = (
    "Run federated SQL against the Zetaris Lightning engine (datasets NY_TAXI, TPCDS_DB) "
    "and return the result rows. Use it to ground answers in real data; the agent joins "
    "the rows with its own memory before answering."
)


class ZetarisFederatedTool:
    """The federated query tool: run SQL, format rows, join with agent memory."""

    name = TOOL_NAME
    description = TOOL_DESCRIPTION

    def __init__(self, client=None):
        self.client = client or ZetarisClient()

    def run(self, sql, page_limit=200):
        """Execute federated SQL. Returns the client result dict; raises ZetarisUnavailable."""
        if not sql or not sql.strip():
            raise ValueError("empty SQL")
        return self.client.query(sql.strip(), page_limit=page_limit)

    def available(self):
        """Best-effort liveness probe (used by the agent to decide whether to try)."""
        try:
            self.run("SELECT 1 AS ok", page_limit=1)
            return True
        except (ZetarisUnavailable, ValueError):
            return False

    @staticmethod
    def format_rows(result, max_rows=20):
        """Render a result set as compact text rows for the prompt/context."""
        columns = result.get("columns") or []
        rows = result.get("rows") or []
        lines = []
        if columns:
            lines.append(" | ".join(str(c) for c in columns))
        for row in rows[:max_rows]:
            if isinstance(row, dict):
                lines.append(" | ".join(str(row.get(c, "")) for c in columns) if columns
                             else " | ".join(f"{k}={v}" for k, v in row.items()))
            else:
                lines.append(str(row))
        if len(rows) > max_rows:
            lines.append(f"... ({len(rows) - max_rows} more rows)")
        return "\n".join(lines)

    def ground(self, question, result, recalled_memory, max_rows=20, max_memory=6):
        """Join a federated result set with recalled memory into one provenance-labelled block.

        `recalled_memory` is the agent's recall() output (dicts with 'text').
        Returns context text; never contains credentials.
        """
        started = time.time()
        parts = [
            f"QUESTION: {question}",
            "",
            f"SOURCE A — Zetaris Lightning federated SQL ({result.get('engine', 'zetaris')}):",
            f"query: {result.get('sql', '')}",
            f"rows: {result.get('row_count', len(result.get('rows', [])))}",
            self.format_rows(result, max_rows=max_rows),
            "",
            "SOURCE B — agent memory (Meterless H-MEM recall):",
        ]
        memory = (recalled_memory or [])[:max_memory]
        if memory:
            for entry in memory:
                text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
                parts.append(f"- {text}")
        else:
            parts.append("(no recalled memories)")
        parts += [
            "",
            "GROUNDING RULES:",
            "- Statements about data values must come from SOURCE A and may cite the query.",
            "- Statements about the user/preferences/history must come from SOURCE B.",
            "- Never invent rows; if the two sources conflict, say so explicitly.",
            f"(join built in {int((time.time() - started) * 1000)}ms)",
        ]
        return "\n".join(parts)
