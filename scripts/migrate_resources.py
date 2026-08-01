# -*- coding: utf-8 -*-
"""Non-destructive migration from legacy project resources to the new layout."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migration_plan() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for name in ("topics.json", "high_potential_pairs.json"):
        source = ROOT / "data" / "raw" / name
        if source.exists():
            pairs.append((source, ROOT / "data" / "seed" / name))
    abstracts = ROOT / "data" / "raw" / "sample_abstracts"
    if abstracts.exists():
        for source in sorted(abstracts.glob("*")):
            if source.is_file():
                pairs.append((source, ROOT / "data" / "seed" / "sample_abstracts" / source.name))
    thesis = ROOT / "thesis_draft.md"
    if thesis.exists():
        pairs.append((thesis, ROOT / "docs" / "research" / thesis.name))
    return pairs


def migrate(apply: bool) -> dict:
    report = {"mode": "apply" if apply else "dry-run", "items": [], "ok": True}
    for source, target in migration_plan():
        item = {"source": str(source.relative_to(ROOT)), "target": str(target.relative_to(ROOT))}
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or checksum(source) != checksum(target):
                shutil.copy2(source, target)
            item["verified"] = checksum(source) == checksum(target)
            report["ok"] = report["ok"] and item["verified"]
        else:
            item["verified"] = None
        report["items"].append(item)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely copy legacy resources into the new layout.")
    parser.add_argument("--apply", action="store_true", help="Copy and verify files. Sources are never deleted.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    report = migrate(args.apply)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
