# Cochee

Cochee is a conversational AI agent for Fantasy Premier League (FPL) that helps managers make more informed decisions about player selection, captaincy, and upcoming fixtures.

With over 11 million players competing in FPL, making decisions involves weighing factors such as player form, fixture difficulty, and price. General-purpose LLMs can explain football concepts, but their training data alone cannot reliably provide current, data-backed FPL recommendations.

Cochee addresses this by combining an LLM with tools backed by an FPL database. The model interprets questions, selects the relevant tools, and explains the results, while deterministic scoring logic handles player evaluation. This keeps recommendations grounded in application data rather than relying solely on the model's pretrained knowledge.

Built for the Alexa+ track of the Amazon Developer Hackathon 2026.
---

## How it works

The LLM doesn't query the database directly. It requests tools through an MCP client, while the application handles data retrieval and player scoring.

```text
User question
     ↓
LLM (Groq / gpt-oss-120b)
     ↓ tool request
MCP client (llm_client.py)
     ↓
MCP server (FastAPI-MCP)
     ↓
Tools: top_players, similar_players,
       compare_players, player_fixtures
     ↓
Application logic and scoring advisors
     ↓
PostgreSQL + pgvector
(668 players, 380 fixtures, 24-feature vectors)
```

The system separates three responsibilities:

1. **Computation** — Scoring advisors evaluate players based on form, fixtures, and value using deterministic logic rather than an LLM.

2. **Tool execution** — The MCP server exposes the available tools. The client passes tool requests to the server and returns their results to the LLM.

3. **Conversation** — The LLM interprets the manager's question, selects relevant tools, uses their results, and explains the answer in natural language.

This separation keeps player scoring in application code rather than relying on the LLM to perform calculations. The scoring logic is repeatable and easier to test, while the LLM handles the flexible, conversational interface.
```

---

#### The four tools

| Tool | What it's for |
|---|---|
| `top_players` | Rank players using filters such as position, team, price, ownership, and scoring weights. |
| `similar_players` | Find statistically similar players using pgvector. |
| `compare_players` | Compare 2–5 players side by side using the same metrics. |
| `player_fixtures` | Show a player's upcoming fixtures and their difficulty ratings. |

Every tool returns a `reason` field containing a pre-built, one-line explanation of its result. This gives the LLM a grounded explanation to work with instead of generating every justification from scratch. It's a simple way to reduce unsupported reasoning.

---

## ## Four challenges that changed the design

**1. MCP transport mismatch — `405 Method Not Allowed`**

The MCP client used Streamable HTTP, but the server was mounted using an SSE-based transport. Requests failed with `405 Method Not Allowed`. After tracing the issue, I found that `fastapi-mcp`'s `mount()` method was deprecated for my setup and `mount_http()` was the correct replacement. One line changed, and the pipeline started working.

This was where I learned that an MCP transport isn't just a configuration detail. The client and server need to communicate using compatible transport mechanisms.

**2. The LLM invented first names**

My tool returned `web_name`, which contained names like `Palmer`. The LLM sometimes expanded these into full names, such as "Joe Palmer" or "James Gibbs-White," even when the names were incorrect.

I changed the tool to return `first_name` and `second_name`, giving the model the complete player name from the source data.

The lesson: sometimes, the LLM makes mistakes because the information you give it is incomplete. Providing the correct, complete data reduces the need for it to guess.

**3. Captaincy recommendations exposed a scoring-design problem**

`top_players` initially weighted form, fixtures, and value equally. Because the value score favored cheaper players, a £5m defender could rank highly as a captaincy option, but defenders arent the idle picks for captains.

The scoring logic was doing what I had designed it to do. The problem was that the weights didn't match the decision being made.

I added a `min_price` filter and configured captaincy questions to prioritize form and fixtures, with value weighted at zero:

`{form: 0.5, fixtures: 0.5, value: 0.0}`

The lesson: a scoring model can be mathematically consistent and still produce poor recommendations when its objective doesn't match the user's intent.

**4. Making tool calls more resilient**

Groq's `gpt-oss-120b` occasionally returned malformed tool-call names containing internal control tokens, such as `top_players<|channel|>commentary`. This caused the API request to fail and could leave the user with a traceback.

I added error handling for `BadRequestError` and `APIConnectionError`, with a single retry for the relevant failures. This also helps recover from stale HTTP connections after idle periods.

The lesson: a working agent needs more than a successful tool call. It also needs controlled failure handling so that occasional API or connection errors don't unnecessarily crash the user-facing application.

---

## How to run it

### With Docker (recommended)

Requires Docker and a free Groq API key.

```bash
git clone https://github.com/davidopara-tech/cochee.git
cd cochee

# 1. Copy the env template and add your Groq key
cp .env.example .env
# edit .env → paste your key from https://console.groq.com

# 2. Start database + server (first run builds the image + syncs data)
docker compose up

# 3. In a second terminal — interactive agent
docker compose run --rm client

The agent is now interactive. Ask it an FPL question — anything from
"who should I captain?" to "find me a cheap midfielder" to "compare Saka
and Palmer". Type `quit` to exit.

---

## Data ingestion

`scripts/scheduler.py` refreshes FPL data every 4 hours. It runs `sync` (fetch
from the FPL API) then `embed` (recompute vectors), logging to both stdout and
`scheduler.log`. On a 429 it honours `Retry-After`. On transient failures it
retries next cycle. On fatal bugs it exits so the failure isn't silently
retried forever.

Run with `python -m scripts.scheduler`. Stop with Ctrl+C.

I considered a tiered design (static / matchday / on-demand) and rejected it.
Live in-match polling adds 200+ lines of matchday-detection logic and a class
of bugs that only appear during live matches. FPL decisions happen before the
deadline. Four hours is right-sized for the product.

---

## What's not built

- **Personal squad integration.** The FPL `my-team` endpoint requires session
  cookies, which means storing FPL credentials. Two to four hours of work and a
  new class of security questions. Out of scope for a hackathon build.

- **Persistent conversation history.** The LLM remembers your team for the
  current session. Close the script and it forgets.
  
- **Dev-tier headroom.** Groq's free tier caps at 200K tokens/day, which is
  tight for long test sessions. A one-off $5 dev tier removes this.

---

## Stack

Python 3.14 · FastAPI · PostgreSQL 18 + pgvector · SQLAlchemy 2.0
· fastapi-mcp 0.4.0 · Groq (`gpt-oss-120b`)

---

## License

MIT — see [LICENSE](LICENSE).