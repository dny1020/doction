## Purpose

Defines the licence doction is offered under, every place that fact is declared and must
agree, what an operator running it for other people is obliged to do, and what licence a new
dependency may carry. doction is a web application people host for others, so the licence is
part of its behaviour and not only its paperwork.

## ADDED Requirements

### Requirement: doction is licensed AGPL-3.0-only

The project SHALL be licensed under the GNU Affero General Public License, version 3, with
no "or later" option.

`LICENSE` MUST contain the verbatim licence text as published by the Free Software
Foundation. A paraphrase, a summary, or a link in place of the text does not satisfy this.

The licence is chosen for a specific property: doction is reached over a network, so the
obligation has to attach to operating it and not only to distributing it. A licence whose
obligations trigger on distribution alone MUST NOT be adopted for this project.

#### Scenario: The licence text is the real one

- **WHEN** `LICENSE` is compared against the FSF's published AGPL-3.0 text
- **THEN** it matches verbatim, with no edits, omissions or added preamble

#### Scenario: A contributor proposes a permissive relicence

- **WHEN** a change would move the project to a licence that obliges only distributors
- **THEN** it is rejected, because network use is the case doction has to cover

### Requirement: Every declaration of the licence agrees

The licence is declared in more than one place. All of those places SHALL state the same
licence, and the set of places SHALL be recorded so it can be checked rather than recalled.

At minimum the following MUST agree: the licence text, the Python project metadata, the
frontend package metadata, the README badge, the README licence section, the terms
contributions are accepted under, and the published repository description.

A declaration that disagrees with the others is a defect of the same kind as a failing test,
because the effective terms become ambiguous. This SHALL be verified mechanically, not by
review, since the failure mode is a stale copy nobody thought to look at.

#### Scenario: One declaration is left behind

- **WHEN** the licence changes and any declared copy still names the previous licence
- **THEN** the inconsistency is reported as a failure, naming the file that disagrees

#### Scenario: Metadata outside the repository

- **WHEN** a declaration lives somewhere a commit cannot reach, such as the hosting
  platform's own repository description
- **THEN** it is still part of the set that must agree, and the procedure says who updates
  it and when

### Requirement: Relicensing is not retroactive

A change of licence SHALL apply from a stated version onward and MUST NOT be presented as
altering the terms of versions already published.

Whoever received an earlier release keeps the terms it was published under. Documentation
that records a relicence MUST name the first version carrying the new licence and MUST state
that the earlier grant is not withdrawn.

#### Scenario: Someone holds an older release

- **WHEN** a user obtained a version published under a previous licence
- **THEN** that version's terms continue to apply to their copy, and the changelog says so
  explicitly

### Requirement: An operator knows what running doction obliges

Because the licence attaches obligations to network use, the documentation SHALL state what
an operator actually owes, in the terms a self-hoster would ask the question.

It MUST distinguish three cases: running an unmodified instance, modifying an instance and
keeping it private, and modifying an instance that other people interact with over a
network. For the third case it MUST say that the corresponding source has to be offered to
those users.

A licence a self-hoster cannot act on is a licence that will be breached by accident, so
stating the obligation is part of shipping it.

#### Scenario: An unmodified private instance

- **WHEN** someone runs a published release without changes, for themselves or their team
- **THEN** the documentation tells them they owe nothing further

#### Scenario: A modified instance serving other people

- **WHEN** an operator changes doction and lets others use it over a network
- **THEN** the documentation tells them those users are entitled to the modified source, and
  how that offer is expected to be made

### Requirement: The running instance offers its source to its users

Because the licence attaches its obligation to network use, the obligation SHALL be
discharged by the software and not left to the operator's diligence alone.

A running instance MUST report, through its machine-readable status surface, the licence it
is under and the location of the corresponding source. The interface MUST surface that
information to a signed-in user without requiring them to read the repository.

The source location MUST be configurable by the operator, because an operator who modifies
doction owes *their* users *their* source, not this project's. A deployment that cannot
point at its own fork cannot comply, so a hardcoded upstream URL would defeat the
requirement it appears to satisfy.

#### Scenario: A user of a hosted instance looks for the source

- **WHEN** a signed-in user opens the interface looking for licence and source information
- **THEN** they find the licence name and a reachable link to the corresponding source,
  without leaving the application

#### Scenario: An operator runs a modified fork

- **WHEN** an operator has modified doction and configured their own source location
- **THEN** the instance reports that location rather than the upstream project's

#### Scenario: The operator configures nothing

- **WHEN** no source location is configured
- **THEN** the instance reports the upstream project's location, so an unmodified
  deployment is compliant with no setup

### Requirement: A new dependency's licence is compatible

A dependency MAY be added only if its licence permits the resulting work to be distributed
and operated under AGPL-3.0-only.

Permissive licences and weak copyleft satisfy this. A licence incompatible with GPL-3.0 also
fails here, GPL-2.0-only among them. A dependency whose terms contradict the network-source
obligation MUST NOT be added at all, regardless of how convenient it is.

Compatibility SHALL be established before the dependency lands, not discovered afterwards,
because removing a dependency from a published release is not possible.

#### Scenario: A pull request adds a dependency

- **WHEN** a change introduces a new runtime or build dependency
- **THEN** its licence is identified and confirmed compatible before the change is accepted

#### Scenario: An incompatible licence is proposed

- **WHEN** a candidate dependency is GPL-2.0-only, or otherwise cannot be combined under
  AGPL-3.0-only
- **THEN** it is rejected, and the rejection names the licence rather than the package
