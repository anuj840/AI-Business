# Security

## Secrets

Never commit `.env`. `.env.example` holds placeholder values only. Production
secrets (DB password, JWT secret, future SMTP/OpenAI keys) come from environment
variables / a real secret manager, never hard-coded.

## SSRF (crawler)

See `CRAWLER.md`. The crawler is the highest-risk surface since it accepts
arbitrary user-submitted URLs. All validation lives in
`app/services/crawler/ssrf.py` and is covered by `tests/test_ssrf.py`.

## Input validation

All API request bodies are validated via Pydantic schemas (`app/schemas/`). SQL
is only ever executed through SQLAlchemy's parameterized query builder — no raw
string-interpolated SQL anywhere in this codebase.

## AI output

LLM responses are never executed, rendered as HTML, or trusted as fact without
going through schema validation (`app/schemas/ai_outputs.py`) first — see `AI.md`.

## Human approval gate

`OutreachDraft.approved` defaults to `false`. There is currently no send
capability in the codebase at all (deferred to the outreach/email phase) — this
is a deliberate design constraint, not just a default.

## Not yet implemented (tracked for later phases)

- Authentication / JWT sessions (no auth exists yet — do not deploy this
  vertical slice publicly as-is)
- Rate limiting
- CSRF protection (not yet relevant — no session-based auth or forms exist yet)
- Audit logging of admin actions
- Secure headers middleware
