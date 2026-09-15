# Database

PostgreSQL, accessed via SQLAlchemy 2.0 async ORM + Alembic migrations.

## Current schema (vertical slice)

Deliberately minimal — only what the current pipeline needs. The full spec's
table list (organizations, campaigns, subscriptions, etc.) is added incrementally
as each feature is actually built, not created speculatively up front.

```
businesses
  id (uuid, pk)
  name, country, region, city, industry, phone, email
  submitted_website_url
  notes
  source_name, source_ref, discovered_at  -- set for discovery-engine results, null for manual entry
  deal_status       (NEW | CONTACTED | REPLIED | INTERESTED | NOT_INTERESTED | DO_NOT_CONTACT | CONVERTED)
  deal_status_updated_at
  created_at, updated_at

deal_activities     (N:1 with businesses -- a timeline)
  id (uuid, pk)
  business_id (fk -> businesses)
  status (nullable)  -- set when this entry represents a status change
  note (nullable)
  created_at, updated_at

websites            (1:1 with businesses)
  id (uuid, pk)
  business_id (fk -> businesses, unique)
  url
  status            (WEBSITE_FOUND | NO_WEBSITE_FOUND | WEBSITE_UNCERTAIN | WEBSITE_UNAVAILABLE)
  pages_crawled
  crawl_data (json) -- raw crawl summary, cached to avoid re-crawling

website_analysis    (1:1 with websites)
  id (uuid, pk)
  website_id (fk -> websites, unique)
  facts (json)      -- deterministic facts only, never AI-touched

lead_scores         (1:1 with businesses)
  id (uuid, pk)
  business_id (fk -> businesses, unique)
  overall_score (int 0-100)
  category_scores (json)
  reasons (json)    -- [{"label": str, "points": int}, ...]

opportunities       (1:1 with businesses)
  id (uuid, pk)
  business_id (fk -> businesses, unique)
  opportunity_type  (NEW_WEBSITE | WEBSITE_REDESIGN | WEBSITE_OPTIMIZATION |
                      LEAD_CONVERSION | AI_AUTOMATION | SEO_GROWTH | OTHER_SERVICE | IGNORE)
  confidence (float)
  reasons (json)
  recommended_service

audits              (1:1 with businesses)
  id (uuid, pk)
  business_id (fk -> businesses, unique)
  report (json)     -- {summary, items: [{kind: FACT|AI_INFERENCE|RECOMMENDATION, ...}], ...}
  ai_model

outreach_drafts     (1:1 with businesses)
  id (uuid, pk)
  business_id (fk -> businesses, unique)
  subject, body
  approved (bool, default false)  -- human approval gate, spec section 29
  ai_model

jobs                (N:1 with businesses -- one row per /analyze run)
  id (uuid, pk)
  job_type          (ANALYZE_BUSINESS)
  status            (QUEUED | RUNNING | COMPLETED | FAILED | RETRYING | CANCELLED)
  business_id (fk -> businesses)
  started_at, completed_at
  error
  retry_count
  job_metadata (json)  -- e.g. {"business_name": "..."} for display without a join
```

All child tables cascade-delete with their business.

## Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Planned additions (not yet created)

Per the phased roadmap: `organizations` / `organization_members` (multi-tenancy),
`business_contacts` / `business_locations` / `business_sources` (discovery +
multi-source deduplication -- provenance currently lives directly on
`businesses`, see DISCOVERY.md), `campaigns` / `campaign_recipients` /
`outreach_events` / `replies` (outreach engine), `customers` / `subscriptions`
(billing), `ai_requests` / `ai_provider_logs` (cost tracking), `system_settings`,
`audit_logs`.
