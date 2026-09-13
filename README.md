# AI Business Growth Platform

Internal (eventually SaaS) platform to discover foreign-market businesses, analyze their
digital presence, identify genuine commercial opportunities, and generate personalized,
human-approved outreach.

**Current status: vertical slice (Phase 1 proof-of-concept).** Full roadmap in the
master spec: see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## What it does

**Discovery**: give it a market (country/region/city) + industry, and it finds real
candidate businesses via OpenStreetMap (free, public data), deduplicates against what's
already in your database, and adds the new ones — see `DISCOVERY.md`.

**Analysis pipeline** (per business, triggered manually): `crawl → deterministic
analysis → website quality score → lead score → opportunity classification →
AI-generated audit → AI-generated outreach draft (requires human approval before any
send)`.

Explicitly **not** included yet (see spec sections 57–58 / ARCHITECTURE.md phases):
campaigns/email sending, multi-tenant auth, background job queue, demo website
generator, chatbot widget, RAG/pgvector, a paid/licensed discovery data source.

## Stack

- Backend: Python 3.12+ (also tested on 3.14), FastAPI, SQLAlchemy (async), Alembic, Playwright
- AI: Ollama (local), pluggable behind `AIProviderInterface` for future OpenAI support
- Database: PostgreSQL
- Frontend: Next.js (App Router) + TypeScript + Tailwind CSS

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

### 3. Frontend

```bash
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, defaults to http://localhost:8000
npm install
npm run dev
```

Visit `http://localhost:3000`.

- **Discover** → enter a market (country/region/city) + industry → finds real
  businesses via OpenStreetMap and adds them to your dashboard.
- **New Business** → add one manually by name + optional website URL.
- Either way, open a business's detail page → **Run Analysis** (takes 30s–2min
  depending on the site and model) → review the AI audit and outreach draft →
  **Approve Draft**.

### 4. Docker Compose (alternative)

```bash
docker compose up --build
```

Brings up Postgres, Ollama, the backend, and the frontend together.

## Trying the vertical slice

Either use the frontend (`http://localhost:3000`) or curl the API directly:

```bash
# 1. Create a business
curl -X POST http://localhost:8000/api/businesses \
  -H "Content-Type: application/json" \
  -d '{"name": "ABC Roofing", "website_url": "https://example.com", "country": "USA", "region": "Texas", "city": "Houston", "industry": "Roofing"}'

# 2. Run the pipeline (crawl -> score -> classify -> AI audit -> outreach draft)
curl -X POST http://localhost:8000/api/businesses/<id>/analyze

# 3. Fetch the persisted result later without re-running
curl http://localhost:8000/api/businesses/<id>/analysis

# 4. Review + approve the outreach draft before any send would ever happen
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
