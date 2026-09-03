## MODIFIED Requirements

### Requirement: Touch hit targets meet a 44px minimum without altering visual density

On devices whose primary pointer is coarse, every interactive control in the shell SHALL
present a hit area of at least 44 by 44 CSS pixels. The control's rendered size MUST NOT
change; only the area that responds to a touch grows.

This includes the controls each page row carries in the tree — its disclosure control, its
overflow control, and any control for creating a subpage under it. These sit adjacent to one
another in a row shorter than 44px, so their hit areas MUST NOT overlap: a touch intended for one
must never activate another, and a touch on a row's label must never toggle its disclosure.

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
- **THEN** each control responds to a touch within its own 44px target
- **AND** neither target overlaps the other, nor the row's navigation area

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
