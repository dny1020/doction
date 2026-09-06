# navigation Specification

## Purpose
Defines how doction's three-level model — workspace, page, subpage — is addressed and operated:
what a URL identifies, and how the hierarchy is navigated without a pointer. A page's position in
the tree is the product's central idea, so the tree has to be addressable and operable, not just
visible.

## Requirements

### Requirement: The URL identifies the workspace as well as the page

A page's address SHALL name both the workspace and the page. Opening such an address MUST make
that workspace active, regardless of which workspace was active before, and MUST NOT require the
person to switch workspaces first.

The active workspace is currently server-side session state, which is why a link to a page is
only valid for whoever happens to have that workspace active. Addressing the workspace in the URL
is what makes a link to a page a link to a page.

#### Scenario: Opening a page in a non-active workspace

- **WHEN** a person opens a page address naming workspace B while workspace A is active
- **THEN** the page is shown and workspace B becomes the active workspace

#### Scenario: A shared link

- **WHEN** one member sends another the address of a page
- **THEN** the recipient, who is a member of that workspace, sees that page — not a not-found
  and not a different workspace's page of the same name

#### Scenario: Reload and history

- **WHEN** a person navigates through several pages and then reloads, or uses the browser's back
  and forward buttons
- **THEN** each step restores both the workspace and the page it was taken in

#### Scenario: A subpage's address

- **WHEN** a subpage is opened
- **THEN** its address identifies it directly, so it can be linked and bookmarked without going
  through its parent

#### Scenario: Existing page addresses keep working

- **WHEN** a previously bookmarked address that names only the page is opened
- **THEN** it resolves to that page's new address rather than failing

### Requirement: Switching workspaces is navigation, not a reload

Choosing another workspace SHALL be an in-application navigation. It MUST NOT discard the loaded
application, and it MUST leave a history entry that the back button returns from.

#### Scenario: Choosing another workspace

- **WHEN** a person selects a different workspace from the selector
- **THEN** the tree and content update in place and the application is not reloaded

#### Scenario: Going back

- **WHEN** a person switches workspaces and then presses back
- **THEN** they return to where they were in the previous workspace

#### Scenario: Switching with unsaved changes

- **WHEN** a person switches workspaces while an editor holds unsaved changes
- **THEN** the existing unsaved-changes confirmation is shown before the switch proceeds

### Requirement: The page tree presents and preserves the hierarchy

The sidebar SHALL present pages as a hierarchy in which a page with children can be collapsed and
expanded. Collapse state MUST persist across navigation within a session, and the path to the
active page MUST always be expanded so the active page is visible in the tree.

#### Scenario: A page with children

- **WHEN** a page in the tree has subpages
- **THEN** it carries a control that expands and collapses them, and its state is visible without
  relying on colour alone

#### Scenario: A page without children

- **WHEN** a page has no subpages
- **THEN** it carries no disclosure control, and its label aligns with the labels of pages that do

#### Scenario: The active page is revealed

- **WHEN** a page is opened whose ancestors are collapsed
- **THEN** the path to it expands so it is visible and marked as current

#### Scenario: Collapse state survives navigation

- **WHEN** a person collapses a branch and then navigates to a page in another branch
- **THEN** the collapsed branch is still collapsed

### Requirement: The page tree is fully operable from the keyboard

The tree SHALL be reachable and operable using only the keyboard. It MUST take a single Tab stop
rather than one per row, and within it: up and down move between visible rows, right expands a
collapsed row and then moves into it, left collapses an expanded row and otherwise moves to its
parent, and Enter opens the focused page.

Focus MUST be visible at every step, and the tree MUST expose itself to assistive technology as a
tree whose rows carry their level and their expanded state.

#### Scenario: Reaching the tree

- **WHEN** a person tabs through the sidebar
- **THEN** the tree takes one Tab stop, landing on the active page's row or the first row

#### Scenario: Moving and opening

- **WHEN** the tree has focus and the person presses down, up and Enter
- **THEN** focus moves between visible rows in display order and Enter opens the focused page

#### Scenario: Expanding and collapsing

- **WHEN** the focused row is collapsed and the person presses right
- **THEN** it expands without navigating, and a second right press moves focus to its first child

#### Scenario: Collapsing and moving to the parent

- **WHEN** the focused row is expanded and the person presses left
- **THEN** it collapses; pressing left again moves focus to its parent row

#### Scenario: Announced structure

- **WHEN** a screen reader moves through the tree
- **THEN** each row is announced with its nesting level and, where it has children, whether it is
  expanded

#### Scenario: Focus is never lost

- **WHEN** the tree reloads after a page is created, moved, renamed or deleted
- **THEN** focus stays on an existing row rather than returning to the top of the document

### Requirement: Search is reachable by keyboard from anywhere

A global shortcut SHALL open search from anywhere in the application, on both the Command and
Control conventions, and results MUST be selectable and openable without a pointer. The shortcut
MUST work while focus is in a text field and MUST NOT override the browser's own shortcuts.

#### Scenario: Opening search

- **WHEN** a person presses the search shortcut anywhere in the application
- **THEN** search opens with focus in its input, whichever of the two modifier conventions was
  used

#### Scenario: Opening from a text field

- **WHEN** the shortcut is pressed while typing in the editor or in a settings field
- **THEN** search still opens, and the character is not inserted into the field

#### Scenario: Choosing a result

- **WHEN** search is open with results
- **THEN** the arrow keys move the selection, Enter opens the selected page, and Escape closes
  search

#### Scenario: Focus returns

- **WHEN** search is closed without choosing a result
- **THEN** focus returns to whatever held it before search opened

#### Scenario: Closed search is not in the tab order

- **WHEN** search is closed but still present in the document
- **THEN** nothing inside it can be reached by Tab

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
