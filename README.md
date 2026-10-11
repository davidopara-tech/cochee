# Cochee

A conversational FPL advisor for the Amazon Developer Hackathon 2026 (Alexa+ track).

Cochee answers FPL questions like *"I've got £8.5m — who's the best midfielder to bring in?"* by finding players through semantic similarity and scoring them from three perspectives: **Form**, **Fixtures**, and **Value**.

## What it does

Three things, in order of how interesting they are:

1. **Semantic player search** — every player is represented as a 24-feature vector. "Find me a cheaper Saka" is a nearest-neighbour query using [pgvector](https://github.com/pgvector/pgvector).
2. **Three-advisor scoring** — every player gets three 0–10 scores (Form, Fixtures, Value) plus a combined score, with the reasoning behind each.
3. **LLM-facing tools** — three clean, filtered, JSON-friendly functions an LLM can call over HTTP *and* MCP. The LLM picks the tool, we return the numbers.

## Architecture

Cochee is deliberately split into three layers:

```
┌────────────────────────────────────────────┐
│  Conversation (Alexa+ / LLM)               │   ← the AI
│  Understands the user, picks tools         │
└──────────────────┬─────────────────────────┘
                   │ MCP
┌──────────────────▼─────────────────────────┐
│  Orchestration (MCP server)                │   ← the interface
│  Exposes tools to the LLM                  │
└──────────────────┬─────────────────────────┘
                   │ function calls
┌──────────────────▼─────────────────────────┐
│  Computation (advisors, embeddings)        │   ← the math
│  Deterministic, testable, no AI            │
└────────────────────────────────────────────┘
```

The "AI agent" is the LLM at the top. Everything below it is plain Python. This keeps the system fast, cheap, and debuggable.

## Stack

- **Python 3.14**, **FastAPI**
- **PostgreSQL 18 + pgvector** (via Docker)
- **SQLAlchemy 2.0**, psycopg2, pydantic-settings
- **fastapi-mcp 0.4.0** for MCP (Streamable HTTP), pinned to **mcp>=1.12.0,<2** — fastapi-mcp 0.4.0 is not compatible with the mcp 2.x SDK
- **uvicorn** as the ASGI server
- Direct API calls — no CrewAI, no LangGraph

## Getting started

### 1. Start the database

```bash
docker run -d --name cochee-pg \
  -e POSTGRES_USER=<your-user> \
  -e POSTGRES_PASSWORD=<your-password> \
  -e POSTGRES_DB=<your-db> \
  -p 5434:5432 \
  pgvector/pgvector:pg18
```

The image ships with pgvector pre-installed. Port 5434 is used in this project because 5432 and 5433 are commonly occupied by a local Postgres or another container.

> **Note:** In local development, we use `cochee` for the user, password, and database name. Real deployments should inject these from a secrets manager. The actual `.env` file is listed in `.gitignore` and must never be committed.

### 2. Configure environment

Create `.env` at the project root:

```
DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5434/<db>
```

### 3. Install dependencies

```bash
python -m venv cochee-venv
cochee-venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 4. Set up the database

```bash
# Register the pgvector extension (once per container)
docker exec -it cochee-pg psql -U <user> -d <db> -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Create tables
python -m scripts.init_db

# Fetch data from the FPL API (20 teams, 38 gameweeks, 667 players, 380 fixtures)
python -m scripts.sync

# Compute the 24-feature embedding for every player
python -m scripts.embed
```

### 5. Try the tools

```bash
python -m scripts.test_tools
```

### 6. Run the API + MCP server

```bash
uvicorn app.main:app --reload
```

- HTTP routes: `http://127.0.0.1:8000/tools/*` (Postman-friendly)
- API docs: `http://127.0.0.1:8000/docs`
- MCP endpoint: `http://127.0.0.1:8000/mcp`

Verify the MCP menu:

```bash
python mcp_test.py
```

Expected: three tools — `top_players`, `similar_players`, `compare_players`.

## Project layout

```
cochee/
├── app/
│   ├── main.py            FastAPI app + MCP mount
│   ├── database.py        Engine, session factory, base class
│   ├── models.py          Team, Gameweek, Fixture, Player (with Vector(24), search_name)
│   ├── fpl_client.py      FPL API calls with retries and backoff
│   ├── ingest.py          Cleans and upserts FPL data into Postgres
│   ├── embeddings.py      Computes the 24-feature vector per player
│   ├── tools.py           LLM-facing tools (get_top_players, find_similar_players, compare_players)
│   ├── routers/
│   │   ├── schemas.py     Pydantic request models
│   │   ├── health.py      GET /health
│   │   └── tools_router.py POST /tools/* — the three tool endpoints
│   └── advisors/
│       ├── common.py      Shared helpers (min_max, scale, weighted_score)
│       ├── form.py        Form advisor
│       ├── fixtures.py    Fixtures advisor
│       ├── value.py       Value advisor
│       └── combined.py    Combines the three into one score
├── scripts/
│   ├── init_db.py         Create tables
│   ├── sync.py            Fetch from FPL and ingest
│   ├── embed.py           Compute embeddings
│   ├── check_db.py        Connection sanity check
│   └── test_*.py          One test per advisor and for the tools
└── mcp_test.py            Verifies the MCP menu (tools/list)
```

## Design decisions worth knowing

- **Primary keys are FPL's own IDs.** This makes re-ingestion a clean `INSERT ... ON CONFLICT DO UPDATE` instead of a delete-and-recreate.
- **All 24 features are min-max scaled to [0, 1].** Without scaling, price (`156`) would dominate distance math over xG/90 (`0.45`).
- **Position, availability, and price are hard filters, not preferences.** You cannot swap a striker for a midfielder in FPL — so similarity search must never compare across positions.
- **Advisors score; callers filter.** Keeps advisors pure and reusable.
- **Tools return small dicts, not ORM objects.** The LLM only needs a name, price, three scores, and a reason — not the full 40-column row.
- **`search_name` column on `players`.** Concatenates first name, second name, and web name (lowercased). Enables token-based name search — `"Bruno Fernandes"` matches even when the DB stores `"B.Fernandes"`.
- **Tools return status discriminators, not just data.** `find_similar_players` and `compare_players` return `{"status": "ok" | "partial" | "not_found" | "ambiguous", ...}`. The `ambiguous` case includes candidate players so the LLM can ask the user which one they meant — instead of the tool guessing.

## Rate limiting

The FPL API has no published rate limit, and community reports suggest aggressive polling triggers HTTP 429s. Cochee's plan:

- **Background scheduler** refreshes data on a tiered schedule (hot / warm / cold / frozen).
- **User requests never hit the FPL API directly** — they read from our own database.
- Roughly 30 API calls per day regardless of user count.

The scheduler is not yet implemented; the current `scripts/sync.py` is the manual equivalent.

## License

MIT — see `LICENSE`.

## Acknowledgements

Built for the **Amazon Developer Hackathon 2026** (Alexa+ track). Uses the public [Fantasy Premier League API](https://fantasy.premierleague.com/api/bootstrap-static/) — not affiliated with the Premier League.