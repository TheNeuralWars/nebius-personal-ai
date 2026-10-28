#!/usr/bin/env python3
"""zetaris_query.py — run one federated SQL statement against the local Zetaris platform.

Usage:
  python3 zetaris_query.py "SELECT * FROM NY_TAXI.customers LIMIT 5"

Reads configuration from env (see zetaris_client.py). Prints a compact table and a
JSON form of the rows. Never prints credentials. For proofs: redirect stdout to
proofs/zetaris-*.txt.
"""
import json
import sys

from zetaris_client import ZetarisUnavailable
from zetaris_tool import ZetarisFederatedTool


def main(argv):
    if len(argv) < 2 or not argv[1].strip():
        print("usage: zetaris_query.py \"<SELECT ...>\"", file=sys.stderr)
        return 2
    sql = argv[1].strip()
    tool = ZetarisFederatedTool()
    try:
        result = tool.run(sql)
    except ZetarisUnavailable as e:
        print(f"ZETARIS UNAVAILABLE: {e}", file=sys.stderr)
        return 1
    print(f"engine: {result['engine']}  latency_ms: {result['latency_ms']}  rows: {result['row_count']}")
    print(f"sql: {result['sql']}")
    print()
    print(tool.format_rows(result, max_rows=50))
    print()
    print("JSON:")
    print(json.dumps(result["rows"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
