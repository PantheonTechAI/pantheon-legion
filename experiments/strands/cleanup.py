"""Explicit 24-hour expiry cleanup for an owned, isolated operational store."""

import argparse
from pathlib import Path

from .state import OperationalStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="exact private operational-store root, never a repository root")
    arguments = parser.parse_args()
    if not (Path(arguments.root) / ".legion-strands-store.json").is_file():
        parser.error("cleanup requires an existing owned operational store")
    count = OperationalStore(arguments.root).expire()
    print(f"Removed {count} expired synthetic trial stores; operational snapshots are not recoverable.")


if __name__ == "__main__":
    main()
