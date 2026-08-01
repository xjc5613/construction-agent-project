# -*- coding: utf-8 -*-
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config.settings import LIBRARY_DB_PATH

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('ipc_metrics','ipc_fusions','papers','mixed')),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    checksum TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','inactive','failed')),
    description TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS source_files (
    file_id TEXT PRIMARY KEY,
    dataset_id TEXT,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    checksum TEXT NOT NULL UNIQUE,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    text_coverage REAL NOT NULL DEFAULT 0,
    parse_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
);

CREATE TABLE IF NOT EXISTS imports (
    import_id TEXT PRIMARY KEY,
    dataset_id TEXT,
    file_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'preview',
    mapping_json TEXT NOT NULL DEFAULT '{}',
    preview_json TEXT NOT NULL DEFAULT '{}',
    error_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY(file_id) REFERENCES source_files(file_id)
);

CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    year INTEGER,
    doi TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    abstract TEXT NOT NULL DEFAULT '',
    file_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY(file_id) REFERENCES source_files(file_id),
    UNIQUE(dataset_id, title, year)
);

CREATE TABLE IF NOT EXISTS paper_chunks (
    chunk_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    ordinal INTEGER NOT NULL,
    page_number INTEGER,
    content TEXT NOT NULL,
    FOREIGN KEY(paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
    UNIQUE(paper_id, ordinal)
);

CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(
    paper_id UNINDEXED,
    title,
    abstract,
    keywords,
    content,
    tokenize='unicode61'
);

CREATE TABLE IF NOT EXISTS ipc_metrics (
    metric_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    ipc_code TEXT NOT NULL,
    year INTEGER NOT NULL,
    patent_count REAL,
    degree_centrality REAL,
    betweenness_centrality REAL,
    growth_rate REAL,
    source_row INTEGER,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    UNIQUE(dataset_id, ipc_code, year)
);

CREATE TABLE IF NOT EXISTS ipc_fusions (
    fusion_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    ipc1 TEXT NOT NULL,
    ipc2 TEXT NOT NULL,
    year INTEGER,
    probability REAL NOT NULL CHECK(probability >= 0 AND probability <= 1),
    source_row INTEGER,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    UNIQUE(dataset_id, ipc1, ipc2, year)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_materials (
    material_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    original_filename TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL,
    content TEXT NOT NULL,
    cleaned_content TEXT NOT NULL,
    stored_path TEXT NOT NULL DEFAULT '',
    parse_status TEXT NOT NULL DEFAULT 'ready',
    parse_metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    UNIQUE(project_id, checksum)
);

CREATE TABLE IF NOT EXISTS project_topics (
    topic_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    fusion_pairs_json TEXT NOT NULL DEFAULT '[]',
    operator_notes TEXT NOT NULL DEFAULT '',
    evidence_score REAL NOT NULL DEFAULT 0,
    requires_review INTEGER NOT NULL DEFAULT 1,
    selected INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'candidate',
    merged_into TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS evidence_packages (
    package_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    query_json TEXT NOT NULL DEFAULT '{}',
    quality_json TEXT NOT NULL DEFAULT '{}',
    operator_notes TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    frozen_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(topic_id) REFERENCES project_topics(topic_id)
);

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    dataset_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    relevance REAL NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(package_id) REFERENCES evidence_packages(package_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forecast_jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    evidence_snapshot_path TEXT NOT NULL DEFAULT '',
    topic_snapshot_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'queued',
    evidence_limited INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_ipc_metrics_code_year ON ipc_metrics(ipc_code, year);
CREATE INDEX IF NOT EXISTS idx_ipc_fusions_codes ON ipc_fusions(ipc1, ipc2);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_topics_project ON project_topics(project_id, status);
CREATE INDEX IF NOT EXISTS idx_packages_topic ON evidence_packages(topic_id, status);
"""

SCHEMA_V2 = """
ALTER TABLE evidence_items RENAME TO evidence_items_v1;

CREATE TABLE evidence_items (
    item_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    dataset_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    relevance REAL NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(package_id) REFERENCES evidence_packages(package_id) ON DELETE CASCADE,
    UNIQUE(package_id, evidence_id)
);

INSERT INTO evidence_items(
    item_id,evidence_id,package_id,evidence_type,source_id,dataset_id,title,
    content,metadata_json,relevance,excluded,exclusion_reason
)
SELECT package_id || ':' || evidence_id,evidence_id,package_id,evidence_type,
       source_id,dataset_id,title,content,metadata_json,relevance,excluded,
       exclusion_reason
FROM evidence_items_v1;

DROP TABLE evidence_items_v1;
CREATE INDEX idx_evidence_items_evidence_id ON evidence_items(evidence_id);
CREATE INDEX idx_evidence_items_package ON evidence_items(package_id);
"""


class LibraryDatabase:
    def __init__(self, path: Path = LIBRARY_DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def migrate(self) -> None:
        with self.transaction() as connection:
            connection.executescript(SCHEMA_V1)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)"
            )
            version = connection.execute(
                "SELECT MAX(version) AS version FROM schema_migrations"
            ).fetchone()["version"]
            if version < 2:
                connection.executescript(SCHEMA_V2)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (2)"
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
