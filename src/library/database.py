# -*- coding: utf-8 -*-
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config.settings import LIBRARY_DB_PATH
from .constants import TECHNOLOGY_RELATION_SUGGESTIONS, TECHNOLOGY_SEED

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

SCHEMA_V3 = """
CREATE TABLE technology_nodes (
    node_id TEXT PRIMARY KEY,
    parent_id TEXT,
    level INTEGER NOT NULL CHECK(level IN (1,2,3)),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    taxonomy_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_id) REFERENCES technology_nodes(node_id)
);

CREATE UNIQUE INDEX idx_technology_sibling_name
ON technology_nodes(IFNULL(parent_id,''), name);
CREATE INDEX idx_technology_parent ON technology_nodes(parent_id,sort_order);

CREATE TABLE technology_relations (
    relation_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    relation_type TEXT NOT NULL CHECK(relation_type IN ('related','depends_on','converges_with')),
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('suggested','confirmed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(source_node_id) REFERENCES technology_nodes(node_id),
    FOREIGN KEY(target_node_id) REFERENCES technology_nodes(node_id),
    CHECK(source_node_id <> target_node_id),
    UNIQUE(source_node_id,target_node_id,relation_type)
);

CREATE TABLE technology_change_logs (
    change_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    operator TEXT NOT NULL DEFAULT 'local-user',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE project_topic_technologies (
    topic_id TEXT NOT NULL,
    technology_node_id TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    relevance REAL NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(topic_id,technology_node_id),
    FOREIGN KEY(topic_id) REFERENCES project_topics(topic_id) ON DELETE CASCADE,
    FOREIGN KEY(technology_node_id) REFERENCES technology_nodes(node_id)
);

CREATE UNIQUE INDEX idx_topic_primary_technology
ON project_topic_technologies(topic_id) WHERE is_primary=1;

CREATE TABLE stage_analysis_runs (
    run_id TEXT PRIMARY KEY,
    project_id TEXT,
    technology_node_id TEXT NOT NULL,
    input_checksum TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    quality_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(technology_node_id) REFERENCES technology_nodes(node_id),
    UNIQUE(technology_node_id,input_checksum,algorithm_version)
);

CREATE TABLE stage_analysis_items (
    analysis_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    direction_key TEXT NOT NULL,
    relation TEXT NOT NULL,
    stages_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0,
    limitations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(run_id) REFERENCES stage_analysis_runs(run_id) ON DELETE CASCADE
);

ALTER TABLE datasets ADD COLUMN public_kind TEXT NOT NULL DEFAULT '';
ALTER TABLE datasets ADD COLUMN technology_node_id TEXT;
ALTER TABLE datasets ADD COLUMN period_code TEXT;
ALTER TABLE datasets ADD COLUMN migration_status TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE datasets ADD COLUMN lineage_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE source_files ADD COLUMN content_role TEXT NOT NULL DEFAULT '';
ALTER TABLE imports ADD COLUMN component_kind TEXT NOT NULL DEFAULT '';

ALTER TABLE projects ADD COLUMN technology_node_id TEXT;
ALTER TABLE projects ADD COLUMN baseline_year INTEGER NOT NULL DEFAULT 2025;
ALTER TABLE projects ADD COLUMN target_year INTEGER NOT NULL DEFAULT 2040;
ALTER TABLE projects ADD COLUMN scope_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN legacy_mode INTEGER NOT NULL DEFAULT 1;

ALTER TABLE project_materials ADD COLUMN analysis_kind TEXT NOT NULL DEFAULT 'integrated_analysis';
ALTER TABLE project_materials ADD COLUMN review_status TEXT NOT NULL DEFAULT 'ready';

ALTER TABLE forecast_jobs ADD COLUMN baseline_year INTEGER NOT NULL DEFAULT 2025;
ALTER TABLE forecast_jobs ADD COLUMN target_year INTEGER NOT NULL DEFAULT 2040;
ALTER TABLE forecast_jobs ADD COLUMN forecast_nodes_json TEXT NOT NULL DEFAULT '["2030","2035","2040"]';
ALTER TABLE forecast_jobs ADD COLUMN taxonomy_snapshot_json TEXT NOT NULL DEFAULT '{}';

CREATE UNIQUE INDEX idx_stage_dataset_identity
ON datasets(technology_node_id,period_code,public_kind,version)
WHERE technology_node_id IS NOT NULL AND period_code IS NOT NULL AND public_kind <> '';
CREATE INDEX idx_datasets_technology_period
ON datasets(technology_node_id,period_code,public_kind,status);
CREATE INDEX idx_topic_technologies_node
ON project_topic_technologies(technology_node_id);
CREATE INDEX idx_stage_analysis_technology
ON stage_analysis_runs(technology_node_id,created_at);
"""

