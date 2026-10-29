# Hermes Personal AI

**Track:** Nebius x NVIDIA Global AI Hackathon — Personal AI · **Team:** GoalWorld (Nico Del Bello Pez Dorado)

A personal AI agent that never breaks its own canon. `hermes-personal-ai` is the open-source core of the **Hermes agent fleet** (10 role profiles running 24/7 on a VPS): it answers with persistent memory and — the part that makes it *personal* — a **CanonGuard** that verifies every generated answer against the user's own ground truth before it is shown, and repairs it when it drifts.


[![Live demo](https://img.shields.io/badge/demo-live-brightgreen)](https://goalworld.fun/hermes-demo/) [![Video](https://img.shields.io/badge/video-YouTube-red)](https://youtu.be/4PknV8iASQQ) [![Runtime](https://img.shields.io/badge/runtime-Nebius%20Token%20Factory-blue)](https://api.tokenfactory.nebius.com) [![Model](https://img.shields.io/badge/model-NVIDIA%20Nemotron%203%20Super-76B900)](#) [![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

## At a glance (for judges)

- **Try it (no login):** https://goalworld.fun/hermes-demo/ · recorded proof run: https://goalworld.fun/hermes-demo/proof
- **Video (<3 min):** https://youtu.be/4PknV8iASQQ
- **Runtime:** every demo call goes to Nebius Token Factory; default model **** (see ). Token Factory request ids are printed in the demo and logged in .
- **What to watch for:** a draft that leaks "As an AI..." gets caught by CanonGuard and repaired before you see it.
- **Evidence:** , , .

> Note: the "Real results" log below is an earlier run (2026-10-22) on , also on Token Factory. The current default is NVIDIA Nemotron 3 Super.

## Problem

Personal AI assistants hallucinate about *you*: wrong names, invented dates, confident fiction about your own life. On a team of autonomous agents this gets worse — every agent can invent its own version of the truth.

## What it does

1. **Memory**: a persistent JSONL memory store (facts, decisions, preferences) with keyword+recency recall — the agent's long-term personal state, inspectable and editable by the user as plain files.
2. **CanonGuard** (ported from *Living Canon*, our AMD ACT III project): deterministic rules compiled from a `canon.json` the user authors — protected facts, banned claims, required qualifiers. Every generated answer is checked *before* display.
3. **Repair loop**: on a violation the agent is asked to fix only the flagged claims; rules re-run; remaining violations are shown to the user (no hidden failures).
4. **AUTOIMPROVE-lite**: after each task the agent appends a self-critique line to memory, so the same mistake is caught by the guard next time.

## Real results (live, Nebius Token Factory)

Actual run output (`./run_live.sh`, 2026-10-22), model **`NousResearch/Hermes-4-405B`** on `https://api.tokenfactory.nebius.com/v1`:

```
=== Scenario 1: answer grounded in persistent memory ===
[S1] DRAFT: 'Martin, 28, successfully shipped the parser on 2026-10-20.'
[S1] CanonGuard: 0 violations (clean)  -> shown

=== Scenario 2: messy draft leaks a banned phrase -> guard + repair ===
[S2] DRAFT: 'As an AI, I am pleased to report that Martin shipped the parser today.'
[S2] CanonGuard CAUGHT 1 violation: banned claim: no corporate filler voice ('as an ai')
[S2] FINAL: 'I am pleased to report that Martin shipped the parser today.'  -> shown
```

The agent answers from memory, and CanonGuard both **verifies** clean answers and **repairs** violations before display. `python3 -m unittest discover -s tests -v` → 5 tests, all passing (`OK`).

## Open Agent Hackathon 2026 extension (branch `hackathon/open-agent`)

This project was brought to the **Wildcard [Tinkerer]** track of the
[Open Agent Hackathon 2026](https://hackathon.genai.works/event/open-agent-hackathon-2026)
and extended with sponsor technology (new work only — see `HACKATHON.md` for
the pre-existing vs new provenance):

- **Meterless H-MEM** (`hmem/`): hierarchical memory engine implemented from
  Meterless's H-MEM spec — provenance, hybrid retrieval ranking, feedback
  deltas, 17-action audit ledger, sleep/dream cycles, conflict resolution.
  **13/13 checks pass** on Meterless's own conformance suite
  (`proofs/meterless-hmem-conformance.txt`).
- **NVIDIA Nemotron** (`planner.py`): the agent's reasoning core — plans every
  task over recalled memories before answering and drafts the dream insights
  its memory later approves. Free tier (`nemotron-3-ultra-550b-a55b:free`),
  every call metered with append-only receipts (`proofs/nemotron-receipts.jsonl`).
- **Zetaris** (federated data layer): pending sponsor credentials — planned
  integration documented in `HACKATHON.md`.

Run the live extension demo (needs the local OmniRoute gateway; the key is
loaded at runtime and never printed): `./run_hackathon_demo.sh`.
Submission draft: `SUBMISSION_DRAFT.md`.

## Setup & Run

```bash
# 1) Offline demo (mock provider, no API key needed)
python3 demo.py

# 2) Tests
python3 -m unittest discover -s tests -v

# 3) LIVE demo on Nebius Token Factory (OpenAI-compatible)
#    Get a key at https://tokenfactory.nebius.com/ then either:
cp .env.example .env          # and fill in NEBIUS_API_KEY  (gitignored)
#    or, recommended — load the key from a secure file at runtime (never echoed):
./run_live.sh                 # reads /data/secrets/nebius_api_key by default
```

`run_live.sh` sets `NEBIUS_API_KEY` from a secure file (override path with `NEBIUS_KEY_FILE`) and runs `demo_live.py`. The key is **never** printed or committed. Configuration is via env vars (`HERMES_LLM_PROVIDER`, `HERMES_LLM_MODEL`, `HERMES_LLM_BASE_URL`) — see `.env.example`. Any OpenAI-compatible endpoint works.

## Architecture

`agent.py` (task loop) → `llm.py` (mock | OpenAI-compatible client, base URL + model via env) → `guard.py` (CanonGuard: deterministic rules over `canon.json`) → `memory.py` (JSONL store, keyword+recency recall) → output, with a repair pass on violations.

## Responsible use

No API keys in the repo (env vars / a secure key file only). Memory is plain local files — the user owns and can delete it. MIT licensed.

## Status & next (for Devpost)

- [x] Core loop (memory + CanonGuard + repair) working, tests green
- [x] Offline demo with recorded output
- [x] **Live demo on Nebius Token Factory inference** (`NousResearch/Hermes-4-405B`)
- [x] 3-min demo video script (`VIDEO_SCRIPT.md`)
- [ ] Record VO / produce the demo video
- [ ] Publish public GitHub repo (secret scan clean → awaiting maintainer's OK)
