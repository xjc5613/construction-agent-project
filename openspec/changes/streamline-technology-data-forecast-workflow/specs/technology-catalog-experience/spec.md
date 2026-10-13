## ADDED Requirements

### Requirement: Hierarchy-first technology catalog
The system SHALL make the three-level technology hierarchy the primary technology-management view. The primary view MUST expose technology names, levels, parent-child structure, activation state, child count, and concise data coverage without requiring users to interpret stable IDs, slugs, taxonomy versions, or audit records.

#### Scenario: Researcher opens technology management
- **WHEN** a researcher opens the technology management page
- **THEN** the system displays the technology tree and coverage summary without showing stable IDs, slugs, taxonomy versions, or change logs as primary fields

#### Scenario: Researcher selects a leaf technology
- **WHEN** a researcher selects an active level-three technology
- **THEN** the system displays its full path and counts of active datasets, papers, IPC records, and referencing projects

### Requirement: Focused catalog editing
The system SHALL support adding, renaming, moving, and ordering technology nodes from the hierarchy view. Descriptions, matching keywords, and aliases MUST remain available through a secondary advanced editor because they are used by topic-to-technology matching.

#### Scenario: Rename a technology
- **WHEN** a maintainer renames a technology from the hierarchy
- **THEN** the stable node ID and historical references remain unchanged while the current display name and audit record are updated

#### Scenario: Edit matching terms
- **WHEN** a maintainer opens advanced settings for a technology
- **THEN** the system allows descriptions, keywords, and aliases to be edited without exposing internal storage fields

### Requirement: Secondary technology lifecycle governance
The system SHALL preserve reversible technology deactivation for reference protection but MUST present it as a secondary governance action rather than a primary catalog category. Inactive technologies MUST be excluded from default catalog views and new dataset, topic, and project selections.

#### Scenario: Deactivate a referenced technology
- **WHEN** a maintainer confirms deactivation of a technology referenced by historical evidence or forecasts
- **THEN** the system marks the technology inactive, preserves all historical references, and removes it from new-work selectors

#### Scenario: View inactive technologies
- **WHEN** a maintainer explicitly enables the inactive-technology filter
- **THEN** the system displays inactive technologies with their reference impact and a restore action

### Requirement: Consistent effective activation
The system MUST prevent a hierarchy from presenting an inactive parent with independently active descendants. Deactivating a node with active descendants SHALL require either cancelling the action or explicitly confirming cascade deactivation, and restoration SHALL require an active parent.

#### Scenario: Deactivate a parent with active children
- **WHEN** a maintainer requests deactivation of a technology that has active descendants
- **THEN** the preview identifies all descendants and requires explicit cascade confirmation before changing their effective state

#### Scenario: Restore a child under an inactive parent
- **WHEN** a maintainer attempts to restore a child whose parent is inactive
- **THEN** the system rejects the action and directs the maintainer to restore the parent first

### Requirement: Advanced governance remains available
The system SHALL retain cross-domain relations, immutable change history, stable identifiers, and reference-impact details, but SHALL place them in an advanced governance view that does not interrupt the normal research workflow.

#### Scenario: Maintainer investigates historical changes
- **WHEN** a maintainer opens advanced governance for a technology
- **THEN** the system displays its stable ID, relation records, reference impact, and immutable change history
