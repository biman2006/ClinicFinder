# Implementation Roadmap

**Target:** Public-facing, responsive healthcare discovery web application for Kolkata, West Bengal, India.

**Product scope:** Clinic discovery and healthcare service information. The clinic data provider is undecided. Appointment booking is deferred to a later phase.

**Frontend stack:** HTML5, CSS3, and vanilla JavaScript (ES6+).

**Backend stack:** Python and FastAPI.

---

## Phase 0 — Resolve Launch Blockers

- Keep the clinic data provider undecided until available options are compared against Kolkata coverage, terms of use, pricing, attribution requirements, caching restrictions, and required field availability.
- Decide the initial launch boundary, language requirements, typed location versus device geolocation, and responsibility for verifying and correcting clinic records.
- Define how pharmacy presence will be represented separately from specific medicine stock availability. Do not promise current stock without a reliable source and an established update process.
- Review applicable privacy, security, legal, and provider requirements before public release.
- Record unresolved decisions and explicitly mark them as deferred where appropriate.

**Exit gate:** Open questions are answered or explicitly documented as deferred. The data-source selection process and its justification are documented.

## Phase 1 — Backend Scaffold

- Create a FastAPI application with `GET /health`.
- Add environment-based settings, `.env.example`, `.gitignore`, and a test setup.
- Add at least one pytest test verifying the health endpoint's response.
- Keep the backend minimal.
- Do not add a database, external data provider, symptom AI, authentication, or appointment booking at this stage.

**Exit gate:** The application starts locally, the health endpoint responds correctly, and the health test passes.

## Phase 2 — Frontend Scaffold (HTML, CSS, JavaScript)

- Create a responsive frontend using HTML5, CSS3, and vanilla JavaScript (ES6+).
- Do not use React, Vite, TypeScript, Next.js, or another frontend framework.
- Maintain the existing project structure and reuse the existing frontend files where possible:
  - `frontend/index.html`
  - `frontend/style.css`
  - `frontend/script.js`
- Build the clinic search interface with:
  - User-entered location.
  - Symptoms, known disease, or medical specialty.
  - Search radius.
  - Home sample collection availability.
- Implement client-side form validation and clear UI states:
  - Initial state.
  - Loading state.
  - Successful results state.
  - No-results state.
  - Error state.
- Use mock clinic records for interface testing only. Clearly label every mock record as **"Demo Data — Not Verified"**.
- Connect the frontend to the local FastAPI `GET /health` endpoint using the JavaScript Fetch API.
- Display backend connection status based on the actual request result.
- Handle network failures, unsuccessful HTTP responses, and invalid response data without crashing.
- Configure FastAPI CORS only as needed for the chosen local frontend development origin.
- Keep the frontend accessible, responsive, and usable on desktop and mobile browsers.
- Do not implement real clinic search, live provider integration, or appointment booking in this phase.
- Do not represent mock records as real or verified healthcare information.

**Exit gate:** The frontend runs locally, works on desktop and mobile, supports the required UI states, labels demo records clearly, and successfully communicates with the local backend health endpoint. Backend connection failures are displayed accurately.

## Phase 3 — Provider Evaluation and Decision

- Compare permitted data sources using a documented checklist covering:
  - Kolkata coverage and geographic accuracy.
  - Clinic and healthcare service fields.
  - Ratings and review usage terms.
  - Opening hours and availability of relevant service information.
  - Attribution requirements.
  - Pricing and rate limits.
  - Caching and storage restrictions.
  - Data freshness and reliability.
  - Commercial and public-facing usage permissions.
- Document the comparison and choose a provider only after reviewing the applicable terms.
- Define an internal provider adapter interface before implementing provider-specific integration.
- Do not assume that a provider supplies fields or grants permissions that have not been verified.

**Exit gate:** The selected provider, permitted fields, attribution rules, usage restrictions, and refresh requirements are documented. If no suitable provider is approved, record the decision and defer integration.

## Phase 4 — Internal Schema and Discovery Logic

- Define clinic, specialty, and verification or claim models after the data shape and source requirements are agreed.
- Add database migrations only when the storage design has been decided.
- Implement reviewed specialty mapping, location and radius filtering, and explainable result ranking.
- Track data provenance, verification status, and freshness where applicable.
- Define how missing, unknown, conflicting, and expired information is represented.
- Add tests for missing or expired claims, invalid inputs, location filtering, ranking behavior, and provider failures.
- Use synthetic test data where real provider integration is not yet available.

**Exit gate:** Deterministic search works against synthetic test data. Ranking behavior is testable, and the application makes no unsupported claims about clinics, services, or availability.

## Phase 5 — Real Data Integration and Verification

- Integrate the approved provider through the documented adapter interface.
- Use only data permitted by the provider's applicable terms.
- Implement a clinic verification and correction workflow.
- Display unknown, unverified, conflicting, or stale information accurately.
- Apply the agreed data refresh policy and attribution requirements.
- Test provider failures, incomplete responses, duplicate records, and stale data.

**Exit gate:** Permitted source data flows through the system end to end. Attribution, refresh behavior, and correction handling work as documented.

## Phase 6 — Pharmacy and Medicine Data

- Add pharmacy presence only when the relationship between the clinic and pharmacy has been verified.
- Treat pharmacy presence and specific medicine stock as separate data fields and capabilities.
- Defer specific medicine stock until a reliable data partner or accountable update workflow is established.
- Define medicine identifiers, stock freshness thresholds, source attribution, and stale-data behavior before displaying stock information.
- Never present expired, unknown, or unverified stock information as current availability.

**Exit gate:** Pharmacy relationships are appropriately verified. Medicine stock is displayed only when its source and freshness satisfy the documented requirements; otherwise, stock remains unknown or the feature is deferred.

## Phase 7 — Public Pilot Readiness

- Add appropriate rate limiting, monitoring, error reporting, backups, and security testing.
- Implement privacy notices and accessible user interfaces.
- Review secret management, environment configuration, dependency security, and deployment configuration.
- Establish a process for clinic corrections, user support, and data-quality incidents.
- Test the application with approved data before public launch.
- Document known limitations and operational responsibilities.

**Exit gate:** The product owner reviews and approves security, privacy, provider terms, data quality, operational readiness, and the public pilot plan.

## Phase 8 — Appointment Booking (Later Phase)

- Decide who owns appointment slots and how clinics will be onboarded.
- Define authentication, authorization, clinic roles, and schedule management.
- Implement timezone-aware availability and appointment slots.
- Use appropriate transaction handling or locking to prevent conflicting bookings.
- Implement idempotency, appointment status transitions, cancellations, and notifications.
- Define whether a booking is pending, requested, confirmed, or rejected by the clinic.
- Ensure confirmation reflects the clinic's actual approval rather than a successful request submission.
- Test simultaneous booking attempts, retries, cancellation flows, and failure recovery.

**Exit gate:** Double-booking is prevented under tested concurrent conditions, and users receive an accurate appointment status based on the actual booking workflow.

---

## Definition of Done for Every Phase

1. Automated tests pass for the implemented functionality.
2. Manual verification steps and their results are recorded.
3. Documentation, assumptions, and known limitations are updated.
4. Secrets and sensitive credentials are not committed to version control.
5. Changes are reviewed and committed in small, understandable units.
6. The phase exit gate is verified before starting the next phase.
7. Unimplemented features are clearly distinguished from working functionality.