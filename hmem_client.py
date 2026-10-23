"""Python bridge to the Meterless H-MEM engine (hmem/src/cli.ts).

Each call is one JSON command piped to `node hmem/src/cli.ts`; state lives in a
JSON file next to the caller's memory journal. Node runs the TypeScript engine
directly (type stripping), so there is no build step and no npm dependency.

If node is unavailable the caller should fall back gracefully (H-MEM spec
section 4.3: "graceful degradation ... preserve capture continuity").
"""
import json
import os
import shutil
import subprocess

CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hmem", "src", "cli.ts")


class HMemError(RuntimeError):
    pass


class HMemClient:
    def __init__(self, state_path, timeout=30):
        self.state_path = state_path
        self.timeout = timeout

    @staticmethod
    def available():
        return shutil.which("node") is not None and os.path.exists(CLI)

    def _run(self, **cmd):
        cmd["state"] = self.state_path
        proc = subprocess.run(
            ["node", CLI],
            input=json.dumps(cmd),
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if not proc.stdout.strip():
            raise HMemError(f"hmem cli produced no output (stderr: {proc.stderr.strip()[:200]})")
        out = json.loads(proc.stdout)
        if not out.get("ok"):
            raise HMemError(out.get("error", "unknown hmem error"))
        return out["result"]

    # -- memory records ----------------------------------------------------
    def add(self, content, source, **fields):
        return self._run(op="add", content=content, source=source, **fields)

    def query(self, query, threshold=0.0, topN=5):
        return self._run(op="query", query=query, threshold=threshold, topN=topN)

    def feedback(self, mem_id, kind):
        return self._run(op="feedback", id=mem_id, kind=kind)

    def history(self, mem_id):
        return self._run(op="history", id=mem_id)

    def info(self):
        return self._run(op="info")

    # -- dream / sleep / conflicts ----------------------------------------
    def dream(self):
        return self._run(op="dream")

    def dream_approve(self, proposal_id, content=None):
        cmd = {"op": "dream_approve", "id": proposal_id}
        if content:
            cmd["content"] = content
        return self._run(**cmd)

    def dream_reject(self, proposal_id):
        return self._run(op="dream_reject", id=proposal_id)

    def conflicts_scan(self):
        return self._run(op="conflicts_scan")

    def conflicts_resolve(self, conflict_id):
        return self._run(op="conflicts_resolve", id=conflict_id)

    def sleep_preview(self):
        return self._run(op="sleep_preview")

    def sleep_execute(self):
        return self._run(op="sleep_execute")

    def sleep_restore(self, backup_id):
        return self._run(op="sleep_restore", backupId=backup_id)
