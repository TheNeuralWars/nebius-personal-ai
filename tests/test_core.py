import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import Agent
from guard import CanonGuard
from memory import Memory

CANON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "canon.json")


class TestGuard(unittest.TestCase):
    def test_catches_forbidden_age(self):
        g = CanonGuard(CANON)
        v = g.check("Martin (19) shipped the parser today.")
        self.assertEqual(len(v), 1)
        self.assertIn("martin age", v[0]["rule"])

    def test_clean_text_passes(self):
        g = CanonGuard(CANON)
        self.assertEqual(g.check("Martin (28) shipped the parser today."), [])

    def test_banned_claim(self):
        g = CanonGuard(CANON)
        v = g.check("lorem ipsum dolor")
        self.assertEqual(len(v), 1)


class TestMemory(unittest.TestCase):
    def test_recall(self):
        with tempfile.TemporaryDirectory() as td:
            m = Memory(os.path.join(td, "m.jsonl"))
            m.add("Martin is 28 (canon)")
            m.add("weather is fine")
            hits = m.recall("martin age")
            self.assertTrue(hits and "28" in hits[0]["text"])


class TestAgent(unittest.TestCase):
    def test_repair_loop_shows_clean_answer(self):
        with tempfile.TemporaryDirectory() as td:
            a = Agent(memory_path=os.path.join(td, "m.jsonl"), canon_path=CANON)
            out = a.run("Draft a status line about Martin")
            self.assertTrue(out["shown"])
            self.assertEqual(out["violations"], [])
            self.assertIn("28", out["answer"])


if __name__ == "__main__":
    unittest.main()
