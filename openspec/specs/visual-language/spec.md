# visual-language Specification

## Purpose
TBD - created by archiving change 005-visual-language. Update Purpose after archive.

## Requirements

### Requirement: Data and prose are never set alike

The interface SHALL render machine-shaped values in a different type family from the sentences
around them. A slug, a tag, a heading path, a timestamp, a count, a version, a delivery status, a
retrieval constant and a code fragment are data. A description, a label, a heading, a button and a
message are prose.

Monospace SHALL be reserved for data and MUST NOT be used for a sentence. This is the rule that
makes doction read as a reference work rather than as an application with content inside it, and it
serves both audiences at once: a person scanning for a value finds it without reading, and a person
reading a sentence is never asked to parse a path.

#### Scenario: A value among words

- **WHEN** a page's tags, its last-updated date, or the number of indexed pages is displayed
- **THEN** each is set in the data face, distinguishable from the surrounding text at a glance

#### Scenario: A sentence is never monospaced

- **WHEN** any descriptive text is displayed — a section description, an empty state, a toast, a
  confirmation
- **THEN** it is set in the text face, whatever the surface it sits on

#### Scenario: Provenance in a search result

- **WHEN** a result or a retrieved fragment shows its page and heading path
- **THEN** the path reads as data and the title reads as prose

#### Scenario: Nothing renders below the legibility floor

- **WHEN** any text is rendered
- **THEN** its size is at or above the interface's smallest defined step, in both faces

### Requirement: One accent, and it recedes

The interface SHALL use a single accent hue for every emphatic role — links, the active item,
primary actions, focus rings, selection. A second hue is permitted only for destructive intent,
which is not emphasis but warning.

The accent MUST be a colour that recedes on the page rather than competing with the text. On
documentation the reader's attention belongs to the words; an accent that pulls the eye first is
working against the product.

#### Scenario: One hue across the interface

- **WHEN** the interface is surveyed
- **THEN** links, the active page in the tree, primary buttons, focus rings and selected states all
  use the same hue

#### Scenario: Destructive is not accent

- **WHEN** a destructive control is displayed
- **THEN** it uses the warning hue and is distinguishable from a primary action

#### Scenario: The accent is readable on its surface

- **WHEN** the accent is used for text on any surface it appears on
- **THEN** the contrast ratio is at least 4.5:1

### Requirement: A control's boundary can be seen

The interface SHALL distinguish a decorative line from a line that bounds a control. A decorative
line may sit below the threshold of easy visibility; a control's boundary MUST NOT.

Anything a person can click, type into or select from SHALL be bounded by a line meeting at least
3:1 against the surface behind it, or by another affordance carrying that contrast. A control whose
only boundary is a decorative hairline is a control some people cannot find.

#### Scenario: An input on the page

- **WHEN** a text field, a select or a bordered button is displayed
- **THEN** its boundary meets at least 3:1 against the surface it sits on

#### Scenario: A divider between sections

- **WHEN** a line separates two regions and bounds nothing interactive
- **THEN** it may be lighter, because losing it costs nothing but tidiness

#### Scenario: Focus is always visible

- **WHEN** any control receives keyboard focus
- **THEN** the focus indicator is visible against both the control and the surface behind it, in
  both themes

### Requirement: Both themes carry the same language

Every token SHALL be defined for the light and the dark theme, and both MUST satisfy the same
contrast requirements. The dark theme is not the light one inverted: it is designed, and the source
this language comes from is light-only, so its dark counterpart is original work.

Neither theme may drop a distinction the other makes — if the light theme separates a decorative
line from a control boundary, so does the dark one.

#### Scenario: Switching themes

- **WHEN** a person switches between themes
- **THEN** every surface, line, ink level and accent has a defined value and nothing falls back to a
  browser default

#### Scenario: Contrast holds in the dark

- **WHEN** contrast is measured in the dark theme
- **THEN** text, accent and control boundaries meet the same ratios required of the light theme

#### Scenario: No flash on load

- **WHEN** a page is opened with the dark theme stored
- **THEN** it paints dark on the first frame

### Requirement: The palette stays small and its roles are named

The interface SHALL define a bounded set of tokens — surfaces, ink levels, lines, one accent, one
warning — and every rule SHALL reference a token rather than a literal colour. The token's name
SHALL say what it is for, not what it looks like.

