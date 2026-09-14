# Environment Variables

Copy `.env.example` to `.env` and fill in real values for local development.

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `development` | Environment name |
| `DEBUG` | `true` | Enables SQL echo, FastAPI debug mode |
| `DATABASE_URL` | `postgresql+asyncpg://ai_business:ai_business@localhost:5432/ai_business` | Async Postgres connection string |
| `AI_PROVIDER` | `ollama` | `ollama` now; `openai` once `OpenAIProvider` is implemented |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model tag; must be pulled via `ollama pull <model>` first |
| `OLLAMA_TEMPERATURE` | `0.2` | Sampling temperature |
| `OLLAMA_MAX_TOKENS` | `2048` | Max output tokens (`num_predict`) |
| `OLLAMA_TIMEOUT_SECONDS` | `90` | HTTP timeout per request |
| `OLLAMA_MAX_RETRIES` | `2` | Retries on transient (5xx/network) failures, exponential backoff |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string for the ARQ job queue |
| `JOB_MAX_RETRIES` | `1` | ARQ retries per analyze job on an unhandled exception |
| `JOB_TIMEOUT_SECONDS` | `600` | Hard ceiling per analyze job (crawl + two AI calls) |
| `CRAWLER_MAX_PAGES` | `8` | Max pages crawled per website |
| `CRAWLER_TIMEOUT_MS` | `20000` | Per-page navigation timeout |
| `JWT_SECRET` | — | Reserved for the auth phase; must be a long random value in production |

Never commit `.env`. It's already covered by `.gitignore`.
