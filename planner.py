"""NVIDIA Nemotron reasoning core + Meterless-style call metering.

Nemotron (nvidia/nemotron-3-ultra-550b-a55b, free tier) is the product's
reasoning engine, reached through the local OmniRoute gateway (OpenAI-compatible).
Every model call emits an auditable receipt — the metering record of the agent's
spend per call, in the spirit of the Meterless trust ledger: append-only,
machine-readable, never carrying credentials.

Configuration (all optional, no secrets in code or logs):
  OMNIROUTE_BASE_URL   gateway base URL   (default http://127.0.0.1:20128/v1)
  OMNIROUTE_API_KEY    bearer key for the gateway
  NEMOTRON_MODEL       model slug         (default the free Nemotron 3 Ultra)
"""
import json
import os
import time
import urllib.request

DEFAULT_MODEL = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
RECEIPT_VERSION = "meterless-receipt-v1"


class MeteringLog:
    """Append-only receipts for model calls (metering per call, no keys)."""

    def __init__(self, path=None):
        self.path = path
        self.receipts = []

    def record(self, request_id, model, latency_ms, usage, purpose):
        receipt = {
            "meter": RECEIPT_VERSION,
            "ts": round(time.time(), 3),
            "request_id": request_id,
            "model": model,
            "purpose": purpose,
            "latency_ms": latency_ms,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "cost_usd": 0.0,
        }
        self.receipts.append(receipt)
        if self.path:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a") as f:
                f.write(json.dumps(receipt) + "\n")
        return receipt

    def summary(self):
        total_tokens = sum(r.get("total_tokens") or 0 for r in self.receipts)
        total_latency = sum(r.get("latency_ms") or 0 for r in self.receipts)
        return {
            "calls": len(self.receipts),
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency,
            "total_cost_usd": 0.0,
            "models": sorted({r["model"] for r in self.receipts}),
        }


class NemotronPlanner:
    """Reasoning/planner component backed by NVIDIA Nemotron."""

    def __init__(self, metering=None, model=None, base_url=None, api_key=None):
        self.base_url = (base_url or os.environ.get("OMNIROUTE_BASE_URL") or "http://127.0.0.1:20128/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("OMNIROUTE_API_KEY") or ""
        self.model = model or os.environ.get("NEMOTRON_MODEL") or DEFAULT_MODEL
        self.metering = metering or MeteringLog()

    def complete(self, system, user, purpose="reasoning", max_tokens=300, temperature=0.2):
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=180) as r:
            body = json.loads(r.read().decode())
        latency_ms = int((time.time() - t0) * 1000)
        self.metering.record(
            request_id=body.get("id", "unknown"),
            model=body.get("model", self.model),
            latency_ms=latency_ms,
            usage=body.get("usage", {}),
            purpose=purpose,
        )
        return body["choices"][0]["message"]["content"]

    def plan(self, task, context):
        """Reason over the recalled context and return a short execution plan."""
        system = (
            "You are the reasoning core of a personal AI agent. "
            "Given a task and recalled memories, produce a concise plan: "
            "3 numbered steps and the facts the answer must respect. "
            "No preamble."
        )
        return self.complete(system, f"TASK: {task}\n\nRECALLED MEMORIES:\n{context}", purpose="plan")

    def draft_insight(self, memory_texts):
        """Draft a dream-cycle insight from clustered memories (H-MEM spec 7)."""
        system = (
            "You synthesize durable insights from clusters of agent memories. "
            "Return one sentence stating the pattern or invariant, no preamble."
        )
        return self.complete(system, "MEMORIES:\n- " + "\n- ".join(memory_texts), purpose="dream_insight")
