## ADDED Requirements

### Requirement: Project lifecycle is reversible and reference-safe
The system SHALL allow project metadata editing, archive, and restore. It SHALL preserve projects and related data that are referenced by forecast jobs.

#### Scenario: Project metadata is edited
- **WHEN** an operator saves a valid project name or description
- **THEN** the project is updated and its baseline, target, scope snapshot, evidence, and jobs remain unchanged

#### Scenario: Project with history is archived
- **WHEN** an operator confirms archive for a project with forecast jobs
- **THEN** the project is removed from active project choices while its history and results remain accessible

#### Scenario: Archived project is restored
- **WHEN** an operator restores an archived project
- **THEN** it returns to active project choices with its prior resources intact

### Requirement: Material lifecycle preserves frozen research inputs
The system SHALL support material metadata/content editing and soft deletion for future workflow use while preventing removal or mutation that would invalidate frozen task evidence.

#### Scenario: Unreferenced text material is edited
- **WHEN** an operator saves valid changes to text material that is not frozen in a task snapshot
- **THEN** the material is updated and affected derived readiness is recalculated

#### Scenario: Referenced material is removed from future use
- **WHEN** an operator deletes material already referenced by a frozen snapshot
- **THEN** the material is marked inactive for future extraction but remains available to historical task recovery

### Requirement: Dataset lifecycle distinguishes deprecation from deletion
The system SHALL allow published datasets to be deprecated and drafts to be deleted only when they contain no committed records and have no evidence, analysis, or snapshot references.

#### Scenario: Published dataset is deprecated
- **WHEN** an operator confirms deprecation of a published dataset
- **THEN** new retrieval excludes it while existing evidence packages and snapshots continue to identify it

#### Scenario: Referenced dataset deletion is requested
- **WHEN** an operator requests deletion of a dataset with records or references
- **THEN** hard deletion is rejected and the response offers deprecation with an impact summary

#### Scenario: Empty unreferenced draft is deleted
- **WHEN** an operator confirms deletion of an empty draft dataset with no references
- **THEN** the dataset is removed and the operation is recorded

### Requirement: Consequential operations require impact confirmation
The system SHALL preview and require confirmation for topic delete/archive/merge, taxonomy archive/move, resource archive/deprecation/deletion, legacy classification, and forecast start. Confirmation SHALL be bound to the reviewed payload and expire.

#### Scenario: Topic merge is previewed
- **WHEN** an operator requests a merge preview
- **THEN** the system shows source topics, resulting name, technology associations, affected evidence, and forecast references before commit

#### Scenario: Confirmed payload changes
- **WHEN** a commit payload differs from the payload bound to its confirmation token
- **THEN** the operation is rejected and a new preview is required

### Requirement: Technology edits use a coherent save model
The system SHALL stage technology name, description, keywords, aliases, ordering, and primary-parent changes together and SHALL apply them only through explicit save confirmation.

#### Scenario: Primary parent selection changes
- **WHEN** an operator selects a different primary parent but has not saved
- **THEN** no backend move occurs and the page is marked as having unsaved changes

#### Scenario: Technology draft is saved
- **WHEN** an operator saves a valid technology edit draft
- **THEN** all changed fields and the parent move are committed transactionally and included in the change log

### Requirement: Legacy classification is isolated and validated
The system SHALL classify a legacy dataset through a dedicated dialog initialized from that dataset, displaying before and after technology, period, and kind. The backend SHALL validate active level-three technology, allowed period and kind, and a valid version.

#### Scenario: Legacy dataset classification opens
- **WHEN** an operator selects classification for an unmapped dataset
- **THEN** the dialog does not inherit hidden defaults from the new-dataset form and requires an explicit technology selection or acknowledgment

#### Scenario: Classification is confirmed
- **WHEN** the operator reviews and confirms valid before/after values
- **THEN** only the selected dataset is classified and the audit record contains both value sets

### Requirement: Business fields use shared validation
The system SHALL reject malformed business fields consistently at API and UI boundaries and SHALL return field-specific errors.

#### Scenario: Punctuation-only version is submitted
- **WHEN** a dataset version such as `@@@` is submitted
- **THEN** creation is rejected with a version format error and no dataset is stored

