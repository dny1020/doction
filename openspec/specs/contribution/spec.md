# contribution Specification

## Purpose
Defines what the repository owes whoever arrives wanting to change it: that its own way of
working is discoverable from a clone rather than from the maintainer's private files, that
work already identified and deliberately deferred is visible rather than buried in review
notes, and that every contribution carries a record of the terms it was offered under.

## Requirements

### Requirement: The workflow is discoverable from a clone

Whoever obtains the repository SHALL be able to learn how work is proposed, decided and
reviewed here, using only files that a clone contains.

That MUST include the fact that behaviour is specified before it is written, where the
current behaviour contracts live, and where the reason behind a past decision can be found.
A repository that carries a large decision record while explaining it nowhere is worse than
one with no record, because the reader cannot tell the record exists.

Orientation MUST NOT depend on a file excluded from version control. The maintainer's own
working notes are legitimately private; the project's way of working is not, and the two
must not be the same file.

This SHALL be verified mechanically: the orientation a contributor needs is reachable from
tracked files, and no tracked file points at an untracked one.

#### Scenario: Someone clones the repository and wants to contribute

- **WHEN** they read the orientation the repository provides
- **THEN** they learn that work is proposed before it is written, and where to find both the
  current contracts and the reasoning behind past decisions

#### Scenario: An agent works on the repository

- **WHEN** a coding agent obtains the repository with no access to the maintainer's private
  configuration
- **THEN** it finds the same orientation, because the project's conventions travel with the
  project

#### Scenario: A tracked document references guidance

- **WHEN** any tracked file points a reader at further guidance
- **THEN** the target is also tracked, so following the pointer does not dead-end

### Requirement: Orientation points rather than duplicates

A document whose purpose is orientation SHALL link to the authoritative source for each
subject rather than restating it.

Its own content is limited to what no other document states. Where the gate, the visual
system, the release procedure or the architecture are already documented, orientation names
where they are and stops.

One fact stated in two files becomes two facts that disagree. This project has already
corrected that failure three times — a licence declared in seven places with one left
behind, release notes that would have been written twice, a published description
contradicting the licence — and orientation documents are unusually prone to it, because
restating is easier than linking.

#### Scenario: A convention changes

- **WHEN** a documented convention is updated in the document that owns it
- **THEN** no orientation document needs editing, because it referred to that document
  rather than repeating it

#### Scenario: Reviewing an orientation document

- **WHEN** an orientation document is reviewed
- **THEN** any statement that duplicates an authoritative source is replaced by a reference
  to it

### Requirement: Identified work is visible

Work that has been identified and deliberately not done SHALL be recorded somewhere a
reader can find it, and MUST NOT exist only in review notes or the task file of an archived
change.

The record MUST state what is known and be ordered by what matters, and MUST NOT carry dates
or commitments. A single-maintainer project that promises a schedule publishes a document
that is wrong within weeks; one that lists what is pending stays true until the work is
done.

An absence of visible work is read as an absence of work. That is a misrepresentation when a
backlog exists: it denies a would-be contributor the one thing they need, which is somewhere
to start.

#### Scenario: Someone looks for a place to start

- **WHEN** a potential contributor looks for what needs doing
- **THEN** they find identified work rather than an empty tracker that suggests there is
  nothing to do

#### Scenario: A change defers something deliberately

- **WHEN** a change records that something was identified and left undone
- **THEN** that item reaches the visible record rather than remaining only in the change's
  notes

#### Scenario: Time passes without the work being done

- **WHEN** the record is read months later
- **THEN** nothing in it has become false, because it committed to no dates

### Requirement: A contribution records the terms it was offered under

Every contribution from outside the maintainer SHALL carry an explicit record that it is
offered under the project's licence.

A statement in a contributing guide that opening a pull request implies agreement is not
such a record: it asserts consent without evidencing it. The record MUST be attached to the
contribution itself so it survives independently of any policy document's wording at the
time.

The mechanism MUST NOT require assigning copyright to the maintainer. The consequence of
that choice SHALL be documented: the project cannot be relicensed without the permission of
everyone who has contributed.

This is required before it is needed. Obtaining the record from the first contributor costs
nothing; reconstructing it retroactively across many is not possible, and an unlicensable
contribution cannot be removed from a release that has shipped.

#### Scenario: An outside contribution arrives

- **WHEN** someone proposes a change from outside the maintainer
- **THEN** it carries an explicit statement of the terms it is offered under, and is not
  merged without one

#### Scenario: A future relicensing is considered

- **WHEN** relicensing the project is considered
- **THEN** the documentation already states that contributor permission is required, because
  no copyright was assigned

#### Scenario: The requirement is in force before any contribution exists

- **WHEN** the project has no outside contributors yet
- **THEN** the requirement is still in force, since its value is entirely in being earlier
  than the first contribution
