// JSON stdio CLI for the H-MEM engine — the bridge used by the Python agent
// (hmem_client.py). One JSON command on stdin, one JSON result on stdout.
//
//   echo '{"op":"query","query":"...","state":"/path/state.json"}' | node hmem/src/cli.ts

import { HMEM } from "./index.ts";

interface Command {
  op: string;
  state?: string;
  [key: string]: unknown;
}

async function main(): Promise<void> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  const raw = Buffer.concat(chunks).toString("utf-8").trim();
  let cmd: Command;
  try {
    cmd = JSON.parse(raw || "{}");
  } catch (err) {
    process.stdout.write(JSON.stringify({ error: `invalid JSON command: ${(err as Error).message}` }));
    process.exit(1);
  }

  const clock = typeof cmd.clockNow === "number" ? () => cmd.clockNow as number : undefined;
  const hmem = new HMEM({ persistPath: cmd.state, clock });
  try {
    let out: unknown;
    switch (cmd.op) {
      case "add":
        out = hmem.add(cmd as never);
        break;
      case "query":
        out = hmem.query(String(cmd.query), {
          threshold: typeof cmd.threshold === "number" ? cmd.threshold : undefined,
          topN: typeof cmd.topN === "number" ? cmd.topN : undefined,
        });
        break;
      case "feedback":
        out = hmem.feedback(String(cmd.id), cmd.kind as never);
        break;
      case "history":
        out = hmem.ledger.history(String(cmd.id));
        break;
      case "sleep_preview":
        out = hmem.sleep.preview();
        break;
      case "sleep_execute":
        out = hmem.sleep.execute();
        break;
      case "sleep_restore":
        out = { restored: hmem.sleep.restore(String(cmd.backupId)) };
        break;
      case "dream":
        out = hmem.dreaming.dream();
        break;
      case "dream_approve":
        out = hmem.dreaming.approve(String(cmd.id), typeof cmd.content === "string" ? cmd.content : undefined) ?? null;
        break;
      case "dream_reject":
        out = { rejected: hmem.dreaming.reject(String(cmd.id)) };
        break;
      case "conflicts_scan":
        out = hmem.conflicts.scan();
        break;
      case "conflicts_resolve": {
        const conflict = hmem.conflicts.conflicts.find((c) => c.id === cmd.id);
        if (!conflict) throw new Error(`unknown conflict ${cmd.id}`);
        out = { outcome: hmem.conflicts.autoResolve(conflict) };
        break;
      }
      case "info":
        out = {
          records: hmem.store.all().length,
          ledgerEntries: hmem.ledger.all().length,
          proposals: hmem.dreaming.proposals.length,
          conflicts: hmem.conflicts.conflicts.length,
        };
        break;
      default:
        throw new Error(`unknown op: ${cmd.op}`);
    }
    process.stdout.write(JSON.stringify({ ok: true, result: out }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, error: (err as Error).message }));
    process.exit(1);
  }
}

main();
