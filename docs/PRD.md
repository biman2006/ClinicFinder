# Product Requirements Document (PRD)
**Product:** Clinic Discovery & Service Information Platform  
**Launch area:** Kolkata, West Bengal, India  
**Platform:** Public-facing responsive website  
**Status:** Draft; clinic-data source remains undecided  
**Version:** 0.2

## 1. Confirmed decisions
- The intended product is public-facing, not only a portfolio demo.
- Initial launch geography is Kolkata, West Bengal.
- Initial platform is a responsive website.
- Clinic-data source is not yet selected.
- Appointment booking is a later phase, not the first MVP.
- “Medicine” includes both pharmacy presence and availability of specific medicines; neither should be displayed as current fact without an appropriate source and freshness indicator.

## 2. Problem and goal
Help people discover nearby clinics using a location and symptoms or a known disease/condition, understand which services may be relevant, and compare trustworthy information. Later, allow appointment booking only where the platform or an authorized integration has real availability data.

## 3. User roles (proposed; confirm details)
- Visitor: searches and views public listings.
- Patient account holder: potentially manages bookings in a later phase.
- Clinic staff: potentially maintains clinic-owned details and schedules after verification/onboarding.
- Platform administrator: reviews claims, reports, corrections and access.

## 4. MVP scope: discovery website
- Accept a location via text search; device geolocation may be added only with clear permission and a fallback.
- Accept symptoms and/or a known condition as search text.
- Map search text to relevant specialties/services using a transparent, reviewed mapping. This is not diagnosis.
- Search supported clinics within a configurable area/radius once data-source coverage and terms are decided.
- Display clinic name, address, distance, contact details, hours, specialties/services and rating/review information only when supplied by an approved source.
- Show doctors and doctor schedules only when independently sourced or clinic-verified.
- Show pharmacy presence separately from specific medicine stock.
- Show home sample collection and diagnostic-test availability as `available`, `unavailable`, or `unknown`, with source and last-checked time where possible.
- Explain ranking criteria and data limitations.
- Handle no results, missing data, stale data, invalid input, provider failure and loading states.
- Provide appropriate messaging that the product is not an emergency service or a diagnostic tool.

## 5. Data quality requirements
- Unknown is not the same as unavailable.
- A map/place listing does not prove a doctor works there, a service is offered, a medicine is in stock, or an appointment slot is open.
- Do not invent clinic facts, doctors, schedules, ratings, feedback, test availability or medicine inventory.
- Record provenance and freshness for changeable claims.
- Do not copy reviews or retain provider data unless the selected provider's terms permit it.
- Public launch is blocked until data source, usage rights, coverage, update policy, privacy notice, and correction/complaint process are confirmed.

## 6. Later phase: appointment booking
- Determine whether clinics manage slots in the platform, an external scheduling system supplies them, or requests require manual confirmation.
- Let users select a clinic, doctor, date and real slot/request workflow.
- Recheck availability atomically before confirming a slot.
- Show `request_submitted` when the clinic has not yet confirmed; do not call it a confirmed booking prematurely.
- Define account requirements, minimal patient information, timezone, cancellation/rescheduling rules, notifications, audit events and access control before implementation.

## 7. Medicine and pharmacy feature boundary
Two distinct features are requested:
1. **Pharmacy presence:** whether the clinic has an associated/on-site pharmacy or a linked pharmacy.
2. **Specific medicine stock:** whether a named medicine is currently in stock at a specific pharmacy.

These require different data models and sources. Specific stock changes rapidly and must include source and checked time. Do not provide medication recommendations, prescribe, or imply that stock information guarantees suitability for a patient. Pharmacy presence can be included earlier only when verified; live stock is deferred until a pharmacy data partner or reliable update workflow is chosen.

## 8. Non-functional requirements for public use
- Privacy-by-design; collect the minimum necessary data and do not persist symptom queries by default unless a documented need and lawful basis are established.
- HTTPS, secure secret handling, input validation, access controls for any admin/clinic management, rate limiting, and audit logging for sensitive changes.
- Accessible, responsive UI with keyboard support and clear error states.
- Data provenance, refresh/expiry policy, correction mechanism and provider attribution.
- Backups, monitoring, error handling, and deployment/security review before public launch.
- Confirm applicable Indian privacy, healthcare, consumer, and third-party provider requirements with qualified advice before launch.

## 9. Out of scope for first MVP
- Appointment booking and payment processing.
- Diagnosis, prescriptions, medicine recommendations, or emergency triage.
- Claims that a clinic is medically “best” without a transparent, validated basis.
- Live specific-medicine inventory until a suitable source/update mechanism is chosen.
- Medical-record storage or telemedicine.

## 10. Acceptance criteria for MVP
- User can search by location and symptom/known condition.
- Results come from the configured approved source or are explicitly labelled demo data during development.
- Specialty matching and ranking criteria are documented and tested.
- Missing fields are shown as unknown rather than fabricated or assumed negative.
- Source/freshness metadata is surfaced for important changeable facts where available.
- Automated tests cover validation, matching, radius boundaries, no results, stale/missing claims and provider failure.
- Public release is not enabled until data rights, privacy/security, correction workflows and operations are reviewed.
