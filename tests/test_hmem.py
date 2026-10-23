"""Tests for the new hackathon work: Meterless H-MEM engine (via the Node
bridge), memory integration, and the NVIDIA Nemotron planner metering.

Run: python3 -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hmem_client import HMemClient, HMemError
from memory import Memory
from planner import MeteringLog, NemotronPlanner

CANON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "canon.json")

T0 = 1750000000000
DAY = 24 * 60 * 60 * 1000


def fresh_client(td, clock=T0):
    return HMemClient(os.path.join(td, "state.json"))


@unittest.skipUnless(HMemClient.available(), "node not available for the H-MEM engine")
class TestHMemEngine(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = self._td.name
        self.client = fresh_client(self.td)

    def tearDown(self):
        self._td.cleanup()

    def test_records_without_source_are_rejected(self):
        with self.assertRaises(HMemError):
            self.client.add("orphan record", source="")

    def test_feedback_deltas_and_review_tag(self):
        m = self.client.add("feedback target", source="test", confidence=0.7)
        after = self.client.feedback(m["id"], "wrong")
        self.assertAlmostEqual(after["confidence"], 0.5, places=9)
        self.assertIn("review", after["tags"])
        after = self.client.feedback(m["id"], "helpful")
        self.assertAlmostEqual(after["confidence"], 0.55, places=9)
        self.assertEqual(after["accessCount"], 1)

    def test_ledger_reconstructs_create_then_feedback(self):
        m = self.client.add("audited record", source="test", confidence=0.7)
        self.client.feedback(m["id"], "wrong")
        actions = [e["action"] for e in self.client.history(m["id"])]
        self.assertEqual(actions, ["create", "feedback"])
        last = self.client.history(m["id"])[-1]
        self.assertAlmostEqual(last["previousState"]["confidence"], 0.7, places=9)
        self.assertAlmostEqual(last["newState"]["confidence"], 0.5, places=9)

    def test_confidence_orders_ranking(self):
        high = self.client.add("the deploy window is monday morning", source="test", confidence=0.9, layer="working")
        low = self.client.add("the deploy window is monday morning", source="test", confidence=0.4, layer="working")
        result = self.client.query("deploy window", threshold=0, topN=10)
        order = [r["memory"]["id"] for r in result["memories"]]
        self.assertLess(order.index(high["id"]), order.index(low["id"]))

    def test_conflict_scan_and_gated_resolution(self):
        a = self.client.add("always enable telemetry uploads for diagnostics", source="test", confidence=0.95)
        b = self.client.add("never enable telemetry uploads for diagnostics", source="test", confidence=0.2)
        found = self.client.conflicts_scan()
        self.assertGreater(len(found), 0)
        outcome = self.client.conflicts_resolve(found[0]["id"])
        self.assertIn(outcome["outcome"], ("resolved", "queued"))
        # resolution never deletes records
        self.assertEqual(self.client.info()["records"], 2)

    def test_dream_proposals_need_approval(self):
        self.client.add("prefer short bullet answers", source="test", type="preference")
        self.client.add("prefer python for scripting", source="test", type="preference")
        before = self.client.info()["records"]
        proposals = self.client.dream()
        self.assertGreater(len(proposals), 0)
        self.assertEqual(self.client.info()["records"], before)  # nothing materialized
        created = self.client.dream_approve(proposals[0]["id"])
        self.assertEqual(created["layer"], "long_term")
        self.assertGreater(len(created.get("derivedFrom") or []), 0)

    def test_sleep_guardrails_protect_derived_memories(self):
        # add at T0 with a fixed clock
        for payload in (
            {"content": "random one-off note about parking near the office", "source": "chat"},
            {"content": "synthesized insight about the quarterly roadmap", "source": "dreaming", "derivedFrom": ["mem-x"]},
        ):
            cmd = {"op": "add", "clockNow": T0, "state": self.client.state_path, **payload}
            import subprocess
            proc = subprocess.run(["node", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hmem", "src", "cli.ts")],
                                  input=json.dumps(cmd), capture_output=True, text=True, timeout=30)
            json.loads(proc.stdout)
        # age the store 40 days via injected clock
        import subprocess
        cli = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hmem", "src", "cli.ts")

        def run(cmd):
            proc = subprocess.run(["node", cli], input=json.dumps(cmd), capture_output=True, text=True, timeout=30)
            return json.loads(proc.stdout)["result"]

        preview = run({"op": "sleep_preview", "clockNow": T0 + 40 * DAY, "state": self.client.state_path})
        ids = run({"op": "info", "clockNow": T0 + 40 * DAY, "state": self.client.state_path})
        self.assertEqual(ids["records"], 2)  # preview must not mutate
        self.assertEqual(len(preview["toArchive"]), 1)  # only the plain record
        report = run({"op": "sleep_execute", "clockNow": T0 + 40 * DAY, "state": self.client.state_path})
        self.assertTrue(report["backupId"])
        self.assertEqual(run({"op": "info", "clockNow": T0 + 40 * DAY, "state": self.client.state_path})["records"], 1)


class TestMemoryIntegration(unittest.TestCase):
    def test_keyword_fallback_without_hmem(self):
        with tempfile.TemporaryDirectory() as td:
            m = Memory(os.path.join(td, "m.jsonl"), use_hmem=False)
            m.add("Martin is 28 (canon)")
            m.add("weather is fine")
            hits = m.recall("martin age")
            self.assertTrue(hits and "28" in hits[0]["text"])

    @unittest.skipUnless(HMemClient.available(), "node not available")
    def test_hmem_ranking_used_when_available(self):
        with tempfile.TemporaryDirectory() as td:
            m = Memory(os.path.join(td, "m.jsonl"))
            m.add("Martin is 28 (canon)", kind="canon")
            m.add("weather is fine", kind="note")
            hits = m.recall("martin age")
            self.assertTrue(hits and "28" in hits[0]["text"])
            self.assertIn("score", hits[0])
            self.assertIn("hmem_id", hits[0])


class _FakeCompletions(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "id": "gen-test-0001",
            "model": body.get("model", "test"),
            "choices": [{"message": {"content": "PLAN-OK"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }).encode())

    def log_message(self, format, *args):
        pass


class TestNemotronPlannerMetering(unittest.TestCase):
    def test_call_is_metered_with_receipt_without_keys(self):
        server = HTTPServer(("127.0.0.1", 0), _FakeCompletions)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as td:
                receipts_path = os.path.join(td, "receipts.jsonl")
                metering = MeteringLog(receipts_path)
                planner = NemotronPlanner(
                    metering=metering,
                    base_url=f"http://127.0.0.1:{port}/v1",
                    api_key="fake-key-not-a-secret",
                )
                out = planner.complete("system", "user", purpose="plan")
                self.assertEqual(out, "PLAN-OK")
                summary = metering.summary()
                self.assertEqual(summary["calls"], 1)
                self.assertEqual(summary["total_tokens"], 15)
                self.assertEqual(summary["total_cost_usd"], 0.0)
                receipt = json.loads(open(receipts_path).read().strip())
                self.assertEqual(receipt["request_id"], "gen-test-0001")
                self.assertNotIn("api_key", json.dumps(receipt))
                self.assertNotIn("fake-key-not-a-secret", json.dumps(receipt))
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
