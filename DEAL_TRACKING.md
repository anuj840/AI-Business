# Deal / Status Tracking

Implements the biggest gap flagged in the business-strategy discussion:
nothing tracked what happened after you approved an outreach draft. No way
to know if any of this generates revenue.

## Scope: adapted from spec section 27, not built as-is

The spec's recipient states (`NEW, RESEARCHED, READY, CONTACTED, REPLIED,
INTERESTED, NOT_INTERESTED, DO_NOT_CONTACT, CONVERTED, BOUNCED`) are
campaign-recipient states -- they assume a campaign/sending system that
updates them automatically (a send confirms CONTACTED, a bounce webhook
sets BOUNCED, etc.). None of that exists yet (spec section 58 explicitly
defers it).

So `DealStatus` here is a **manual, per-business status** you set yourself
as you work a lead in the real world -- sent an email through your own
client, got a reply, closed the deal. Trimmed to what makes sense without
send infrastructure:

`NEW, CONTACTED, REPLIED, INTERESTED, NOT_INTERESTED, DO_NOT_CONTACT, CONVERTED`

(Dropped `RESEARCHED`/`READY` as pre-contact workflow states not worth the
complexity yet; dropped `BOUNCED` since nothing sends email to bounce.)

## Data model

- `Business.deal_status` (+ `deal_status_updated_at`) -- the current state,
  always queryable/sortable/filterable directly.
- `DealActivity` -- a timeline table (spec section 35's "Notes ... Status
  ... Timeline"). Each row is a status change, a free-text note, or both
  together. Changing `Business.deal_status` via `PATCH .../status` always
  logs a `DealActivity` row too, so the timeline is a complete record of
  every transition, not just the ones someone happened to annotate.

## API

- `PATCH /api/businesses/{id}/status` -- `{"status": "CONTACTED"}`
- `POST /api/businesses/{id}/activity` -- `{"note": "...", "status": "..."}` (either alone, or both)
- `GET /api/businesses/{id}/activity` -- timeline, newest first

## Where it shows up

- Business detail page: status badge + dropdown right in the header, plus
  an Activity section (note input + optional status + Add button, timeline
  below).
- Dashboard: a Status column.
- Analytics: a Deal Status breakdown, and a Status column on Hot Deals.

## The one behavior change that matters most

**Hot Deals now excludes terminal statuses** (`CONVERTED`,
`NOT_INTERESTED`, `DO_NOT_CONTACT`) regardless of score. Before this,
Hot Deals only looked at score + reachability + opportunity + draft
approval -- a lead you'd already closed or explicitly rejected had no way
to stop showing up as "worth working." Verified live: marking a real
lead (Mend Roofing) `CONVERTED` immediately removed it from the Hot Deals
list; reverted after confirming (it wasn't actually converted, just a
test).

## Verified live

Full round-trip via the actual UI (not just the API): changed a business's
status via the dropdown, added a note with a simultaneous status change,
confirmed the timeline showed both the UI-created and earlier API-created
entries correctly interleaved newest-first, confirmed the header badge and
dashboard/analytics columns all stayed in sync.

Also fixed a real (if minor) pre-existing responsiveness bug found while
adding the Status column: both the dashboard and Hot Deals tables used
`overflow-hidden` on their outer container, which clips a wide table on a
narrow screen instead of letting it scroll -- changed to a nested
`overflow-x-auto` wrapper around just the `<table>`, keeping the rounded
outer border but letting the table itself scroll horizontally when needed.
