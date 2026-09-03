## Purpose

Defines what the interface reports about doction's machine-facing surfaces: whether the REST API
and the MCP endpoint are answering, and what happened to the webhooks the server tried to
deliver. doction's primary consumer is an agent, and an agent's failures are currently invisible
from the interface a person looks at.

## ADDED Requirements

### Requirement: The interface reports whether the API and the MCP endpoint are answering

The application SHALL present, outside the settings area, a compact indicator of the reachability
of the REST API and of the MCP endpoint. It MUST distinguish reachable, unreachable and
degraded — the API answering while the database is not — and MUST report each surface separately,
because they fail separately.

The indicator MUST be quiet when everything is healthy. A permanent green badge is noise; the
indicator earns its place by being visible when something is wrong.

#### Scenario: Everything healthy

- **WHEN** both surfaces answer and the database is reachable
- **THEN** the indicator is unobtrusive and does not occupy a region of its own in the shell

#### Scenario: The API is unreachable

- **WHEN** requests to the API fail to reach the server
- **THEN** the indicator says so, and says it in a way that is visible from any view

#### Scenario: The API answers but the database does not

- **WHEN** the deployment reports its database as unreachable
- **THEN** the indicator reports a degraded server rather than a healthy or an unreachable one

#### Scenario: The MCP endpoint is separately reported

- **WHEN** the MCP endpoint does not answer while the REST API does
- **THEN** the indicator reports the MCP surface as unavailable and the API as available

#### Scenario: Recovery is noticed without a reload

- **WHEN** a surface that was unreachable starts answering again
- **THEN** the indicator returns to its healthy presentation on its own

#### Scenario: Checking is bounded

- **WHEN** the indicator polls the surfaces it reports on
- **THEN** it does so at a fixed interval that does not tighten while a surface is failing, and
  it stops while the document is hidden

#### Scenario: Detail on demand

- **WHEN** a person opens the indicator
- **THEN** they see which surface is failing and the deployment facts the system report already
  provides, without leaving the view they were in

### Requirement: Webhook delivery outcomes are visible per endpoint

For each registered webhook, the interface SHALL report the outcome of its recent delivery
attempts: when each was attempted, which event it carried, whether it succeeded, and what the
endpoint returned. A webhook that is failing MUST be identifiable as failing from the list, before
opening it.

doction's webhooks are outbound: the server signs an event and delivers it, retrying with backoff.
What a person needs is whether those deliveries are landing.

#### Scenario: A failing endpoint

- **WHEN** a registered webhook's recent deliveries have all failed
- **THEN** the list marks that webhook as failing, without the person having to open it

#### Scenario: Delivery history

- **WHEN** a person opens a webhook
- **THEN** they see its recent attempts with, for each, the event, the time, the outcome and the
  status the endpoint returned

#### Scenario: A delivery still queued

- **WHEN** an event is queued for a webhook and not yet attempted
- **THEN** it is shown as pending rather than as failed

#### Scenario: Retries are not separate events

- **WHEN** one event has been retried several times
- **THEN** it is presented as one event with its attempts, not as several unrelated events

#### Scenario: A webhook that has never fired

- **WHEN** a webhook has been registered but no matching event has occurred
- **THEN** it is shown as never fired rather than as failing

#### Scenario: Reading history does not deliver anything

- **WHEN** a person views delivery history
- **THEN** no delivery is triggered, retried or cancelled as a result

#### Scenario: The secret stays secret

- **WHEN** delivery history is displayed
- **THEN** it contains no signing secret, and no request header carrying one
