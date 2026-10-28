"""Live Zetaris demo — the federated data layer of the agent.

Part A: direct federated SQL against the platform's registered sample datasets
        (NY_TAXI / TPCDS_DB) through the documented SQL Query API.
Part B: the full agent loop with the tool wired in — the Nemotron planner
        decides whether to federate and with which SQL, the tool runs it, the
        rows are joined with the agent's recalled memory (Meterless H-MEM) with
        provenance labels, and the generator answers from that grounding.

Run with ./run_zetaris_demo.sh (loads the OmniRoute gateway key at runtime,
never printed). Everything printed is real tool output; redirect to
proofs/zetaris-*.txt for the submission evidence.
"""
import json
import os
import tempfile

from agent import Agent
from llm import LLM
from planner import MeteringLog, NemotronPlanner
from zetaris_client import ZetarisUnavailable
from zetaris_tool import ZetarisFederatedTool

CANON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canon.json")
RECEIPTS = os.path.join("proofs", "zetaris-nemotron-receipts.jsonl")

SAMPLE_QUERIES = [
    "SELECT * FROM NY_TAXI.customers LIMIT 5",
    "SELECT i_item_id, i_item_desc, i_current_price FROM TPCDS_DB.item LIMIT 5",
]


def hr(title):
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def part_a(tool):
    hr("Part A — federated SQL over the Zetaris sample datasets")
    for sql in SAMPLE_QUERIES:
        print(f"\nSQL> {sql}")
        result = tool.run(sql)
        print(f"engine: {result['engine']}  latency_ms: {result['latency_ms']}  rows: {result['row_count']}")
        print(tool.format_rows(result, max_rows=10))


def part_b(planner, tool):
    hr("Part B — agent loop: Nemotron plans the federation, tool grounds the answer")
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        agent = Agent(memory_path=path, canon_path=CANON, llm=LLM(), planner=planner, data_tool=tool)
        # Seed one memory fact so the grounding block has both sources to join.
        agent.memory.add("Martin's favourite pickup zone is Midtown (user-stated preference).", kind="canon")
        task = ("Compare the number of yellow-taxi trips per pickup zone. "
                "What does the data say about Martin's favourite zone?")
        print(f"TASK: {task}")
        out = agent.run(task)
        print(f"\nPLAN (Nemotron):\n{out['plan']}")
        print(f"\nFEDERATED_SQL decided by the planner: {out['federated_sql']}")
        print(f"rows returned: {out['federated_rows']}")
        print(f"\nGROUNDING (federated rows JOIN agent memory):\n{out['grounding']}")
        print(f"\nANSWER (shown={out['shown']}, canon violations={out['violations']}):\n{out['answer']}")
    finally:
        for suffix in ("", ".hmem.json"):
            try:
                os.remove(path + suffix)
            except OSError:
                pass


def main():
    metering = MeteringLog(path=RECEIPTS)
    planner = NemotronPlanner(metering=metering)
    tool = ZetarisFederatedTool()
    try:
        part_a(tool)
        part_b(planner, tool)
    except ZetarisUnavailable as e:
        print(f"\nZETARIS UNAVAILABLE: {e}", file=__import__("sys").stderr)
        return 1
    hr("Metering (every model call, append-only receipts)")
    print(json.dumps(metering.summary(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
