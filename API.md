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

Returns `201` with the created `BusinessOut`.

### `GET /api/businesses`

List all businesses, newest first.

### `GET /api/businesses/{id}`

Fetch one business.

### `POST /api/businesses/{id}/analyze`

Runs the full pipeline **synchronously** (crawl → deterministic analysis → website
quality score → lead score → opportunity classification → AI audit → AI outreach
draft) and persists every result. Returns the full `PipelineResultOut`:

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

Re-running `/analyze` re-runs the whole pipeline and overwrites the prior result
for that business (upsert, not append).

> This endpoint is currently synchronous — a slow crawl/AI call blocks the
> request. Once the Redis/worker phase lands, this becomes
> `{"job_id": "...", "status": "queued"}` per spec section 39, with no change
> to the pipeline logic itself.

### `GET /api/businesses/{id}/analysis`

Returns the same `PipelineResultOut` shape as `/analyze`, but reads the persisted
result instead of re-running the pipeline. Use this to render a business's page
without paying the crawl/AI cost again. Returns `404` if `/analyze` has never
been run for this business.

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