SCHEMA_V4 = """
ALTER TABLE projects ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE projects ADD COLUMN archived_at TEXT;

ALTER TABLE project_materials ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE project_materials ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
ALTER TABLE project_materials ADD COLUMN deactivated_at TEXT;

ALTER TABLE datasets ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE datasets ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
ALTER TABLE datasets ADD COLUMN deprecated_at TEXT;

ALTER TABLE forecast_jobs ADD COLUMN request_checksum TEXT NOT NULL DEFAULT '';
ALTER TABLE forecast_jobs ADD COLUMN idempotency_key TEXT;
ALTER TABLE forecast_jobs ADD COLUMN parent_job_id TEXT;
ALTER TABLE forecast_jobs ADD COLUMN options_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE forecast_jobs ADD COLUMN request_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE forecast_jobs ADD COLUMN progress REAL NOT NULL DEFAULT 0;
ALTER TABLE forecast_jobs ADD COLUMN current_stage TEXT NOT NULL DEFAULT 'queued';
ALTER TABLE forecast_jobs ADD COLUMN snapshot_checksum TEXT NOT NULL DEFAULT '';
ALTER TABLE forecast_jobs ADD COLUMN artifact_health TEXT NOT NULL DEFAULT 'initializing';
ALTER TABLE forecast_jobs ADD COLUMN error_code TEXT NOT NULL DEFAULT '';
ALTER TABLE forecast_jobs ADD COLUMN error_message TEXT NOT NULL DEFAULT '';
ALTER TABLE forecast_jobs ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
ALTER TABLE forecast_jobs ADD COLUMN started_at TEXT;
ALTER TABLE forecast_jobs ADD COLUMN completed_at TEXT;
ALTER TABLE forecast_jobs ADD COLUMN cancel_requested_at TEXT;

UPDATE project_materials SET updated_at=created_at WHERE updated_at='';
UPDATE datasets SET updated_at=imported_at WHERE updated_at='';
UPDATE forecast_jobs SET updated_at=created_at WHERE updated_at='';
UPDATE projects SET lifecycle_status='archived',archived_at=updated_at
WHERE status='archived';
UPDATE datasets SET lifecycle_status='deprecated',deprecated_at=imported_at
WHERE status='inactive';

UPDATE forecast_jobs
SET status='failed',
    error_code='duplicate_active_migration',
    error_message='迁移时发现同一项目存在重复活动任务',
    current_stage='failed',
    completed_at=CURRENT_TIMESTAMP,
    updated_at=CURRENT_TIMESTAMP
WHERE status IN ('queued','running','cancelling')
  AND rowid NOT IN (
      SELECT MAX(rowid) FROM forecast_jobs
      WHERE status IN ('queued','running','cancelling')
      GROUP BY project_id
  );

CREATE UNIQUE INDEX idx_forecast_jobs_idempotency
ON forecast_jobs(idempotency_key)
WHERE idempotency_key IS NOT NULL AND idempotency_key <> '';
CREATE UNIQUE INDEX idx_forecast_jobs_one_active_project
ON forecast_jobs(project_id)
WHERE status IN ('queued','running','cancelling');
CREATE INDEX idx_forecast_jobs_project_created
ON forecast_jobs(project_id,created_at DESC);
CREATE INDEX idx_materials_project_lifecycle
ON project_materials(project_id,lifecycle_status,created_at DESC);
CREATE INDEX idx_datasets_lifecycle
ON datasets(lifecycle_status,status,imported_at DESC);
"""

