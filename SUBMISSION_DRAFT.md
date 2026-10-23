# SUBMISSION DRAFT — Open Agent Hackathon 2026 (Wildcard [Tinkerer])

Status: DRAFT (nothing submitted). Map 1:1 onto the platform's submission
form when submitting. Hard deadline 2026-10-27 23:45 UTC.

## Title

Hermes Personal AI — the agent that remembers why it knows

## Tagline

Canon-guarded personal AI with Meterless H-MEM memory and a NVIDIA Nemotron
reasoning core: every answer is planned, grounded, audited — and corrected.

## Track

Primary: **Wildcard [Tinkerer] — Bring Your Own Project** (extends the
existing Nebius Personal AI agent with sponsor technology; scored on the new
work). Cross-entry for the in-kind prize **Best use of NVIDIA Nemotron**.

## Team

Solo entry — Nico (team locks at first submission on the platform; platform
account identity to be confirmed at submission time).

## Short description (form field, ~500 chars)

Hermes Personal AI is a personal agent with a canon of protected facts and a
repair loop that never shows a violating answer. For this hackathon we gave it
two sponsor superpowers: a production-grade memory (Meterless H-MEM: hybrid
retrieval with provenance, feedback deltas, audit ledger, sleep/dream cycles,
conflict resolution — implemented from the spec, 13/13 on Meterless's own
conformance suite) and a reasoning core (NVIDIA Nemotron plans every answer
before it is generated, and drafts the insights its memory later approves).
Every model call is metered with append-only receipts.

## Long description (form field)

**Problem.** Personal AI agents forget, contradict themselves and cannot
explain where an answer came from. A vector store plus a summarizer surfaces
stale facts, buries corrections and records nothing about why the agent
believes what it believes.

**Solution.** Hermes Personal AI answers only from memory, guarded by a canon
of protected facts (CanonGuard): drafts that violate the canon are repaired
before they are ever shown. For the hackathon we extended it with:

1. **Meterless H-MEM (memory).** New: `hmem/` — an independent implementation
   of Meterless's H-MEM spec as the agent's memory layer. Records carry
   mandatory source + provenance and live in a knowledge graph; retrieval uses
   the spec's hybrid formula (semantic, keyword, tag, domain, entity, layer,
   recency, superseded penalty × confidence); feedback moves confidence by the
   spec's exact deltas; every mutation lands in a 17-action append-only audit
   ledger; a sleep cycle consolidates/archives with guardrails + backups; a
   dreaming cycle proposes insights that only a human approval materializes
   (with `derivedFrom` lineage); contradictions are detected and auto-resolved
   only above a confidence gate — losers are superseded, never deleted.
   Verified with Meterless's own conformance suite: 13/13 checks pass
   (evidence in the repo, `proofs/meterless-hmem-conformance.txt`).

2. **NVIDIA Nemotron (reasoning).** New: `planner.py` — Nemotron
   (nemotron-3-ultra-550b-a55b, free tier) is the agent's reasoning core: it
   plans the task over recalled memories before generation, drafts the
   dream-cycle insights the memory then governs, and (in the live demo) is the
   generator too. Every call is metered with append-only receipts (request id,
   model, latency, tokens — never credentials): the agent knows what it spent.

3. **Zetaris (data).** New: the agent's data layer runs **federated SQL over
   Zetaris Lightning** (local Zetaris platform, LOCAL mode, loopback only).
   The Nemotron planner decides whether to federate and with which SQL over
   the registered sample datasets (NY_TAXI, TPCDS_DB); a real tool executes
   it (SQL Query API, or JDBC via a tiny Java helper and the licensed
   Lightning driver) and **joins the result rows with the agent's Meterless
   H-MEM memories** in one provenance-labelled grounding block, so every
   statement can cite Zetaris data, memory, or flag a conflict. Read-only SQL
   only; only result rows travel back. Real query output in
   `proofs/zetaris-federated-query.txt`.

**Why the sponsor tech is used this way (uniqueness).** Meterless is not a
drop-in library — it is a spec with a conformance suite, so we implemented the
engine into our own stack and proved correctness with the sponsor's own
runner, then wired the full lifecycle (feedback → confidence → ranking →
dreaming approval → sleep) into the product loop. Nemotron is not a text
generator bolted on the side: it is the step the agent takes *before*
answering, and the memory system audits and meters everything it does.

