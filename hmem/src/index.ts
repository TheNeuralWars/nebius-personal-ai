// HMEM — Meterless hierarchical memory engine.
//
// Independent implementation of the H-MEM spec (Meterless/Meterless,
// engines/hmem/AGENTS.md, Apache-2.0) for the Nebius Personal AI agent.
// Service boundaries follow spec section 11:
//   MemoryStoreService / TrustLedgerService / MemoryRetrievalService /
//   DreamingService / SleepCycleService / ConflictDetectionService.
// The 17-action audit ledger (section 9.1) records every mutation.
//
// Conformance: Meterless conformance/runner.ts with HMEM_IMPL pointing at
// this file (see hmem/README.md).

import * as fs from "node:fs";
import * as path from "node:path";

import type {
  FeedbackKind,
  HMEMOptions,
  LedgerAction,
  MemoryLayer,
  MemoryRecord,
  MemoryType,
  ProvenanceOrigin,
  QueryResult,
} from "./types.ts";
import { DEFAULTS, FEEDBACK_DELTAS, clamp01 } from "./types.ts";
import { contentTokens, embed, extractEntities, inferDomain, inferNamespace, jaccard, topTokens } from "./text.ts";
import { TrustLedger, snapshot } from "./ledger.ts";
import { MemoryStoreService } from "./store.ts";
import { retrieve } from "./retrieval.ts";
import { SleepCycleService } from "./sleep.ts";
import { DreamingService } from "./dreaming.ts";
import { ConflictDetectionService } from "./conflicts.ts";

export * from "./types.ts";

interface AddInput {
  content: string;
  source: string;
  type?: MemoryType;
  layer?: MemoryLayer;
  confidence?: number;
  tags?: string[];
  derivedFrom?: string[];
  supersedes?: string;
  chatId?: string;
  missionId?: string;
  goalRunId?: string;
  provenanceOrigin?: ProvenanceOrigin;
  provenanceLabel?: string;
}

const ORIGIN_BY_SOURCE: Record<string, ProvenanceOrigin> = {
  chat: "chat_message",
  chat_message: "chat_message",
  user_correction: "user_correction",
  document: "document",
  file: "file_save",
  dreaming: "dream",
  dream: "dream",
  model_response: "model_response",
  plan_completion: "plan_completion",
};

const UPDATE_LANGUAGE = /\b(correction|corrected|updated|update|no longer|instead|actually|wrong|supersedes|replaces|fixed)\b/i;

export class HMEM {
  readonly clock: () => number;
  readonly actor: string;
  readonly store: MemoryStoreService;
  readonly ledger: TrustLedger;
  readonly sleep: SleepCycleService;
  readonly dreaming: DreamingService;
  readonly conflicts: ConflictDetectionService;
  private persistPath?: string;
  private idSeq = 0;

  constructor(opts: HMEMOptions = {}) {
    this.clock = opts.clock ?? (() => Date.now());
    this.actor = opts.actor ?? "system";
    this.persistPath = opts.persistPath;
    this.store = new MemoryStoreService();
    this.ledger = new TrustLedger();
    (this.store as unknown as { _persistHook?: () => void })._persistHook = () => this.persist();

    this.sleep = new SleepCycleService(this.store, this.ledger, this.clock, this.actor, (input) =>
      this.materialize(input),
    );
    this.dreaming = new DreamingService(this.store, this.ledger, this.clock, this.actor, (input) =>
      this.materialize(input),
    );
    this.conflicts = new ConflictDetectionService(this.store, this.ledger, this.clock, this.actor);

    if (this.persistPath && fs.existsSync(this.persistPath)) this.load();
  }

  // Spec section 2: source and confidence are mandatory — a record with no
  // source must be rejected by construction.
  add(input: AddInput): MemoryRecord {
    if (!input || typeof input.content !== "string" || input.content.trim().length === 0) {
      throw new Error("HMEM.add: content is required");
    }
    if (!input.source || String(input.source).trim().length === 0) {
      throw new Error("HMEM.add: source is mandatory — a record with no source is rejected by construction");
    }

    const now = this.clock();
    const tags = [...(input.tags ?? [])];
    const record: MemoryRecord = {
      id: `mem-${++this.idSeq}`,
      content: input.content,
      type: input.type ?? "general",
      layer: input.layer ?? "short_term",
      timestamp: now,
      lastAccessed: now,
      accessCount: 0,
      tags,
      embedding: embed(input.content),
      confidence: clamp01(input.confidence ?? 0.8),
      source: input.source,
      provenance: {
        origin: input.provenanceOrigin ?? ORIGIN_BY_SOURCE[input.source] ?? "manual",
        learnedAt: now,
        label: input.provenanceLabel ?? `captured from ${input.source}`,
      },
      chatId: input.chatId,
      missionId: input.missionId,
      goalRunId: input.goalRunId,
      domain: inferDomain(input.content, tags),
      namespace: inferNamespace(inferDomain(input.content, tags)),
      entities: extractEntities(input.content),
      relatedTo: [],
      supersedes: input.supersedes,
      derivedFrom: input.derivedFrom ? [...input.derivedFrom] : undefined,
    };
    record.namespace = inferNamespace(record.domain);

    this.discoverRelationships(record);
    this.store.put(record);
    this.ledger.log(record.id, "create", this.actor, now, { newState: snapshot(record), details: { source: record.source } });
    this.persist();
    return record;
  }

