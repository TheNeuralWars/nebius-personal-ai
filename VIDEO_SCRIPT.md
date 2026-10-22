# Demo Video Script — Hermes Personal AI
### ~3 minutes · English · Nebius x NVIDIA Global AI Hackathon

> Target length: ~3:00 at ~150 wpm (~450 spoken words) + demo screencast beats.
> VO = voice-over. SC = on-screen. Bracketed notes are for the editor, not spoken.

---

## [0:00–0:25] THE PROBLEM

**SC:** Black screen. Quick montage of chat UIs confidently stating wrong facts.

**VO:**
"Your personal AI is supposed to know *you*. Instead, it hallucinates about you —
the wrong name, an invented date, confident fiction about your own life.
On a team of autonomous agents it gets worse: every agent invents its own version
of the truth. I'm Nico from GoalWorld, and this is **Hermes Personal AI** —
an agent that never breaks its own canon."

---

## [0:25–0:55] THE IDEA

**SC:** Logo + one-line: "Memory · CanonGuard · Repair."

**VO:**
"Hermes Personal AI has three parts.
First, **persistent memory** — plain, inspectable files the user owns.
Second, **CanonGuard** — deterministic rules compiled from a `canon.json` the user authors:
protected facts, banned claims, required qualifiers.
Third, a **repair loop** — before any answer is shown, CanonGuard verifies it against
your ground truth and, if it drifted, asks the model to fix only the flagged claims.
Nothing unverified ever reaches you."

---

## [0:55–2:15] LIVE DEMO (screen recording)

**SC:** Terminal. `./run_live.sh`. Real Nebius Token Factory inference — show the model name
`NousResearch/Hermes-4-405B` in the header.

**VO (over Scenario 1):**
"Let's watch it live on real Nebius inference. I've stored two facts in memory:
Martin is twenty-eight — that's canon — and he shipped the parser on October twentieth.
Now I ask for a status line."

**SC:** S1 draft + final: *"Martin, 28, successfully shipped the parser on 2026-10-20."*
CanonGuard: **0 violations (clean)** → shown.

**VO:**
"It answered from memory, and CanonGuard verified it — clean, so it's shown."

**VO (over Scenario 2):**
"Now the interesting case. I hand it a messy draft that leaks corporate filler —
'As an AI, I am pleased to report…'. A naive assistant would publish that."

**SC:** S2 draft: *"As an AI, I am pleased to report that Martin shipped the parser today."*
CanonGuard **CAUGHT 1 violation** — `banned claim: no corporate filler voice ('as an ai')`.
Repair runs. FINAL: *"I am pleased to report that Martin shipped the parser today."*

**VO:**
"CanonGuard catches it before display, the repair pass strips only the violation,
and the clean line is shown. Same model, same prompt — the canon is what makes it *yours*."

---

## [2:15–2:45] WHY IT MATTERS

**SC:** Split screen: "hallucinating assistant" vs "canon-guarded agent."

**VO:**
"This is the core of the Hermes fleet — ten role profiles running twenty-four-seven
on a VPS. Every answer, from every agent, is checked against the same canon before
it's shown. No hidden failures: if something can't be repaired, you see it, not a
confident lie."

---

## [2:45–3:00] CLOSE

**SC:** Repo URL · "Open source · MIT" · Nebius Token Factory logo · Devpost.

**VO:**
"Hermes Personal AI is open source on Nebius Token Factory — memory you own,
a guard you author, and answers you can trust.
I'm Nico. Thanks for watching."

---

## Production notes
- The live run is `./run_live.sh` (loads the API key at runtime; the key is never on screen).
- Real model used: `NousResearch/Hermes-4-405B` on `https://api.tokenfactory.nebius.com/v1`.
- Keep the CanonGuard "CAUGHT" lines visible — that's the money shot.
- B-roll: `python3 -m unittest discover -s tests -v` → "5 tests OK".
