# Clinic search audit

**Reviewed:** 12 October 2026

## Current Overpass behavior

The current adapter is [`backend/integrations/overpass.py`](../backend/integrations/overpass.py).
Its query searches only `nwr["amenity"="clinic"]` and
`nwr["healthcare"="clinic"]` inside the requested radius. It does not search
provider names, operators, brands, hospitals, or diagnostic centres. Results
are requested with `out center tags`, so ways use their Overpass `center`
coordinates.

The response mapper:

- skips elements without an integer OSM `type`/`id`, a usable name, or a
  supported coordinate;
- accepts `node`, `way`, and `relation` elements; ways and relations require
  Overpass `center` coordinates;
- calculates Haversine distance from the requested coordinates and excludes
  results beyond the requested radius;
- deduplicates only repeated `(type, id)` pairs;
- preserves OSM tags in `source_data`;
- leaves missing fields unknown and marks every result `unverified`.

## Evidence and limits

The supplied Overpass export (`export.json`) is timestamped
`2026-10-11T10:45:20Z` and contains OSM clinic-tagged elements, but it does
not establish complete Barrackpore coverage and does not contain enough
evidence to confirm or reject a particular Apollo, Jibok, or Suraksha branch.
A text search of the supplied export did not find those provider names. That
is evidence only about this export, not proof that the real-world branches do
not exist.

The application has no provider-brand query, but it does have an independently
verified SQLite directory and branch-verification workflow. Therefore a missing
expected result could be caused by absent OSM mapping, incompatible OSM tags,
an absent directory record, a location outside the requested radius, missing
coordinates/name, a stale/deactivated directory record, or a provider response
failure. The existing code does not provide evidence to distinguish those
causes for a specific real-world branch without authoritative branch evidence.

The live endpoint was probed on 12 October 2026. The direct Overpass request
returned HTTP 200, while one application request returned HTTP 503 with
`overpass=unavailable` and `directory=ok`; a separate adapter probe then
returned 69 listings. This establishes a transient provider request failure
for that application request, not missing real-world coverage.

The audit also found two application defects: `nwr` relation results were
discarded by the mapper, and a successful empty source combined with a failed
source was incorrectly classified as total provider failure. Both are fixed
and covered by mocked tests.

No real-world provider coverage is claimed by this audit. Provider names and
branches must be added to the directory only after an authorized administrator
confirms the actual branch, address, and coordinates.

The broader-source investigation is documented in
[`SOURCE_EVALUATION.md`](SOURCE_EVALUATION.md). No additional live provider was
integrated because no candidate had a validated, permitted branch-level API.

## Change made after the audit

The search now combines the existing OSM adapter with a local SQLite directory
of independently maintained branch records. Directory records are empty by
default, require authenticated administrator actions, retain field-level
provenance and verification dates, and are searched by their actual stored
coordinates. This improves coverage only when records have been independently
verified; it does not fabricate or infer branches.
