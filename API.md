# API (vertical slice)

Base URL: `http://localhost:8000`

No authentication yet — see `SECURITY.md`. Do not expose this outside a trusted
local/dev network.

## Health

- `GET /health` — liveness only.
- `GET /ready` — checks database + Ollama connectivity, returns `{"status": "ok"|"degraded", "checks": {...}}`.

## Businesses

### `POST /api/businesses`

Create a business record.

```json
{
  "name": "ABC Roofing",
  "website_url": "https://example.com",
  "country": "USA",
  "region": "Texas",
  "city": "Houston",
  "industry": "Roofing",
  "phone": "+1 555-0100",
  "email": "info@example.com",
  "notes": "optional"
}
```

`website_url` is optional — omit it if no website is known; the pipeline will
classify the business as `NO_WEBSITE_FOUND` / `NEW_WEBSITE` opportunity.

If a website was given but no `phone`/`email`, a fast contact-only check
runs automatically before the response comes back (see `CONTACT.md`) — a
few extra seconds, not the full pipeline.

Returns `201` with the created `BusinessOut`.

### `GET /api/businesses`

List all businesses, newest first.

### `GET /api/businesses/{id}`

Fetch one business.

### `POST /api/businesses/{id}/find-contact`

Fast (a few seconds), AI-free phone/email-only check — crawls up to 2 pages
of the business's website purely for contact info. See `CONTACT.md`. `400`
if the business has no website URL. Never overwrites an existing
phone/email.

```json
{"phone": "+1 555-0100", "email": "info@example.com", "reachable": true, "pages_checked": 2, "updated": true}
```

### `POST /api/businesses/{id}/analyze`

Enqueues the pipeline (crawl → deterministic analysis → website quality score →
lead score → opportunity classification → AI audit → AI outreach draft) as a
background job (spec section 39) and returns immediately — HTTP `202`:

```json
{"job_id": "...", "status": "QUEUED"}
```

The actual work runs in a separate ARQ worker process (`app/worker/`), not this
request. Poll `GET /api/jobs/{job_id}` until `status` is `COMPLETED`, then fetch
`GET /api/businesses/{id}/analysis` for the result. See `JOBS.md`.

Re-running `/analyze` re-runs the whole pipeline and overwrites the prior result
for that business (upsert, not append) once the new job completes.

### `GET /api/jobs/{job_id}`

```json
{
  "id": "...", "job_type": "ANALYZE_BUSINESS",
  "status": "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "RETRYING" | "CANCELLED",
  "business_id": "...", "started_at": "...", "completed_at": "...",
  "error": null, "retry_count": 0, "metadata": {"business_name": "..."}
}
```

### `GET /api/businesses/{id}/analysis`

Returns the same `PipelineResultOut` shape a completed job produces, reading the
persisted result rather than re-running anything. Use this to render a
business's page without paying the crawl/AI cost again. Returns `404` if no
`/analyze` job has ever completed for this business.

```json
{
  "business": {...},
  "website_status": "WEBSITE_FOUND",
  "pages_crawled": 5,
  "facts": {...},
  "quality_score": {"overall": 62, "categories": {...}, "reasons": [...]},
  "opportunity": {"type": "LEAD_CONVERSION", "confidence": 0.7, "reasons": [...], "recommended_service": "Conversion Package"},
  "lead_score": {"overall": 58, "reasons": [...]},
  "audit": {"summary": "...", "items": [{"kind": "FACT"|"AI_INFERENCE"|"RECOMMENDATION", ...}], ...},
  "outreach_draft": {"subject": "...", "body": "...", "requires_human_approval": true}
}
```

## Discovery

### `POST /api/discovery/run`

Finds candidate businesses matching a market + industry via OpenStreetMap,
deduplicates against existing businesses, and persists the new ones. Does
**not** run `/analyze` on them -- see `DISCOVERY.md`.

```json
{
  "country": "USA",
  "region": "Texas",
  "city": "Houston",
  "industry": "Roofing",
  "max_results": 20
}
```

Returns:

```json
{
  "found": 10,
  "created": 10,
  "skipped_duplicates": 0,
  "businesses": [ /* BusinessOut[] */ ],
  "source_error": null
}
```

`source_error` is set (with `businesses: []`) if the data source itself
failed or was rate-limited -- distinct from a genuine zero-results match.

## Outreach

### `GET /api/businesses/{id}/outreach-draft`

Fetch the current draft (404 if `/analyze` hasn't been run, or the opportunity
was `IGNORE` and no draft was generated).

### `POST /api/businesses/{id}/outreach-draft/approve`

Marks the draft as human-approved. **No send capability exists in this codebase
yet** — approval only flips a flag for the future outreach/email phase to key off.

## Errors

Standard FastAPI/Pydantic validation errors (422) for bad request bodies; `404`
for missing resources; `500` with a generic message if the pipeline fails
unexpectedly (full error detail goes to structured logs, never to the client).
