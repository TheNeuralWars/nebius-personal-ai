# VIDEO SCRIPT — Open Agent Hackathon 2026 (Wildcard [Tinkerer])

Hermes Personal AI demo · ~2:06 · English · AI voice-over (ElevenLabs, voice "George",
eleven_multilingual_v2) + terminal screencast rendered from REAL proof outputs in `proofs/`.
Final file: `Hermes_Personal_AI_demo.mp4` (1920x1080, H.264 + AAC). AI-generated voice: label as AI media.

| Time | Screen (SC) | Voice-over (VO) |
|---|---|---|
| 0:00 | Title card: Hermes Personal AI · sponsors | Personal AI agents forget, contradict themselves, and can't tell you where an answer came from. Hermes Personal AI is different: it remembers why it knows. Every answer is planned, grounded, audited, and corrected before you ever see it. |
| 0:17 | Architecture: H-MEM recall → Nemotron plan → Zetaris SQL → generate → CanonGuard → receipts | Here's the idea. Memory is Meterless H-MEM: hybrid retrieval with provenance, feedback deltas, an append-only audit ledger, and sleep and dream cycles. A canon of protected facts, CanonGuard, repairs any draft that violates it. And NVIDIA Nemotron is the reasoning core: it plans every answer before generation. |
| 0:40 | `run_hackathon_demo.sh` output A1–A3 + conformance 13/13 (`proofs/hackathon-demo-output.txt`, `proofs/meterless-hmem-conformance.txt`) | This is a real run. H-MEM captures memories with provenance and ranks them. Helpful feedback moves confidence by exactly the spec's delta, and lands in the ledger. A contradiction is detected and auto-resolved, with nothing deleted. And we didn't just claim compatibility: Meterless's own conformance suite passes thirteen out of thirteen checks. |
| 1:03 | Zetaris REST query over NY_TAXI.customers (columns trimmed) + JDBC probe (`proofs/zetaris-federated-query.txt`) — no credentials on screen | Next, data. The Nemotron planner decides whether to federate, and writes read-only SQL over Zetaris Lightning. Here are real rows from the NY Taxi dataset, returned through the Zetaris SQL Query API. The agent joins those rows with its H-MEM memories in one provenance-labelled grounding block. |
| 1:25 | `proofs/nemotron-receipts.jsonl`: 3 request ids, latency, tokens, $0.00 + final answer | And the agent knows what it spent. Every Nemotron call writes an append-only Meterless receipt: request id, model, purpose, latency, tokens, and cost. Here are the three real calls from this demo: a dream insight, a plan, and the generation. Total cost: zero dollars, and no credentials ever logged. |
| 1:48 | Close card: repo URL, branch, sponsors | Hermes Personal AI: Meterless memory, Nemotron reasoning, Zetaris data, all inside a canon-guarded loop. The code is open on GitHub, at github.com/TheNeuralWars/nebius-personal-ai, branch hackathon/open-agent. Thanks for watching. |

Note: Zetaris runs amd64-emulated on the ARM VPS (queries take 5–65 s), so the video shows the captured real output rather than a live wait.
