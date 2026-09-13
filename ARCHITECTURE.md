# Architecture

Modular monolith (spec section 68) — not microservices. Modules are separated cleanly
under `backend/app/services/` so they can be extracted into services later if scale
ever justifies it.

## Vertical slice (current)

```
Next.js frontend (frontend/)
  │  Dashboard, New Business form, Business detail page
  │  (Run Analysis / Approve Draft)
  ▼
FastAPI (app/api/routes)
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
PostgreSQL (SQLAlchemy async + Alembic)
```

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

## Deferred to later phases (see MASTER PROMPT sections 57–58)

- Multi-tenant auth / organizations
- Lead discovery engine + pluggable source providers
- Redis + Celery/ARQ background workers (pipeline currently runs synchronously
  in-request; `run_full_pipeline()` is already isolated from the request handler
  so moving it into a worker task is a routing change, not a rewrite)
- Campaigns / email sending / follow-up sequences
- Demo website generator / redesign preview / chatbot widget
- pgvector / RAG knowledge system
- Analytics, niche comparison, ML-based scoring
- OpenAI provider

## Data model (vertical slice)

`Business 1—1 Website 1—1 WebsiteAnalysis`, plus `Business 1—1 {LeadScore, Opportunity,
Audit, OutreachDraft}`. See `backend/app/models/business.py`. The full spec's
multi-tenant schema (organizations, campaigns, subscriptions, etc.) is intentionally
not created yet — tables are added when the corresponding feature is built, per the
"don't blindly create every table" instruction in the spec.
