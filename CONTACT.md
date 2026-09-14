# Contact-Only Check

`app/services/contact/finder.py`. Answers one question fast (a few seconds):
does this business have a phone or email we can actually reach them
through, before spending 45s-3min crawling and calling the AI model on the
full pipeline.

## Why this exists

Outreach can only ever reach a lead through a phone number or an email
address. Running the full analysis pipeline on a business that turns out
to have neither is wasted crawl + AI compute. This does the cheap, useful
part first: a bounded 2-page crawl (homepage + whatever it links to) purely
for regex-extracted contact info, reusing the existing crawler and SSRF
guard, with zero AI calls.

## When it runs

- **Automatically** right after a business is created (`POST
  /api/businesses`) if a website URL was given but phone/email weren't —
  awaited inline since it's fast; a failure here never blocks business
  creation.
- **Automatically** during Discovery, for newly discovered businesses that
  have a website but no phone/email from the source — bounded concurrency
  (5 at a time) and capped at 30 per discovery run so one call can't have
  open-ended duration.
- **On demand** via `POST /api/businesses/{id}/find-contact` (and the
  "Check Contact Info" button on the business detail page) — safe to
  re-run anytime.

## What it never does

Overwrite an existing phone/email (same "never overwrite, only fill gaps"
rule as the full pipeline's backfill — see `pick_best_email` in
`app/services/pipeline.py`, shared by both). Run any AI call. Follow more
than 2 pages. Crawl a business that has no website URL at all (nothing to
check).
