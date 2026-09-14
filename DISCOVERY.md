# Lead Discovery Engine

Implements spec sections 6-9: given a target market + industry, find real
candidate businesses, deduplicate against what's already in the database, and
persist the new ones. Discovery does **not** run the analysis pipeline
(crawl + AI) automatically -- that stays a separate, explicit action per
business, since it's the slow/expensive step (see `ARCHITECTURE.md`).

## Data source: OpenStreetMap

Per spec section 74 ("use free/local technology wherever practical") and
section 7 ("prefer public business directories... authorized APIs"), the
current provider uses:

- **Nominatim** (`app/services/discovery/geocode.py`) -- free geocoder, turns
  "Houston, Texas, USA" into a bounding box. No API key.
- **Overpass API** (`app/services/discovery/osm_provider.py`) -- free query
  API over OpenStreetMap data, used to find businesses tagged with the
  relevant category within that bounding box. No API key.

Both are public, keyless, general-purpose data APIs -- this is not scraping:
no browser automation, no bypassing access controls, no private data. Usage
respects each service's policy (descriptive User-Agent, one bounded request
per discovery run, capped result count).

### Trade-offs vs. a paid provider

OSM coverage depends entirely on how well an area has been mapped by
volunteers. In practice:

- Dense in many US/EU cities, sparse in others.
- Contact info (phone/website/email) is present only when someone tagged it
  -- expect some results with a name and location but no website or phone.
- No review counts, ratings, or business-size data (unlike Google Places
  or Yelp Fusion).

This is intentional for the MVP: zero cost, zero signup, real data, good
enough to prove and use the discovery -> analysis -> outreach loop. Spec
section 7 explicitly calls for "licensed data providers later" -- adding
Google Places or Yelp Fusion later is a matter of writing a new
`LeadSourceProvider` implementation; nothing else in the app changes.

## Provider architecture

```
DiscoveryCriteria (country, region, city, industry, max_results)
        │
        ▼
LeadSourceProvider.discover()        <- interface, app/services/discovery/provider.py
        │
        ▼
OpenStreetMapProvider                 <- current implementation
        │
        ▼
list[DiscoveredBusiness]
        │
        ▼
dedup against existing Business rows  <- app/services/discovery/dedup.py
        │
        ▼
persist new Business rows (source_name, source_ref, discovered_at set)
```

`OpenStreetMapProvider.last_error` is set (and surfaced through the API as
`source_error`) when the *source itself* failed (geocoding or Overpass
unavailable/rate-limited) -- this is distinguished from a genuine
zero-matches result so the UI doesn't silently look identical to "no
businesses found" when the real story is "try again in a minute."

## Getting bulk volume without a paid API or scraping

Two knobs, both free and zero-signup, that multiply how many real
businesses a single call returns:

1. **Omit `city`.** `DiscoveryCriteria.city` is optional -- if you pass only
   `country` + `region`, Nominatim geocodes the whole state/region and
   Overpass searches that entire bounding box. Verified live: one call for
   `country=USA, region=Colorado, industry=Dental` (no city) returned real
   dental practices spanning Denver, Lakewood, Parker, and more, in one
   request.
2. **List multiple industries, comma-separated.** `industry="Roofing,
   Plumbing, Electrician"` unions all three into a single Overpass query
   instead of three separate discovery runs. Each result is tagged with the
   *specific* category it actually matched (derived from its own OSM tags
   via `label_from_osm_tags`), not the combined search string -- so a
   roofer found this way still shows `industry: "Roofer"`, not
   `"Roofing, Plumbing, Electrician"`.

Verified live: one call for `region=Colorado, industry="Roofing, Plumbing,
Electrician", max_results=30` returned 30 real businesses (11 roofers, 11
plumbers, 8 electricians) across multiple Colorado cities in 14.6 seconds.
`max_results` ceiling raised from 50 to 200 accordingly.

What this does *not* solve: OSM's per-listing detail sparsity (a result
found this way can still lack phone/email/website if no one tagged it --
see the trade-offs section above). Volume and per-listing richness are
separate problems; a licensed provider (Google Places, etc.) would improve
richness, not volume, and stays a config-swap away behind
`LeadSourceProvider` whenever that's wanted.

## Industry matching

OSM has no single "industry" field; businesses are tagged with one of
several keys (`shop=`, `amenity=`, `craft=`, `office=`, `leisure=`) depending
on category. `app/services/discovery/industry_map.py` curates common
mappings (roofing, plumbing, dental, cafe, law firm, etc.). An industry with
no curated mapping falls back to a keyword search against the `name` tag,
which is less precise -- extend the map as real usage reveals gaps.

## Deduplication

Single-source today, so dedup (`app/services/discovery/dedup.py`) compares
each candidate against existing businesses by normalized name + city, or an
exact phone match. A full `business_sources` table for multi-source
provenance (spec section 8) is deferred until a second source exists to
actually reconcile against -- for now, `source_name`/`source_ref`/
`discovered_at` columns directly on `businesses` capture provenance.

## API

```
POST /api/discovery/run
{
  "country": "USA",
  "region": "Texas",
  "city": "Houston",
  "industry": "Roofing",
  "max_results": 20
}
```

Returns `{found, created, skipped_duplicates, businesses, source_error}`.

## Not yet built

- Multiple concurrent source providers merged together
- Scheduled/recurring discovery runs
- Admin UI for managing the industry tag map
- A paid provider (Google Places, Yelp Fusion) for denser/richer coverage
