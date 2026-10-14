# Live clinic source evaluation

**Reviewed:** 12 October 2026

## Decision

No additional live clinic source was integrated. The repository does not have
evidence of a free, documented, branch-level API with permitted automated use,
geographic filtering, and fields that can be mapped reliably to the existing
clinic contract.

Adding a website scraper would create an unverified dependency on undocumented
HTML, could violate provider terms, and would not establish that retrieved
records are current or independently verified.

## Candidate sources

| Candidate | Evidence reviewed | Useful fields | Decision |
| --- | --- | --- | --- |
| Apollo Hospitals official directory | [Apollo facilities](https://www.apollohospitals.com/facilities/hospitals) and [Apollo 24|7 hospitals and clinics](https://www.apollo247.com/hospitals-and-clinics). The official facilities page returned HTTP 403 during this review. No public developer API or automated-access terms were found. | Potentially branch names, addresses, contacts, and facility categories through the user-facing site | Do not automate without written provider permission or documented API access |
| Suraksha Diagnostics official directory | [Suraksha clinic details](https://www.surakshanet.com/clinic-details/) was reachable during this review. No documented developer API or permission for bulk automated extraction was found. | Branch pages may expose location and contact details | Do not scrape; request an approved feed/API or use manual verification |
| ABDM Health Facility Registry | [ABDM registry](https://nhpr.abdm.gov.in/nhpr/v4) was reachable as a registry site. This review did not establish a public, unauthenticated, radius-queryable branch API or the freshness/usage terms required by this application. | Registry records may contain facility identity and location | Not validated for this integration |
| Data.gov.in health datasets | [Data.gov.in](https://data.gov.in/) was not fetchable from this environment (HTTP 403). Search results describe datasets and APIs, but no specific dataset was validated for current clinic-branch coverage, query parameters, licensing, and update guarantees. | Dataset-dependent facility and geographic fields | Not validated for live search |
| OpenStreetMap/Overpass | Existing adapter. [OSM API usage policy](https://operations.osmfoundation.org/policies/api/) permits Overpass as a read-only ecosystem service subject to provider limits, attribution, and responsible usage. | OSM IDs, tags, names, coordinates, mapped contacts | Retained as discovery-only and unverified |

Third-party business directories were not considered authoritative or clearly
permitted for automated reuse and were excluded.

## Permitted manual-import workflow

Until an approved provider feed is obtained, an authorized administrator can
maintain branch coverage through the existing authenticated SQLite directory:

1. Confirm the actual branch, address, coordinates, facility type, and any
   contact fields using an authoritative provider source or direct confirmation.
2. Record the source and field-specific evidence with
   `POST /admin/clinic-directory`.
3. Review the new record while it is `pending`.
4. Use `PUT /admin/clinic-directory/{id}?verify=true` only after the evidence
   supports the fields being verified.
5. Re-check records before the configured stale threshold. Re-verification
   updates the check time; deactivation preserves history when a branch is
   confirmed closed or invalid.
6. Review changes through
   `GET /admin/clinic-directory/{id}/audit`.

This workflow does not create records from provider brand names alone. OSM
results remain unverified and are never promoted automatically.

## Re-evaluation criteria

A future live source can be added behind the provider abstraction only after
written or published evidence confirms:

- permitted automated access and attribution/licensing terms;
- branch-level identity and geographic fields;
- a bounded location/radius query or a permitted downloadable feed;
- freshness/update behavior;
- safe rate limits and timeout expectations; and
- a mapping for field-level provenance without implying verification merely
  because data was fetched.
