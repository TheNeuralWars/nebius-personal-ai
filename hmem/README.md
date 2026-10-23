# Meterless H-MEM engine (hmem/)

Hierarchical memory for the Nebius Personal AI agent — an independent
implementation of the **Meterless H-MEM** spec
([Meterless/Meterless](https://github.com/Meterless/Meterless),
`engines/hmem/AGENTS.md`, Apache-2.0), built to pass Meterless's own
conformance suite.

## What it implements

- Canonical memory model with mandatory `source`, provenance, layers,
  confidence and graph links (spec section 2).
- Hybrid retrieval ranking with the canonical formula (section 6.1):
  `raw = 0.35·semantic + 0.20·keyword + 0.10·tag + 0.10·domain + 0.15·entity
  + 0.05·layer + 0.05·recency − 0.20·superseded`, `score = clamp01(raw) × confidence`.
- Feedback adaptation with exact deltas (section 9.2): helpful +0.05,
  not_helpful −0.03, wrong −0.20 (+ `review` tag).
- Append-only audit ledger with the canonical 17 actions (section 9.1).
- Sleep cycle: preview-first, consolidation/archive/synthesis with the
  section 8.2 guardrails and backup/restore.
- Dreaming with a human approval boundary (section 7): proposals never
  materialize before `approve()`, which creates long-term records with
  `derivedFrom` lineage.
- Conflict detection and gated auto-resolution (section 10): losers are marked
  `supersededBy` (penalized in ranking), never deleted.

Service boundaries follow section 11: `store`, `ledger`, `sleep`, `dreaming`,
`conflicts` plus `add/query/feedback` on the `HMEM` facade.

## Layout

| Path | What |
|---|---|
| `src/index.ts` | `HMEM` facade: add / query / feedback + persistence |
| `src/types.ts` | canonical contract + operational defaults |
| `src/text.ts` | dependency-free hashed embeddings + enrichment heuristics |
| `src/{store,ledger,retrieval,sleep,dreaming,conflicts}.ts` | services |
| `src/cli.ts` | JSON stdio CLI used by `hmem_client.py` (Python bridge) |
| `conformance/` | Meterless conformance runner (vendored, Apache-2.0) |

## Verify

```bash
HMEM_IMPL=$PWD/src/index.ts npx tsx conformance/runner.ts
# 13/13 checks passed (see ../proofs/meterless-hmem-conformance.txt)
```

The engine runs directly on Node >= 22.18 (type stripping, no build step):

```bash
echo '{"op":"add","content":"hello","source":"cli"}' | node src/cli.ts
```

## Provenance & license

- Engine: original implementation for this repo, written against the
  Meterless H-MEM spec. Apache-2.0 spec © Meterless.
- `conformance/`: vendored unmodified from Meterless/Meterless
  (Apache-2.0) apart from the attribution header.
- The spec's ambiguity points are resolved the same way Meterless's own
  reference resolves them (conflict decision confidence, sleep guardrails).