  // Spec section 5 relationship discovery: relatedTo links require shared
  // entities plus domain affinity (multi-signal relatedness >= 0.35);
  // supersedes edges require high similarity AND correction/update language.
  private discoverRelationships(record: MemoryRecord): void {
    const tokensA = contentTokens(record.content);
    for (const other of this.store.all()) {
      const sharedEntities = record.entities.filter((e) => other.entities.includes(e));
      const relatedness =
        0.5 * jaccard(tokensA, contentTokens(other.content)) +
        0.2 * jaccard(record.tags, other.tags) +
        0.1 * (record.domain === other.domain ? 1 : 0) +
        0.2 * jaccard(record.entities, other.entities);

      if (sharedEntities.length > 0 && record.domain === other.domain && relatedness >= DEFAULTS.dreamRelatedness) {
        if (record.relatedTo.length < DEFAULTS.relatedCap && !record.relatedTo.includes(other.id)) {
          record.relatedTo.push(other.id);
        }
        if (other.relatedTo.length < DEFAULTS.relatedCap && !other.relatedTo.includes(record.id)) {
          other.relatedTo.push(record.id);
        }
      }

      const sim = jaccard(tokensA, contentTokens(other.content));
      if (!record.supersedes && sim >= 0.8 && UPDATE_LANGUAGE.test(record.content)) {
        record.supersedes = other.id;
        const prev = snapshot(other);
        other.supersededBy = record.id;
        this.ledger.log(other.id, "update", this.actor, this.clock(), {
          previousState: prev,
          newState: snapshot(other),
          details: { supersededBy: record.id },
        });
      }
    }
  }

  query(query: string, opts: { threshold?: number; topN?: number } = {}): QueryResult {
    const now = this.clock();
    const result = retrieve(query, this.store.all(), {
      threshold: opts.threshold,
      topN: opts.topN,
      now,
    });
    for (const r of result.memories) {
      r.memory.lastAccessed = now;
      r.memory.score = r.relevance;
      this.ledger.log(r.memory.id, "read", this.actor, now, {
        details: { query: query.slice(0, 120), relevance: Number(r.relevance.toFixed(4)) },
      });
    }
    this.persist();
    return result;
  }

  // Spec section 9.2 feedback adaptation: exact deltas.
  feedback(id: string, kind: FeedbackKind): MemoryRecord {
    const m = this.store.get(id);
    if (!m) throw new Error(`HMEM.feedback: unknown memory ${id}`);
    const delta = FEEDBACK_DELTAS[kind];
    if (delta === undefined) throw new Error(`HMEM.feedback: unknown kind ${kind}`);
    const prev = snapshot(m);

    if (kind === "helpful") m.accessCount += 1;
    m.confidence = clamp01(m.confidence + delta);
    if (kind === "wrong" && !m.tags.includes("review")) m.tags.push("review");

    this.ledger.log(m.id, "feedback", this.actor, this.clock(), {
      previousState: prev,
      newState: snapshot(m),
      details: { kind, delta },
    });
    this.persist();
    return m;
  }

  private materialize(input: {
    content: string;
    source: string;
    layer: MemoryLayer;
    type: MemoryType;
    derivedFrom: string[];
    provenanceOrigin: ProvenanceOrigin;
    provenanceLabel: string;
  }): MemoryRecord {
    return this.add({
      content: input.content,
      source: input.source,
      layer: input.layer,
      type: input.type,
      derivedFrom: input.derivedFrom,
      provenanceOrigin: input.provenanceOrigin,
      provenanceLabel: input.provenanceLabel,
      confidence: 0.8,
    });
  }

  ledgerAction(id: string): LedgerAction[] {
    return this.ledger.history(id).map((e) => e.action);
  }

  // ---- persistence -------------------------------------------------------

  private load(): void {
    if (!this.persistPath) return;
    const raw = JSON.parse(fs.readFileSync(this.persistPath, "utf-8"));
    this.idSeq = raw.idSeq ?? 0;
    this.store.restore(raw.records ?? []);
    this.ledger.restore(raw.ledger ?? []);
    this.dreaming.proposals = raw.proposals ?? [];
    this.conflicts.conflicts = raw.conflicts ?? [];
  }

  persist(): void {
    if (!this.persistPath) return;
    const state = {
      idSeq: this.idSeq,
      records: this.store.snapshotAll(),
      ledger: this.ledger.all(),
      proposals: this.dreaming.proposals,
      conflicts: this.conflicts.conflicts,
    };
    fs.mkdirSync(path.dirname(this.persistPath), { recursive: true });
    fs.writeFileSync(this.persistPath, JSON.stringify(state));
  }
}
