from src.library import LibraryDatabase, LibraryRepository
from src.research.migration import migration_plan


def test_v3_migration_classifier_is_read_only_and_separates_legacy_evidence(tmp_path):
    repository = LibraryRepository(LibraryDatabase(tmp_path / "migration.sqlite3"))
    old = repository.create_dataset("ipc_metrics", "old", "v1", period_code="2010_2015", public_kind="ipc")
    unknown = repository.create_dataset("papers", "unknown", "v1", public_kind="paper", research_contract_version=2)
    before = repository.get_dataset(old["dataset_id"])["research_contract_version"]
    plan = migration_plan(repository)
    by_id = {item["dataset_id"]: item for item in plan["datasets"]}
    assert plan["dry_run"] and plan["requires_explicit_review"]
    assert by_id[old["dataset_id"]]["category"] == "needs_period_split"
    assert by_id[unknown["dataset_id"]]["category"] == "quarantined_legacy"
    assert repository.get_dataset(old["dataset_id"])["research_contract_version"] == before