SCHEMA_V5 = """
CREATE INDEX IF NOT EXISTS idx_technology_effective_lookup
ON technology_nodes(parent_id,status,level,sort_order);
CREATE INDEX IF NOT EXISTS idx_datasets_eligibility
ON datasets(technology_node_id,migration_status,lifecycle_status,status,period_code,public_kind);
CREATE INDEX IF NOT EXISTS idx_papers_dataset_year_title
ON papers(dataset_id,year,title);
CREATE INDEX IF NOT EXISTS idx_ipc_metrics_dataset_year_code
ON ipc_metrics(dataset_id,year,ipc_code);
CREATE INDEX IF NOT EXISTS idx_ipc_fusions_dataset_year
ON ipc_fusions(dataset_id,year);
CREATE INDEX IF NOT EXISTS idx_imports_dataset_status
ON imports(dataset_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_source_files_dataset_parse
ON source_files(dataset_id,parse_status,created_at);
"""

SCHEMA_V6 = """
ALTER TABLE projects ADD COLUMN research_contract_version INTEGER NOT NULL DEFAULT 2;
ALTER TABLE projects ADD COLUMN active_research_design_id TEXT;

ALTER TABLE forecast_jobs ADD COLUMN research_contract_version INTEGER NOT NULL DEFAULT 2;
ALTER TABLE forecast_jobs ADD COLUMN graph_thread_id TEXT;
ALTER TABLE forecast_jobs ADD COLUMN publication_state TEXT NOT NULL DEFAULT 'not_evaluated';

ALTER TABLE datasets ADD COLUMN evidence_grade TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE papers ADD COLUMN paper_type TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE papers ADD COLUMN source_database TEXT NOT NULL DEFAULT '';
ALTER TABLE papers ADD COLUMN publication_date TEXT;
ALTER TABLE papers ADD COLUMN citation_count INTEGER;
ALTER TABLE papers ADD COLUMN citation_observed_at TEXT;

CREATE TABLE research_designs (
    design_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    research_contract_version INTEGER NOT NULL,
    research_question TEXT NOT NULL DEFAULT '',
    paper_types_json TEXT NOT NULL DEFAULT '[]',
    ipc_analysis_level TEXT NOT NULL DEFAULT 'main_group',
    candidate_target TEXT NOT NULL DEFAULT 'emergence',
    data_cutoff TEXT NOT NULL DEFAULT '',
    completeness_policy TEXT NOT NULL DEFAULT 'include_partial_with_sensitivity',
    parameters_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    checksum TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    UNIQUE(project_id,version),
    UNIQUE(project_id,checksum)
);

CREATE TABLE patents (
    patent_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    publication_number TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    abstract TEXT NOT NULL DEFAULT '',
    application_year INTEGER NOT NULL,
    applicant_type TEXT NOT NULL DEFAULT '',
    legal_status TEXT NOT NULL DEFAULT '',
    file_id TEXT,
    source_row INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    FOREIGN KEY(file_id) REFERENCES source_files(file_id),
    UNIQUE(dataset_id,publication_number)
);

CREATE TABLE patent_ipcs (
    assignment_id TEXT PRIMARY KEY,
    patent_id TEXT NOT NULL,
    ipc_code_raw TEXT NOT NULL,
    ipc_code_normalized TEXT NOT NULL,
    ipc_level TEXT NOT NULL DEFAULT 'main_group',
    ipc_edition TEXT NOT NULL DEFAULT '',
    mapping_status TEXT NOT NULL DEFAULT 'mapped',
    mapping_rule_version TEXT NOT NULL DEFAULT 'ipc-main-group-v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(patent_id) REFERENCES patents(patent_id) ON DELETE CASCADE,
    UNIQUE(patent_id,ipc_code_normalized,ipc_level)
);

CREATE TABLE data_coverage (
    coverage_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    year INTEGER NOT NULL,
    observation_cutoff TEXT NOT NULL DEFAULT '',
    expected_count INTEGER,
    observed_count INTEGER,
    completeness TEXT NOT NULL DEFAULT 'unknown'
        CHECK(completeness IN ('complete','partial','unknown','not_applicable')),
    researcher_notes TEXT NOT NULL DEFAULT '',
    reviewed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    UNIQUE(dataset_id,source_kind,year)
);

CREATE TABLE ipc_code_mappings (
    mapping_id TEXT PRIMARY KEY,
    ipc_code_raw TEXT NOT NULL,
    ipc_code_normalized TEXT NOT NULL,
    analysis_level TEXT NOT NULL,
    source_edition TEXT NOT NULL DEFAULT '',
    target_edition TEXT NOT NULL DEFAULT '',
    rule_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK(status IN ('suggested','confirmed','unresolved','deprecated')),
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ipc_code_raw,analysis_level,source_edition,target_edition,rule_version)
);

CREATE TABLE reduced_ipc_edges (
    reduced_edge_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    ipc1 TEXT NOT NULL,
    ipc2 TEXT NOT NULL,
    cooccurrence_count INTEGER NOT NULL,
    source_patent_count INTEGER,
    ipc1_count INTEGER,
    ipc2_count INTEGER,
    total_patent_count INTEGER,
    normalization_method TEXT NOT NULL DEFAULT '',
    denominator_json TEXT NOT NULL DEFAULT '{}',
    source_row INTEGER,
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    CHECK(ipc1 < ipc2),
    UNIQUE(dataset_id,year,ipc1,ipc2)
);

CREATE TABLE researcher_fusion_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    project_id TEXT,
    dataset_id TEXT,
    ipc1 TEXT NOT NULL,
    ipc2 TEXT NOT NULL,
    stated_probability REAL,
    rationale TEXT NOT NULL DEFAULT '',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id),
    CHECK(ipc1 < ipc2)
);

CREATE TABLE network_runs (
    network_run_id TEXT PRIMARY KEY,
    project_id TEXT,
    snapshot_checksum TEXT NOT NULL,
    research_contract_version INTEGER NOT NULL,
    algorithm_version TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    input_checksum TEXT NOT NULL,
    result_checksum TEXT NOT NULL DEFAULT '',
    evidence_grade TEXT NOT NULL DEFAULT 'canonical',
    status TEXT NOT NULL DEFAULT 'running',
    random_seed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    UNIQUE(input_checksum,algorithm_version)
);

CREATE TABLE network_nodes (
    node_measure_id TEXT PRIMARY KEY,
    network_run_id TEXT NOT NULL,
    observation_kind TEXT NOT NULL,
    observation_key TEXT NOT NULL,
    ipc_code TEXT NOT NULL,
    patent_count INTEGER NOT NULL DEFAULT 0,
    degree_centrality REAL,
    betweenness_centrality REAL,
    closeness_centrality REAL,
    eccentricity REAL,
    eigenvector_centrality REAL,
    community_id TEXT,
    layout_x REAL,
    layout_y REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(network_run_id) REFERENCES network_runs(network_run_id) ON DELETE CASCADE,
    UNIQUE(network_run_id,observation_kind,observation_key,ipc_code)
);

CREATE TABLE ipc_edges_yearly (
    edge_id TEXT PRIMARY KEY,
    network_run_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    ipc1 TEXT NOT NULL,
    ipc2 TEXT NOT NULL,
    cooccurrence_count INTEGER NOT NULL,
    supporting_patent_count INTEGER NOT NULL,
    association_strength REAL,
    jaccard REAL,
    pmi REAL,
    denominators_json TEXT NOT NULL DEFAULT '{}',
    supporting_patent_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_grade TEXT NOT NULL DEFAULT 'canonical',
    FOREIGN KEY(network_run_id) REFERENCES network_runs(network_run_id) ON DELETE CASCADE,
    CHECK(ipc1 < ipc2),
    UNIQUE(network_run_id,year,ipc1,ipc2)
);

CREATE TABLE ipc_edges_period (
    edge_id TEXT PRIMARY KEY,
    network_run_id TEXT NOT NULL,
    period_code TEXT NOT NULL,
    ipc1 TEXT NOT NULL,
    ipc2 TEXT NOT NULL,
    cooccurrence_count INTEGER NOT NULL,
    supporting_patent_count INTEGER NOT NULL,
    association_strength REAL,
    jaccard REAL,
    pmi REAL,
    denominators_json TEXT NOT NULL DEFAULT '{}',
    supporting_patent_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_grade TEXT NOT NULL DEFAULT 'canonical',
    FOREIGN KEY(network_run_id) REFERENCES network_runs(network_run_id) ON DELETE CASCADE,
    CHECK(ipc1 < ipc2),
    UNIQUE(network_run_id,period_code,ipc1,ipc2)
);

CREATE TABLE node_transitions (
    transition_id TEXT PRIMARY KEY,
    network_run_id TEXT NOT NULL,
    ipc_code TEXT NOT NULL,
    from_observation TEXT NOT NULL,
    to_observation TEXT NOT NULL,
    transition_type TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    threshold_json TEXT NOT NULL DEFAULT '{}',
    sensitivity_status TEXT NOT NULL DEFAULT 'not_evaluated',
    FOREIGN KEY(network_run_id) REFERENCES network_runs(network_run_id) ON DELETE CASCADE,
    UNIQUE(network_run_id,ipc_code,from_observation,to_observation,transition_type)
);

CREATE TABLE community_memberships (
    membership_id TEXT PRIMARY KEY,
    network_run_id TEXT NOT NULL,
    observation_kind TEXT NOT NULL,
    observation_key TEXT NOT NULL,
    ipc_code TEXT NOT NULL,
    community_id TEXT NOT NULL,
    stable_community_id TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    FOREIGN KEY(network_run_id) REFERENCES network_runs(network_run_id) ON DELETE CASCADE,
    UNIQUE(network_run_id,observation_kind,observation_key,ipc_code)
);

CREATE TABLE feature_runs (
    feature_run_id TEXT PRIMARY KEY,
    network_run_id TEXT NOT NULL,
    cutoff_year INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    candidate_policy_json TEXT NOT NULL DEFAULT '{}',
    feature_definitions_json TEXT NOT NULL DEFAULT '{}',
    input_checksum TEXT NOT NULL,
    result_checksum TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(network_run_id) REFERENCES network_runs(network_run_id),
    UNIQUE(input_checksum,schema_version)
);

CREATE TABLE fusion_candidates (
    candidate_id TEXT PRIMARY KEY,
    feature_run_id TEXT NOT NULL,
    ipc1 TEXT NOT NULL,
    ipc2 TEXT NOT NULL,
    target_type TEXT NOT NULL,
    eligible INTEGER NOT NULL DEFAULT 1,
    exclusion_reason TEXT NOT NULL DEFAULT '',
    label INTEGER,
    label_window TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(feature_run_id) REFERENCES feature_runs(feature_run_id) ON DELETE CASCADE,
    CHECK(ipc1 < ipc2),
    UNIQUE(feature_run_id,ipc1,ipc2,target_type)
);

CREATE TABLE fusion_features (
    feature_value_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    feature_value REAL,
    feature_status TEXT NOT NULL DEFAULT 'observed',
    lineage_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(candidate_id) REFERENCES fusion_candidates(candidate_id) ON DELETE CASCADE,
    UNIQUE(candidate_id,feature_name)
);

CREATE TABLE model_runs (
    model_run_id TEXT PRIMARY KEY,
    feature_run_id TEXT NOT NULL,
    model_kind TEXT NOT NULL,
    model_version TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    random_seed INTEGER NOT NULL DEFAULT 0,
    input_checksum TEXT NOT NULL,
    artifact_path TEXT NOT NULL DEFAULT '',
    result_checksum TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    selected INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY(feature_run_id) REFERENCES feature_runs(feature_run_id),
    UNIQUE(input_checksum,model_kind,model_version)
);

CREATE TABLE model_calibrations (
    calibration_id TEXT PRIMARY KEY,
    model_run_id TEXT NOT NULL,
    method TEXT NOT NULL,
    support_count INTEGER NOT NULL DEFAULT 0,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    artifact_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'not_estimable',
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id),
    UNIQUE(model_run_id,method)
);

CREATE TABLE fusion_predictions (
    prediction_id TEXT PRIMARY KEY,
    model_run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    raw_score REAL NOT NULL,
    probability_status TEXT NOT NULL DEFAULT 'uncalibrated',
    calibrated_probability REAL,
    interval_low REAL,
    interval_high REAL,
    explanation_json TEXT NOT NULL DEFAULT '{}',
    limitations_json TEXT NOT NULL DEFAULT '[]',
    stability_status TEXT NOT NULL DEFAULT 'not_evaluated',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id),
    FOREIGN KEY(candidate_id) REFERENCES fusion_candidates(candidate_id),
    UNIQUE(model_run_id,candidate_id),
    UNIQUE(model_run_id,rank),
    CHECK(calibrated_probability IS NULL OR
          (calibrated_probability >= 0 AND calibrated_probability <= 1)),
    CHECK(interval_low IS NULL OR interval_low >= 0),
    CHECK(interval_high IS NULL OR interval_high <= 1)
);

CREATE TABLE validation_folds (
    fold_id TEXT PRIMARY KEY,
    model_run_id TEXT NOT NULL,
    fold_name TEXT NOT NULL,
    train_cutoff INTEGER NOT NULL,
    outcome_start INTEGER NOT NULL,
    outcome_end INTEGER NOT NULL,
    input_checksum TEXT NOT NULL,
    support_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id),
    UNIQUE(model_run_id,fold_name)
);

CREATE TABLE validation_metrics (
    metric_id TEXT PRIMARY KEY,
    model_run_id TEXT NOT NULL,
    fold_id TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    status TEXT NOT NULL DEFAULT 'estimated',
    reason TEXT NOT NULL DEFAULT '',
    interval_low REAL,
    interval_high REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id),
    FOREIGN KEY(fold_id) REFERENCES validation_folds(fold_id),
    UNIQUE(model_run_id,fold_id,metric_name)
);

CREATE TABLE ablation_runs (
    ablation_id TEXT PRIMARY KEY,
    model_run_id TEXT NOT NULL,
    omitted_feature_family TEXT NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    rank_changes_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'completed',
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id),
    UNIQUE(model_run_id,omitted_feature_family)
);

CREATE TABLE sensitivity_runs (
    sensitivity_id TEXT PRIMARY KEY,
    model_run_id TEXT NOT NULL,
    sensitivity_kind TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    candidate_changes_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'completed',
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id)
);

CREATE TABLE publication_gates (
    gate_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    job_id TEXT,
    model_run_id TEXT,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    overridden INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT NOT NULL DEFAULT '',
    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(job_id) REFERENCES forecast_jobs(job_id),
    FOREIGN KEY(model_run_id) REFERENCES model_runs(model_run_id),
    UNIQUE(project_id,job_id,gate_name)
);

CREATE TABLE graph_threads (
    thread_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    graph_version TEXT NOT NULL,
    state_schema_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    current_node TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES forecast_jobs(job_id)
);

CREATE TABLE graph_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    state_json TEXT NOT NULL,
    state_checksum TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(thread_id) REFERENCES graph_threads(thread_id) ON DELETE CASCADE,
    UNIQUE(thread_id,sequence),
    UNIQUE(thread_id,state_checksum)
);

CREATE TABLE graph_node_events (
    event_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    input_refs_json TEXT NOT NULL DEFAULT '[]',
    output_refs_json TEXT NOT NULL DEFAULT '[]',
    output_checksum TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    error_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(thread_id) REFERENCES graph_threads(thread_id) ON DELETE CASCADE
);

CREATE TABLE human_reviews (
    review_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    review_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approve','edit','reject')),
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT 'local-user',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(thread_id) REFERENCES graph_threads(thread_id)
);

CREATE TABLE prompt_manifests (
    prompt_manifest_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'zh-CN',
    input_schema_version TEXT NOT NULL,
    output_schema_version TEXT NOT NULL,
    template_checksum TEXT NOT NULL,
    template_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role,prompt_version,template_checksum)
);

CREATE TABLE model_manifests (
    model_manifest_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_profile_json TEXT NOT NULL DEFAULT '{}',
    parameters_json TEXT NOT NULL DEFAULT '{}',
    dependency_versions_json TEXT NOT NULL DEFAULT '{}',
    checksum TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE export_manifests (
    export_manifest_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    manifest_version TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum TEXT NOT NULL UNIQUE,
    export_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'building',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(job_id) REFERENCES forecast_jobs(job_id)
);

CREATE INDEX idx_projects_contract ON projects(research_contract_version,lifecycle_status);
CREATE INDEX idx_patents_dataset_year ON patents(dataset_id,application_year);
CREATE INDEX idx_patents_publication ON patents(publication_number);
CREATE INDEX idx_patent_ipcs_code ON patent_ipcs(ipc_code_normalized,patent_id);
CREATE INDEX idx_coverage_dataset_year ON data_coverage(dataset_id,year,completeness);
CREATE INDEX idx_ipc_mapping_lookup ON ipc_code_mappings(ipc_code_raw,analysis_level,status);
CREATE INDEX idx_reduced_edges_year ON reduced_ipc_edges(dataset_id,year,ipc1,ipc2);
CREATE INDEX idx_network_runs_project ON network_runs(project_id,created_at DESC);
CREATE INDEX idx_network_nodes_lookup ON network_nodes(network_run_id,observation_kind,observation_key,ipc_code);
CREATE INDEX idx_network_edges_year ON ipc_edges_yearly(network_run_id,year,ipc1,ipc2);
CREATE INDEX idx_network_edges_period ON ipc_edges_period(network_run_id,period_code,ipc1,ipc2);
CREATE INDEX idx_transitions_code ON node_transitions(network_run_id,ipc_code);
CREATE INDEX idx_candidates_pair ON fusion_candidates(ipc1,ipc2,target_type);
CREATE INDEX idx_predictions_rank ON fusion_predictions(model_run_id,rank);
CREATE INDEX idx_validation_model ON validation_metrics(model_run_id,metric_name);
CREATE INDEX idx_sensitivity_model ON sensitivity_runs(model_run_id,sensitivity_kind);
CREATE INDEX idx_checkpoints_thread ON graph_checkpoints(thread_id,sequence DESC);
CREATE INDEX idx_events_thread ON graph_node_events(thread_id,created_at);
CREATE INDEX idx_reviews_target ON human_reviews(thread_id,review_kind,target_id);
CREATE INDEX idx_exports_job ON export_manifests(job_id,created_at DESC);
"""


