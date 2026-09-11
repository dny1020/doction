# doction documentation

The [project README](../README.md) is the tour: what doction is, the feature list, a quick
start, and the REST and MCP surfaces. These pages are the reference you reach for once it
is running.

| Page | What it answers |
| --- | --- |
| [Installation](install.md) | Getting a working instance, from Compose to a bare `docker run` behind a proxy |
| [Configuration](configuration.md) | Every environment variable, what it does, and what breaks if you skip it |
| [Architecture](architecture.md) | How the pieces fit, and why the odd-looking decisions are what they are |
| [Operations](operations.md) | Upgrades, backup and restore, logs, capacity, what to do at 3am |
| [Agents and MCP](mcp.md) | Connecting an agent, the auth model, and which of the 27 tools to reach for |
| [Troubleshooting](troubleshooting.md) | Symptom-first index of the failures people actually hit |
| [Development](../CONTRIBUTING.md) | Local setup, the check gate, and how to get a change merged |

## Other documents in the repo

- [`DESIGN.md`](../DESIGN.md) — the visual system, describing what is *implemented*. When
  it disagrees with `app/static/style.css`, the document is the defect.
- [`SECURITY.md`](../SECURITY.md) — the security model, the reporting channel, and the
  hardening checklist.
- [`CHANGELOG.md`](../CHANGELOG.md) — what changed per release.
- `evals/results/` — the retrieval measurements behind the search constants. This is why
  the reranker ships off and why the stemmer is English.

## Conventions used here

- Commands assume the container. Prefix with `docker compose exec doction` if you are
  running the Compose stack.
- `$DOCTION` is the base URL of your instance, e.g. `https://wiki.example.com`.
- Anything marked **opt-in** is off unless you set its flag. doction starts with
  everything expensive disabled.
