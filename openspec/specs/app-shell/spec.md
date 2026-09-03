## Purpose

Defines the behaviour of doction's SPA layout shell: which chrome stays visible while
content scrolls, how the shell reflows between desktop, tablet and phone viewports, and the
ergonomic floor for controls driven by touch rather than a mouse.

## Requirements

### Requirement: Sidebar chrome remains visible while the page tree scrolls

The sidebar SHALL scroll only its page tree. The sidebar's header region (brand, workspace
selector, search field) and its footer region (Inbox, New page, language, theme, user menu)
MUST remain visible at every scroll position of the tree, on every viewport size.

#### Scenario: Long page tree scrolled to the bottom

- **WHEN** a workspace contains more pages than fit the sidebar's height and the user
  scrolls the page tree to its end
- **THEN** the brand, workspace selector and search field remain visible at the top of the
  sidebar
- **AND** the Inbox link, New page button, theme control and user avatar remain visible at
  the bottom of the sidebar

#### Scenario: Short page tree

- **WHEN** the page tree is shorter than the available sidebar height
- **THEN** the tree does not scroll and no scrollbar is shown for it
- **AND** the footer region remains pinned to the bottom edge of the sidebar

#### Scenario: Sidebar scroll does not chain to the page behind it

- **WHEN** the user scrolls past either end of the page tree on a touch device
- **THEN** the main content area behind the sidebar does not scroll

### Requirement: Page-row actions remain usable at any scroll position

The per-page actions menu in the page tree SHALL be fully visible and operable regardless of
where its row sits within the scrolled tree. It MUST NOT be clipped by the tree's scroll
boundary.

#### Scenario: Actions on a row near the bottom of the visible tree

- **WHEN** the user opens the actions menu for a page row close to the bottom edge of the
  scrolled tree
- **THEN** the entire menu is visible and every option in it can be selected

#### Scenario: Move and rename behaviour is unchanged

- **WHEN** the user chooses Move or Rename from a row's actions
- **THEN** the existing move and rename flows run unchanged, including the alias that keeps
  previously written wikilinks resolving

### Requirement: The sidebar visibility control is always reachable

A control to hide or show the sidebar SHALL be visible and operable at every scroll
position, on every viewport size. The user MUST never have to scroll any region in order to
reach it.

#### Scenario: Hiding the sidebar from a scrolled tree

- **WHEN** the sidebar is open, the page tree is scrolled away from the top, and the user
  looks for the hide control
- **THEN** the hide control is visible without scrolling the tree back up

#### Scenario: Showing the sidebar from a scrolled document

- **WHEN** the sidebar is hidden and the user has scrolled deep into a long page
- **THEN** a control to show the sidebar is visible without scrolling back to the top of the
  document

#### Scenario: Control is not obscured by content

- **WHEN** the sidebar visibility control is displayed over or beside the content area
- **THEN** it does not overlap page text, breadcrumbs or headings at any scroll position

### Requirement: Small viewports present a minimal persistent content header

On viewports at or below the mobile breakpoint, the content area SHALL present a persistent
header that remains visible while the document scrolls. The header MUST be limited to a
single row containing at most: the sidebar visibility control, the current page title, and a
single overflow control for that page's secondary actions.

The header MUST NOT introduce navigation patterns absent from the desktop interface — no
tab bar, no bottom navigation, no search field of its own, and no brand mark (the brand
remains in the sidebar).

#### Scenario: Header persists while reading

- **WHEN** the user scrolls a long page on a phone
- **THEN** the header remains fixed at the top of the content area
- **AND** the sidebar visibility control and page title stay visible throughout

#### Scenario: Header stays minimal

- **WHEN** the header is rendered on any small viewport
- **THEN** it occupies a single row
- **AND** it contains no controls beyond the sidebar toggle, the page title, and one
  overflow control

#### Scenario: Header is absent on desktop

- **WHEN** the viewport is above the mobile breakpoint
- **THEN** no content header is rendered, and the sidebar visibility control remains in its
  existing desktop position

### Requirement: Editing controls remain reachable on small viewports

On viewports at or below the mobile breakpoint, the controls that commit or abandon an edit
SHALL remain reachable at every scroll position while the editor is open. The user MUST NOT
have to scroll to another part of the document to save.

#### Scenario: Saving from the bottom of a long document

- **WHEN** the user is editing a long page on a phone and has scrolled to the end of the text
- **THEN** the save and cancel controls are reachable without scrolling back to the top

#### Scenario: Unsaved-changes guard is unaffected

- **WHEN** the user navigates away with unsaved changes
- **THEN** the existing unsaved-changes confirmation is shown, unchanged by the relocation of
  the save controls

#### Scenario: Desktop editor is unchanged

- **WHEN** the editor is opened above the mobile breakpoint
- **THEN** the title field and the save and cancel controls appear in their existing
  positions with their existing spacing

