# ClinicFinder — Provider Evaluation

**Project:** ClinicFinder  
**Launch geography:** Kolkata, West Bengal, India  
**Evaluation status:** Initial research — decision pending  
**Budget constraint:** ₹0 for the initial prototype  
**Appointment booking:** Deferred  
**Last reviewed:** 11 October 2026

---

## 1. Purpose

This document evaluates potential data sources for ClinicFinder, a public-facing healthcare discovery platform.

The selected source should support accurate clinic discovery in Kolkata while satisfying applicable licensing, privacy, attribution, pricing, storage, and reliability requirements.

No provider has been selected. Research findings must be validated against actual coverage, documentation, and permitted use before implementation.

## 2. Required Data Fields

The following fields are desired. Their availability must not be assumed.

| Field | Priority | Validation requirement |
|---|---|---|
| Clinic name | Required | Identify the facility consistently |
| Address or locality | Required | Usable location within Kolkata |
| Latitude and longitude | Required for radius search | Coordinates available or lawfully geocodable |
| Clinic category | High | Distinguish clinics, hospitals, and other facilities |
| Medical specialties | High | Confirm the source actually supplies this field |
| Contact number | High | Source and verification date recorded |
| Opening hours | Medium | Availability and freshness established |
| Home sample collection | Medium | Explicitly supported or independently verified |
| Ratings and reviews | Optional | Display and reuse permissions established |
| Pharmacy presence | Future | Pharmacy relationship independently established |
| Specific medicine stock | Deferred | Reliable stock source and freshness process required |

Missing information must be represented as unknown, not inferred or fabricated.

## 3. Candidate A — OpenStreetMap

**Official source:** https://www.openstreetmap.org/

**License:** Open Database License (ODbL).

### Potential advantages

- Open geographic data that may be usable without purchasing a commercial places-data subscription.
- Can include mapped healthcare facilities and geographic coordinates.
- Supports a possible low-cost prototype, subject to appropriate data access and infrastructure.

### Limitations and risks

- Kolkata coverage and completeness for clinics, specialties, contact numbers, and opening hours have not yet been measured.
- A mapped healthcare facility is not automatically verified, currently operating, or accepting patients.
- Public OpenStreetMap services have separate usage policies. Public Nominatim must not be treated as an unrestricted bulk-search API.
- Attribution is required. Database reuse and distribution must be assessed under ODbL.

### Official references

- License and attribution: https://www.openstreetmap.org/copyright
- Nominatim usage policy: https://operations.osmfoundation.org/policies/nominatim/

### Validation tasks

1. Examine a representative sample of healthcare facilities across Kolkata localities.
2. Measure how many records have usable names, coordinates, and addresses.
3. Check whether specialty and contact information are present.
4. Determine an appropriate data access and refresh method.
5. Document attribution and license implications.

**Status:** Candidate for evaluation; not approved.

## 4. Candidate B — Open Government Data Platform India

**Official catalog:** https://www.data.gov.in/catalog/hospital-directory-national-health-portal

**Additional resource:** https://www.data.gov.in/resource/national-hospital-directory-geo-code-and-additional-parameters-updated-till-last-month

### Potential advantages

- Government-published healthcare directory resources may provide facility names, locations, categories, contact details, and other hospital information.
- A separate resource describes geographic coordinates and additional parameters.
- The resource page reports an update date of 2 June 2025 for the geocoded directory. This does not, by itself, establish the currentness of every individual record.

### Limitations and risks

- The directory may focus on hospitals rather than providing comprehensive coverage of small clinics.
- Kolkata-specific completeness and the accuracy of individual records remain unverified.
- The available fields and permitted reuse must be checked against the actual downloadable dataset and its applicable license.
- Data availability does not establish that a facility remains operational.

### Validation tasks

1. Download the relevant dataset using the official resource page.
2. Inspect its schema and license.
3. Filter for West Bengal and Kolkata-related locations.
4. Count records with usable coordinates, addresses, and contact information.
5. Check for duplicates, missing values, and stale records.
6. Confirm that public-facing reuse is permitted.

**Status:** Candidate for evaluation; not approved.

## 5. Candidate C — Google Maps Platform Places API

**Official documentation:** https://developers.google.com/maps/documentation/places/web-service

**Pricing:** https://mapsplatform.google.com/intl/en_in/pricing/

**Policies:** https://developers.google.com/maps/documentation/places/web-service/policies

### Potential advantages

- Provides place-search capabilities and structured place information.
- May offer useful location and contact fields for discovery.
- India-specific pricing includes free monthly usage thresholds for eligible API SKUs; the applicable SKU and billing requirements must be checked.

### Limitations and risks

- Free usage is not a guarantee that every feature or future usage level will cost ₹0.
- Billing setup and usage monitoring may be necessary.
- Attribution and display rules apply.
- Places content has caching and storage restrictions, with specific exceptions such as place IDs.
- Provider terms may constrain how returned data is combined, stored, refreshed, or displayed.

### Validation tasks