SCHEMA_V7 = """
ALTER TABLE datasets ADD COLUMN research_contract_version INTEGER NOT NULL DEFAULT 2;
CREATE INDEX idx_datasets_research_contract
ON datasets(research_contract_version,period_code,status,lifecycle_status);
"""

SCHEMA_V8 = """
ALTER TABLE fusion_predictions ADD COLUMN evidence_grade TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE fusion_predictions ADD COLUMN probability_authority TEXT NOT NULL DEFAULT 'deterministic_model'
    CHECK(probability_authority IN ('deterministic_model','validated_model'));
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
                version = 2
            if version < 3:
                connection.executescript(SCHEMA_V3)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (3)"
                )
                version = 3
            if version < 4:
                connection.executescript(SCHEMA_V4)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (4)"
                )
                version = 4
            if version < 5:
                connection.executescript(SCHEMA_V5)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (5)"
                )
                version = 5
            if version < 6:
                connection.executescript(SCHEMA_V6)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (6)"
                )
                version = 6
            if version < 7:
                connection.executescript(SCHEMA_V7)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (7)"
                )
                version = 7
            if version < 8:
                connection.executescript(SCHEMA_V8)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (8)"
                )
            self._seed_taxonomy(connection)

    @staticmethod
    def _seed_taxonomy(connection: sqlite3.Connection) -> None:
        for node_id, parent_id, level, name, slug, sort_order in TECHNOLOGY_SEED:
            connection.execute(
                """INSERT OR IGNORE INTO technology_nodes(
                    node_id,parent_id,level,name,slug,sort_order,taxonomy_version
                ) VALUES (?,?,?,?,?,?,1)""",
                (node_id, parent_id, level, name, slug, sort_order),
            )
        for source, target, relation_type in TECHNOLOGY_RELATION_SUGGESTIONS:
            relation_id = f"relation_{source[5:]}_{target[5:]}_{relation_type}"
            connection.execute(
                """INSERT OR IGNORE INTO technology_relations(
                    relation_id,source_node_id,target_node_id,relation_type,status
                ) VALUES (?,?,?,?, 'suggested')""",
                (relation_id, source, target, relation_type),
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
