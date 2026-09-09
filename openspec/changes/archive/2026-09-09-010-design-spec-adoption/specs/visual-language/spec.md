## MODIFIED Requirements

### Requirement: Code is a terminal, and inline code is not

A fenced code block SHALL be rendered as a dark inset surface, and SHALL be legible whether or
not a language was declared on the fence.

Inline code SHALL NOT share that surface. A span inside a sentence is typography, and setting
it on a dark slab turns running prose into a row of chips.

The block's text colour SHALL be declared on the block itself rather than delegated to the
syntax highlighter, because highlighting is applied only to fences that name a language and a
fence without one would otherwise inherit the document's ink onto the inset.

The block SHALL keep its edge against whichever canvas it sits on. Where the block and the
canvas are close in luminance, the border carries the separation, and the border is therefore
measured against the canvas rather than against the block.

#### Scenario: A fence with no language

- **WHEN** a code block is rendered without a declared language
- **THEN** its text meets the contrast requirement against the block's own ground

#### Scenario: Code inside a sentence

- **WHEN** inline code appears in running prose
- **THEN** it is set on the document's own surface, not on the block's

#### Scenario: The block does not follow the theme

- **WHEN** the theme is switched
- **THEN** the code block's edge remains visible against both canvases, and its syntax palette
  meets the same ratios on whichever ground the block uses

## ADDED Requirements

### Requirement: A token rename is proved by what renders, not by what it is called

Where the token vocabulary changes, the interface SHALL render identically before and after,
and that SHALL be demonstrated by comparing resolved values rather than by reading names.

A vocabulary change is rarely a rename. When a name exists in both vocabularies with different
meanings, when a scale shifts by a step, or when two names trade places, a substitution pass
produces a stylesheet that parses, leaves no undefined token, and is wrong. Name-based checks
cannot see any of it, because both sides are valid identifiers.

Every scope that redefines the vocabulary SHALL be renamed in step with the root. A name
changed in one scope and not another does not fail loudly: the caller silently resolves the
value it inherits from elsewhere, which is the wrong value in exactly the places that were
missed.

Consumers outside the stylesheet SHALL be renamed in the same change. A token read by name at
runtime returns empty when the name moves, and the code that reads it falls back to a default
that no one chose.

#### Scenario: A permutation rather than a rename

- **WHEN** a name in the new vocabulary already exists in the old one with a different meaning
- **THEN** the substitution passes through an intermediate name, so no call site is rewritten
  twice

#### Scenario: Proving the rename changed nothing

- **WHEN** the rename is complete
- **THEN** the resolved value of every affected property is identical to the recorded baseline

#### Scenario: A token read from script

- **WHEN** code outside the stylesheet reads a token by name
- **THEN** that reader is updated in the same change, and the surface it paints is checked

### Requirement: A stated value that fails a threshold is corrected and recorded

Where the design document states a value that does not meet the contrast its role requires, the
interface SHALL use the nearest value on the same hue that does, and the replacement and its
measurement SHALL be recorded where the project keeps its design record — the design document
when that document is versioned with the code, and the change that made the correction when it
is not. What matters is that the record ships with the repository; a correction written only
into a file that never gets committed is a correction nobody will find.

This applies to values the document supplies, not only to roles it omits. A specification is a
statement of intent; a measured threshold is a statement of fact about who can use the result.
When they disagree the measurement wins, and the disagreement is written down so the next
reader does not restore the failing value believing it was never considered.

A colour SHALL also be checked against the gamut it will render in. A value outside that gamut
is mapped by the browser to something the author did not choose, so a ratio computed from the
authored value describes a colour nobody sees.

#### Scenario: A specified colour fails its role

- **WHEN** a value named in the design document does not meet the ratio its role requires
- **THEN** the interface uses the nearest passing value on that hue, and the versioned design
  record carries both the replacement and the measurement that forced it

#### Scenario: A colour outside the gamut

- **WHEN** a specified colour falls outside the rendering gamut
- **THEN** it is brought inside the gamut deliberately, rather than left for the browser to map

#### Scenario: A capability the deployment cannot rely on

- **WHEN** a colour function the document uses is not supported across the deployment's browser
  floor, and its failure mode is silent
- **THEN** the value is precomputed instead, so that it renders and can be measured
