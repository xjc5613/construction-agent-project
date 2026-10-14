# -*- coding: utf-8 -*-
import sqlite3

import pytest

from src.library import LibraryDatabase, LibraryRepository
from src.library.database import SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5
from src.research.repository import ResearchRepository


@pytest.fixture()
def repositories(tmp_path):
    database = LibraryDatabase(tmp_path / "v6.sqlite3")
    return LibraryRepository(database), ResearchRepository(database)


def test_v6_additive_schema_and_indexes(repositories):
    library, _ = repositories
    required = {
        "patents", "patent_ipcs", "data_coverage", "ipc_code_mappings",
        "network_runs", "network_nodes", "ipc_edges_yearly", "ipc_edges_period",
        "feature_runs", "fusion_candidates", "fusion_predictions",
        "validation_folds", "validation_metrics", "publication_gates",
        "graph_threads", "graph_checkpoints", "graph_node_events", "human_reviews",
        "prompt_manifests", "model_manifests", "export_manifests",
    }
    with library.db.connect() as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0] == 9
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        indexes = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
    assert required <= tables
    assert {"idx_patents_dataset_year", "idx_candidates_pair",
            "idx_checkpoints_thread"} <= indexes
    # Reopening performs no destructive or duplicate migration.
    LibraryDatabase(library.db.path)


def test_legacy_v5_database_upgrades_without_losing_records(tmp_path):
    path = tmp_path / "legacy-v5.sqlite3"
    connection = sqlite3.connect(str(path))
    try:
        for version, schema in enumerate(
            (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5), start=1
        ):
            connection.executescript(schema)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
                (version,),
            )
        connection.execute(
            "INSERT INTO projects(project_id,name) VALUES ('legacy','Legacy project')"
        )
        connection.commit()
    finally:
        connection.close()
    upgraded = LibraryDatabase(path)
    with upgraded.connect() as connection:
        assert connection.execute(
            "SELECT name FROM projects WHERE project_id='legacy'"
        ).fetchone()[0] == "Legacy project"
        row = connection.execute(
            "SELECT research_contract_version FROM projects WHERE project_id='legacy'"
        ).fetchone()
        assert row[0] == 2
        assert connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0] == 9


def test_patent_assignment_transaction_and_duplicate_constraints(repositories):
    library, research = repositories
    dataset = library.create_dataset("ipc_metrics", "patents", "v1")
    patent = {
        "dataset_id": dataset["dataset_id"], "publication_number": "CN-1",
        "title": "robot", "abstract": "construction robot",
        "application_year": 2024, "applicant_type": "enterprise",
        "legal_status": "active", "source_row": 2,
    }
    saved = research.add_patent_with_ipcs(patent, [{
        "ipc_code_raw": "B25J 9/16", "ipc_code_normalized": "B25J9/00",
        "ipc_edition": "2024.01",
    }])
    assert saved["ipc_assignments"][0]["ipc_code_raw"] == "B25J 9/16"
    with pytest.raises(sqlite3.IntegrityError):
        research.add_patent_with_ipcs(patent, [{
            "ipc_code_raw": "E04B 1/00", "ipc_code_normalized": "E04B1/00",
        }])
    with library.db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM patents").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM patent_ipcs").fetchone()[0] == 1


def test_mapping_coverage_paper_metadata_and_immutable_run(repositories):
    library, research = repositories
    dataset = library.create_dataset("papers", "evidence", "v1")
    mapping = research.save_ipc_mapping({
        "ipc_code_raw": "B25J 9/16", "ipc_code_normalized": "B25J9/00",
        "analysis_level": "main_group", "source_edition": "2024.01",
        "target_edition": "2025.01", "rule_version": "map-v1",
    })
    assert mapping["ipc_code_raw"] == "B25J 9/16"
    coverage = research.upsert_coverage({
        "dataset_id": dataset["dataset_id"], "source_kind": "paper", "year": 2025,
        "observation_cutoff": "2025-10-01", "observed_count": 8,
        "completeness": "partial", "researcher_notes": "第四季度未覆盖",
    })
    assert coverage["completeness"] == "partial"
    paper = library.add_paper(dataset["dataset_id"], {
        "title": "Typed paper", "year": 2025, "paper_type": "journal_article",
        "source_database": "Scopus", "publication_date": "2025-06-01",
        "citation_count": 4, "citation_observed_at": "2025-10-01",
    })
    assert paper["title"] == "Typed paper"

    payload = {
        "snapshot_checksum": "snapshot-a", "algorithm_version": "network-v1",
        "parameters": {"seed": 7}, "input_checksum": "input-a", "random_seed": 7,
    }
    first = research.create_network_run(payload)
    second = research.create_network_run(payload)
    assert first["network_run_id"] == second["network_run_id"]
    research.complete_network_run(first["network_run_id"], "result-a")
    with pytest.raises(ValueError, match="不可变"):
        research.complete_network_run(first["network_run_id"], "result-b")
