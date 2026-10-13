## ADDED Requirements

### Requirement: Write operations provide consistent feedback and suppression
The system SHALL give each write operation pending state, duplicate-submit suppression, caught error feedback, field errors where applicable, and success confirmation.

#### Scenario: Save is double-clicked
- **WHEN** an operator activates a save action repeatedly while its request is pending
- **THEN** only one mutation is submitted and the action communicates its pending state

#### Scenario: Async mutation fails
- **WHEN** a write request returns an error or cannot be completed
- **THEN** the failure is caught, announced, and displayed near the affected action without losing entered values

### Requirement: Responsive layout avoids document overflow
The system SHALL remain operable at viewport widths of 390px and above without document-level horizontal overflow. Dense content MAY use local scrolling or a card representation.

#### Scenario: Workbench loads at 390px
- **WHEN** any primary workflow page is rendered at a 390px viewport
- **THEN** navigation is available, primary content fits the viewport, actions remain reachable, and only explicitly dense components may scroll horizontally within their own bounds

#### Scenario: Dense detail loads at 1024px
- **WHEN** technology detail or a topic table is rendered at 1024px
- **THEN** controls do not overlap or truncate essential operation labels

### Requirement: Text is readable for sustained use
The system SHALL use design tokens that keep essential and supporting text at readable sizes and WCAG AA contrast against their backgrounds.

#### Scenario: Supporting text is rendered
- **WHEN** hints, table metadata, statuses, or workflow explanations are displayed
- **THEN** they use the defined minimum supporting-text size and contrast rather than 7–10px low-contrast styling

### Requirement: Native and custom controls are keyboard accessible
The system SHALL retain native form controls in the accessibility tree, provide accessible names, visible focus indicators, and keyboard operation for navigation, topic selection, configuration, and dialogs.

#### Scenario: Forecast enhancement is toggled by keyboard
- **WHEN** keyboard focus reaches an enhancement checkbox and Space is pressed
- **THEN** its checked state changes and is announced by assistive technology

#### Scenario: Topic row checkbox is focused
- **WHEN** assistive technology encounters a topic selection control
- **THEN** its accessible name identifies the topic and selection purpose

### Requirement: Navigation, notifications, tables, and editing use semantics
The system SHALL identify current navigation with `aria-current`, announce transient notifications through an appropriate live region, render tabular datasets with table semantics, and use labeled explicit controls for editable topic names.

#### Scenario: Current page is announced
- **WHEN** focus moves through the application navigation
- **THEN** assistive technology can identify the link or control for the current page

#### Scenario: Save notification appears
- **WHEN** an asynchronous save succeeds or fails
- **THEN** the notification is announced once through the correct live region

#### Scenario: Data table is inspected
- **WHEN** a screen reader navigates a project, dataset, topic, or result table
- **THEN** headers and cells have programmatically determinable relationships

#### Scenario: Topic name is edited
- **WHEN** an operator edits a topic name
- **THEN** a labeled input with explicit save and cancel replaces blur-dependent content editing

### Requirement: Dialogs manage focus and dismissal safely
The system SHALL implement dialogs with dialog semantics, accessible title, initial focus, focus containment, Escape dismissal where safe, and focus restoration. Destructive confirmation SHALL not be committed by backdrop dismissal.

#### Scenario: Confirmation dialog opens
- **WHEN** a consequential operation requires confirmation
- **THEN** focus moves into the dialog, remains contained, and returns to the trigger after cancel or completion

#### Scenario: Escape closes a safe dialog
- **WHEN** Escape is pressed in a non-pending dialog
- **THEN** the dialog closes without committing the operation

### Requirement: Empty and search states are explicit
The system SHALL distinguish an empty collection from a filtered no-result state and SHALL provide a useful next action.

#### Scenario: IPC query has no matches
- **WHEN** an IPC search completes with zero rows
- **THEN** the result region states that no data matched the query and offers query adjustment or dataset guidance

#### Scenario: Technology search has no matches
- **WHEN** the taxonomy contains nodes but none match the search text
- **THEN** the interface explains that the search condition produced no results rather than suggesting initialization

### Requirement: Charts provide equivalent alternatives
The system SHALL accompany charts with a concise textual summary and an accessible data representation containing the essential plotted values.

#### Scenario: Forecast chart is unavailable visually
- **WHEN** a user cannot perceive or operate the chart
- **THEN** the same trend, categories, nodes, and key values are available through text and a semantic data table or download

### Requirement: Critical journeys have automated browser coverage
The project SHALL provide Playwright tests for complete workflow, readiness gates and overrides, duplicate prevention, refresh/deep-link recovery, history/results, cancellation/retry, confirmation, dirty-state protection, empty states, keyboard accessibility, and 390px/1024px layouts using deterministic mocked forecast execution.

#### Scenario: UI regression suite runs
- **WHEN** the documented browser test command runs in a prepared local or CI environment
- **THEN** critical journeys execute without contacting paid model providers and failures produce actionable traces or screenshots
