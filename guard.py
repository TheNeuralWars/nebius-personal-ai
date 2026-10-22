"""CanonGuard: deterministic rules over canon.json (ported from Living Canon)."""
import json
import re


class CanonGuard:
    def __init__(self, canon_path):
        with open(canon_path) as f:
            self.canon = json.load(f)

    def check(self, text):
        """Return a list of violations: {'rule', 'detail'} dicts."""
        violations = []
        low = text.lower()
        for fact in self.canon.get("protected_facts", []):
            hits = any(p in low for p in fact["patterns"])
            if hits:
                for bad in fact.get("must_not_contain", []):
                    if bad.lower() in low:
                        violations.append({
                            "rule": f"canon fact #{fact['id']} ({fact['topic']})",
                            "detail": f"{fact['claim']} — output contains forbidden '{bad}'",
                        })
        for banned in self.canon.get("banned_claims", []):
            if banned["pattern"].lower() in low:
                violations.append({
                    "rule": "banned claim",
                    "detail": f"{banned['reason']} ('{banned['pattern']}')",
                })
        return violations

    def repair_prompt(self, violations):
        lines = [f"- {v['rule']}: {v['detail']}" for v in violations]
        return ("Fix ONLY these canon violations in your previous answer; "
                "keep everything else identical:\n" + "\n".join(lines))
