"""Offline command-line interface for ARAF."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .core import validate_payload


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python -m araf.cli <research-plan.json>", file=sys.stderr)
        return 2

    path = Path(args[0])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2

    if not isinstance(data, dict):
        print(json.dumps({
            "valid": False,
            "errors": ["top-level JSON value must be an object"],
        }, indent=2))
        return 2

    report = validate_payload(data)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
