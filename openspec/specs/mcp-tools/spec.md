# mcp-tools Specification

## Purpose
Defines the contract doction offers an agent over the Model Context Protocol: which tools exist,
what each is for, and what they are forbidden from doing. An agent picks a tool from its
description alone, so the surface has to be legible without reading doction's source.

## Requirements

### Requirement: Five tools cover the agent's working loop

The MCP surface SHALL expose, under stable names, one tool for each thing an agent does with a
knowledge base: find something, gather context about it, understand how the workspace is
organised, read a document exactly as stored, and write back what it learned.

- `search_knowledge` — ranked pages for a query, filterable by workspace, tag and page type.
- `get_rag_context` — the assembled top-k fragments with their provenance.
- `get_workspace_tree` — workspaces, pages and subpages as a hierarchy.
- `read_page_raw` — a page's markdown exactly as stored, frontmatter included.
- `upsert_page_section` — create or replace one section of a page.

Each tool's description MUST say what distinguishes it from its neighbours, so that an agent can
tell `search_knowledge` from `get_rag_context` without trying both.

#### Scenario: Choosing between search and context

- **WHEN** an agent reads the tool list
- **THEN** the descriptions make clear that one ranks pages and the other returns passages to
  read

#### Scenario: Every tool declares its schema

- **WHEN** an agent lists the tools
- **THEN** each one declares its parameters, which are required, and what it returns

#### Scenario: Existing tool names keep working

- **WHEN** an agent configured against the previous tool names calls one of them
- **THEN** it still works, so a running conversation does not break on a deploy

### Requirement: Search is filterable by workspace, tag and type

`search_knowledge` SHALL accept a query plus optional filters for workspace, tag and page type,
and MUST apply them as filters on retrieval rather than on a truncated result list. Filtering
after the fact returns fewer results than exist.

#### Scenario: Filtering by tag

- **WHEN** an agent searches with a tag filter
- **THEN** every result carries that tag, and a page that would have ranked below the cut without
  the filter can now appear

#### Scenario: Filtering by type

- **WHEN** an agent searches with a page type from the frontmatter, such as `runbook`
- **THEN** only pages of that type are returned

#### Scenario: Combined filters

- **WHEN** a tag and a type are given together
- **THEN** results satisfy both

#### Scenario: A filter that matches nothing

- **WHEN** a filter excludes every page
- **THEN** the tool returns an empty list rather than falling back to unfiltered results

#### Scenario: Workspace defaults to the caller's active one

- **WHEN** no workspace is named
- **THEN** the caller's active workspace is used, as every other tool already does

### Requirement: Raw reads return the document, not a rendering

`read_page_raw` SHALL return the page's markdown byte-for-byte as stored, including its
frontmatter block, and MUST NOT render, sanitize, summarize or reflow it. An agent asking for the
raw page is going to edit it, and it needs to see what it will be editing.

#### Scenario: Frontmatter is included

- **WHEN** a page has a frontmatter block
- **THEN** it is present in the returned content, unparsed, in its original position
- **AND** the parsed fields are also available separately, so the agent need not parse it twice

#### Scenario: Content is unmodified

- **WHEN** a page contains HTML, unusual whitespace, or a malformed fence
- **THEN** the returned content is identical to what a subsequent write would have to preserve

#### Scenario: Metadata accompanies the content

- **WHEN** a page is read
- **THEN** its title, slug, parent and last-updated time come with it

### Requirement: An agent can write one section without rewriting the page

`upsert_page_section` SHALL replace or append a single section, addressed by its heading, leaving
the rest of the page untouched. Today an agent that learns one fact must send the whole body back,
overwriting anything another writer changed in between.

The write MUST be atomic with respect to the rest of the page, and MUST go through the same path
as any other page write, so history, indexing and webhooks all behave identically.

#### Scenario: Updating an existing section

- **WHEN** an agent writes a section whose heading already exists
- **THEN** that section's body is replaced
- **AND** every other section of the page is unchanged, byte for byte

#### Scenario: Adding a new section

- **WHEN** the named heading does not exist
- **THEN** the section is appended with that heading, at the requested level

#### Scenario: A page that does not exist yet

- **WHEN** the target page does not exist
- **THEN** the tool either creates it with that one section or reports that it is missing, and its
  description says which — it does not do one while implying the other

#### Scenario: Concurrent writers

- **WHEN** two agents update two different sections of one page at overlapping times
- **THEN** both edits survive

#### Scenario: The write behaves like any other

- **WHEN** a section is written
- **THEN** a version is recorded in the page's history, the page is queued for re-indexing, and
  the same event fires to webhooks as for any other page update

#### Scenario: Ambiguous heading

- **WHEN** the page contains two sections with the same heading at the same level
- **THEN** the tool refuses and says so, rather than picking one

### Requirement: Tools that read never write, and every tool states its effect

Each tool SHALL be either read-only or explicitly a write, and its description MUST say which.
`search_knowledge`, `get_rag_context`, `get_workspace_tree` and `read_page_raw` are read-only and
MUST NOT modify any page, queue, or stored state.

No MCP tool SHALL generate prose. Tools return stored content and computed rankings; the agent
writes the answer.

#### Scenario: A read leaves nothing behind

- **WHEN** any read-only tool is called
- **THEN** no page, index entry or delivery queue changes as a result

#### Scenario: Writes are identified as writes

- **WHEN** an agent lists the tools
- **THEN** the ones that modify the workspace are identifiable as such from their descriptions

#### Scenario: No tool composes text

- **WHEN** any tool returns content
- **THEN** that content is either stored page text or computed metadata, never prose doction wrote

### Requirement: The tool surface is authenticated and workspace-scoped

Every tool call SHALL require a valid token and SHALL resolve to a workspace the caller is a
member of. A workspace the caller cannot read MUST be indistinguishable from one that does not
exist.

#### Scenario: An unauthenticated call

- **WHEN** a tool is called without a valid token
- **THEN** it is refused, exactly as the existing tools are

#### Scenario: A workspace the caller is not a member of

- **WHEN** a tool names a workspace the caller cannot read
- **THEN** the response is the same as for a workspace that does not exist

#### Scenario: Listing tools stays open

- **WHEN** a client initializes the connection or lists the tools
- **THEN** it succeeds without a token, as it does today, while calling any tool does not
