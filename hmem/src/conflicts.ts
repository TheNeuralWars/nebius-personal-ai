// ConflictDetectionService — contradiction scanning and gated auto-resolution
// (spec section 10). Detection uses opposing phrase pairs and conflicting
// numeric values on similar content; resolution keeps both records and marks
// the loser supersededBy (penalized in ranking, never deleted).

import type { ConflictRecord, MemoryRecord } from "./types.ts";
import { DEFAULTS, clamp01 } from "./types.ts";
import { cosine } from "./text.ts";
import type { MemoryStoreService } from "./store.ts";
import type { TrustLedger } from "./ledger.ts";
import { snapshot } from "./ledger.ts";

const OPPOSING_PAIRS: Array<[RegExp, RegExp]> = [
  [/\balways\b/, /\bnever\b/],
  [/\benable\b/, /\bdisable\b/],
  [/\ball\b/, /\bnone\b/],
  [/\bincrease\b/, /\bdecrease\b/],
  [/\ballow\b/, /\bdeny\b/],
  [/\bstart\b/, /\bstop\b/],
  [/\binclude\b/, /\bexclude\b/],
  [/\bkeep\b/, /\bdelete\b/],
  [/\bmust\b/, /\bmust not\b/],
  [/\bon\b/, /\boff\b/],
];

export class ConflictDetectionService {
  conflicts: ConflictRecord[] = [];
  private seq = 0;
  private store: MemoryStoreService;
  private ledger: TrustLedger;
  private clock: () => number;
  private actor: string;

  constructor(
    store: MemoryStoreService,
    ledger: TrustLedger,
    clock: () => number,
    actor: string,
  ) {
    this.store = store;
    this.ledger = ledger;
    this.clock = clock;
    this.actor = actor;
  }

  scan(): ConflictRecord[] {
    const all = this.store.all();
    const found: ConflictRecord[] = [];
    for (let i = 0; i < all.length; i++) {
      for (let j = i + 1; j < all.length; j++) {
        const c = this.check(all[i], all[j]);
        if (c) {
          this.conflicts.push(c);
          found.push(c);
          this.ledger.log(c.memoryA, "conflict_detected", this.actor, this.clock(), {
            details: { with: c.memoryB, reason: c.reason, confidence: c.confidence },
          });
        }
      }
    }
    this.store.persist();
    return found;
  }

  private check(a: MemoryRecord, b: MemoryRecord): ConflictRecord | undefined {
    // supersedes relation suppresses conflict: an intended replacement.
    if (a.supersedes === b.id || b.supersedes === a.id || a.supersededBy === b.id || b.supersededBy === a.id) {
      return undefined;
    }

    const sim = Math.max(0, cosine(a.embedding, b.embedding));
    let reason = "";
    let confidence = 0;

    for (const [p, q] of OPPOSING_PAIRS) {
      if ((p.test(a.content) && q.test(b.content)) || (q.test(a.content) && p.test(b.content))) {
        if (sim > 0.5) {
          reason = "opposing phrase pair on similar content";
          confidence = 0.5 + 0.3 * sim;
        }
      }
    }
    if (!reason && sim > 0.8) {
      const numsA = a.content.match(/\d+(\.\d+)?/g) ?? [];
      const numsB = b.content.match(/\d+(\.\d+)?/g) ?? [];
      if (numsA.length && numsB.length && numsA.join() !== numsB.join()) {
        reason = "high-similarity conflicting numeric values";
        confidence = 0.55 + 0.25 * sim;
      }
    }
    if (!reason) return undefined;

    // Confidence modifiers (spec section 10.1).
    const sharedEntities = a.entities.filter((e) => b.entities.includes(e));
    if (sharedEntities.length > 0) confidence += 0.1;
    if (a.domain === b.domain) confidence += 0.05;
    if (a.relatedTo.includes(b.id)) confidence -= 0.1; // explicit relation lowers false positives

    return {
      id: `conflict-${++this.seq}`,
      memoryA: a.id,
      memoryB: b.id,
      reason,
      confidence: clamp01(confidence),
      resolved: false,
    };
  }

  // Weighted auto-decision heuristics (spec section 10.2): recency, access
  // frequency, confidence, content richness and source reliability combine
  // into a per-record score; the decision confidence blends the detection
  // confidence with the relative margin between the two candidates.
  autoResolve(conflict: ConflictRecord): "resolved" | "queued" {
    const a = this.store.get(conflict.memoryA);
    const b = this.store.get(conflict.memoryB);
    if (!a || !b) return "queued";

    const scoreOf = (m: MemoryRecord) =>
      0.3 * (m.lastAccessed / Math.max(1, this.clock())) +
      0.2 * Math.min(1, m.accessCount / 10) +
      0.25 * m.confidence +
      0.1 * Math.min(1, m.content.length / 200) +
      0.15 * (m.provenance.origin === "user_correction" ? 1 : 0.5);

    const sa = scoreOf(a);
    const sb = scoreOf(b);
    const margin = Math.abs(sa - sb) / Math.max(sa, sb);
    const decisionConfidence = clamp01(conflict.confidence * 0.6 + margin * 0.8);

    if (decisionConfidence < DEFAULTS.conflictAutoResolveGate) return "queued";

    const winner = sa >= sb ? a : b;
    const loser = sa >= sb ? b : a;
    const prev = snapshot(loser);
    loser.supersededBy = winner.id; // kept and penalized, never deleted
    conflict.resolved = true;
    conflict.resolution = winner.id === conflict.memoryA ? "keep_a" : "keep_b";
    this.ledger.log(loser.id, "conflict_resolved", this.actor, this.clock(), {
      previousState: prev,
      newState: snapshot(loser),
      details: { conflictId: conflict.id, winner: winner.id, decisionConfidence: Number(decisionConfidence.toFixed(3)) },
    });
    this.store.persist();
    return "resolved";
  }

  queue(): ConflictRecord[] {
    return this.conflicts.filter((c) => !c.resolved);
  }
}
