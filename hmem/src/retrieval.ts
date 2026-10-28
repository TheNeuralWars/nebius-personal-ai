// MemoryRetrievalService — hybrid ranking and prompt reinjection
// (spec section 6). The canonical formula:
//
//   raw = 0.35·semantic + 0.20·keyword + 0.10·tag + 0.10·domain
//       + 0.15·entity + 0.05·layer + 0.05·recency − 0.20·superseded
//   score = clamp01(raw) × confidence

import type { MemoryRecord, QueryResult, RetrievedMemory } from "./types.ts";
import { DEFAULTS, DAY_MS, clamp01 } from "./types.ts";
import { contentTokens, cosine, embed, extractEntities, inferDomain, jaccard, topTokens } from "./text.ts";

const LAYER_WEIGHTS: Record<string, number> = { long_term: 1.0, working: 0.8, short_term: 0.6 };

export interface QueryOptions {
  threshold?: number;
  topN?: number;
  now: number;
}

export function scoreRecord(
  queryEmbedding: number[],
  queryTopTokens: string[],
  queryDomain: string,
  queryEntities: string[],
  m: MemoryRecord,
  now: number,
): number {
  const semantic = Math.max(0, cosine(queryEmbedding, m.embedding));
  const keyword = jaccard(queryTopTokens, contentTokens(m.content));
  const tag = jaccard(queryTopTokens, m.tags);
  const domain = m.domain === queryDomain ? 1 : 0;
  const entity = jaccard(queryEntities, m.entities);
  const layer = LAYER_WEIGHTS[m.layer] ?? 0.6;
  const ageDays = Math.max(0, (now - m.lastAccessed) / DAY_MS);
  const recency = Math.exp(-ageDays / DEFAULTS.recencyDays);
  const superseded = m.supersededBy ? 1 : 0;

  const raw =
    0.35 * semantic +
    0.20 * keyword +
    0.10 * tag +
    0.10 * domain +
    0.15 * entity +
    0.05 * layer +
    0.05 * recency -
    0.20 * superseded;
  return clamp01(raw) * clamp01(m.confidence);
}

export function retrieve(query: string, records: MemoryRecord[], opts: QueryOptions): QueryResult {
  const threshold = opts.threshold ?? DEFAULTS.retrievalThreshold;
  const topN = opts.topN ?? DEFAULTS.retrievalTopN;
  const qEmbedding = embed(query);
  const qTokens = topTokens(query, 8);
  const qDomain = inferDomain(query);
  const qEntities = extractEntities(query);

  const scored: RetrievedMemory[] = [];
  const scores: Record<string, number> = {};
  for (const m of records) {
    const score = scoreRecord(qEmbedding, qTokens, qDomain, qEntities, m, opts.now);
    scores[m.id] = Number(score.toFixed(6));
    if (score > threshold) scored.push({ memory: m, relevance: score });
  }
  scored.sort((a, b) => b.relevance - a.relevance);
  const top = scored.slice(0, topN);

  // Reinjection format (spec section 6.2): domain-grouped blocks with layer
  // markers and optional entities, plus trace metadata.
  const byDomain = new Map<string, RetrievedMemory[]>();
  for (const r of top) {
    const list = byDomain.get(r.memory.domain) ?? [];
    list.push(r);
    byDomain.set(r.memory.domain, list);
  }
  const context = [...byDomain.entries()]
    .map(([domain, items]) => {
      const lines = items
        .map((r) => {
          const ents = r.memory.entities.length ? ` [${r.memory.entities.slice(0, 5).join(", ")}]` : "";
          return `- (${r.memory.layer}) ${r.memory.content}${ents} — score ${r.relevance.toFixed(3)}`;
        })
        .join("\n");
      return `[${domain}]\n${lines}`;
    })
    .join("\n");

  return {
    memories: top,
    context,
    trace: {
      retrievalReason: `hybrid ranking over ${records.length} memories (query domain: ${qDomain})`,
      strategy: top.length === 0 ? "minimal" : top.some((r) => r.memory.type === "personal" || r.memory.type === "preference") ? "personal" : "comprehensive",
      scores,
    },
  };
}
