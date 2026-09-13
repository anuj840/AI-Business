# Crawler

`app/services/crawler/playwright_crawler.py` — Playwright-based, headless Chromium.

## Limits

- `CRAWLER_MAX_PAGES` (default 8) — bounded breadth-first crawl of same-domain links
  starting from the homepage. Never unlimited (spec section 10).
- `CRAWLER_TIMEOUT_MS` (default 20000) per page navigation.
- Only follows links on the same registered domain (`netloc` match).

## SSRF protection (spec section 44)

`app/services/crawler/ssrf.py` validates every URL before Playwright touches it —
the initial submitted URL AND every internal link the crawler is about to follow
(guards against redirect/DNS-rebinding tricks). Blocked:

- non-http(s) schemes
- `localhost` / loopback / literal private IPs
- link-local, multicast, reserved, unspecified ranges
- cloud metadata hosts (e.g. `169.254.169.254`, `metadata.google.internal`)
- URLs with embedded credentials (`user:pass@host`)

DNS is resolved and **every** resolved address is checked (not just the first),
so a hostname that round-robins to a private IP is still rejected.

## What it extracts (raw signals only — no interpretation)

- title, meta description, H1s, visible text excerpt
- form count
- internal/external links, social links
- emails/phones found in visible text (regex-based)
- external script sources (used to infer chat widgets / analytics / booking systems
  via hostname/keyword matching — still just a raw signal, not a verdict)
- HTTP status per page
- presence of `/robots.txt` and `/sitemap.xml`

Interpretation of these signals into scored/classified facts happens in
`app/services/analysis/deterministic.py`, deliberately kept separate from the
crawler itself.

## Failure handling

A single page failing to load never aborts the whole crawl — it's logged and
skipped. A fatal crawler error (e.g. browser launch failure) returns
`CrawlResult(reachable=False, error=...)` rather than raising, so the pipeline can
still produce a `WEBSITE_UNCERTAIN` classification and a degraded-but-useful audit
instead of crashing the whole job (spec section 66).
