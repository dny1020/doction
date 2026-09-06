## ADDED Requirements

### Requirement: The graph is a place in the workspace

The graph view SHALL live at a workspace-scoped address alongside the workspace's other places, and
SHALL be reachable from the navigation rather than only by typing a URL. It obeys the same rules as
every other route: the workspace is named in the address, the mount path is configuration, and the
document title names the view.

#### Scenario: Addressing the graph

- **WHEN** the graph view is open
- **THEN** the address names the workspace, and sharing it opens the same workspace's graph

#### Scenario: Reaching the graph

- **WHEN** a workspace is open
- **THEN** the graph is reachable from the navigation
