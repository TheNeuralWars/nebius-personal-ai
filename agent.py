"""Agent loop: recall -> plan (Nemotron) -> generate -> CanonGuard -> repair (max 2) -> show -> self-critique."""
from guard import CanonGuard
from llm import LLM
from memory import Memory

MAX_REPAIRS = 2


class Agent:
    def __init__(self, memory_path="memory.jsonl", canon_path="canon.json", llm=None, planner=None):
        self.memory = Memory(memory_path)
        self.guard = CanonGuard(canon_path)
        self.llm = llm or LLM()
        self.planner = planner

    def run(self, task):
        context = self.memory.recall(task)
        ctx_text = "\n".join(f"- {e['text']}" for e in context) or "(empty)"
        plan = self.planner.plan(task, ctx_text) if self.planner else ""
        system = ("You are Hermes, a personal AI. Answer with facts from MEMORY only. "
                  "MEMORY:\n" + ctx_text)
        if plan:
            system += "\n\nPLAN (reasoning core):\n" + plan
        answer = self.llm.complete(system, task)
        draft = answer  # first raw model output, kept for transparency/demo
        violations = []
        caught = []  # violations found before repair, kept for the demo
        for attempt in range(MAX_REPAIRS + 1):
            violations = self.guard.check(answer)
            if not violations:
                break
            if attempt == 0:
                caught = list(violations)
            if attempt == MAX_REPAIRS:
                return {"answer": answer, "violations": violations, "shown": False, "draft": draft, "caught": caught, "plan": plan}
            fix_user = self.guard.repair_prompt(violations) + "\n\nPrevious answer:\n" + answer
            answer = self.llm.complete("Fix ONLY these canon violations; keep everything else identical.", fix_user)
        self.memory.add(f"task: {task} -> answer ok", kind="task_log")
        self.memory.add(f"critique: guard checked {len(context)} recalled facts, "
                        f"{len(violations)} violations at show time", kind="self_critique")
        return {"answer": answer, "violations": [], "shown": True, "draft": draft, "caught": caught, "plan": plan}
