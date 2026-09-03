## Purpose

Defines what doction's markdown renderer accepts and what it is allowed to put into the DOM. The
server stores raw markdown and renders nothing, so every rendering decision is a client-side one
and every one of them is a security boundary. This capability covers all of them, including the
paths that render page-derived content without going through the markdown renderer at all.

## ADDED Requirements

### Requirement: Embedded HTML is sanitized, never trusted and never discarded wholesale

The renderer SHALL allow HTML embedded in markdown and SHALL pass the complete rendered output
through an allowlist sanitizer before it enters the DOM. The allowlist MUST be defined by doction
rather than inherited from a library default, and it MUST reject, at minimum: `<script>`,
`<iframe>`, `<object>`, `<embed>`, `<form>`, every `on*` event-handler attribute, `style`
attributes, and `javascript:` or `data:` URLs in `href` and `src`.

Sanitization MUST run on output, after markdown is converted to HTML, not on the markdown source.
Filtering the source cannot see what the renderer will produce.

#### Scenario: A page carrying a script tag

- **WHEN** a page's markdown contains a `<script>` element and the page is read
- **THEN** no script from that page executes
- **AND** the surrounding markdown renders normally rather than the whole document being refused

#### Scenario: An event handler on an allowed element

- **WHEN** a page contains an otherwise-allowed element carrying an `onerror`, `onclick` or
  `onload` attribute
- **THEN** the element renders with that attribute removed

#### Scenario: A javascript: URL in a link

- **WHEN** a page contains a link or image whose URL scheme is `javascript:`
- **THEN** the element renders without a working URL, and activating it does nothing

#### Scenario: Benign inline HTML survives

- **WHEN** a page uses inline HTML that carries meaning rather than behaviour — a `<details>`
  block, an `<abbr>`, a `<sup>`, a `<kbd>`, a `<br>`
- **THEN** it renders as that element, not as escaped text and not as nothing

#### Scenario: The editor preview and the reading view agree

- **WHEN** the same markdown is shown in the editor's live preview and in the reading view
- **THEN** both render identical HTML, having passed through the same sanitizer

### Requirement: Enabling HTML does not cost any GFM syntax

The syntax doction renders today SHALL continue to render after embedded HTML is allowed, and the
GFM syntax it does not yet render SHALL be added. Specifically, the renderer MUST handle tables,
strikethrough, autolinks, fenced code blocks with a language, task lists, and inline and block
math.

Sanitization MUST NOT remove the markup these produce. A task list's checkbox, a code block's
language class and a math node's markup are renderer output, not page-authored HTML.

#### Scenario: Task list

- **WHEN** a page contains `- [ ]` and `- [x]` list items
- **THEN** they render as unchecked and checked items rather than as literal bracket text
- **AND** the checkboxes are not editable from the reading view, which is read-only

#### Scenario: Table

- **WHEN** a page contains a pipe table with an alignment row
- **THEN** it renders as a table with the declared column alignment

#### Scenario: Fenced code with a language

- **WHEN** a page contains a fenced block tagged with a language
- **THEN** the rendered block keeps the language class that the syntax highlighter looks for
- **AND** the highlighter still highlights it after sanitization

#### Scenario: Mermaid block

- **WHEN** a page contains a fenced block tagged `mermaid`
- **THEN** it becomes a diagram exactly as it does today, and the diagram source is inserted as
  text rather than as markup

#### Scenario: Math

- **WHEN** a page contains inline math and a display-math block
- **THEN** each renders as mathematics rather than as literal delimiters
- **AND** the markup the math renderer emits is not stripped by the sanitizer

#### Scenario: Code containing markup is not executed

- **WHEN** a fenced code block's contents are themselves HTML, including a script element
- **THEN** that HTML is displayed as code and nothing in it runs

### Requirement: Every path that renders page-derived content is sanitized

Any interface element whose content originates in a page — its body, its title, a search
snippet, a note excerpt, a diff — SHALL be inserted as text, or as HTML that has passed the
sanitizer. No such element may be inserted as unsanitized markup.

This requirement exists because the renderer's own safety is not the whole surface: a search
snippet built by the database and injected as HTML bypasses the renderer entirely.

#### Scenario: Search snippet containing markup

- **WHEN** a page's body contains an HTML element with an event handler, and a search matches
  text in that page
- **THEN** the snippet in the results shows that markup as text
- **AND** nothing from the snippet executes

#### Scenario: Match highlighting still works

- **WHEN** a search result is displayed
- **THEN** the matched terms are still visually distinguished within the snippet
- **AND** that distinction is produced from match positions or from escaped markup, not by
  injecting the database's output as HTML

#### Scenario: Snippets from every search mode

- **WHEN** results come from keyword, semantic or hybrid search
- **THEN** all three snippets are encoded the same way, so no mode is safe while another is not

#### Scenario: Page titles

- **WHEN** a page title contains characters that are significant in HTML
- **THEN** it renders as those characters wherever the title appears — the tree, breadcrumbs,
  the command palette, the browser tab, a toast — and not as markup
