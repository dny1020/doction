## Purpose

Defines what someone else's deployment of doction must be able to change without editing source,
and what a running doction is guaranteed never to fetch from the internet. doction is meant to run
on hardware its user administers, sometimes with no route out of the network at all, and both
properties have to be enforceable rather than merely intended.

## ADDED Requirements

### Requirement: The running application makes no external network request

Every asset the application needs SHALL be served by the deployment itself. Fonts, icons,
favicons, stylesheets, scripts, the syntax highlighter, the diagram renderer, the math renderer
and any source map MUST come from the deployment's own origin.

This SHALL be verified mechanically against the built bundle and the served HTML and CSS, not
asserted in documentation, so a dependency that reaches for a CDN fails the build rather than the
deployment.

#### Scenario: A deployment with no route to the internet

- **WHEN** doction is loaded on a network with no external route
- **THEN** every view renders completely, with its intended fonts, icons and diagrams

#### Scenario: The guarantee is enforced by the build

- **WHEN** the frontend is built
- **THEN** the check fails if the bundle, the HTML or the stylesheets reference any host other
  than the deployment's own origin

#### Scenario: A dependency that fetches at runtime

- **WHEN** a library would fetch a resource at runtime rather than at build time
- **THEN** that resource is vendored into the deployment and the library is pointed at the local
  copy

#### Scenario: Lazily loaded features

- **WHEN** a feature loads its code only when a page needs it — the highlighter, the diagram
  renderer, the math renderer
- **THEN** it loads from the deployment's own origin

#### Scenario: Icons and favicons

- **WHEN** the interface renders its icons, the browser tab icon, or the installable-application
  icons
- **THEN** all of them come from the deployment

### Requirement: Deployment-specific paths are configuration, not source

The path the application is served from and the locations of the API, the MCP endpoint and the
static assets SHALL be settable at build or deploy time without editing source files. The
defaults MUST be the current ones, so an existing deployment needs no change.

Requests to the deployment's own surfaces SHALL be made relative to the configured base rather
than to a hardcoded absolute path, because the session cookie requires same-origin requests and a
hardcoded prefix breaks the moment a deployment is served from anywhere else.

#### Scenario: Serving from another path

- **WHEN** a deployment serves the application from a path other than the default
- **THEN** routing, asset URLs and API requests all resolve, with no source change

#### Scenario: Defaults are unchanged

- **WHEN** no configuration is supplied
- **THEN** the application behaves exactly as it does today

#### Scenario: The MCP endpoint's location

- **WHEN** a deployment exposes the MCP endpoint at a path other than the default
- **THEN** the interface's status reporting checks the configured path

#### Scenario: Nothing secret is configured into the frontend

- **WHEN** the frontend's configuration is assembled
- **THEN** it contains only paths and feature flags, and no credential, token or signing secret,
  since anything given to the frontend is published to whoever loads it

#### Scenario: Missing configuration does not fail silently

- **WHEN** a configuration value is required and absent
- **THEN** the build fails and names it, rather than producing a bundle that requests an
  undefined path

### Requirement: The document title names the document

The browser's title SHALL identify the current document, its workspace and the application, in
that order of specificity, and MUST change as the person navigates. The title MUST be plain text
whatever the page title contains.

#### Scenario: Reading a page

- **WHEN** a person opens a page
- **THEN** the browser tab shows that page's title, its workspace, and the application name

#### Scenario: Navigating

- **WHEN** a person moves from one page to another
- **THEN** the title updates without a reload, and the history entry for each page carries its
  own title

#### Scenario: Views without a document

- **WHEN** a person is in settings, trash, notes, the editor, or the not-found state
- **THEN** the title names that view rather than repeating the last page's title

#### Scenario: A page title containing markup

- **WHEN** a page's title contains characters significant in HTML
- **THEN** the browser tab shows those characters literally

#### Scenario: A renamed page

- **WHEN** a page's title is changed and saved
- **THEN** the browser title reflects the new title without a reload
