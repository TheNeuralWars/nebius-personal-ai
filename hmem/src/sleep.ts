// SleepCycleService — consolidation, archival, synthesis (spec section 8).
// Preview-first: preview() is pure and never mutates the store; execute()
// takes a backup snapshot before applying anything.

import type { MemoryRecord, SleepPreview, SleepReport } from "./types.ts";
import { DEFAULTS, DAY_MS } from "./types.ts";
import { cosine } from "./text.ts";
import type { MemoryStoreService } from "./store.ts";
import type { TrustLedger } from "./ledger.ts";
import { snapshot } from "./ledger.ts";

export class SleepCycleService {
  private backups = new Map<string, MemoryRecord[]>();
  private backupSeq = 0;
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
    provenanceOrigin: "sleep_synthesis";
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
      provenanceOrigin: "sleep_synthesis";
      provenanceLabel: string;
    }) => MemoryRecord,
  ) {
    this.store = store;
    this.ledger = ledger;
    this.clock = clock;
    this.actor = actor;
    this.materialize = materialize;
  }

  preview(): SleepPreview {
    const now = this.clock();
    const all = this.store.all();

    // Referenced ids: anything pointed at by relatedTo / supersedes / derivedFrom.
    const referenced = new Set<string>();
    for (const m of all) {
      for (const r of m.relatedTo) referenced.add(r);
      if (m.supersedes) referenced.add(m.supersedes);
      for (const d of m.derivedFrom ?? []) referenced.add(d);
    }

    const toConsolidate = all
      .filter((m) => m.layer === "short_term" && now - m.lastAccessed >= DEFAULTS.consolidationDays * DAY_MS)
      .map((m) => m.id);

    const toArchive = all
      .filter((m) => {
        const oldEnough = now - m.timestamp >= DEFAULTS.archiveMinDays * DAY_MS;
        const lowAccess = m.accessCount <= DEFAULTS.archiveMaxAccess;
        const unreferenced = !referenced.has(m.id);
        if (!(oldEnough && lowAccess && unreferenced)) return false;
        // Guardrails (spec section 8.2): never archive these three classes.
        if (m.supersedes) return false;                          // superseding/current record
        if ((m.derivedFrom ?? []).length > 0) return false;      // derived/synthesized memory
        if (m.relatedTo.length >= DEFAULTS.hubThreshold) return false; // relationship hub
        return true;
      })
      .map((m) => m.id);

    const toSynthesize: string[][] = [];
    const used = new Set<string>();
    for (const a of all) {
      if (used.has(a.id)) continue;
      const group = [a.id];
      for (const b of all) {
        if (b.id === a.id || used.has(b.id)) continue;
        if (cosine(a.embedding, b.embedding) >= DEFAULTS.synthesisCosine) group.push(b.id);
      }
      if (group.length >= 2) {
        for (const id of group) used.add(id);
        toSynthesize.push(group);
      }
    }

    return { toConsolidate, toArchive, toSynthesize };
  }

  execute(preview?: SleepPreview): SleepReport {
    const plan = preview ?? this.preview();
    const backupId = `backup-${++this.backupSeq}`;
    this.backups.set(backupId, this.store.snapshotAll());
    const actionLog: string[] = [];

    for (const id of plan.toConsolidate) {
      const m = this.store.get(id);
      if (!m) continue;
      const prev = snapshot(m);
      m.layer = "long_term";
      this.ledger.log(id, "sleep_consolidate", this.actor, this.clock(), {
        previousState: prev,
        newState: snapshot(m),
        details: { backupId },
      });
      actionLog.push(`consolidated ${id}`);
    }

    for (const id of plan.toArchive) {
      const m = this.store.get(id);
      if (!m) continue;
      this.ledger.log(id, "sleep_archive", this.actor, this.clock(), {
        details: { age: this.clock() - m.timestamp, accessCount: m.accessCount, backupId },
      });
      this.store.delete(id, "sleep archive");
      actionLog.push(`archived ${id}`);
    }

    let synthesized = 0;
    for (const group of plan.toSynthesize) {
      const members = group.map((id) => this.store.get(id)).filter((m): m is MemoryRecord => !!m);
      if (members.length < 2) continue;
      const merged = this.materialize({
        content: members.map((m) => m.content).join(" | "),
        source: "sleep:synthesis",
        layer: "long_term",
        type: "factual",
        derivedFrom: members.map((m) => m.id),
        provenanceOrigin: "sleep_synthesis",
        provenanceLabel: `synthesized from ${members.length} memories`,
      });
      // Merge tags/entities, inherit non-internal relationships.
      for (const m of members) {
        for (const t of m.tags) if (!merged.tags.includes(t)) merged.tags.push(t);
        for (const e of m.entities) if (!merged.entities.includes(e) && merged.entities.length < 10) merged.entities.push(e);
        for (const r of m.relatedTo) {
          if (!group.includes(r) && !merged.relatedTo.includes(r) && merged.relatedTo.length < 5) merged.relatedTo.push(r);
        }
      }
      this.ledger.log(merged.id, "sleep_synthesize", this.actor, this.clock(), {
        details: { sources: group, backupId },
      });
      for (const m of members) this.store.delete(m.id, "merged by sleep synthesis");
      synthesized++;
      actionLog.push(`synthesized ${merged.id} from ${group.join(", ")}`);
    }

    this.store.persist();
    return {
      backupId,
      consolidated: plan.toConsolidate.length,
      archived: plan.toArchive.length,
      synthesized,
      actionLog,
    };
  }

  restore(backupId: string): boolean {
    const snap = this.backups.get(backupId);
    if (!snap) return false;
    this.store.restore(snap);
    this.ledger.log("*", "restore", this.actor, this.clock(), { details: { backupId } });
    this.store.persist();
    return true;
  }
}
