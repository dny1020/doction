## ADDED Requirements

### Requirement: Chrome and canvas are different materials

The interface SHALL distinguish the navigation chrome from the document canvas by material,
not only by position. The chrome is a dark ink-green region in both themes; the canvas is warm
paper in the light theme and warm charcoal in the dark one.

A region that changes material SHALL redefine the palette's token *names* within its own
scope rather than restating every rule it contains. A rule resolves a token at the element it
matched, so a scoped redefinition re-themes every descendant without editing the rules
themselves. Any rule that has to be edited to survive the region is evidence the region was
introduced in the wrong place.

Every token the region redefines SHALL be derived against the worst of that region's own
grounds, in both themes, to the same ratios the canvas is held to. A region is not an excuse
for a lower bar; it is a different set of grounds to measure against.

An element that lives inside the region in the document but paints outside it on screen SHALL
re-enter the canvas palette. Otherwise one class renders two ways depending on which subtree
happens to own it.

#### Scenario: The chrome is a distinct material

- **WHEN** the application is viewed in either theme
- **THEN** the navigation chrome reads as a different material from the document, and the
  document remains the brighter, primary surface

#### Scenario: A region re-themes without rule edits

- **WHEN** a shared component is rendered inside the chrome and again on the canvas
- **THEN** both instances are correct for their ground, and neither required a rule of its own

#### Scenario: The region is measured against its own grounds

- **WHEN** contrast is measured inside the chrome, in both themes
- **THEN** ink, accent and control boundaries meet the same ratios required on the canvas,
  against the darkest and lightest grounds the chrome itself uses

#### Scenario: A modal escapes its subtree

- **WHEN** a dialog declared inside the chrome is opened over the canvas
- **THEN** it is painted in the canvas palette, identical to the same dialog declared elsewhere

#### Scenario: A colour that no token controls

- **WHEN** an element inside the chrome takes its colour from outside the token system
- **THEN** the region's ground is chosen so that element still meets its own contrast
  requirement, and the constraint is recorded where the ground is defined

### Requirement: Code is a terminal, and inline code is not

A fenced code block SHALL be rendered as a dark inset surface, the same one in both themes,
and SHALL be legible whether or not a language was declared on the fence.

Inline code SHALL NOT share that surface. A span inside a sentence is typography, and setting
it on a dark slab turns running prose into a row of chips.

The block's text colour SHALL be declared on the block itself rather than delegated to the
syntax highlighter, because highlighting is applied only to fences that name a language and a
fence without one would otherwise inherit the document's ink onto the inset.

#### Scenario: A fence with no language

- **WHEN** a code block is rendered without a declared language
- **THEN** its text meets the contrast requirement against the block's own ground

#### Scenario: Code inside a sentence

- **WHEN** inline code appears in running prose
- **THEN** it is set on the document's own surface, not on the block's

#### Scenario: The block does not follow the theme

- **WHEN** the theme is switched
- **THEN** the code block keeps one ground and one syntax palette, and its edge remains visible
  against both canvases
