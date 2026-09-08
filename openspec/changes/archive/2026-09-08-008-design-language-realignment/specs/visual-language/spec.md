## MODIFIED Requirements

### Requirement: One accent, and it recedes

The interface SHALL use a single hue for every **interactive** emphatic role — links, the active
item, primary actions, focus rings, selection. That hue MUST be readable as text on every surface
it appears on, and it MUST recede on the page rather than compete with the words.

A second hue is permitted as an **identity marker**: the small, non-textual signals that say which
product this is — an indicator beside an active item, a small icon, a status dot, an avatar, a
highlight rule. The marker MUST NOT set body text on a surface where it fails 4.5:1, and it MUST
NOT be the only carrier of any meaning. A third hue is permitted for destructive intent, which is
not emphasis but warning.

Two hues is not two accents. The split is by *job* — one for what a person acts on and reads, one
for what the page points at — and a role that is not one of those three uses neither.

#### Scenario: One hue across the interface

- **WHEN** the interface is surveyed
- **THEN** links, the active page in the tree, primary buttons, focus rings and selected states all
  use the interactive hue

#### Scenario: The marker marks and does not speak

- **WHEN** the identity hue is used
- **THEN** it appears as an indicator, an icon, a dot or a rule, and never as a sentence or a label
  that is the only way to know something

#### Scenario: Destructive is not accent

- **WHEN** a destructive control is displayed
- **THEN** it uses the warning hue and is distinguishable from a primary action

#### Scenario: The accent is readable on its surface

- **WHEN** any of the three hues is used for text on any surface it appears on
- **THEN** the contrast ratio is at least 4.5:1, and where the identity hue cannot meet it the
  readable form of that hue is used instead

## ADDED Requirements

### Requirement: The canvas is paper

The application's surfaces SHALL be warm paper rather than white. No surface in the light theme
may be `#FFFFFF`, and no surface in the dark theme may be a neutral or blue-tinted grey: the dark
theme is warm charcoal, and it is designed rather than inverted.

Surfaces SHALL form a stated hierarchy — page, paper, elevated paper, floating — and a screen
SHALL use the shallowest level that does its job. A section that reads correctly on the page does
not get a container.

The interface MAY carry a paper texture, and where it does the texture SHALL sit at or below the
intensity at which a reader stops noticing it as a layer. Texture belongs to the canvas. It SHALL
NOT be applied to the editor, tables, forms, dense data views, modals or code blocks, where it
competes with the thing being read.

#### Scenario: No white surface

- **WHEN** any surface token is read in the light theme
- **THEN** its value is warm paper, and none of them is pure white

#### Scenario: The dark theme is warm

- **WHEN** any surface token is read in the dark theme
- **THEN** it is a warm charcoal, not a neutral or blue grey, and not pure black

#### Scenario: Texture stays under the threshold

- **WHEN** the texture is rendered on any screen
- **THEN** it is perceived as tactility rather than as a visible pattern, and text over it loses no
  contrast

#### Scenario: Dense surfaces are clean

- **WHEN** the editor, a table, a form, a modal or a code block is rendered
- **THEN** no texture is painted behind it

### Requirement: The design document governs, and deviations are written into it

`DESIGN.md` is the visual source of truth. Every token, type step, radius and shadow the interface
defines SHALL trace to a value stated there.

Where a stated value cannot be used — because it fails a contrast threshold, or because the
application needs a role the document does not name — the implementation SHALL NOT diverge
silently. The replacement is derived from the same hue, it meets the threshold, and it is written
back into `DESIGN.md` with its measurement. A source of truth that the code quietly disagrees with
has stopped being one.

A value present in `DESIGN.md` for a surface this application does not have is not a deviation and
needs no note.

#### Scenario: A stated colour fails a threshold

- **WHEN** a colour named in `DESIGN.md` does not meet the ratio its role requires
- **THEN** the interface uses the lightest value on that hue that does, and `DESIGN.md` records
  both the replacement and the measurement that forced it

#### Scenario: A role the document does not name

- **WHEN** the interface needs a token `DESIGN.md` has no entry for
- **THEN** the token is added to `DESIGN.md` with the reason it exists

#### Scenario: Reading the token block

- **WHEN** the stylesheet's token block is read against `DESIGN.md`
- **THEN** every value matches the document or is one the document records as a deviation
