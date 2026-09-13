# AI Business Growth Platform

Internal (eventually SaaS) platform to discover foreign-market businesses, analyze their
digital presence, identify genuine commercial opportunities, and generate personalized,
human-approved outreach.

**Current status: vertical slice (Phase 1 proof-of-concept).** Full roadmap in the
master spec: see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## What the vertical slice does

Input: a business name + (optional) website URL.

Pipeline: `crawl → deterministic analysis → website quality score → lead score →
opportunity classification → AI-generated audit → AI-generated outreach draft (requires
human approval before any send)`.

Explicitly **not** included yet (see spec sections 57–58 / ARCHITECTURE.md phases):
lead discovery engine, campaigns/email sending, multi-tenant auth, background job queue,
demo website generator, chatbot widget, RAG/pgvector.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy (async), Alembic, Playwright
- AI: Ollama (local), pluggable behind `AIProviderInterface` for future OpenAI support
- Database: PostgreSQL
- Frontend: not yet built (planned: Next.js + TypeScript + Tailwind)

## Local setup

### 1. Prerequisites
- Python 3.12+
- PostgreSQL running locally (or via Docker Compose)
- [Ollama](https://ollama.com) installed and running, with a model pulled:
  ```
  ollama pull llama3.1:8b
  ```

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium

cp ../.env.example ../.env   # then edit values as needed
```

Create the database, then run migrations:

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs, `/health` and `/ready`
for health checks.

### 3. Docker Compose (alternative)

```bash
docker compose up --build
```

Brings up Postgres, Ollama, and the backend together.

## Trying the vertical slice

```bash
# 1. Create a business
curl -X POST http://localhost:8000/api/businesses \
  -H "Content-Type: application/json" \
  -d '{"name": "ABC Roofing", "website_url": "https://example.com", "country": "USA", "region": "Texas", "city": "Houston", "industry": "Roofing"}'

# 2. Run the pipeline (crawl -> score -> classify -> AI audit -> outreach draft)
curl -X POST http://localhost:8000/api/businesses/<id>/analyze

# 3. Review + approve the outreach draft before any send would ever happen
curl http://localhost:8000/api/businesses/<id>/outreach-draft
curl -X POST http://localhost:8000/api/businesses/<id>/outreach-draft/approve
```

## Tests

```bash
cd backend
pytest
```

## Security notes

The crawler validates every submitted URL (and every internal redirect/link it
follows) against an SSRF blocklist — see `app/services/crawler/ssrf.py`. It refuses
localhost, private/link-local/reserved IP ranges, and cloud metadata endpoints, and
re-resolves DNS on every hop to avoid DNS-rebinding bypass. See `SECURITY.md` (to be
expanded) for the full policy.

## Documentation

- `ARCHITECTURE.md` — phased build plan and module boundaries
- `AI.md` — provider abstraction, prompt management, structured-output validation
- `CRAWLER.md` — crawler design and limits
