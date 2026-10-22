# Hermes Personal AI

**Track:** Nebius x NVIDIA Global AI Hackathon — Personal AI · **Team:** GoalWorld (Nico Del Bello Pez Dorado)

A personal AI agent that never breaks its own canon. `hermes-personal-ai` is the open-source core of the **Hermes agent fleet** (10 role profiles running 24/7 on a VPS): it answers with persistent memory and — the part that makes it *personal* — a **CanonGuard** that verifies every generated answer against the user's own ground truth before it is shown, and repairs it when it drifts.

## Problem

Personal AI assistants hallucinate about *you*: wrong names, invented dates, confident fiction about your own life. On a team of autonomous agents this gets worse — every agent can invent its own version of the truth.

## What it does

1. **Memory**: a persistent JSONL memory store (facts, decisions, preferences) with keyword+recency recall — the agent's long-term personal state, inspectable and editable by the user as plain files.
2. **CanonGuard** (ported from *Living Canon*, our AMD ACT III project): deterministic rules compiled from a `canon.json` the user authors — protected facts, banned claims, required qualifiers. Every generated answer is checked *before* display.
3. **Repair loop**: on a violation the agent is asked to fix only the flagged claims; rules re-run; remaining violations are shown to the user (no hidden failures).
4. **AUTOIMPROVE-lite**: after each task the agent appends a self-critique line to memory, so the same mistake is caught by the guard next time.

## Real results (offline, mock provider)

Actual run output (`python3 demo.py`, 2026-10-21):

```
[1] user task: 'Draft a status line about Martin'
[1] final: 'Martin (28) shipped the parser today.'  shown=True violations=0
[2] memory recall('martin age') ->
    task: Draft a status line about Martin -> answer ok
    Martin shipped the parser on 2026-10-20
    Martin is 28 (canon, fixed 2026-10-05)
```

The mock provider deliberately drafts `Martin (19)` first; CanonGuard flags the age violation and the repair pass fixes it to `28` before display (5 unit tests cover this path).

`python3 -m unittest discover -s tests -v` → 5 tests, all passing (`OK`).

## Run

```bash
python3 demo.py                      # offline demo, no API key needed (mock provider)
python3 -m unittest discover -s tests -v

# Live LLM (OpenAI-compatible; Nebius AI Studio by default):
export HERMES_LLM_PROVIDER=nebius
export NEBIUS_API_KEY=...            # never commit keys; .env is gitignored
python3 demo.py
```

## Architecture

`agent.py` (task loop) → `llm.py` (mock | OpenAI-compatible client, base URL + model via env) → `guard.py` (CanonGuard: deterministic rules over `canon.json`) → `memory.py` (JSONL store, keyword+recency recall) → output, with a repair pass on violations.

## Responsible use

No API keys in the repo (env vars only). Memory is plain local files — the user owns and can delete it. MIT licensed.

## Status & next (for Devpost)

- [x] Core loop (memory + CanonGuard + repair) working, tests green
- [x] Offline demo with recorded output
- [ ] Live demo on Nebius inference (needs the $25 promo code redeemed — pending login)
- [ ] 3-min demo video (script + VO)
- [ ] Public GitHub repo (secret scan first, then Nico's OK to publish)
