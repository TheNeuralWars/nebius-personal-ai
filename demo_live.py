"""Live demo of the Hermes Personal AI loop on REAL Nebius Token Factory inference.

Run via ./run_live.sh (loads NEBIUS_API_KEY from the secure file at runtime).

Shows the full value loop transparently:
  1. memory-grounded answer -> CanonGuard verifies -> shown (0 violations)
  2. a messy draft that leaks corporate filler -> CanonGuard catches -> repair -> shown clean
"""
import os
import tempfile

from agent import Agent

CANON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canon.json")

def show(tag, out):
    print(f"\n[{tag}] DRAFT from model:\n    {out.get('draft', out['answer'])!r}")
    caught = out.get("caught", [])
    if caught:
        print(f"[{tag}] CanonGuard CAUGHT {len(caught)} violation(s) in the draft:")
        for v in caught:
            print(f"    - {v['rule']}: {v['detail']}")
    else:
        print(f"[{tag}] CanonGuard: 0 violations (clean)")
    print(f"[{tag}] FINAL shown={out['shown']} (unrepaired violations left: {len(out['violations'])}):\n    {out['answer']!r}")

def main():
    model = os.environ.get("HERMES_LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    provider = os.environ.get("HERMES_LLM_PROVIDER", "nebius")
    print(f"Hermes Personal AI — LIVE demo | provider={provider} model={model}")

    with tempfile.TemporaryDirectory() as td:
        agent = Agent(memory_path=os.path.join(td, "memory.jsonl"), canon_path=CANON)
        agent.memory.add("Martin is 28 (canon, fixed 2026-10-05)", kind="canon")
        agent.memory.add("Martin shipped the parser on 2026-10-20", kind="event")

        print("\n=== Scenario 1: answer grounded in persistent memory ===")
        out = agent.run("Draft a one-line status about Martin.")
        show("S1", out)

        print("\n=== Scenario 2: messy draft leaks a banned phrase -> guard + repair ===")
        messy = ("lorem ipsum. As an AI I am pleased to report that Martin shipped "
                 "the parser today.")
        out = agent.run(
            "Polish this rough draft into a one-line status. Keep the writer's original "
            "phrasing and tone, just make it flow:\n\n" + messy
        )
        show("S2", out)

        print("\n=== memory recall('martin age') ===")
        for e in agent.memory.recall("martin age"):
            print(f"    {e['text']}")

if __name__ == "__main__":
    main()