1. Identify the precise API endpoints and fields required.
2. Verify current India pricing and applicable free usage thresholds.
3. Check billing setup requirements before making requests.
4. Review caching, storage, attribution, and public-facing display restrictions.
5. Determine whether the intended architecture is compatible with the provider's terms.
6. Establish request limits and cost alerts if the provider is adopted.

**Status:** Candidate for evaluation; not approved.

## 6. Comparison Matrix

Scores are intentionally left unassigned until evidence is collected.

| Evaluation criterion | OpenStreetMap | Government directory | Google Places |
|---|---|---|---|
| Kolkata clinic coverage | To validate | To validate | To validate |
| Small-clinic coverage | To validate | To validate | To validate |
| Coordinates | To validate | Resource includes geographic coordinates; completeness to validate | Field availability to validate |
| Specialty data | To validate | To validate | Field availability to validate |
| Phone and opening hours | To validate | To validate | Field availability to validate |
| Ratings and reviews | Not established | Not established | Availability and permitted use to validate |
| Initial cost | Data license is open; service/hosting costs may remain | Download availability and permitted use to verify | SKU-specific pricing and billing to verify |
| Attribution requirements | Required | Check applicable dataset license | Required |
| Persistent storage | Review ODbL obligations | Check dataset license | Subject to provider restrictions |
| Refresh strategy | To design | Depends on dataset updates | Depends on API and provider terms |
| Public launch suitability | Pending review | Pending review | Pending review |

## 7. Kolkata Coverage Validation Method

Before selecting a provider, define a repeatable evaluation sample covering multiple parts of the intended launch area.

Suggested areas for sampling include:

- New Town and Rajarhat
- Salt Lake
- Central Kolkata
- South Kolkata
- North Kolkata

These are proposed sampling areas, not a claim that any candidate has complete coverage there.

For each candidate, record:

- Number of returned healthcare facilities
- Number with usable names and coordinates
- Number with usable addresses
- Number with phone numbers
- Number with specialty information
- Duplicate-record rate
- Number of records that can be independently checked
- Data access and reuse restrictions
- Time and cost required for validation

Do not treat the number of records returned as proof of completeness. Use the same sampling method for each candidate.

## 8. Data Verification and Freshness

ClinicFinder must distinguish between source-provided information and independently verified information.

Each stored record or claim should eventually support:

- Source identifier
- Source URL or reference, where permitted
- Retrieval timestamp
- Verification status
- Last verification timestamp, if verified
- Data freshness status
- Correction history, where appropriate

Unknown or stale information must not be displayed as current.

A source listing a facility does not, by itself, verify that the facility is open, provides a particular specialty, offers home collection, or stocks a particular medicine.

## 9. Provider Decision Rules

A provider can be approved only after:

1. Kolkata coverage has been evaluated.
2. Required fields and their availability have been confirmed.
3. Applicable licenses and terms have been reviewed.
4. Pricing and usage limits have been checked.
5. Storage, caching, and attribution rules have been documented.
6. A practical refresh and correction process has been defined.
7. The proposed integration has been checked against the intended public-facing use.

If no candidate satisfies the requirements within the available budget, document the limitations and defer real-data integration rather than inventing a source or promising unsupported functionality.

## 10. Current Decision

**Provider selection: Pending.**

No live clinic data provider has been approved for ClinicFinder.

The current frontend remains a demonstration using fictional records. The backend health endpoint verifies service availability only and does not perform clinic discovery.

### Next actions

- [ ] Inspect the official government directory resource and its license.
- [ ] Evaluate a representative OpenStreetMap sample for Kolkata.
- [ ] Identify the Google Places fields and applicable pricing for the intended use.
- [ ] Complete the comparison matrix with evidence.
- [ ] Record the provider decision and rationale.
- [ ] Define the provider adapter only after the decision is documented.

### Decision record

| Item | Status |
|---|---|
| Launch geography | Kolkata, West Bengal |
| Budget | ₹0 for the initial prototype |
| Data provider | Undecided |
| Real clinic search | Not implemented |
| Pharmacy presence | Deferred pending verification |
| Specific medicine stock | Deferred |
| Appointment booking | Deferred |

---

## References

1. OpenStreetMap, Copyright and License: https://www.openstreetmap.org/copyright
2. OpenStreetMap Foundation, Nominatim Usage Policy: https://operations.osmfoundation.org/policies/nominatim/
3. Open Government Data Platform India, Hospital Directory: https://www.data.gov.in/catalog/hospital-directory-national-health-portal
4. Open Government Data Platform India, Geocoded Hospital Directory: https://www.data.gov.in/resource/national-hospital-directory-geo-code-and-additional-parameters-updated-till-last-month
5. Google Maps Platform, Places API policies: https://developers.google.com/maps/documentation/places/web-service/policies
6. Google Maps Platform, India pricing: https://mapsplatform.google.com/intl/en_in/pricing/

**Note:** This document records initial research, not legal advice or proof of complete coverage. Recheck provider documentation and terms before implementation and public launch.



Dataset inspected: hospital_directory.csv



Total records: 30,273



West Bengal records: 1,164



Kolkata district records: 416



Kolkata records with usable coordinates: 0



Kolkata records with specialty information: 20



Decision: not sufficient as a standalone source for radius-based clinic discovery