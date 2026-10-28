"""Public live demo: Hermes Personal AI on Nebius Token Factory + NVIDIA Nemotron.

Stdlib-only HTTP server. The API key is read from a file at startup (NEBIUS_API_KEY_FILE)
and never returned or logged. Hard caps protect credits: fixed scenarios, short input,
per-IP and global daily limits, max_tokens=400 per call.
"""
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.environ.get("NEBIUS_API_KEY_FILE", "/run/secrets/nebius_api_key")
if os.path.exists(KEY_FILE):
    os.environ["NEBIUS_API_KEY"] = open(KEY_FILE).read().strip()
os.environ.setdefault("HERMES_LLM_PROVIDER", "nebius")
os.environ.setdefault("HERMES_LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")

from agent import Agent  # noqa: E402
from llm import LLM  # noqa: E402

DAILY_CAP = int(os.environ.get("DEMO_DAILY_CAP", "150"))
IP_WINDOW, IP_MAX = 600, 5
_lock = threading.Lock()
_day = {"date": "", "count": 0}
_ip = {}

SCENARIOS = {
    "grounded": ("Grounded answer from memory", "Draft a one-line status about Martin."),
    "repair": ("Messy draft -> CanonGuard catches -> repair",
               "Polish this rough draft into a one-line status. Keep the writer's original phrasing "
               "and tone, just make it flow:\n\nlorem ipsum. As an AI I am pleased to report that "
               "Martin shipped the parser today."),
}


class Receipts:
    def __init__(self):
        self.items = []

    def record(self, **kw):
        u = kw.get("usage") or {}
        self.items.append({"request_id": kw.get("request_id"), "model": kw.get("model"),
                           "latency_ms": kw.get("latency_ms"), "purpose": kw.get("purpose"),
                           "prompt_tokens": u.get("prompt_tokens"),
                           "completion_tokens": u.get("completion_tokens")})


def allow(ip):
    now = time.time()
    with _lock:
        d = time.strftime("%Y-%m-%d", time.gmtime())
        if _day["date"] != d:
            _day.update(date=d, count=0)
        if _day["count"] >= DAILY_CAP:
            return "daily demo cap reached - see recorded proof below"
        hits = [t for t in _ip.get(ip, []) if now - t < IP_WINDOW]
        if len(hits) >= IP_MAX:
            return "slow down - max 5 runs per 10 minutes"
        hits.append(now)
        _ip[ip] = hits
        _day["count"] += 1
    return None


def run(scenario, question):
    rec = Receipts()
    with tempfile.TemporaryDirectory() as td:
        agent = Agent(memory_path=os.path.join(td, "m.jsonl"), canon_path=os.path.join(HERE, "canon.json"),
                      llm=LLM(metering=rec))
        agent.memory.add("Martin is 28 (canon, fixed 2026-10-05)", kind="canon")
        agent.memory.add("Martin shipped the parser on 2026-10-20", kind="event")
        task = question if scenario == "custom" else SCENARIOS[scenario][1]
        out = agent.run(task)
    return {"task": task, "draft": (out.get("draft") or out["answer"]).strip(),
            "caught": out.get("caught", []), "final": out["answer"].strip(), "shown": out["shown"],
            "unrepaired": len(out["violations"]), "receipts": rec.items,
            "provider": "Nebius Token Factory", "model": os.environ["HERMES_LLM_MODEL"]}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._send(200, open(os.path.join(HERE, "demo_web", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/proof":
            return self._send(200, open(os.path.join(HERE, "proofs", "nebius-tokenfactory-live.txt"), "rb").read(), "text/plain; charset=utf-8")
        if p == "/health":
            return self._send(200, json.dumps({"ok": True, "model": os.environ["HERMES_LLM_MODEL"], "runs_today": _day["count"], "cap": DAILY_CAP}))
        self._send(404, '{"error":"not found"}')

    def do_POST(self):
        if self.path.split("?")[0] != "/api/run":
            return self._send(404, '{"error":"not found"}')
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 2000)
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, '{"error":"bad json"}')
        scenario = req.get("scenario", "grounded")
        question = str(req.get("question", ""))[:200]
        if scenario not in (*SCENARIOS, "custom") or (scenario == "custom" and not question.strip()):
            return self._send(400, '{"error":"unknown scenario"}')
        ip = (self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For", "").split(",")[0]
              or self.client_address[0])
        why = allow(ip)
        if why:
            return self._send(429, json.dumps({"error": why}))
        try:
            return self._send(200, json.dumps(run(scenario, question)))
        except Exception as e:
            return self._send(502, json.dumps({"error": f"upstream error: {e.__class__.__name__}"}))

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), H).serve_forever()
