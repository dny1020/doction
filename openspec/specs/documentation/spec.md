# documentation Specification

## Purpose

Defines what the project owes a reader who wants to use doction rather than operate it: that
the behaviour they will meet is written down even where it is surprising, that what the
documentation asserts is held to the code by something that fails rather than by good
intentions, that the interface reference covers the whole surface the application serves and
names the version it describes, and that the published documentation is built from the tracked
files and refuses to publish a link that does not resolve.

## Requirements

### Requirement: Using doction is documented, not only operating it

The documentation SHALL explain how to use the wiki, not only how to install, configure and run
it.

That MUST cover writing and organising pages, how a page links to another and how an unresolved
link is represented, tags, the metadata block at the top of a page, the search modes and what a
query does, and the graph view.

Where the behaviour a user will meet differs from the behaviour they would reasonably guess, the
documentation MUST state the actual behaviour. A parser that accepts one spelling of a
construction and silently ignores another, and a query language that drops the operator a user
typed, are the cases that cost a reader the most and are the least discoverable from the
interface.

Documented behaviour MUST be behaviour that was measured against the running code, not inferred
from reading it.

#### Scenario: Someone starts using a fresh instance

- **WHEN** they look for how to write a page, link it to another, tag it and find it again
- **THEN** the documentation answers all four, from files the repository tracks

#### Scenario: A construction is accepted in one spelling and ignored in another

- **WHEN** the documentation describes a metadata block or a query
- **THEN** it states which spellings take effect and which are silently ignored, rather than
  describing only the spelling that works

#### Scenario: A user types an operator the search does not implement

- **WHEN** the documentation describes searching
- **THEN** it says what happens to that operator, rather than leaving the reader to infer that
  the result they got was the result they asked for

### Requirement: Documented behaviour is verified against the code

Behaviour that the documentation asserts SHALL be covered by an automated check that fails when
the code stops behaving that way.

The check MUST fail on divergence rather than on absence: documentation that has quietly become
wrong is worse than documentation that is missing, because a reader cannot tell.

When such a check fails, its failure MUST identify the documentation that has to change, so the
person who changed the behaviour is told what their change made untrue.

#### Scenario: A documented parsing or search behaviour changes

- **WHEN** code changes so that a behaviour the documentation describes no longer holds
- **THEN** the gate fails and names the documentation that describes it

#### Scenario: The documentation and the code agree

- **WHEN** the gate runs against a tree where nothing has diverged
- **THEN** it passes, and it has examined the documented behaviours rather than passing by
  finding nothing to check

### Requirement: The reference covers every operation the application serves

The interface reference SHALL cover every operation the running application exposes, and this
SHALL be verified against the application's own description of its surface rather than
maintained by hand.

An endpoint added without documentation MUST fail the gate. A reference that is a hand-kept
list drifts from the code silently, and the drift is invisible precisely to the reader who
depends on the list being complete.

The reference MUST be grouped, so that a reader looking for one area is not reading a flat list
of every operation the application serves.

#### Scenario: A route is added without documentation

- **WHEN** a new operation is added to the application and the reference is not updated
- **THEN** the gate fails and names the undocumented operation

#### Scenario: A documented operation is removed from the application

- **WHEN** an operation the reference describes no longer exists
- **THEN** the gate fails, so the reference cannot describe a surface that is not served

### Requirement: The reference names the version it describes

The machine-readable interface description the application serves SHALL declare the version of
the software serving it.

A reference that declares a version the software does not report is worse than one that declares
none, because a reader has no way to tell which of the two numbers is the software they are
talking to.

Where the application serves interactive documentation of its own interface, the documentation
SHALL state whether that surface requires outbound network access, so an operator running an
isolated instance is not left debugging a page that cannot load.

#### Scenario: A reader checks which version a reference describes

- **WHEN** the interface description is read
- **THEN** the version it declares is the version the deployment reports about itself

#### Scenario: The interactive documentation is opened on an isolated instance

- **WHEN** an operator opens the application's own interface documentation with no outbound
  network access
- **THEN** the documentation has already told them that this surface fetches assets externally,
  so the blank page is explained rather than investigated

### Requirement: The published documentation is built from the tracked files and never publishes a broken link

The published documentation SHALL be built from the documentation the repository tracks, in an
automated build, and the build MUST fail rather than publish a link that does not resolve.

This covers navigation within the published documentation, which the existing reachability gate
deliberately does not: that gate checks that a tracked document does not point at an untracked
file, and says nothing about whether a link resolves once the documentation is a site.

A link MUST NOT be converted to an external address in order to make the build pass. Doing so
removes it from the reachability gate, which trades one check for another rather than satisfying
both.

#### Scenario: A document links to something that does not resolve in the published form

- **WHEN** the site is built
- **THEN** the build fails and nothing is published

#### Scenario: A document links to a file outside the documentation directory

- **WHEN** documentation references a file the repository tracks outside that directory
- **THEN** the build resolves it by including that file, and both the reachability gate and the
  site build continue to check it

#### Scenario: The published documentation is read

- **WHEN** a reader follows the published documentation
- **THEN** what they read was built from the tracked files of the commit it was published from

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
