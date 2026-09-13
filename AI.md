# AI Architecture

## Provider abstraction

```
Application code
      │
      ▼
app/services/ai/service.py   (task routing + structured-output validation)
      │
      ▼
AIProviderInterface           (app/services/ai/provider.py)
      │
      ▼
OllamaProvider (now)  /  OpenAIProvider (future)
```

Nothing outside `app/services/ai/` knows which concrete provider is active.
Switch providers via the `AI_PROVIDER` env var; add a new provider by implementing
`AIProviderInterface.generate()` and registering it in `app/services/ai/factory.py`.

## Task types (current)

| Task type          | Prompt                              | Schema                |
|---------------------|--------------------------------------|------------------------|
| `AUDIT_GENERATION`  | `app/prompts/audit_generation/v1.txt`| `AuditAIOutput`         |
| `OUTREACH_DRAFT`    | `app/prompts/outreach/v1.txt`        | `OutreachAIOutput`      |

Deterministic checks (HTTPS, forms, meta tags, etc.) never go through the LLM —
see `app/services/analysis/deterministic.py`.

## Structured output contract

Every AI call that needs structured data:

1. Renders a versioned prompt template asking for JSON matching a documented schema.
2. Calls the provider.
3. Extracts JSON from the raw text (`app/services/ai/json_utils.py` handles markdown
   fences and stray prose).
4. Validates against a Pydantic schema (`app/schemas/ai_outputs.py`).
5. On failure, retries once with a correction suffix appended to the prompt.
6. On repeated failure, logs the error and returns a safe fallback — callers never
   crash and prospect records are never corrupted (spec section 66).

## Fact vs. inference

The audit report tags every item:

- `FACT` — from deterministic analysis, never touched by the LLM
- `AI_INFERENCE` — LLM-identified strength/weakness
- `RECOMMENDATION` — LLM-suggested action

The LLM is explicitly instructed never to fabricate reviews, pricing, certifications,
or performance claims, and to say "unknown" rather than guess.

## Cost/usage tracking

Not yet implemented (deferred — see spec section 47). When added, it will wrap
`AIProviderInterface.generate()` calls to log task type, provider, model, input/output
size, duration, and success — without touching call sites.
