## Purpose

Defines what a view shows when it has no content to show, and requires that the three reasons for
that be distinguishable: the content has not arrived yet, there is genuinely none, or fetching it
failed. Today all three render the same word.

## ADDED Requirements

### Requirement: Loading, empty and failed are three different states

Every view that fetches data SHALL present a distinct state for each of: a request in flight, a
successful response with no content, and a failed request. No two of the three may render the
same thing.

A failed request MUST NOT be presented as an empty result. Reporting an unreachable server as an
empty workspace is a false statement about the user's data.

#### Scenario: The three states are distinguishable

- **WHEN** a view is loading, then resolves with nothing, and separately fails
- **THEN** each of those three outcomes renders differently from the other two

#### Scenario: A failure offers a retry

- **WHEN** any view's fetch fails for a reason other than the content not existing
- **THEN** the view says the request failed and offers a way to retry it without a full reload

#### Scenario: A failure is contained

- **WHEN** one region's fetch fails while another's succeeds
- **THEN** the successful region still renders, and the shell around both stays operable

### Requirement: Loading is shown as the shape of what is arriving

While a request is in flight, the sidebar page tree and the document body SHALL each render a
skeleton whose layout approximates the content it is replacing. Neither may render a bare word.

A skeleton MUST be suppressed for responses fast enough that showing one would be a flash, and it
MUST NOT change the layout when the real content replaces it.

#### Scenario: Sidebar tree loading

- **WHEN** the page tree is being fetched
- **THEN** the sidebar shows placeholder rows at the tree's row height and indentation
- **AND** the sidebar's header and footer regions are already interactive

#### Scenario: Document loading

- **WHEN** a page's content is being fetched
- **THEN** the content area shows placeholder blocks approximating a heading and body text at
  the reading column's width

#### Scenario: No layout shift on arrival

- **WHEN** real content replaces a skeleton
- **THEN** the surrounding layout does not jump

#### Scenario: Fast responses do not flash

- **WHEN** a response arrives faster than the skeleton's appearance delay
- **THEN** no skeleton is shown at all

#### Scenario: A skeleton is not a failure state

- **WHEN** a request has been in flight long enough to be considered failed
- **THEN** the skeleton is replaced by the failure state, so a skeleton never persists
  indefinitely

### Requirement: Empty states say what is empty and offer the action that fills it

When a view resolves successfully with nothing to show, it SHALL say what is empty and, where an
action would create the missing content, offer exactly that action. An empty state MUST NOT be a
blank region, and MUST NOT be shown for content that is optional rather than absent.

#### Scenario: A workspace with no pages

- **WHEN** the active workspace contains no pages
- **THEN** both the sidebar and the content area say so, and the content area offers creating the
  first page

#### Scenario: A page with no subpages

- **WHEN** a page has no children
- **THEN** the subpages region is absent rather than rendered as an empty heading, because
  subpages are optional

#### Scenario: A document with no body

- **WHEN** a page has a title and no content
- **THEN** the reading view says the page is empty and offers editing it, rather than rendering
  an empty column

#### Scenario: A document with too few headings for a table of contents

- **WHEN** a document has fewer headings than a table of contents needs
- **THEN** no table-of-contents column is rendered and the reading column takes its width

#### Scenario: A search with no matches

- **WHEN** a search returns nothing
- **THEN** the result region says so and names the query that found nothing

### Requirement: A missing page or workspace produces a 404 within the shell

A request for a page or workspace that does not exist, or that the person may not read, SHALL
render a not-found state inside the application shell, with a way back. It MUST NOT redirect
silently, blank the screen, or leave the shell in a partly-rendered state.

Existence and permission MUST be indistinguishable from the client: a page in a workspace the
person is not a member of reports as not found, not as forbidden.

#### Scenario: A page that does not exist

- **WHEN** a person opens a URL naming a page slug that does not exist
- **THEN** the not-found state is shown inside the shell, with the sidebar still usable and a
  link back

#### Scenario: A workspace that does not exist

- **WHEN** a person opens a URL whose workspace segment names no workspace they can read — for
  example a page URL under a missing workspace
- **THEN** the not-found state is shown, and it does not reveal whether the workspace exists

#### Scenario: A page in a workspace the person cannot read

- **WHEN** a person opens a page URL for a workspace they are not a member of
- **THEN** the response is indistinguishable from the page not existing

#### Scenario: An unknown route

- **WHEN** a person opens any URL under the application that matches no route
- **THEN** the same not-found state is shown

### Requirement: A server error is reported as a server error

A failed response that is not a not-found SHALL render an error state distinct from the
not-found state, name the failure in the interface language, and offer a retry. A render-time
exception SHALL be caught and reported the same way rather than leaving a blank page.

#### Scenario: The server returns an error

- **WHEN** a page's fetch returns a server error rather than a not-found
- **THEN** the error state is shown, distinct from the not-found state, with a retry

#### Scenario: The server is unreachable

- **WHEN** a fetch fails because the server cannot be reached at all
- **THEN** the same error state is shown, and it says the server is unreachable rather than
  reporting a status code the client never received

#### Scenario: A render exception

- **WHEN** a component throws while rendering
- **THEN** an error state is shown in place of the crash, and the rest of the interface stays
  reachable
