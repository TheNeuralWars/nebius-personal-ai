"""Persistent JSONL memory with keyword + recency recall."""
import json
import os
import time


class Memory:
    def __init__(self, path):
        self.path = path
        self.entries = []
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.entries.append(json.loads(line))

    def add(self, text, kind="note"):
        entry = {"ts": time.time(), "kind": kind, "text": text}
        self.entries.append(entry)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def recall(self, query, k=3):
        terms = [t for t in query.lower().split() if len(t) > 2]
        scored = []
        for e in self.entries:
            text = e["text"].lower()
            score = sum(1 for t in terms if t in text)
            if score:
                scored.append((score, e["ts"], e))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [e for _, _, e in scored[:k]]
