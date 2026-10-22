"""Offline demo of the Hermes Personal AI loop (mock provider, no API key needed)."""
import os
import tempfile

from agent import Agent

CANON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canon.json")


def main():
    with tempfile.TemporaryDirectory() as td:
        agent = Agent(memory_path=os.path.join(td, "memory.jsonl"), canon_path=CANON)
        agent.memory.add("Martin is 28 (canon, fixed 2026-10-05)", kind="canon")
        agent.memory.add("Martin shipped the parser on 2026-10-20", kind="event")

        print("[1] user task: 'Draft a status line about Martin'")
        out = agent.run("Draft a status line about Martin")
        print(f"[1] final: {out['answer']!r}  shown={out['shown']} violations={len(out['violations'])}")

        print("[2] memory recall('martin age') ->")
        for e in agent.memory.recall("martin age"):
            print(f"    {e['text']}")


if __name__ == "__main__":
    main()
