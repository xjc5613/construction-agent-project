#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.validation import diff_manifests


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare immutable research run manifests.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()
    differences = diff_manifests(
        json.loads(args.expected.read_text(encoding="utf-8")),
        json.loads(args.actual.read_text(encoding="utf-8")),
    )
    print(json.dumps({"match": not differences, "differences": differences}, ensure_ascii=False, indent=2))
    return 0 if not differences else 1


if __name__ == "__main__":
    raise SystemExit(main())
