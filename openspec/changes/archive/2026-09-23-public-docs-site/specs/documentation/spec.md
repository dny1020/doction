## ADDED Requirements

### Requirement: The published documentation works with no outbound network access

The published documentation SHALL load completely — text, fonts, styles, icons and search —
from the site's own origin, and MUST NOT request any resource from a third-party host.

doction is run on LANs, VPNs and hosts with no route to the internet, and its documentation is
read there too, including from a local build. A documentation site that fetches a font or a
stylesheet from a CDN degrades exactly where the product is meant to work, and it tells every
reader's address to that third party.

#### Scenario: The site is built and browsed on an isolated machine

- **WHEN** the documentation is built and previewed locally with no outbound network access
- **THEN** every page renders with its intended fonts and styles, and search works

#### Scenario: A built page is inspected for external resources

- **WHEN** the HTML of any built page is inspected
- **THEN** it references no stylesheet, font, script or image on a host other than the site
  itself

### Requirement: The published documentation carries the product's visual language

The published documentation SHALL use the visual language the application implements — its
type families and their roles, its colour tokens for both themes, and its brand mark — rather
than the defaults of the documentation framework.

It MUST take those values from the application's documented visual system and MUST NOT
introduce colours, typefaces or components that the application does not use. A reader moving
between the product and its documentation meets one design, and the documentation does not
become a second design system that drifts from the first.

Both the light and the dark theme MUST be provided, following the reader's system preference
by default, and each MUST meet the contrast the application's visual system requires for text
and links.

#### Scenario: A reader opens the documentation after using the application

- **WHEN** the documentation is viewed in either theme
- **THEN** its body text, headings, code, links and header use the application's typefaces and
  colour roles for that theme

#### Scenario: A colour appears in the documentation's styles

- **WHEN** a colour is declared in the documentation's styles
- **THEN** it is a value the application's visual system defines

### Requirement: The documentation opens on a page that routes a first-time reader

The root of the published documentation SHALL be a landing page that states what doction is,
how it works, and what it does today, and that links directly to the REST API reference, the
MCP reference, the installation guide, the architecture page and a quick start.

The REST API and MCP references MUST be presented together and prominently, since they are the
two ways a program consumes doction. The landing page MUST NOT reproduce those references; it
routes to them.

Every capability the landing page claims MUST already be documented in the reference or the
README. The landing page MUST NOT state metrics, features or plans that the repository does not
already document as existing.

#### Scenario: A first-time visitor opens the site root

- **WHEN** a visitor opens the root of the published documentation
- **THEN** they can reach the REST API reference, the MCP reference, the installation guide and
  the architecture page in one click

#### Scenario: A capability is listed on the landing page

- **WHEN** the landing page names a capability
- **THEN** that capability is described in the reference or the README as present in the
  current release, not planned
