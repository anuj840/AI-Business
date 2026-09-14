# Deployment

**Current status: local development only.** This vertical slice has no
authentication (see `SECURITY.md`) and should not be deployed to a public
endpoint as-is.

## Local (Docker Compose)

```bash
cp .env.example .env   # edit as needed
docker compose up --build
```

Brings up Postgres, Redis, Ollama, the FastAPI backend, the ARQ worker, and the
frontend. First run: pull a model into the Ollama container before analyzing
anything —

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

Then run migrations against the running Postgres container:

```bash
docker compose exec backend alembic upgrade head
```

## Local (without Docker)

See `README.md` "Local setup" section.

## Production (future)

Not yet designed. Will require, at minimum, before any public deployment:

- Authentication (JWT/session) and multi-tenant authorization
- HTTPS termination
- Secrets via a real secret manager (not `.env` files)
- Rate limiting
- Structured log shipping / monitoring
- Worker autoscaling / multiple worker replicas for real throughput (today
  it's one `arq` process — fine for demos, not for concurrent load)
