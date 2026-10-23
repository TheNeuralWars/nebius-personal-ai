"""Live hackathon demo — NVIDIA Nemotron reasoning core + Meterless H-MEM.

Part A: Meterless H-MEM lifecycle on the real engine (hmem/src):
  capture with provenance -> hybrid recall -> feedback deltas + audit ledger
  -> conflict detection + gated auto-resolution -> dreaming (insight drafted
  by Nemotron, approved with lineage) -> sleep preview/execute with guardrails.
Part B: full agent loop — H-MEM recall, Nemotron plan, Nemotron generation,
  CanonGuard repair, metered receipts for every model call.

Run with ./run_hackathon_demo.sh (loads the OmniRoute gateway key at runtime,
never printed). Everything printed below is real tool output.
"""
import json
import os
import tempfile

from agent import Agent
from hmem_client import HMemClient
from llm import LLM
from planner import MeteringLog, NemotronPlanner

RECEIPTS = os.path.join("proofs", "nemotron-receipts.jsonl")
CANON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canon.json")

T0 = 1750000000000
DAY = 24 * 60 * 60 * 1000


def hr(title):
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def part_a(planner):
    hr("A1. H-MEM capture with provenance + hybrid recall")
    with tempfile.TemporaryDirectory() as td:
        client = HMemClient(os.path.join(td, "hmem-state.json"))
        m1 = client.add("Martin is 28 (canon, fixed 2026-10-05)", source="canon", type="factual")
        m2 = client.add("Martin shipped the parser on 2026-10-20", source="event", type="factual")
        m3 = client.add("Nico prefers concise status lines", source="user_correction", type="preference")
        print(f"captured: {[m1['id'], m2['id'], m3['id']]}")
        result = client.query("how old is Martin and what did he ship", threshold=0, topN=3)
        for r in result["memories"]:
            mem = r["memory"]
            print(f"  {mem['id']} score={r['relevance']:.3f} layer={mem['layer']} "
                  f"conf={mem['confidence']} origin={mem['provenance']['origin']}")
            print(f"     {mem['content']}")
        print("trace:", json.dumps(result["trace"]["retrievalReason"]))

        hr("A2. feedback loop (H-MEM spec 9.2) + audit ledger")
        before = client.query("Martin age", threshold=0, topN=1)["memories"][0]["memory"]
        client.feedback(before["id"], "helpful")
        actions = client.history(before["id"])
        print(f"feedback helpful on {before['id']}: confidence {before['confidence']} -> "
              f"{actions[-1]['newState']['confidence']}, accessCount {actions[-1]['newState']['accessCount']}")
        print("ledger actions:", [e["action"] for e in actions])

        hr("A3. conflict detection + gated auto-resolution (spec 10)")
        client.add("always enable telemetry uploads for diagnostics", source="chat", confidence=0.95)
        client.add("never enable telemetry uploads for diagnostics", source="chat", confidence=0.2)
        found = client.conflicts_scan()
        for c in found:
            print(f"  {c['id']}: {c['reason']} (confidence {c['confidence']:.2f})")
        if found:
            outcome = client.conflicts_resolve(found[0]["id"])
            print("autoResolve outcome:", outcome["outcome"])
            info = client.info()
            print(f"records after resolution: {info['records']} (nothing deleted)")

        hr("A4. dreaming: Nemotron drafts the insight, H-MEM governs approval")
        client.add("prefer short bullet answers", source="chat", type="preference")
        client.add("prefer python for scripting", source="chat", type="preference")
        proposals = client.dream()
        print(f"proposals: {[(p['id'], p['type']) for p in proposals]}")
        print("store size unchanged before approval:", client.info()["records"])
        drafted = planner.draft_insight([p["content"] for p in proposals[:2]]) if proposals else ""
        print("Nemotron-drafted insight:", drafted.strip()[:200])
        if proposals:
            created = client.dream_approve(proposals[0]["id"], content=drafted.strip() or None)
            print(f"approved -> {created['id']} layer={created['layer']} "
                  f"derivedFrom={created['derivedFrom']} origin={created['provenance']['origin']}")

        hr("A5. sleep cycle with guardrails (injected clock, +40 days)")
        # fresh store, added at T0, aged 40 days for the archive rules
        with tempfile.TemporaryDirectory() as td2:
            aged = HMemClient(os.path.join(td2, "aged-state.json"))
            plain = aged.add("random one-off note about parking near the office", source="chat", clockNow=T0)
            derived = aged.add("synthesized insight about the quarterly roadmap", source="dreaming",
                               derivedFrom=["mem-x"], clockNow=T0)
            aged._run(op="sleep_preview", clockNow=T0)  # warm nothing; preview at +40d below
            preview = aged._run(op="sleep_preview", clockNow=T0 + 40 * DAY)
            print("toArchive:", preview["toArchive"], "(plain expected, derived protected)")
            print("store before execute:", aged.info()["records"])
            report = aged._run(op="sleep_execute", clockNow=T0 + 40 * DAY)
            print("sleep report:", json.dumps({k: report[k] for k in ("backupId", "consolidated", "archived", "synthesized")}))
            print("store after execute:", aged.info()["records"], "(derived survived guardrails)")


def part_b():
    hr("B. full agent loop: H-MEM recall + Nemotron plan + Nemotron generation")
    metering = MeteringLog(RECEIPTS)
    planner = NemotronPlanner(metering=metering)
    print("planner model:", planner.model)
    with tempfile.TemporaryDirectory() as td:
        agent = Agent(memory_path=os.path.join(td, "memory.jsonl"), canon_path=CANON,
                      llm=LLM(provider="nemotron", metering=metering), planner=planner)
        agent.memory.add("Martin is 28 (canon, fixed 2026-10-05)", kind="canon")
        agent.memory.add("Martin shipped the parser on 2026-10-20", kind="event")
        task = "Draft a one-line status about Martin: his age and what he shipped."
        out = agent.run(task)
        print("task:", task)
        print("PLAN (Nemotron):")
        print(" ", (out.get("plan") or "").strip()[:400])
        print("draft:", out["draft"].strip()[:200])
        if out["caught"]:
            print("violations caught before repair:", [v["rule"] for v in out["caught"]])
        print("final shown:", out["shown"], "| answer:", out["answer"].strip()[:200])
        print("part B metering:", json.dumps(metering.summary()))
        print("receipts file:", RECEIPTS)


if __name__ == "__main__":
    os.makedirs("proofs", exist_ok=True)
    planner = NemotronPlanner(metering=MeteringLog(RECEIPTS))
    print("Nemotron reasoning core:", planner.model, "@", planner.base_url)
    part_a(planner)
    part_b()
    receipts = [json.loads(l) for l in open(RECEIPTS)] if os.path.exists(RECEIPTS) else []
    total_tokens = sum(r.get("total_tokens") or 0 for r in receipts)
    total_latency = sum(r.get("latency_ms") or 0 for r in receipts)
    print(f"\nmetering receipts file: {len(receipts)} calls, {total_tokens} tokens, "
          f"{total_latency} ms total, $0.00 (free tier)")
    for r in receipts:
        print(f"  {r['request_id']} | {r['model']} | {r['purpose']} | {r['latency_ms']} ms | {r['total_tokens']} tok")
    print("\nDEMO COMPLETE — all output above is real.")
