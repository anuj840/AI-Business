# Architecture

Modular monolith (spec section 68) — not microservices. Modules are separated cleanly
under `backend/app/services/` so they can be extracted into services later if scale
ever justifies it.

## Vertical slice (current)

```
Next.js frontend (frontend/)
  │  Dashboard, Discover, New Business form, Business detail page
  │  (Run Analysis polls job status / Approve Draft)
  ▼
FastAPI (app/api/routes)
  │  POST /analyze creates a Job row + enqueues it, returns immediately
  ▼
Redis (ARQ queue)
  │
  ▼
ARQ worker process (app/worker/) ── runs separately from the API process
  │
  ▼
Pipeline orchestrator (app/services/pipeline.py)
  │
  ├── Crawler (Playwright, SSRF-guarded)      app/services/crawler/
  ├── Deterministic analysis (no AI)          app/services/analysis/
  ├── Scoring engine (configurable weights)   app/services/scoring/
  ├── Opportunity classifier (rule-based)     app/services/opportunity/
  ├── AI service (task routing)               app/services/ai/
  │     └── AIProviderInterface → OllamaProvider (OpenAIProvider later)
  ├── Audit generator (facts + AI, tagged)    app/services/audit/
  └── Outreach draft generator                app/services/outreach/
  │
  ▼
PostgreSQL (SQLAlchemy async + Alembic) ── Job row updated to COMPLETED/FAILED
```

See `JOBS.md` for the background job design in full.

Key design decisions:

- **Deterministic vs AI is a hard boundary.** `services/analysis` and `services/scoring`
  never call an LLM. `services/audit` and `services/outreach` call AI only for
  interpretation/copy, and every audit item is tagged `FACT` / `AI_INFERENCE` /
  `RECOMMENDATION` so nothing AI-generated is presented as verified fact.
- **AI provider is swappable.** Application code only depends on
  `AIProviderInterface` (app/services/ai/provider.py). Switching providers is a
  config change (`AI_PROVIDER=openai` once `OpenAIProvider` exists), not a rewrite.
- **Prompts are files, not Python strings**, versioned under `app/prompts/<task>/vN.txt`.
- **AI output is always validated** against a Pydantic schema
  (`app/schemas/ai_outputs.py`) before use; invalid output triggers one correction
  retry, then a safe fallback — it never crashes the request.
- **Human approval gate.** `OutreachDraft.approved` defaults to `false`. No code path
  in this slice sends anything — sending is deferred to the outreach/email phase.
- **SSRF protection is enforced at the crawler boundary**, not just the API layer,
  and re-checked on every followed link (see `app/services/crawler/ssrf.py`).
- **Known contact info is never wasted, even without a website.** A
  no-website business is never crawled, so it has no `facts` beyond
  `reachable: false` on its own — but whatever contact info is already on
  file (phone/email from manual entry or discovery, address from
  `notes`) is folded into `facts` before the audit/outreach/lead-score
  steps run, so a lead with a known phone number isn't treated as if
  nothing is known about it. `OutreachDraft.has_contact_channel` tells the
  UI plainly when there's genuinely no channel (no phone, no email) to
  ever act on the draft through, rather than implying one exists.
- **Domain age catches what technical checks can't.** A site can pass
  every deterministic check (HTTPS, forms, meta tags) and still look
  visually dated. `app/services/domain_age/rdap.py` looks up how long a
  domain has been registered (RDAP, free/official, not scraping); a
  technically-excellent site with a 10+ year old domain is reclassified
  from `IGNORE` to `WEBSITE_REDESIGN` instead of being written off as "no
  opportunity here." See `DOMAIN_AGE.md`.

## Lead discovery engine

Given a market + industry, `app/services/discovery/` finds real candidate
businesses via a pluggable `LeadSourceProvider` (currently OpenStreetMap,
free/keyless), deduplicates against existing businesses, and persists the
new ones -- without running the (expensive) analysis pipeline on them
automatically. See `DISCOVERY.md` for the full design and trade-offs.

## Deferred to later phases (see MASTER PROMPT sections 57–58)

- Multi-tenant auth / organizations
- A second (paid/licensed) discovery source alongside OpenStreetMap
- Campaigns / email sending / follow-up sequences
- Demo website generator / redesign preview / chatbot widget
- pgvector / RAG knowledge system
- Analytics, niche comparison, ML-based scoring
- OpenAI provider

## Data model (vertical slice)

`Business 1—1 Website 1—1 WebsiteAnalysis`, plus `Business 1—1 {LeadScore, Opportunity,
Audit, OutreachDraft}`, plus `Business 1—N Job` (one job per `/analyze` run). See
`backend/app/models/business.py` and `backend/app/models/job.py`. The full spec's
multi-tenant schema (organizations, campaigns, subscriptions, etc.) is intentionally
not created yet — tables are added when the corresponding feature is built, per the
"don't blindly create every table" instruction in the spec.
