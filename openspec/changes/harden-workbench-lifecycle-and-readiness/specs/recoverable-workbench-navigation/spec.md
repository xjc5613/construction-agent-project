## ADDED Requirements

### Requirement: Workflow pages are URL-addressable
The system SHALL encode the active page and required project or job identifiers in the URL and SHALL support browser back, forward, refresh, and direct linking.

#### Scenario: Project evidence route is opened directly
- **WHEN** a user loads `/projects/:projectId/evidence`
- **THEN** the application fetches that project and renders its evidence page without requiring prior in-memory navigation

#### Scenario: Browser back is used
- **WHEN** a user navigates from topics to evidence and then activates browser back
- **THEN** the topics route and its project context are restored

#### Scenario: Unknown identifier is routed
- **WHEN** a route contains an unknown project or job identifier
- **THEN** the application displays a recoverable not-found state with navigation to the relevant list

### Requirement: Project and result context recover from the server
The system SHALL treat route identifiers and backend resources as authoritative and SHALL not require React memory or local storage to restore a project, running task, or completed result.

#### Scenario: Application refreshes during a running job
- **WHEN** a project job route is refreshed while its task is queued or running
- **THEN** polling resumes for that task and current progress is shown

#### Scenario: Application refreshes after completion
- **WHEN** the task completes and the result route is refreshed
- **THEN** the persisted result is reloaded and remains accessible

### Requirement: Current project is explicitly switchable
The system SHALL provide an accessible project switcher showing the selected project and SHALL navigate to the equivalent supported stage or a safe project landing page when selection changes.

#### Scenario: User switches projects from materials
- **WHEN** a different active project is selected and there are no unsaved changes
- **THEN** the application navigates to that project's materials route and reloads its data

#### Scenario: Archived project appears in history context
- **WHEN** an archived project result is opened
- **THEN** its recorded project name and baseline remain visible without presenting it as an active selection

### Requirement: Unsaved changes are protected
The system SHALL track dirty state for technology edits, material text, import mapping, evidence retrieval configuration, and forecast options, and SHALL warn before route, project, or browser navigation discards those changes.

#### Scenario: Internal navigation would discard edits
- **WHEN** a user attempts to leave a dirty material editor
- **THEN** a dialog offers stay, discard, or save when saving is available

#### Scenario: Successful save clears dirty state
- **WHEN** a pending form is saved successfully
- **THEN** subsequent navigation proceeds without a discard warning

#### Scenario: Browser tab closes with unsaved changes
- **WHEN** the browser unloads while registered dirty state exists
- **THEN** the application invokes the browser's unload protection

### Requirement: Baseline display uses selected project facts
The system SHALL display the selected project's recorded baseline and target and SHALL label global defaults only as defaults for new projects.

#### Scenario: Legacy project is selected
- **WHEN** a project with baseline 2025 is active
- **THEN** the dashboard and workflow context display 2025 and do not label that project as a 2026 baseline

