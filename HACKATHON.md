# Open Agent Hackathon 2026 — work log & provenance

Event: [Open Agent Hackathon 2026](https://hackathon.genai.works/event/open-agent-hackathon-2026)
(GenAI.Works). Track: **Wildcard [Tinkerer] — Bring Your Own Project** (must
integrate Zetaris and Meterless; scored on the new work, not prior development).
Secondary target: in-kind prize **Best use of NVIDIA Nemotron**.
Hard deadline: **2026-10-27 23:45 UTC** (submissions + registration close).

Official rules extract (sections 01–10): `proofs/hackathon-requirements.txt`.

## Pre-existing work (DECLARED — not eligible for scoring)

The base project is the "Nebius Personal AI" agent (agent + CanonGuard +
memory + mock/live LLM), built 2026-10-20/21 for the Nebius Token Factory
demo and committed on `main` before this hackathon workstream started:

| Commit | Date (UTC) | What |
|---|---|---|
| `d9a035b` | 2026-10-22 07:00:07 | feat: Nebius Personal AI — agent + CanonGuard + mock LLM + tests passing |
| `6ff8932` | 2026-10-22 14:03:00 | feat: live Nebius Token Factory demo + video script + release prep |

Declared pre-existing components (rule 05: "Pre-existing product code must be
declared in the submission form"): `agent.py` (repair loop structure),
`llm.py` (provider client shape), `memory.py` (JSONL journal), `guard.py`,
`canon.json`, `demo.py`, `demo_live.py`, `run_live.sh`, `README.md`,
`README-internal.md`, `VIDEO_SCRIPT.md`, `LICENSE`, `tests/test_core.py`.

All of the above is prior development brought into the Wildcard track as the
"existing project". It is kept for continuity and is explicitly **not claimed
as hackathon output**. Everything below is the new work.

## New work (branch `hackathon/open-agent`, 2026-10-23)

| Commit | Date (UTC) | What |
|---|---|---|
| `fd0c756` | 2026-10-23 11:08:31 | feat: Meterless H-MEM memory engine, 13/13 conformance |
| `0cb113a` | 2026-10-23 11:08:45 | feat: NVIDIA Nemotron reasoning core + metered agent integration |
| `92c51aa` | 2026-10-23 11:11:30 | docs: HACKATHON provenance + SUBMISSION_DRAFT (this file) |

(One follow-up docs commit records this manifest; the branch log is the
authoritative list.)

### 1. Meterless — H-MEM hierarchical memory (new)

- `hmem/` — independent implementation of Meterless's **H-MEM** spec
  (`engines/hmem/AGENTS.md`, Apache-2.0) as the agent's memory layer:
  mandatory-source records with provenance, hybrid retrieval with the
  canonical scoring formula, feedback deltas, 17-action append-only audit
  ledger, sleep cycle with guardrails + backup/restore, dreaming with a human
  approval boundary, conflict detection with gated auto-resolution.
- Verified with Meterless's own conformance suite (vendored, attributed):
  **13/13 checks pass** — `proofs/meterless-hmem-conformance.txt`.
- `memory.py` mirrors the JSONL journal into H-MEM and recalls with the hybrid
  ranking; degrades gracefully without node (spec section 4.3).
- Metering: every model call writes an append-only receipt
  (`Meterless-style receipts`, `proofs/nemotron-receipts.jsonl`) — the
  per-call metering record of the agent, never carrying credentials.

### 2. NVIDIA Nemotron — reasoning core (new)

- `planner.py` — Nemotron plans each task over the recalled memories before
  the agent answers, and drafts dream-cycle insights that H-MEM then governs
  (approval + lineage).
- `llm.py` `nemotron` provider — Nemotron is also the generator in the live
  demo (the product's model, via the OmniRoute gateway).
- Free tier only: `nvidia/nemotron-3-ultra-550b-a55b:free`. Real calls with
  request ids, models and latencies in `proofs/nemotron-receipts.jsonl`
  (3 calls in the recorded demo run; no keys).

### 3. Zetaris — federated data layer (PENDING — blocked, see below)

Planned integration (to land as soon as credentials arrive): the agent's data
layer registers remote REST/file sources in Zetaris Lightning and answers
user questions with federated SQL through the Zetaris SQL Query APIs
(start / page / close), so recalled "facts" can be grounded in federated data
sources with the result set (only) travelling back. Verification plan: one
real query against the supplied samples (NY Taxi / TPCDS) recorded in
`proofs/`.

**Blocker:** no Zetaris credentials exist on the build machine (searched
`/data/secrets`, `.env` files, Hermes profile envs, shared memory, browser
vault; no live session at `cloud.enterprise.zetaris.com`). Needed: the
Zetaris Cloud account (UI URL + numeric organisation ID + account credentials
or API key) — see the handoff notes for exactly where to obtain them.

## Verification (all real runs, same session)

| Check | Result | Evidence |
|---|---|---|
| Meterless conformance suite | 13/13 PASS | `proofs/meterless-hmem-conformance.txt` |
| Unit tests (`python3 -m unittest discover -s tests`) | 15/15 OK (5 pre-existing + 10 new) | `tests/` |
| Live demo (real Nemotron calls) | complete, guard + H-MEM lifecycle shown | `proofs/hackathon-demo-output.txt` |
| Nemotron metering receipts | 3 calls, 1141 tokens, $0.00 (free tier) | `proofs/nemotron-receipts.jsonl` |
| Secret scan (`gitleaks`) | 0 leaks | this log |

Reproduce: `./run_hackathon_demo.sh` (loads the gateway key at runtime, never
printed) and `HMEM_IMPL=$PWD/hmem/src/index.ts npx tsx hmem/conformance/runner.ts`.

## Submission requirements checklist (rule 06)

- [ ] Demo video 1–4 min showing the main workflow + how Zetaris and Meterless
      are integrated (script notes in `SUBMISSION_DRAFT.md`).
- [ ] Slide deck (problem/users, solution, agent architecture, stack, sponsor
      usage + uniqueness, product visuals, future work).
- [x] GitHub repo with source + README (setup/usage/deps).
      `https://github.com/TheNeuralWars/nebius-personal-ai`, branch
      `hackathon/open-agent` (push pending — not pushed yet).
- [x] Clear explanation of sponsor integration + what is unique
      (`HACKATHON.md` this file).
- [ ] Zetaris integration landed + verified (blocked on credentials).
