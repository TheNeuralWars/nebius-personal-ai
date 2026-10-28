"""Persistent JSONL memory with Meterless H-MEM retrieval.

The JSONL file stays the durable journal; when node is present every entry is
mirrored into the H-MEM engine (hmem/src, Meterless H-MEM spec) and recall()
uses its hybrid ranking with provenance, confidence and layer signals.
Without node the original keyword + recency recall is used (H-MEM spec
section 4.3: graceful degradation, capture continuity preserved).
"""
import json
import os
import re
import time

from hmem_client import HMemClient

KIND_TYPE = {
    "canon": "factual",
    "event": "factual",
    "task_log": "general",
    "self_critique": "general",
    "user_correction": "personal",
    "note": "general",
}


class Memory:
    def __init__(self, path, use_hmem=True):
        self.path = path
        self.entries = []
        self.hmem = None
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.entries.append(json.loads(line))
        if use_hmem and HMemClient.available():
            self.hmem = HMemClient(path + ".hmem.json")

    def add(self, text, kind="note"):
        entry = {"ts": time.time(), "kind": kind, "text": text}
        if self.hmem is not None:
            try:
                rec = self.hmem.add(
                    text,
                    source=kind,
                    type=KIND_TYPE.get(kind, "general"),
                )
                entry["hmem_id"] = rec["id"]
            except Exception:
                self.hmem = None  # graceful degradation to the journal alone
        self.entries.append(entry)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def recall(self, query, k=3):
        if self.hmem is not None:
            try:
                result = self.hmem.query(query, threshold=0.0, topN=k)
                hits = []
                for r in result["memories"]:
                    entry = self._entry_for(r["memory"]["id"])
                    if entry is not None:
                        entry = dict(entry)
                        entry["score"] = r["relevance"]
                        entry["confidence"] = r["memory"]["confidence"]
                        entry["layer"] = r["memory"]["layer"]
                        hits.append(entry)
                if hits:
                    return hits
            except Exception:
                pass  # fall through to keyword recall
        return self._keyword_recall(query, k)

    def feedback(self, entry, kind):
        """Feed retrieval quality back into H-MEM confidence (spec section 9.2)."""
        if self.hmem is not None and entry.get("hmem_id"):
            return self.hmem.feedback(entry["hmem_id"], kind)
        return None

    def _entry_for(self, hmem_id):
        for e in self.entries:
            if e.get("hmem_id") == hmem_id:
                return e
        return None

    def _keyword_recall(self, query, k=3):
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        scored = []
        for e in self.entries:
            text = e["text"].lower()
            score = sum(1 for t in terms if t in text)
            if score:
                scored.append((score, e["ts"], e))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [e for _, _, e in scored[:k]]
