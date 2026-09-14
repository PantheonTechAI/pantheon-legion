"""Execute the real federated conformance matrix against a disposable Tabula stack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .live import DisposableRun, run_disposable_conformance
from .tabula_stack import TabulaDisposableStack


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run federated conformance against a disposable Tabula stack.")
    parser.add_argument("--tabula-root", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="allow the preflight-approved stack to be started")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("refusing to start containers without --execute")
    stack = TabulaDisposableStack(args.tabula_root, args.project_name, args.env_file)
    try:
        results = run_disposable_conformance(DisposableRun(stack.mcp_endpoint, stack.start))
    finally:
        stack.cleanup()
    print(json.dumps([result.__dict__ for result in results], sort_keys=True))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
