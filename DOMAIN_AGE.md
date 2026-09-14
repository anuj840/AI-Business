# Domain Age Signal

User's idea: "if a website is 10-20 years old, it's surely due for a
revamp." Real, legitimate, free signal our deterministic checks couldn't
see on their own — HTTPS/forms/meta-tags/etc. measure technical health,
never visual/design staleness. A site can pass every technical check and
still look like it was built in 2010.

## How it's obtained

`app/services/domain_age/rdap.py` — RDAP (Registration Data Access
Protocol), the modern IANA-standardized replacement for WHOIS. Structured
JSON over HTTPS, not scraping, not a ToS concern. Uses the free public
bootstrap/proxy at `rdap.org`, which redirects to the domain's actual
registry RDAP server based on its TLD (e.g. Verisign for `.com`).

```
GET https://rdap.org/domain/<domain>
  -> 302 redirect to the registry's real RDAP server
  -> { "events": [{"eventAction": "registration", "eventDate": "2010-06-15T..."}, ...] }
```

Verified live against real domains: `example.com` → registered
1995-08-14 (age ~31 years), a real discovered business's domain →
registered 2020-12-23 (age ~6 years, correctly not old enough to trigger
anything).

## Where it plugs in

Runs during `/analyze` for any business with a reachable website (added to
`facts` as `domain_registered_date` / `domain_age_years`), alongside the
existing crawl -- no new pipeline stage, no extra job.

- **Opportunity classifier**: previously, a site that passed every
  technical/functional check (`quality >= 80`, strong conversion +
  automation) was classified `IGNORE`. Now, if the domain is 10+ years
  old, it's reclassified `WEBSITE_REDESIGN` instead — the technical checks
  can't see design staleness, but domain age is a real proxy for it.
- **Lead score**: an old domain adds points directly (`OLD_DOMAIN_BONUS`),
  and — this was a real bug the new logic exposed — the existing
  "strong digital presence, de-prioritize" cap (spec section 62) no longer
  silently overrides an old-domain redesign opportunity. Before this fix,
  a technically excellent but decade-old site would have been capped at a
  low score even after being reclassified as a redesign opportunity,
  contradicting its own classification.

Both thresholds (`DOMAIN_AGE_REDESIGN_THRESHOLD_YEARS` in the classifier,
`OLD_DOMAIN_THRESHOLD_YEARS` in the lead scorer) are set to 10 years and
kept as named constants, not magic numbers, so they're easy to retune.

## Known limitation

`_extract_registrable_domain` strips a leading `www.` but doesn't do full
public-suffix-list parsing — it won't correctly separate a registrable
domain from a subdomain on multi-level ccTLDs like `foo.co.uk` (it would
treat the whole string as the domain to look up, which may 404 against
the registry). Fine for the common single-level TLD case (`.com`, `.net`,
etc.); a real public-suffix-list library would be the fix if this matters
for a specific market.

## Verified live

Ran a full analysis end-to-end after deploying this: `domain_registered_date`
and `domain_age_years` populated correctly from a real RDAP lookup, and the
lead score reasons included the new "Domain registered ~31 years ago —
likely due a design refresh" line with its point contribution, alongside
the existing quality-based reason.
