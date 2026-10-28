// TrustLedgerService — append-only audit ledger (spec section 9.1).
// Every significant mutation is logged with previous/new state snapshots.
// Never destructively pruned.

import type { LedgerAction, LedgerEntry, MemoryRecord } from "./types.ts";

export type Snapshot = Partial<MemoryRecord>;

export function snapshot(m: MemoryRecord): Snapshot {
  return {
    confidence: m.confidence,
    accessCount: m.accessCount,
    tags: [...m.tags],
    layer: m.layer,
    content: m.content,
    lastAccessed: m.lastAccessed,
    supersededBy: m.supersededBy,
  };
}

export class TrustLedger {
  entries: LedgerEntry[] = [];

  log(
    memoryId: string,
    action: LedgerAction,
    actor: string,
    at: number,
    payload: { previousState?: Snapshot; newState?: Snapshot; details?: Record<string, unknown> } = {},
  ): LedgerEntry {
    const entry: LedgerEntry = {
      memoryId,
      action,
      actor,
      timestamp: at,
      previousState: payload.previousState,
      newState: payload.newState,
      details: payload.details,
    };
    this.entries.push(entry);
    return entry;
  }

  history(memoryId: string): LedgerEntry[] {
    return this.entries.filter((e) => e.memoryId === memoryId);
  }

  all(): LedgerEntry[] {
    return [...this.entries];
  }

  export(): LedgerEntry[] {
    return this.all();
  }

  restore(entries: LedgerEntry[]): void {
    this.entries = [...entries];
  }
}
