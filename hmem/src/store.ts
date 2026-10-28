// MemoryStoreService — tiered persistence surface (spec sections 3 and 11):
// CRUD plus snapshot/restore used by the sleep cycle's backup workflow.

import type { MemoryRecord } from "./types.ts";

export class MemoryStoreService {
  private records = new Map<string, MemoryRecord>();

  get(id: string): MemoryRecord | undefined {
    return this.records.get(id);
  }

  all(): MemoryRecord[] {
    return [...this.records.values()];
  }

  put(record: MemoryRecord): MemoryRecord {
    this.records.set(record.id, record);
    return record;
  }

  delete(id: string, _reason?: string): boolean {
    return this.records.delete(id);
  }

  snapshotAll(): MemoryRecord[] {
    return this.all().map((m) => ({ ...m, tags: [...m.tags], entities: [...m.entities], relatedTo: [...m.relatedTo], embedding: [...m.embedding], derivedFrom: m.derivedFrom ? [...m.derivedFrom] : undefined }));
  }

  restore(records: MemoryRecord[]): void {
    this.records.clear();
    for (const r of records) this.records.set(r.id, r);
  }

  persist(): void {
    // Persistence is handled by the HMEM facade (it owns the state file).
    const hook = (this as unknown as { _persistHook?: () => void })._persistHook;
    if (hook) hook();
  }
}
