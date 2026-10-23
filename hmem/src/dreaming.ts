// DreamingService — constructive synthesis with a human approval boundary
// (spec section 7). dream() only proposes; nothing becomes durable memory
// until approve() runs. Insight text can be model-drafted upstream (the
// agent pipeline lets NVIDIA Nemotron rewrite proposals); the engine itself
// stays model-free and deterministic.

import type { DreamProposal, DreamProposalType, MemoryRecord } from "./types.ts";
import { DEFAULTS } from "./types.ts";
import { cosine, jaccard } from "./text.ts";
import type { MemoryStoreService } from "./store.ts";
import type { TrustLedger } from "./ledger.ts";

export class DreamingService {
  proposals: DreamProposal[] = [];
  private seq = 0;
  private store: MemoryStoreService;
  private ledger: TrustLedger;
  private clock: () => number;
  private actor: string;
  private materialize: (input: {
    content: string;
    source: string;
    layer: "short_term" | "working" | "long_term";
    type: "personal" | "factual" | "preference" | "general";
    derivedFrom: string[];
    provenanceOrigin: "dream";
    provenanceLabel: string;
  }) => MemoryRecord;

  constructor(
    store: MemoryStoreService,
    ledger: TrustLedger,
    clock: () => number,
    actor: string,
    materialize: (input: {
      content: string;
      source: string;
      layer: "short_term" | "working" | "long_term";
      type: "personal" | "factual" | "preference" | "general";
      derivedFrom: string[];
      provenanceOrigin: "dream";
      provenanceLabel: string;
    }) => MemoryRecord,
  ) {
    this.store = store;
    this.ledger = ledger;
    this.clock = clock;
    this.actor = actor;
    this.materialize = materialize;
  }

  // Multi-signal relatedness (spec section 7.1): content similarity, tag
  // overlap, shared domain, entity overlap.
  private relatedness(a: MemoryRecord, b: MemoryRecord): number {
    return (
      0.5 * Math.max(0, cosine(a.embedding, b.embedding)) +
      0.2 * jaccard(a.tags, b.tags) +
      0.1 * (a.domain === b.domain ? 1 : 0) +
      0.2 * jaccard(a.entities, b.entities)
    );
  }

  private cluster(): MemoryRecord[][] {
    const all = this.store.all();
    const used = new Set<string>();
    const clusters: MemoryRecord[][] = [];
    for (const seed of all) {
      if (used.has(seed.id)) continue;
      const group = [seed];
      for (const other of all) {
        if (other.id === seed.id || used.has(other.id)) continue;
        if (this.relatedness(seed, other) >= DEFAULTS.dreamRelatedness) group.push(other);
      }
      if (group.length >= DEFAULTS.dreamClusterMinSize) {
        for (const g of group) used.add(g.id);
        clusters.push(group);
      }
    }
    return clusters;
  }

  dream(): DreamProposal[] {
    const created: DreamProposal[] = [];
    const propose = (type: DreamProposalType, content: string, derivedFrom: string[], suggestedDomain?: string) => {
      const count = created.filter((p) => p.type === type).length;
      if (count >= DEFAULTS.maxDreamProposalsPerType) return;
      const proposal: DreamProposal = {
        id: `dream-${++this.seq}`,
        type,
        content,
        derivedFrom,
        suggestedDomain,
        status: "proposed",
      };
      created.push(proposal);
      this.proposals.push(proposal);
      for (const src of derivedFrom) {
        this.ledger.log(src, "dream_proposed", this.actor, this.clock(), {
          details: { proposalId: proposal.id, type },
        });
      }
    };

    // Phase 3: insights from clusters.
    for (const cluster of this.cluster()) {
      const domain = cluster[0].domain;
      propose(
        "insight",
        `Synthesis of ${cluster.length} related memories in ${domain}: ${cluster.map((m) => m.content).join(" | ")}`,
        cluster.map((m) => m.id),
      );
    }

    // Phase 5: invariants from preference / personal / correction signals.
    for (const m of this.store.all()) {
      const signal = m.type === "preference" || m.type === "personal" || m.provenance.origin === "user_correction";
      if (signal) propose("invariant", `Invariant (from ${m.type} signal): ${m.content}`, [m.id]);
    }

    // Phase 4: domain suggestions from uncategorized general memories.
    for (const m of this.store.all()) {
      if (m.type === "general" && m.domain === "general") {
        const hint = m.tags.find((t) => t.includes(":"));
        if (hint) propose("domain", `Reclassify "${m.content.slice(0, 60)}" as ${hint}`, [m.id], hint);
      }
    }

    this.store.persist();
    return created;
  }

  approve(proposalId: string, contentOverride?: string): MemoryRecord | undefined {
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p || p.status !== "proposed") return undefined;
    p.status = "approved";
    if (contentOverride) p.content = contentOverride;

    if (p.type === "domain") {
      for (const src of p.derivedFrom) {
        const m = this.store.get(src);
        if (m && p.suggestedDomain) {
          m.domain = p.suggestedDomain;
          m.namespace = p.suggestedDomain.includes(":") ? p.suggestedDomain.replace(":", "/") : m.namespace;
        }
      }
      this.ledger.log(p.derivedFrom[0] ?? "*", "dream_approved", this.actor, this.clock(), {
        details: { proposalId: p.id, type: p.type },
      });
      this.store.persist();
      return undefined;
    }

    // insight -> long-term factual; invariant -> long-term preference
    // (spec section 7.4). Always carries derivedFrom lineage.
    const record = this.materialize({
      content: p.content,
      source: "dreaming",
      layer: "long_term",
      type: p.type === "invariant" ? "preference" : "factual",
      derivedFrom: [...p.derivedFrom],
      provenanceOrigin: "dream",
      provenanceLabel: `approved ${p.type} proposal ${p.id}`,
    });
    this.ledger.log(record.id, "dream_approved", this.actor, this.clock(), {
      details: { proposalId: p.id, type: p.type },
    });
    this.store.persist();
    return record;
  }

  reject(proposalId: string): boolean {
    const p = this.proposals.find((x) => x.id === proposalId);
    if (!p || p.status !== "proposed") return false;
    p.status = "rejected";
    this.ledger.log(p.derivedFrom[0] ?? "*", "dream_rejected", this.actor, this.clock(), {
      details: { proposalId: p.id },
    });
    return true;
  }
}
