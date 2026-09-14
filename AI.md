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
| `AUDIT_GENERATION`  | `app/prompts/audit_generation/v2.txt`| `AuditAIOutput`         |
| `OUTREACH_DRAFT`    | `app/prompts/outreach/v2.txt`        | `OutreachAIOutput`      |

v2 tightened output size (exact bullet counts, shorter word targets, stronger
"JSON only" reinforcement) versus v1 — see "Generation speed" below. v1 files
are kept on disk per the versioning convention (spec section 19); they're
simply no longer the active version.

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

## Generation speed

Two knobs matter most for a small local model on CPU:

- `OLLAMA_MAX_TOKENS` (default 700, was 2048) — the previous, much larger
  ceiling mostly gave a small/rambling model more room to run long before
  a natural stop, not more useful output. Audit/outreach outputs are meant
  to be a few short bullets or a ~75-word email; 700 tokens is generous
  headroom for that, not a tight squeeze.
- `OLLAMA_TIMEOUT_SECONDS` (default 60, was 90) — the hard per-attempt
  ceiling (see the `asyncio.wait_for` fix noted in JOBS.md). Lowered to
  match the smaller token budget.

Verified live: a typical analyze job (crawl + audit + outreach, on an idle
`llama3.2:1b` instance) dropped from a previous range of roughly 85-300+
seconds to a consistent ~45 seconds after these changes.

**What this does NOT fix**: when the small model fails to produce valid
JSON, `generate_structured` retries once (see above) — and separately,
`OllamaProvider` retries a genuinely slow/unresponsive call up to
`OLLAMA_MAX_RETRIES` times. Under real resource contention (e.g. several
analyze jobs or manual test calls hitting the same single-instance Ollama
container at once on a CPU-only dev machine), each retry can independently
run close to the full `OLLAMA_TIMEOUT_SECONDS` before eventually
succeeding, so an occasional job can still take several minutes even
though every individual attempt is correctly bounded. Observed live: one
job took ~3m40s under contention from concurrent test traffic, while an
isolated run right after (idle Ollama) completed in 47s. This is expected
behavior given CPU-only local inference with no dedicated queueing/
concurrency limit on the Ollama side yet (see RATE LIMITING, spec section
42, not yet implemented) — not something the timeout logic itself can
paper over. A larger/quantized-for-speed model, GPU acceleration, or a
concurrency limit in front of Ollama would address consistency further.

## Cost/usage tracking

Not yet implemented (deferred — see spec section 47). When added, it will wrap
`AIProviderInterface.generate()` calls to log task type, provider, model, input/output
size, duration, and success — without touching call sites.