### Requirement: Only navigation and commit controls are persistent

Page furniture that provides context rather than action SHALL scroll with the document.
Specifically, breadcrumbs, page metadata (last-updated and author), subpage lists, backlinks
and related-page lists MUST NOT be made persistent.

This requirement exists to bound the previous ones: persistence is reserved for controls the
user needs at an arbitrary scroll position, not applied to the interface as a whole.

#### Scenario: Contextual furniture scrolls away

- **WHEN** the user scrolls down a page on any viewport
- **THEN** the breadcrumb trail and the last-updated line scroll out of view with the content

#### Scenario: Table of contents behaviour is unchanged

- **WHEN** the viewport is wide enough to show the table-of-contents column
- **THEN** it remains sticky exactly as it does today
- **AND** it remains hidden below that width

### Requirement: Touch hit targets meet a 44px minimum without altering visual density

On devices whose primary pointer is coarse, every interactive control in the shell SHALL
present a hit area of at least 44 by 44 CSS pixels. The control's rendered size MUST NOT
change; only the area that responds to a touch grows.

This includes the controls each page row carries in the tree — its disclosure control and its
overflow control. These sit at opposite ends of a row narrower than three 44px squares, so
non-overlap takes precedence over the square: their hit areas MUST NOT overlap each other or the
row's navigation area, and a touch on a row's label MUST NOT toggle its disclosure.

Where the two cannot both hold, a control SHALL take the full 44px height of the row and only as
much width as its own gutter allows. The disclosure control is the case this covers: it lives in a
gutter of about 24px to the left of the title, and a 44px square centred on it would cover the
first characters of the title, so tapping the text would collapse the branch instead of opening
the page. A short, full-height target that never steals a touch is worth more than a square one
that does.

On devices with a fine pointer, control sizes and spacing MUST remain exactly as they are
today.

#### Scenario: Buttons on a touch device

- **WHEN** the interface is displayed on a device reporting a coarse primary pointer
- **THEN** buttons, the sidebar toggle, theme and language controls, the search-clear
  control and page-row overflow controls each respond to a touch anywhere within a 44px
  square centred on them

#### Scenario: Tree row controls on a touch device

- **WHEN** a page row carrying a disclosure control and an overflow control is displayed on a
  coarse-pointer device
- **THEN** each control responds to a touch anywhere in a target at least 44px tall
- **AND** no target overlaps another, nor the row's navigation area

#### Scenario: Expanding does not navigate

- **WHEN** a person touches a row's disclosure control
- **THEN** the branch expands or collapses and no navigation occurs

#### Scenario: Rendered size is unchanged on touch

- **WHEN** a control's hit area is expanded for touch
- **THEN** its visible dimensions, padding, border and typography are identical to the same
  control on a fine-pointer device

#### Scenario: Tree density is unchanged

- **WHEN** disclosure controls are added to the tree
- **THEN** row height, indentation per level and the sidebar's visual density are unchanged from
  the current interface on a fine-pointer device

#### Scenario: Desktop density is preserved

- **WHEN** the interface is displayed on a device with a fine primary pointer
- **THEN** no control's height, padding or spacing differs from the current interface

### Requirement: The shell reflows across three viewport bands

The shell SHALL present the sidebar as a persistent column on wide viewports, as a narrowed
persistent column on intermediate viewports, and as an overlay drawer on small viewports.
No viewport width may leave the content area with less usable width than the band above it.

#### Scenario: Intermediate widths keep a usable content area

- **WHEN** the viewport is between the mobile breakpoint and the width at which the
  table-of-contents column is dropped
- **THEN** the sidebar remains a persistent column at a reduced width
- **AND** the content area is wider than it would be with the full-width sidebar

#### Scenario: Wide viewports are unchanged

- **WHEN** the viewport is wide enough to show the table-of-contents column
- **THEN** the sidebar width, content width and spacing are identical to the current
  interface

### Requirement: The mobile sidebar behaves as a dismissable drawer

On viewports at or below the mobile breakpoint, the sidebar SHALL overlay the content rather
than displace it, and MUST be dismissable without using the toggle.

#### Scenario: Opening the drawer

- **WHEN** the user activates the sidebar control on a phone
- **THEN** the sidebar slides over the content and the content behind it is dimmed

#### Scenario: Dismissing by tapping away

- **WHEN** the drawer is open and the user taps the dimmed content area
- **THEN** the drawer closes and no navigation occurs

#### Scenario: Navigating closes the drawer

- **WHEN** the user selects a page from the tree while the drawer is open
- **THEN** the drawer closes and the selected page is shown

#### Scenario: Drawer state is not persisted on mobile

- **WHEN** the user opens the drawer on a phone and later reloads the application
- **THEN** the drawer starts closed, regardless of its state before the reload
