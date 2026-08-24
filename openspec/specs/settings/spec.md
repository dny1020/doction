## Purpose

Defines how doction's settings are grouped, addressed and navigated: which settings belong
together, how each group is reached by URL, and how the navigation between groups behaves as
the viewport narrows.

## Requirements

### Requirement: Each settings section has its own address

Settings SHALL be divided into named sections, each reachable at its own URL under
`/settings`. Navigating between sections MUST be ordinary navigation: the browser's back and
forward buttons move between visited sections, and a section URL can be linked to, bookmarked
and reloaded directly.

#### Scenario: Opening a section directly

- **WHEN** a person loads the URL of a settings section directly
- **THEN** that section's content is shown
- **AND** the section navigation marks that section as the current one

#### Scenario: Back button returns to the previous section

- **WHEN** a person opens one settings section, then another, then presses the browser's back
  button
- **THEN** the first section is shown again

#### Scenario: The bare settings URL stays valid

- **WHEN** a person opens `/settings` with no section named
- **THEN** they land on a section rather than an error or an empty frame

#### Scenario: An unknown section name

- **WHEN** a person opens a settings URL naming a section that does not exist
- **THEN** the interface responds the same way it does to any other unknown URL, rather than
  rendering an empty settings frame

### Requirement: Only the selected section's content is rendered

The settings area SHALL show the content of exactly one section at a time. Content belonging
to other sections MUST NOT be present in the same scroll, whether visible, collapsed, or
below the fold.

#### Scenario: Switching sections replaces the content

- **WHEN** a person moves from one section to another
- **THEN** the previous section's controls are no longer in the document
- **AND** the new section's content starts at the top of the content area

#### Scenario: A section is short enough not to scroll

- **WHEN** a section's content fits the viewport
- **THEN** the settings area does not scroll

### Requirement: Section navigation adapts to viewport width

Navigation between sections SHALL be persistent alongside the content when there is room for
it, and SHALL collapse to a compact selector when there is not. At every width, moving to
another section MUST take a single interaction from the section currently shown.

The threshold is a property of the settings area, not of the application shell: the shell's
sidebar already occupies horizontal space, so section navigation must collapse while the
sidebar is still a persistent column.

#### Scenario: Wide viewport

- **WHEN** the viewport is wide enough for both the shell sidebar and section navigation
- **THEN** every section is listed beside the content
- **AND** the current section is distinguishable from the others

#### Scenario: Intermediate viewport with the sidebar still persistent

- **WHEN** the viewport is too narrow for a second persistent navigation column but wide
  enough that the shell sidebar is still a persistent column
- **THEN** section navigation is presented as a compact selector rather than a list
- **AND** the content area is not narrower than it would be with the list shown

#### Scenario: Small viewport

- **WHEN** the viewport is at a width where the shell sidebar is an overlay drawer
- **THEN** section navigation is a compact selector
- **AND** it is reachable without opening the shell sidebar

#### Scenario: Changing section from the compact selector

- **WHEN** a person uses the compact selector to choose another section
- **THEN** that section is shown and the selector reflects the new current section
- **AND** any overlay the selector opened is dismissed

### Requirement: Settings are grouped by what they act on

Each section SHALL cover one subject, and every setting MUST belong to exactly one section.
A section MUST NOT be presented when the capability behind it does not exist.

#### Scenario: Account settings

- **WHEN** a person opens the account section
- **THEN** they can change their display name and avatar colour, see the email they signed in
  with, and change their password

#### Scenario: Preferences

- **WHEN** a person opens the preferences section
- **THEN** they can change the interface theme and language

#### Scenario: Preferences remain reachable from the shell

- **WHEN** a person uses the theme or language control in the application shell
- **THEN** it works as it does today
- **AND** the preferences section reflects the value that control set

#### Scenario: Machine integrations are separate from the account

- **WHEN** a person opens the access tokens section or the webhooks section
- **THEN** each shows only its own integrations, and neither appears inside the account section

#### Scenario: No section without a capability

- **WHEN** the settings area is rendered
- **THEN** it offers no section whose content would be a placeholder for an unbuilt feature

### Requirement: Section navigation states its own position

The settings area SHALL make clear which section is current, both in the navigation and to
assistive technology, and MUST NOT rely on colour alone to do so.

#### Scenario: Current section is announced

- **WHEN** a screen reader reaches the section navigation
- **THEN** the current section is identifiable as current, not merely styled differently

#### Scenario: Keyboard navigation

- **WHEN** a person moves through the section navigation with the keyboard
- **THEN** each section is focusable, the focused item is visibly indicated, and activating it
  opens that section
