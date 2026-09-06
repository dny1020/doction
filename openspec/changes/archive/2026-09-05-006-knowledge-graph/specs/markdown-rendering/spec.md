## ADDED Requirements

### Requirement: Page-derived syntax becomes tokens, never markup

A syntax extension that turns something written in a document into an element — a wikilink today,
anything similar later — SHALL be implemented as a rule in the markdown parser that emits tokens.
It MUST NOT build an HTML string from document-derived values, and MUST NOT post-process rendered
output with string replacement.

The distinction is not stylistic. A value taken from a document and spliced into HTML is the exact
shape of the stored cross-site scripting closed in change 001. A parser token carries the value as
data, the sanitizer sees an ordinary element, and no path exists by which a document can introduce
an attribute or a tag.

#### Scenario: An extension emits tokens

- **WHEN** a document-level syntax extension renders
- **THEN** it produces parser tokens and the sanitizer receives an ordinary element

#### Scenario: A hostile target

- **WHEN** the extension's target contains a quote, an angle bracket or a script-bearing scheme
- **THEN** the output is inert and the characters render as text

#### Scenario: Rendered output is never rewritten

- **WHEN** the rendering pipeline is read
- **THEN** no step performs string replacement on already-rendered HTML
