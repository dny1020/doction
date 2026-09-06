## ADDED Requirements

### Requirement: A written link is a followable link

A `[[target]]` written in a page SHALL render as a link the reader can follow, in the reading view
and in the editor preview alike. Writing a link and following one are the same gesture in a wiki;
an edge that exists only in the database is not a link.

The transformation SHALL happen in the markdown parser as a token, never by assembling HTML from a
target that came out of a document. A link whose target does not exist SHALL be visibly distinct
from one whose target does, and SHALL still be followable, because the usual reason to write a link
to a missing page is that the page is about to be written.

#### Scenario: Following a wikilink

- **WHEN** a page containing `[[some-page]]` is read
- **THEN** the text renders as a link to that page in the current workspace

#### Scenario: A link with its own text

- **WHEN** a page contains `[[some-page|the label]]`
- **THEN** the label is what is shown and the target is where it goes

#### Scenario: A link to a page that does not exist yet

- **WHEN** the target is not a page in the workspace
- **THEN** the link renders in a distinct state and leads to creating that page

#### Scenario: A wikilink is not an injection point

- **WHEN** a target contains quotes, angle brackets or a script-bearing scheme
- **THEN** the rendered anchor is inert and the characters appear as text

### Requirement: A mention carries enough context to judge it

The reading view SHALL list the pages that link to the current one, and for each SHALL show the
sentence the mention sits in. A list of titles answers who points here; it does not answer whether
the reference matters, and the reader should not have to open three pages to find out.

Mention context SHALL be delivered as text and marked segments, never as markup, so that a page's
own content can never introduce elements into another page's rendering.

#### Scenario: Mentions are listed with their context

- **WHEN** a page is read and other pages link to it
- **THEN** each is listed with the sentence containing the link

#### Scenario: Context cannot carry markup

- **WHEN** the linking page's sentence contains HTML or markdown syntax
- **THEN** it is displayed as characters, with only the mention itself marked

### Requirement: The shape of a workspace can be seen

The application SHALL offer a view of the workspace as a graph: pages as nodes, wikilinks as edges.
A tree shows containment and a search shows relevance; neither shows what clusters, what is
isolated, and what everything depends on.

The view SHALL be drawn by the application rather than by a library's own renderer, so that every
colour and face comes from a design token and both themes are served by the same rules. It SHALL
bound its own work: above a node threshold it renders the most central subgraph and says that it
has done so.

#### Scenario: Seeing the whole workspace

- **WHEN** the graph view is opened
- **THEN** every live page appears as a node and every wikilink as an edge

#### Scenario: The graph obeys the visual language

- **WHEN** the graph is rendered in either theme
- **THEN** its surfaces, lines and accent come from the same tokens as the rest of the interface,
  and node labels are set in the data face

#### Scenario: A workspace too large to draw

- **WHEN** the workspace exceeds the node threshold
- **THEN** the most central subgraph is drawn and the view states that it is a subset

#### Scenario: Reaching a page from the graph

- **WHEN** a node is activated
- **THEN** that page opens

### Requirement: A broken link is reported where it can be fixed

The structural analysis the server computes — central pages, orphans, hubs, authorities and
unresolved targets — SHALL reach a reader. An unresolved wikilink is a fact about the workspace,
and a fact reported to nobody is a workspace that decays while appearing healthy.

#### Scenario: Unresolved targets are listed

- **WHEN** the graph view is opened
- **THEN** every unresolved target is listed with the pages that point at it

#### Scenario: Orphans are visible

- **WHEN** pages have no link in either direction
- **THEN** they are identified as such
