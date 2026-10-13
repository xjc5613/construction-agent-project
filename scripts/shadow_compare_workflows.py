#!/usr/bin/env python3
"""Compare legacy and v3 manifests structurally without claiming scientific equivalence."""
import argparse
import json
from pathlib import Path


def flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items(): result.update(flatten(child, "%s.%s" % (prefix, key) if prefix else key))
        return result
    return {prefix: value}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("legacy", type=Path); parser.add_argument("v3", type=Path)
    args = parser.parse_args()
    legacy, v3 = json.loads(args.legacy.read_text()), json.loads(args.v3.read_text())
    left, right = flatten(legacy), flatten(v3)
    keys = sorted(set(left) | set(right))
    print(json.dumps({"scientific_equivalence_asserted": False, "differences": [
        {"field": key, "legacy": left.get(key), "v3": right.get(key)} for key in keys if left.get(key) != right.get(key)
    ]}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__": main()
