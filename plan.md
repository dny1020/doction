MACHINE LEARNING (clean, Unix-style)
1. embed (the foundation, unavoidable)

Everything starts here.

pages → chunks → embeddings
stored per workspace

Used for:

semantic search
similarity
clustering

Think:

grep, but for meaning

Keep it dumb, fast, local-friendly if possible.

2. rag (but ONLY as a pipe, not a system)

Instead of “chat with docs”, do:

cat context.md | rag | summarize

Design rule:

RAG is not a UI feature
RAG is a CLI-style transformation layer

Use cases:

generate answer from workspace subset
explain a folder/page cluster
extract decisions

Keep scope explicit:

user selects inputs, system never guesses scope

3. summarize (killer feature, cheap, high leverage)

Every markdown page can be:

summary
key points
decisions
TODOs

But IMPORTANT:

async job
not real-time
cached result

Unix philosophy:

like wc -l, not like ChatGPT

4. semantic grep (this is your differentiator)

Instead of:

grep "SIP latency"

You add:

sgrep "where did I discuss SIP performance issues?"

Internally:

embedding similarity + keyword boost

This becomes your killer UX feature.

5. extract (structured intelligence)

Turn markdown into structure:

entities (APIs, systems, names)
tasks
decisions
dates

Output:

{
  "decisions": [],
  "tasks": [],
  "systems": []
}

No magic UI. Just pipes.

6. link graph (no ML heavy, just embeddings + heuristics)

Each page gets:

related pages
backlinks
semantic neighbors

This replaces:

folders obsession
manual linking chaos

Think:

“git commit graph, but for knowledge”

7. MCP layer = “AI shell commands”

Expose ML as tools:

/ml/embed
/ml/search
/ml/rag
/ml/summarize
/ml/extract

So MCP becomes:

your system’s shell interface for intelligence

⚙️ GENERAL PRODUCT SUGGESTIONS (important)
1. Markdown is your API

Don’t fight it.

Add:

frontmatter metadata
inline tags
block-level annotations

Example:

---
type: decision
workspace: telco-core
---

We migrate SIP proxy to Kamailio.

That alone beats 80% of “AI docs apps”.

2. Everything must be composable

No monolith features.

Bad:

“AI assistant button”

Good:

select text → run tool → output pipe
3. Treat pages like files, not documents

Each page should support:

stdin (input context)
stdout (result)
transformations

You are building:

a knowledge shell, not a UI app

4. Workspace = isolated universe

Each workspace gets:

own embeddings index
own RAG context
own memory graph

No global mixing unless explicit.

This is critical for trust.

5. Async-first intelligence

Never block UI with ML.

Pipeline:

write markdown
queue job
enrich later

Like:

systemd timers for intelligence

6. “Explainability over magic”

Every ML output should be traceable:

which pages were used
similarity score
chunks retrieved

No black box RAG.

💀 WHAT YOU SHOULD AVOID (VERY IMPORTANT)
chatbot inside docs (kills Unix philosophy)
continuous AI suggestions (noise)
global memory hallucination
heavy agent systems
real-time streaming inference per keystroke

Those turn your system into bloatware fast.