A token that no rule uses is removed rather than kept for a future that may not arrive, and a token
whose name does not match its value is a defect: it misleads the next reader more than its absence
would.

#### Scenario: No literal colours in rules

- **WHEN** the stylesheet is read
- **THEN** colour values appear in the token definitions and in nothing else

#### Scenario: A token means what it says

- **WHEN** a token names a type family, a role or a state
- **THEN** its value is that thing

#### Scenario: Unused tokens are absent

- **WHEN** the token block is read
- **THEN** every token in it is referenced by at least one rule

### Requirement: The visual language costs nothing at runtime

Every font the interface renders SHALL be served by the deployment itself, and the set SHALL be
justified against its weight. doction runs on a Raspberry Pi and in networks with no route out, so
a family that cannot be vendored cannot be used, and a family that is vendored is paid for on every
cold load.

A type family SHALL be added only if a role in the language requires it and no already-present
family can fill that role.

#### Scenario: No external request

- **WHEN** the interface renders in a network with no external route
- **THEN** every glyph appears as intended, from the deployment's own origin

#### Scenario: A family earns its place

- **WHEN** a type family is part of the language
- **THEN** it fills a role the language names, and it is subset to the ranges the interface renders

#### Scenario: A missing face degrades legibly

- **WHEN** a vendored face fails to load
- **THEN** the fallback stack renders readable text of the same class, never a default serif where
  the design expects a text face

### Requirement: One shape per job

The interface SHALL express each recurring job — a list, a row within it, a text field, a section
label, a unit of metadata, an empty state — through one shared definition. A screen that needs
something different SHALL say so with a modifier on the shared piece rather than a family of its
own.

Nine ways to draw a list is not variety, it is nine chances to disagree. What makes an application
feel finished is that someone who has learned one screen has already learned the others; that
recognition is destroyed by small differences far more easily than by large ones.

A definition with a single caller is not shared and SHALL live with the screen that uses it.

#### Scenario: The same idea in two places

- **WHEN** two screens display a list of things
- **THEN** the rows are the same height, padding and type, and are separated the same way

#### Scenario: A screen that needs an exception

- **WHEN** a screen genuinely needs a different treatment
- **THEN** it applies a modifier to the shared piece, and the exception is visible as such

#### Scenario: Nothing is shared by only one screen

- **WHEN** the stylesheet is read
- **THEN** every shared definition has more than one caller

### Requirement: Elevation means the same thing everywhere

The interface SHALL pair radius and shadow by what a surface *is* — a panel on the page, something
raised over it, or something modal — and that pairing SHALL be the same on every screen. Elevation
is how a reader knows what is on top of what; if a menu is drawn one way here and another there,
the cue stops carrying information and becomes decoration.

#### Scenario: Two menus

- **WHEN** two menus are opened on different screens
- **THEN** they have the same radius and the same shadow

#### Scenario: Flat is not raised

- **WHEN** a surface sits on the page rather than over it
- **THEN** it is bounded by a line and carries no shadow

### Requirement: Nothing is set outside the scale

Spacing, type size and radius SHALL come from the defined scales. A literal value is a decision
made once, in one place, that nothing else can follow.

In particular no text SHALL be set below the smallest size in the type scale. A size chosen to fit
something into a space is a layout problem being paid for by the reader.

#### Scenario: A rule sets a size

- **WHEN** any rule sets spacing, a font size or a radius
- **THEN** the value is a token

#### Scenario: Small text

- **WHEN** the smallest text in the interface is measured
- **THEN** it is the smallest size in the scale, and no smaller

### Requirement: Focus is shown by what a thing is

Focus SHALL be indicated the same way for the same kind of element, and where two indicators
exist the split SHALL be by kind and stated, never by which elements someone remembered to cover.

A control has a box, so it is surrounded. A link inside running text has no box and can break
across two lines, where a ring would draw the rectangle enclosing both fragments — which is not
where the link is. That is a functional reason for a second treatment, and the only kind of reason
that justifies one.

#### Scenario: Moving between controls

- **WHEN** focus moves between a button, a field and a select
- **THEN** the indicator is identical each time

#### Scenario: A link that wraps

- **WHEN** a focused link in prose breaks across two lines
- **THEN** the indicator follows the text rather than the rectangle around it

#### Scenario: No element is left out

- **WHEN** any focusable element receives keyboard focus
- **THEN** it shows one of the two indicators, and which one follows from what it is
