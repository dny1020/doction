WELCOME = """\
# Welcome to doction

A quiet, markdown-first place to think, document, and operate.

- **Capture** notes fast — title, write markdown, save.
- **Search** everything from the sidebar (full-text, instant).
- **Read** in a calm, focused pane.

Use the **+ New** button to create your first page, or edit this one to make it yours.
"""

RUNBOOK = """\
---
type: runbook
tags: [deploy, docker]
---

# Runbook: Deploy doction

An example of the kind of operational note this wiki is built for. The block above is
frontmatter: it marks this page's `type` and tags, so a search for `#deploy` finds it and
an agent asking for runbooks gets it back.

## Before you start

Deploys are manual and there is no rollback. Check what is running first:

```bash
curl -s http://127.0.0.1:8000/health | jq
```

`status` is the process and `db` is the database connection. A `200` with `"db":"error"`
means the app is up and Postgres is not — look there before anything else.

## Steps

1. Push to `main`. GitHub Actions builds the image and publishes it to the registry.
2. On the host, pull it and restart:

```bash
cd /opt/doction
docker compose pull
docker compose down
docker compose up -d
```

3. Confirm the version actually changed, rather than assuming the pull did something:

```bash
curl -s http://127.0.0.1:8000/health | jq .version
```

## What to back up

Two halves, and one without the other does not restore.

| What | Where | Why |
| --- | --- | --- |
| Pages and uploads | `DATA_DIR` (`/data`) | The content and its full history |
| Database | the Postgres volume | Search index, tags, link graph, users |
| Logs | `LOG_DIR` (`/logs`) | Diagnostic only. Do not back up. |

Dump the database *before* archiving the files. A page written between the two steps then
exists on disk without an index row, which reindexing fixes. The reverse order leaves an
index row for a file you do not have, which does not recover.

> Links between pages are written `[[like this]]`. See [[Markdown Cheatsheet]] for the rest
> of the syntax, including the table above.
"""

MARKDOWN_NOTES = """\
# Markdown Cheatsheet

| Element | Syntax |
| --- | --- |
| Heading | `# H1` … `###### H6` |
| Bold | `**text**` |
| Italic | `*text*` |
| Code | `` `inline` `` or fenced ``` blocks |
| Link | `[label](https://example.com)` |
| List | `- item` |

~~Strikethrough~~ and tables are supported out of the box.
"""

SEED_PAGES = [
    ("Welcome to doction", WELCOME),
    ("Runbook: Deploy doction", RUNBOOK),
    ("Markdown Cheatsheet", MARKDOWN_NOTES),
]
