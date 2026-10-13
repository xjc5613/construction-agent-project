#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print a v3 migration plan; apply only explicitly reviewed record IDs."""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config.settings import LIBRARY_DB_PATH
from src.library import LibraryDatabase, LibraryRepository
from src.research.migration import migration_plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=LIBRARY_DB_PATH)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-reviewed", action="store_true")
    parser.add_argument("--dataset-id", action="append", default=[])
    parser.add_argument("--project-id", action="append", default=[])
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore-from", type=Path)
    parser.add_argument("--restored-database", type=Path)
    args = parser.parse_args()
    if args.restore_from:
        if not args.restored_database:
            raise SystemExit("恢复必须指定新的 --restored-database 路径")
        if args.restored_database.exists():
            raise SystemExit("拒绝覆盖已有数据库，请使用新的恢复路径")
        args.restored_database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.restore_from, args.restored_database)
        print(json.dumps({"restored": True, "source": str(args.restore_from),
                          "destination": str(args.restored_database)}, ensure_ascii=False, indent=2)); return
    repository = LibraryRepository(LibraryDatabase(args.database))
    plan = migration_plan(repository)
    if args.verify:
        with repository.db.connect() as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            exports = [dict(row) for row in connection.execute(
                "SELECT export_manifest_id,export_path,status FROM export_manifests ORDER BY created_at"
            ).fetchall()]
        print(json.dumps({"integrity_check": integrity, "plan": plan,
                          "exports": [{**item, "path_exists": Path(item["export_path"]).is_file()} for item in exports]},
                         ensure_ascii=False, indent=2)); return
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    if not args.confirm_reviewed:
        raise SystemExit("拒绝执行：--apply 必须与 --confirm-reviewed 同时使用")
    eligible = set(plan["eligible_dataset_ids"])
    invalid = set(args.dataset_id) - eligible
    if invalid:
        raise SystemExit("拒绝迁移未达到 mapped 等级的数据集: " + ", ".join(sorted(invalid)))
    backup = args.database.with_suffix(args.database.suffix + ".v3-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    shutil.copy2(args.database, backup)
    review_record = backup.with_suffix(backup.suffix + ".review.json")
    review_record.write_text(json.dumps({"plan": plan, "approved_dataset_ids": args.dataset_id,
                                         "approved_project_ids": args.project_id}, ensure_ascii=False, indent=2))
    with repository.db.transaction() as connection:
        for identifier in args.dataset_id:
            connection.execute("UPDATE datasets SET research_contract_version=3 WHERE dataset_id=?", (identifier,))
        for identifier in args.project_id:
            connection.execute("UPDATE projects SET research_contract_version=3,baseline_year=2025,target_year=2040 WHERE project_id=?", (identifier,))
    print(json.dumps({"applied": True, "backup": str(backup), "review_record": str(review_record), "dataset_ids": args.dataset_id,
                      "project_ids": args.project_id}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
