## ADDED Requirements

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

### Requirement: Focus speaks one language

Every focusable element SHALL show focus the same way. Two accessible treatments applied by which
element happens to be focused is still an inconsistency, and it is the one a keyboard user meets
on every screen.

#### Scenario: Moving through a screen by keyboard

- **WHEN** focus moves between a link, a button and a field
- **THEN** the indicator has the same shape, colour and offset each time
