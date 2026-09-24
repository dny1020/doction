# Searching

```bash
curl -s -H "authorization: Bearer $TOKEN" --get $DOCTION/api/search --data-urlencode "q=kamailio"
```

Search is scoped to one workspace and has three modes, selected with `mode=`:

| Mode | What it uses | Available |
| --- | --- | --- |
| `keyword` | PostgreSQL full-text search | always, and the default |
| `semantic` | local embeddings | needs `SEMANTIC_SEARCH=1` |
| `hybrid` | both, fused by rank | needs `SEMANTIC_SEARCH=1` |

The interface's sidebar uses `hybrid`, because semantic alone lets an exact term lose to a page
that is merely related. MCP's `sgrep` returns the ranked list unfiltered, because an agent wants
to do its own cutting.

On an instance with semantic search off, a `semantic` or `hybrid` query is answered with keyword
results rather than an error. Measured on an instance with the flag off, all three modes returned
the same five pages. This is deliberate degradation, but it means a query that seems to work is
not proof that embeddings are on. `GET /api/system` reports `semantic_search` if you need to
know.

## There is no query syntax

Every non-word character is discarded, and what remains is joined as **required prefix terms**.
That single sentence explains every result below, all measured against a running instance holding
one page about Kamailio and one about Asterisk:

| Query | Result | Why |
| --- | --- | --- |
| `kamailio` | the Kamailio page | ordinary term |
| `kam` | the Kamailio page | every term is a prefix match |
| `kamailio OR asterisk` | **nothing** | `or` is an English stopword and is dropped; the two terms are then both required, and no page has both |
| `-asterisk kamailio` | **nothing** | the `-` is discarded, so the term you tried to exclude becomes required |
| `"asterisk queues"` | pages with those words far apart and in either order | the quotes are discarded; there is no phrase search |
| `the` | **nothing** | a query of only stopwords compiles to an empty query |
| `tag:voip` | **nothing** | not a field filter; `tag` becomes a required literal term |

Three of those return zero results while looking like they should return something, and one
returns the opposite of what was asked. None of them is an error, so nothing tells you. If a
query surprises you, reduce it to bare words and try again.

Accents fold in both directions. `renovacion` finds a page containing "Renovación" and the
reverse also holds. That is what the project's own text-search configuration exists for:
`unaccent` runs ahead of the stemmer, so the accented and unaccented spellings index to the same
token.

The stemmer is English on every instance, including instances whose content is Spanish. That is a
measured choice, not an oversight: a Spanish stemmer scored 0.00 on English queries against
Spanish pages in this project's retrieval harness. The numbers are in `evals/results/`.

## What comes back

Each hit carries the page's slug and title and a snippet of up to twelve words with the matched
spans marked. The snippet is prose: frontmatter, fenced code and mermaid blocks, images, heading
marks, list bullets, table pipes and emphasis are taken off first, and links and wikilinks keep
only their text. That happens before the words are chosen, so a snippet is never picked out of a
code block. Ranking is untouched — it runs on the stored markdown, syntax included.

Add `uploads=1` to also match text recognised in uploaded images. That needs `OCR_UPLOADS=1` on
the instance, since the text is extracted when the image is uploaded and not at query time.

## How hybrid combines the two

Hybrid does not concatenate the two result lists. It fuses them by reciprocal rank: each list
contributes `weight / (60 + position)` to a page's score, with the vector list weighted more
heavily than the lexical one. Both constants came from a sweep over this project's own corpus and
query set, recorded in `evals/results/`.

The practical consequence is that a page ranked highly by both methods beats a page ranked first
by one and missing from the other, which is the behaviour you want when one of the two is having
an off day.

## The reranker is off, and should stay off

`RERANK=1` re-scores the top hits with a cross-encoder. On this project's corpus it was measured
as a net loss: it gained 0.01 on mean reciprocal rank, *lost* recall at rank 1, and cost 29 times
the median latency. It ships disabled and [configuration](configuration.md) says the same. Turn
it on only if you have measured your own corpus and found otherwise.

## Where to go next

- [Tags and metadata](tags-and-metadata.md), and why `tag:` is not a filter
- [Configuration](configuration.md) for the search flags and what they cost
- [Agents and MCP](mcp.md) for `sgrep` and the retrieval tools
