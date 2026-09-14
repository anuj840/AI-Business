# Analytics & Hot Deals

Implements the buildable subset of spec section 36. The full funnel
(Discovery → Contacted → Reply → Interested → Demo → Trial → Paid → Retained)
needs campaigns and reply-tracking, which don't exist yet (spec section
16/27) — this reports honestly on what the platform actually collects
today: discovery/analysis/scoring/outreach-draft state.

## `GET /api/analytics/summary`

Funnel/breakdown counts: total businesses, analyzed vs not, reachable
count, breakdowns by opportunity type / website status / priority tier /
discovery source, outreach draft counts, background job health.

## `GET /api/analytics/hot-deals`

The direct, actionable answer to "which leads should I work today" —
businesses that are simultaneously:

- a real opportunity (`opportunity_type != IGNORE`)
- reachable (phone or email on file)
- not yet approved for outreach (still actionable)

...sorted by lead score descending. Built entirely from data already
collected — no new source required. `priority_label()` (in
`app/services/scoring/lead_score.py`) was written early on but sat unused
until this feature gave it a purpose.

## What "hot" doesn't yet account for

Review count/rating, business age, and social proof are the strongest
real-world "will they actually buy" signals (see discussion in chat) but
aren't in our free data source (OpenStreetMap rarely has them). A licensed
provider (Google Places, etc.) would add these — deferred per the earlier
"stay fully free" decision. Until then, lead score + reachability +
opportunity clarity is the best signal available.

## A real bug found and fixed while building this

Postgres rejected the source-breakdown query with a `GroupingError`:
`func.coalesce(Business.source_name, "manual")` called twice (once in
`SELECT`, once in `GROUP BY`) compiles to two separate bound-parameter
expressions even with an identical literal, and Postgres doesn't recognize
them as the same grouping expression. Fixed by building the expression
once and reusing the same object in both places. Verified live against
the real 67-business dataset before and after.
