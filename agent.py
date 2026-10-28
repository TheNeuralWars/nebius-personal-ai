"""Agent loop: recall -> plan (Nemotron) -> federated tool (Zetaris) -> generate -> CanonGuard -> repair (max 2) -> show -> self-critique."""
from guard import CanonGuard
from llm import LLM
from memory import Memory
from zetaris_client import ZetarisUnavailable

MAX_REPAIRS = 2


class Agent:
    def __init__(self, memory_path="memory.jsonl", canon_path="canon.json", llm=None, planner=None, data_tool=None):
        self.memory = Memory(memory_path)
        self.guard = CanonGuard(canon_path)
        self.llm = llm or LLM()
        self.planner = planner
        self.data_tool = data_tool

    def _federate(self, task, ctx_text, context):
        """Ask the planner for a federated query and run the Zetaris tool.

        Returns (sql, row_count, grounding_text). The tool degrades gracefully:
        if the platform is down the agent answers from memory alone.
        """
        if self.data_tool is None:
            return None, 0, ""
        decide = getattr(self.planner, "decide_federated_query", None) if self.planner else None
        sql = decide(task, ctx_text) if decide else None
        if not sql:
            return None, 0, ""
        try:
            result = self.data_tool.run(sql)
        except (ZetarisUnavailable, ValueError) as e:
            self.memory.add(f"federated: query unavailable ({e.__class__.__name__})", kind="task_log")
            return sql, 0, f"(federated data unavailable: {e.__class__.__name__}; answering from memory)"
        grounding = self.data_tool.ground(task, result, context)
        self.memory.add(f"federated: {sql} -> {result.get('row_count', 0)} rows", kind="task_log")
        return sql, result.get("row_count", 0), grounding

    def run(self, task):
        context = self.memory.recall(task)
        ctx_text = "\n".join(f"- {e['text']}" for e in context) or "(empty)"
        plan = self.planner.plan(task, ctx_text) if self.planner else ""
        system = ("You are Hermes, a personal AI. Answer with facts from MEMORY only. "
                  "MEMORY:\n" + ctx_text)
        if plan:
            system += "\n\nPLAN (reasoning core):\n" + plan
        federated_sql, federated_rows, grounding = self._federate(task, ctx_text, context)
        if grounding:
            system += "\n\nFEDERATED GROUNDING (Zetaris Lightning):\n" + grounding
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
                return {"answer": answer, "violations": violations, "shown": False, "draft": draft,
                        "caught": caught, "plan": plan, "federated_sql": federated_sql,
                        "federated_rows": federated_rows, "grounding": grounding}
            fix_user = self.guard.repair_prompt(violations) + "\n\nPrevious answer:\n" + answer
            answer = self.llm.complete("Fix ONLY these canon violations; keep everything else identical.", fix_user)
        self.memory.add(f"task: {task} -> answer ok", kind="task_log")
        self.memory.add(f"critique: guard checked {len(context)} recalled facts, "
                        f"{len(violations)} violations at show time", kind="self_critique")
        return {"answer": answer, "violations": [], "shown": True, "draft": draft,
                "caught": caught, "plan": plan, "federated_sql": federated_sql,
                "federated_rows": federated_rows, "grounding": grounding}
