# System Architecture
**Product:** Public-facing clinic discovery website for Kolkata, West Bengal  
**Status:** Draft proposal; data provider is undecided. Appointment booking is deferred.

## 1. Architecture principles
- Start with a modular monolith.
- Keep third-party place discovery separate from verified clinic-owned claims.
- Do not invent missing clinic, doctor, schedule, review, service or stock information.
- Track source, verification state and freshness for changeable facts.
- No diagnosis or treatment recommendation; symptom-to-specialty matching is informational.
- Do not select a provider until its terms, pricing, attribution, storage restrictions and Kolkata coverage are assessed.

## 2. Proposed component diagram
```text
Responsive website (React + Vite + TypeScript; proposed)
              | HTTPS / JSON
              v
FastAPI backend (Python; proposed)
  ├── Search API and request validation
  ├── Symptom/condition-to-specialty mapping
  ├── Clinic filtering and explainable ranking
  ├── Clinic/service claim query service
  ├── Provider adapter interface (provider TBD)
  └── Later: authentication, clinic admin, booking
              |
              v
PostgreSQL (proposed; PostGIS optional)
  ├── internal clinic and specialty records
  ├── data claims + source/freshness metadata
  ├── pharmacy association records
  └── later: users, schedules, slots, appointments, audit events
```

## 3. Modules
- `api/`: HTTP routes and Pydantic request/response schemas.
- `services/`: specialty mapping, filtering, ranking and claim logic.
- `repositories/`: database access.
- `models/`: SQLAlchemy entities.
- `schemas/`: API contracts.
- `integrations/`: provider adapters only; do not spread provider-specific payloads through the codebase. The current evaluation foundation contains an OpenStreetMap/Overpass adapter with normalized, unverified listings; it is not yet a selected production provider.
- `core/`: settings, logging, error handling and security.
- `tests/`: unit and API integration tests.

## 4. Discovery flow
1. Validate location and search text.
2. Resolve text location to coordinates using the selected provider, or accept device coordinates with permission.
3. Match symptoms/known condition to candidate specialties using a reviewed, versioned mapping. Do not diagnose.
4. Query the selected clinic/place data source and internal verified records.
5. Normalize results and attach source/freshness/verification metadata.
6. Apply distance and relevant-service filters.
7. Rank with explainable criteria such as distance, supported service match, opening status when current hours are available, and source confidence. Do not treat star ratings alone as clinical quality.
8. Return `match_reasons`, `data_sources`, `last_verified_at`, and unknown values explicitly.

## 5. Provider selection gate
The source is undecided. Evaluate candidates against: Kolkata coverage, permitted use of clinic/place details, review/rating terms, storage/caching rules, attribution, price/quotas, reliability, geocoding, opening-hours freshness, and whether the source has any clinic-specific service data. A general place provider is not assumed to supply doctor affiliations, home collection, medicine stock, or bookable slots.

The provider foundation accepts validated coordinate/radius searches and keeps
provider-specific request and response handling behind the adapter boundary.
OpenStreetMap element type and ID are retained for stable source identity;
missing fields remain unknown and all returned listings are marked unverified.
The adapter uses one bounded request without automatic retries and converts
timeouts, transport failures, HTTP failures and malformed responses into safe
structured provider errors.

Text location resolution is isolated in a separate Nominatim geocoding adapter
and `/locations/search` route. It performs one request per submitted search,
uses a descriptive User-Agent, enforces a one-request-per-second application
interval, and does not implement autocomplete or automatic retries. Multiple
matches are returned to the client for explicit user selection. Coordinates
are labelled approximate and are not treated as the user's exact location.

## 6. Proposed initial API
All routes provisional; use `/api/v1` once versioning is introduced.
- `GET /health`
- `POST /search/clinics`
- `GET /clinics/{clinic_id}`
- `GET /clinics/{clinic_id}/services`
- `GET /clinics/{clinic_id}/doctors` only when sourced/verified
- Pharmacy presence and specific medicine stock endpoints are not finalized; avoid designing them until data source/update rules are chosen.

## 7. Data entities (conceptual)
- `Clinic`: internal ID, name, address, coordinates, contact, listing status.
- `ClinicSourceRecord`: source, external reference, fetched/verified times, attribution.
- `Specialty`: canonical name and reviewed synonyms/mappings.
- `ClinicSpecialty`: clinic/specialty relationship, source and verification status.
- `DataClaim`: claim type/value/status/source/verified time/expiry.
- `Doctor`: clinic relationship, name, specialty and verification metadata.
- `Pharmacy`: distinct pharmacy entity; associated clinic relationship is explicit and verified.
- `MedicineStockClaim` (deferred): pharmacy, medicine identifier/name, stock status, source, checked time and expiry. A stale claim must not be presented as current.
- Later only: `User`, `DoctorSchedule`, `AppointmentSlot`, `Appointment`, `BookingEvent`, `ConsentRecord`.

## 8. Ranking and medical safety
Use hard eligibility filters before ranking. Explain why a listing appears. Symptom mapping is not diagnosis and must not claim the clinic can treat a condition unless a relevant service is verified. For urgent/life-threatening symptoms, display reviewed local emergency guidance; do not attempt to triage with an unvalidated model.

## 9. Privacy/security/operations
- Do not persist search symptoms by default; document any later retention purpose and consent/legal basis.
- Keep API keys server-side; use environment variables locally and a secret manager in deployment.
- Validate input, limit request sizes/rates, configure production CORS narrowly, use HTTPS, and enforce authorization for any clinic/admin write path.
- Avoid putting symptoms or patient details in logs.
- Provide a correction/reporting channel and define how listings are removed or updated.
- Before public launch, review applicable Indian legal/privacy obligations and selected provider terms with qualified advice.

## 10. Appointment booking — later architecture
Clinic staff or a trusted integration must own slot availability. Use a transaction plus row lock/unique constraint to prevent double-booking. Include explicit timezone, idempotency, booking state transitions, audit history, cancellation policy, notification retries and authorization. If clinic approval is pending, return a request-submitted state rather than false confirmation.