**Demo evidence.** Real runs only: conformance scorecard, 15/15 unit tests,
live demo transcript with real Nemotron request ids and latencies
(`proofs/`).

**Future work.** Dream insights on a schedule; multi-user canon profiles;
serving the same loop over an OpenAI-compatible endpoint so any app can use
it; registering custom remote sources in Zetaris beyond the sample datasets.

## Tech used

- Python 3 agent (recall → plan → generate → CanonGuard → repair → self-critique)
- TypeScript (Node >= 22.18, no build step) — Meterless H-MEM engine
- NVIDIA Nemotron 3 Ultra (550B A55B, free tier) via the OmniRoute gateway
- Meterless H-MEM spec + conformance suite (Apache-2.0, vendored runner)
- Zetaris Lightning (federated SQL over NY_TAXI / TPCDS_DB — SQL Query API
  + JDBC driver; local platform install, loopback only)
- JSONL metering receipts (append-only)

## Sponsor usage summary (form field)

- **Meterless:** H-MEM implemented as the memory core (spec sections 2, 6, 7,
  8, 9, 10), conformant 13/13 on the official suite; per-call metering
  receipts in the Meterless trust-ledger spirit. Unique: the whole memory
  lifecycle drives the product loop (feedback deltas move real confidence,
  dreaming needs approval, sleep guardrails protect derived knowledge).
- **NVIDIA Nemotron:** reasoning core (plan-before-answer), dream-insight
  drafter, and demo generator — every call metered with request-id-level
  receipts. Unique: Nemotron is the *step before* the answer, inside a
  guarded loop, not a chat endpoint.
- **Zetaris:** the federated data layer: the Nemotron planner decides the
  federation, the tool runs read-only SQL over the sample datasets and joins
  the rows with H-MEM memory under explicit provenance rules. Unique: data
  grounding with a memory join inside a canon-guarded loop, with only result
  rows travelling back.

## Demo / video script notes (target: 3 min 30 s)

1. (0:00–0:20) Hook: "Your agent forgets. Ours can show its work." Product
   shot: the answer with the canon badge.
2. (0:20–1:10) The loop: user asks about Martin → H-MEM recall with scores +
   provenance → Nemotron plan appears → answer generated → CanonGuard catches
   a violation in the draft → repair → clean answer shown (all real terminal
   output, `proofs/hackathon-demo-output.txt`).
3. (1:10–2:10) Meterless H-MEM lifecycle: feedback 'helpful' (+0.05
   confidence, ledger entry) → contradiction detected (always/never) →
   auto-resolution marks the loser superseded, nothing deleted → dreaming
   (Nemotron drafts the insight) → approval creates a long_term memory with
   lineage → sleep cycle archives the stale note, protects the derived one.
   Conformance scorecard 13/13 on screen.
4. (2:10–2:50) Zetaris federated segment: the Nemotron planner picks the SQL
   over NY_TAXI/TPCDS_DB → real result rows on screen
   (`proofs/zetaris-federated-query.txt`) → the grounding block joins those
   rows with an H-MEM memory, provenance-labelled → metering receipts: 3
   Nemotron calls, ids + latencies + $0.00.
5. (2:50–3:30) Architecture diagram + sponsor logos + what's next.

AI-generated media in the submission carries the platform's AI label.

## Links

- Repo: https://github.com/TheNeuralWars/nebius-personal-ai
- Work branch (must be pushed before submission): `hackathon/open-agent`
- Evidence: `proofs/` (conformance, demo output, metering receipts, rules)
- Provenance & sponsor detail: `HACKATHON.md`

## Checklist of missing items

- [x] Zetaris federated query component landed + verified
      (`proofs/zetaris-*.txt`; local platform install, loopback only).
- [ ] Push `hackathon/open-agent` (not pushed yet, by instruction).
- [ ] Record the 1–4 min demo video (script above).
- [ ] Build the slide deck (structure in the long description).
- [ ] Confirm the platform account identity + team name at submission.
- [ ] Submit before 2026-10-27 23:45 UTC (registration closes same time).
