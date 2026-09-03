# client-resilience Specification

## Purpose
Defines how the client behaves when the server it depends on is slow, unreachable, or asked to do
the same thing twice. doction is self-hosted, often on a Raspberry Pi behind a VPN, so an
unreachable server is an ordinary condition rather than an exceptional one. Losing someone's
writing to it is not acceptable.

## Requirements

### Requirement: Unsaved editing survives the server going away

While a page is being edited, the client SHALL keep the in-progress title and body outside React
state, on the device, so that they survive a failed save, a reload, a crash and a closed tab.
Recovery MUST NOT depend on the server being reachable.

A draft SHALL be written under a key naming the workspace and the page, so drafts for different
pages never overwrite one another.

#### Scenario: The server dies mid-edit

- **WHEN** a person has typed into the editor and the server becomes unreachable
- **THEN** the typing continues to work, and the draft is on the device

#### Scenario: A failed save

- **WHEN** a save fails
- **THEN** the failure is reported, the text stays on screen, and the draft is retained

#### Scenario: Returning after a reload

- **WHEN** a person reloads or reopens the editor for a page that has a newer local draft than
  the server's copy
- **THEN** the draft is offered, saying it is unsaved local work, and the person chooses whether
  to restore it or discard it

#### Scenario: A confirmed save clears the draft

- **WHEN** a save succeeds
- **THEN** the draft for that page is removed, so the next visit does not offer stale work

#### Scenario: Drafts do not leak between pages

- **WHEN** a person has unsaved drafts for two different pages
- **THEN** opening either offers only its own draft

#### Scenario: Local storage is unavailable

- **WHEN** the device refuses local storage, as in a private window
- **THEN** the editor still works, and the absence of drafts is not reported as an error

#### Scenario: The existing navigation guards are kept

- **WHEN** a person navigates away from, or closes, an editor holding unsaved changes
- **THEN** the existing in-application confirmation and the browser's own warning both still
  appear

### Requirement: Connection loss is reported without interrupting the work

While the server is unreachable, the client SHALL say so, keep the editor usable, and resume
normally when the server returns. It MUST NOT navigate away, clear the editor, log the person out,
or throw away a failed request's payload.

#### Scenario: Editing while disconnected

- **WHEN** the server becomes unreachable while the editor is open
- **THEN** the interface says the server is unreachable and the editor stays usable

#### Scenario: Saving while disconnected

- **WHEN** a save is attempted while the server is unreachable
- **THEN** the attempt is reported as failed with a way to retry, and the content is not lost

#### Scenario: Reconnection

- **WHEN** the server becomes reachable again
- **THEN** the notice clears and a retried save succeeds

#### Scenario: An expired session is not a connection problem

- **WHEN** a request fails because the session is no longer valid
- **THEN** that is reported as a session problem, not as a connection problem, and any unsaved
  work is preserved across signing in again

### Requirement: Repeated input is debounced rather than sent per keystroke

Any input that causes a request or a repeated computation SHALL be debounced. This covers, at
minimum: search-as-you-type, draft writing, and the editor's live preview rendering.

Debouncing MUST cancel superseded work rather than queue it, and a pending timer MUST be cleared
when its component unmounts.

#### Scenario: Search while typing

- **WHEN** a person types a query without pausing
- **THEN** one request is issued after they pause, not one per character

#### Scenario: Superseded responses are discarded

- **WHEN** a slow response for an earlier query arrives after a later query's response
- **THEN** the displayed results correspond to the latest query

#### Scenario: Draft writing

- **WHEN** a person types continuously in the editor
- **THEN** the draft is written at a bounded rate rather than on every keystroke

#### Scenario: Preview rendering

- **WHEN** a person types continuously in the editor
- **THEN** the preview re-renders at a bounded rate and typing does not stutter in a long document

#### Scenario: Unmounting during a pending debounce

- **WHEN** a person navigates away while a debounce timer is pending
- **THEN** the pending work does not run and nothing attempts to update an unmounted view

### Requirement: An action cannot be submitted twice

Any action that changes server state SHALL be blocked from running again while its own request is
in flight. The control that triggered it MUST be visibly disabled for that period, and the
interface MUST show that something is happening.

This applies to destructive actions in particular: deleting a page, deleting a workspace and the
pages under it, removing a member, revoking a token, deleting a webhook, permanently purging from
trash, and moving or renaming a page.

#### Scenario: Double-clicking delete

- **WHEN** a person confirms a deletion and activates the control twice in quick succession
- **THEN** exactly one delete request is sent

#### Scenario: Deleting a page with subpages

- **WHEN** a person deletes a page that has subpages
- **THEN** the confirmation states that the subpages are affected, and the action is guarded
  against a second submission for its whole duration

#### Scenario: The control reports it is working

- **WHEN** an action is in flight
- **THEN** its control is disabled and the interface indicates work in progress

#### Scenario: Failure re-enables the control

- **WHEN** an action fails
- **THEN** the failure is reported and the control becomes usable again so it can be retried

#### Scenario: Guarding one action does not freeze the interface

- **WHEN** one action is in flight
- **THEN** unrelated controls stay usable

#### Scenario: Confirming twice does not queue two actions

- **WHEN** a confirmation dialog is dismissed by confirming and reopened before the first request
  finishes
- **THEN** the second confirmation does not produce a second request

### Requirement: Everything the client subscribes to is released

Every listener, observer, timer, abortable request and long-lived connection the client creates
SHALL be released when the thing that created it goes away. Nothing may remain registered after
the component that registered it unmounts, and nothing may fire twice because it was registered
twice.

#### Scenario: Keyboard shortcut listeners

- **WHEN** a view that registers global keyboard shortcuts is mounted and unmounted repeatedly
- **THEN** a shortcut press triggers its action exactly once

#### Scenario: Editor teardown

- **WHEN** the editor unmounts
- **THEN** its shortcut listener, its unload guard, and its debounce timers are all released

#### Scenario: Observers

- **WHEN** a document with a table of contents is replaced by another
- **THEN** the previous document's observers are disconnected and no longer report

#### Scenario: Status polling

- **WHEN** the status indicator unmounts, or the document becomes hidden
- **THEN** its polling stops and does not resume until it is mounted and visible again

#### Scenario: Event streams

- **WHEN** the client holds a server-sent-event or socket connection and the view holding it goes
  away
- **THEN** the connection is closed rather than left open, and it is not reopened on each
  reconnection attempt without bound

#### Scenario: In-flight requests for an abandoned view

- **WHEN** a person navigates away while a request for the previous view is in flight
- **THEN** its response does not update the interface
