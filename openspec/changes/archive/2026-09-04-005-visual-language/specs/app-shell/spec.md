## MODIFIED Requirements

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

Adapting for touch SHALL NOT change control sizes or spacing on a device with a fine pointer. The
constraint is on the adaptation, not on the interface: a deliberate change to the visual language
may alter density on both pointers together, and remains bound by the 44px floor. What is forbidden
is density drifting as a side effect of making something touchable.

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

- **WHEN** a control is adapted for coarse pointers
- **THEN** no control's height, padding or spacing differs on a fine pointer from what it was
  before that adaptation
