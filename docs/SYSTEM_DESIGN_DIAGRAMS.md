# ClinicFinder --- System Design Diagrams

**Status:** Architecture draft\
**Initial area:** Kolkata, West Bengal\
**Frontend:** HTML, CSS, JavaScript initially; React may be introduced
later\
**Backend:** FastAPI\
**Data provider:** Not yet selected\
**Appointment booking:** Future phase

> These diagrams describe the intended design, not a fully implemented
> system. Placeholder clinic records must never be presented as real
> data.

## 1. System context

``` mermaid
flowchart LR
    VISITOR["Website visitor / patient"]
    STAFF["Clinic staff / verifier (future)"]
    ADMIN["Platform administrator (future)"]
    WEB["ClinicFinder website"]
    API["FastAPI backend"]
    DATA["Selected clinic/place provider (undecided)"]
    DB[("Platform database (PostgreSQL proposed)")]

    VISITOR --> WEB
    WEB <-->|"HTTPS / JSON"| API
    API <--> DATA
    API <--> DB
    STAFF -. "future: manage verified data" .-> API
    ADMIN -. "future: review listings" .-> API
```

## 2. High-level application architecture

``` mermaid
flowchart TD
    USER["Website visitor"]
    FE["Frontend: HTML, CSS, JavaScript"]
    API["FastAPI REST API"]
    SCHEMA["Pydantic validation"]
    SEARCH["Clinic search service"]
    SPECIALTY["Reviewed specialty mapping"]
    GEO["Location resolution and distance filtering"]
    ADAPTER["Clinic provider adapter"]
    EXT["External provider (undecided)"]
    DB[("Platform data: PostgreSQL proposed")]
    VERIFY["Source, verification and freshness metadata"]
    RANK["Filtering and explainable ranking"]
    RESULT["Normalized JSON response"]
    BOOK["Booking module (future)"]

    USER --> FE
    FE <-->|"HTTPS / JSON"| API
    API --> SCHEMA --> SEARCH
    SEARCH --> SPECIALTY
    SEARCH --> GEO
    SEARCH --> ADAPTER
    ADAPTER <--> EXT
    SEARCH <--> DB
    ADAPTER --> VERIFY
    DB --> VERIFY
    SPECIALTY --> RANK
    GEO --> RANK
    VERIFY --> RANK --> RESULT --> API
    BOOK -. "future" .-> DB
```

## 3. Clinic search request sequence

``` mermaid
sequenceDiagram
    actor User as Visitor
    participant UI as Frontend
    participant API as FastAPI
    participant Search as Search service
    participant Provider as Location/provider adapter
    participant DB as Platform database

    User->>UI: Enter location and search query
    UI->>API: POST /api/v1/search/clinics
    API->>API: Validate request
    alt Invalid request
        API-->>UI: Structured validation error
    else Valid request
        API->>Search: Execute search
        Search->>Search: Map query to reviewed specialties
        Search->>Provider: Resolve location / retrieve candidates
        Provider-->>Search: Candidate data or provider error
        Search->>DB: Retrieve platform-owned claims
        DB-->>Search: Clinic and verification data
        Search->>Search: Filter, rank, attach provenance
        Search-->>API: Normalized results
        API-->>UI: JSON response
        UI-->>User: Display results and match reasons
    end
```

## 4. Data provenance and verification

``` mermaid
flowchart TD
    SOURCE["Incoming listing or claim"]
    NORMALIZE["Normalize to internal format"]
    RECORD["Record source and reference"]
    VERIFY{"Verification policy satisfied?"}
    VERIFIED["Mark verified with timestamp"]
    UNKNOWN["Mark unverified / unknown"]
    FRESH{"Within freshness policy?"}
    DISPLAY["Display with source and last-checked time"]
    QUALIFY["Display as stale, unverified or unknown"]
    CORRECT["Correction / re-verification"]

    SOURCE --> NORMALIZE --> RECORD --> VERIFY
    VERIFY -->|Yes| VERIFIED --> FRESH
    VERIFY -->|No| UNKNOWN --> QUALIFY
    FRESH -->|Yes| DISPLAY
    FRESH -->|No| QUALIFY
    QUALIFY --> CORRECT --> VERIFY
```

A map listing does not prove doctor affiliation, home collection,
pharmacy presence, current medicine stock, or bookable appointment
availability.

## 5. Conceptual entity relationship diagram

This is a conceptual model, not a finalized schema or migration. Booking
entities are future-phase concepts.

``` mermaid
erDiagram
    CLINIC ||--o{ CLINIC_SOURCE_RECORD : has
    CLINIC ||--o{ CLINIC_SPECIALTY : offers
    SPECIALTY ||--o{ CLINIC_SPECIALTY : classifies
    CLINIC ||--o{ DOCTOR : associated_with
    CLINIC ||--o{ SERVICE_CLAIM : has
    DOCTOR ||--o{ DOCTOR_SCHEDULE : has
    DOCTOR ||--o{ APPOINTMENT : receives
    CLINIC ||--o{ APPOINTMENT : hosts

    CLINIC {
        uuid id PK
        string name
        string address
        decimal latitude
        decimal longitude
        string listing_status
    }
    CLINIC_SOURCE_RECORD {
        uuid id PK
        uuid clinic_id FK
        string source_type
        string source_reference
        datetime last_verified_at
    }
    SPECIALTY {
        uuid id PK
        string canonical_name
    }
    CLINIC_SPECIALTY {
        uuid clinic_id FK
        uuid specialty_id FK
        string verification_status
    }
    DOCTOR {
        uuid id PK
        uuid clinic_id FK
        string name
        string verification_status
    }
    SERVICE_CLAIM {
        uuid id PK
        uuid clinic_id FK
        string claim_type
        string status
        datetime verified_at
    }
    DOCTOR_SCHEDULE {
        uuid id PK
        uuid doctor_id FK
        datetime starts_at
        datetime ends_at
    }
    APPOINTMENT {
        uuid id PK
        uuid doctor_id FK
        uuid clinic_id FK
        string status
    }
```

### Data model notes

-   Unknown is different from unavailable.
-   Store source and last verification time for changeable claims.
-   Doctor affiliations and schedules require a trustworthy source.
-   Medicine inventory needs a separate model for medicine identity,
    pharmacy/source, stock status and last-checked time.
-   Booking entities and constraints must be designed before booking is
    implemented.

## 6. Future appointment booking sequence

``` mermaid
sequenceDiagram
    actor Patient
    participant UI as Frontend
    participant API as FastAPI
    participant Booking as Booking service
    participant DB as Database
    participant Clinic as Scheduling owner

    Patient->>UI: Choose clinic, doctor, date and slot
    UI->>API: Request available slots
    API->>Booking: Find eligible slots
    Booking->>Clinic: Check schedule, if integrated
    Clinic-->>Booking: Availability response
    Booking-->>API: Available slots
    API-->>UI: Display slots and booking terms
    Patient->>UI: Submit booking request
    UI->>API: POST appointment request
    API->>Booking: Validate and recheck slot
    Booking->>DB: Transactionally reserve or record slot
    alt Slot available
        DB-->>Booking: Persisted booking
        Booking-->>API: Actual booking status
        API-->>UI: Confirmed or pending status
    else Slot unavailable
        DB-->>Booking: Conflict
        Booking-->>API: Slot unavailable
        API-->>UI: Ask patient to select another slot
    end
```

A booking must be labelled `confirmed` only when the scheduling workflow
actually confirms it. If clinic approval is required, show a pending
status.

## 7. Logical deployment view

Hosting is not selected; this is a vendor-neutral production view.

``` mermaid
flowchart TD
    BROWSER["User browser"]
    FEHOST["Frontend static hosting"]
    HTTPS["HTTPS API endpoint"]
    APP["FastAPI hosting"]
    DB[("PostgreSQL")]
    SECRET["Environment secrets / secret manager"]
    PROVIDER["Selected external provider"]
    OBS["Logs, monitoring and alerts"]
    BACKUP["Database backups and recovery"]

    BROWSER --> FEHOST --> HTTPS --> APP
    APP <--> DB
    APP <--> PROVIDER
    SECRET -. "configuration" .-> APP
    APP --> OBS
    DB --> BACKUP
```

## 8. Error and resilience flow

``` mermaid
flowchart TD
    REQUEST["Incoming search request"]
    VALID{"Request valid?"}
    PROVIDER{"Provider responds?"}
    DATA{"Usable data available?"}
    RESULTS["Return results with provenance"]
    VALIDATION["Return validation error"]
    DEGRADED["Return permitted partial results with limitations"]
    EMPTY["Return empty results and helpful message"]
    LOG["Record safe operational metadata / request ID"]

    REQUEST --> VALID
    VALID -->|No| VALIDATION
    VALID -->|Yes| PROVIDER
    PROVIDER -->|No| DEGRADED
    PROVIDER -->|Yes| DATA
    DATA -->|Yes| RESULTS
    DATA -->|No| EMPTY
    VALIDATION --> LOG
    DEGRADED --> LOG
    EMPTY --> LOG
    RESULTS --> LOG
```

Do not log sensitive symptom text unnecessarily. Provider failures must
never cause fabricated clinic data.

## 9. Intended repository structure

This is a target structure. Add modules only when the corresponding
implementation phase begins.

``` text
clinic_platform_blueprint/
├── .github/
│   └── copilot-instructions.md
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── api/search.py
│   ├── schemas/search.py
│   ├── services/
│   │   ├── clinic_search.py
│   │   ├── specialty_mapping.py
│   │   └── ranking.py
│   ├── integrations/clinic_provider.py
│   ├── models/
│   ├── repositories/
│   ├── core/config.py
│   └── tests/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── API_CONTRACT.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   ├── OPEN_QUESTIONS.md
│   └── SYSTEM_DESIGN_DIAGRAMS.md
├── .env.example
├── .gitignore
└── README.md
```

## 10. Decisions still open

1.  External clinic/place/geocoding provider, pricing, coverage,
    attribution and data-retention terms.
2.  How clinics, doctors, opening hours, pharmacy presence, home
    collection and medicine stock will be verified and refreshed.
3.  Initial specialty mappings and their review process.
4.  Database and hosting plan based on budget and expected traffic.
5.  Appointment slot ownership, confirmation semantics, cancellation
    rules and notifications.

## 11. How to use this document

Save this file as `docs/SYSTEM_DESIGN_DIAGRAMS.md`. GitHub can render
Mermaid diagrams embedded in Markdown, allowing diagrams to live beside
the written architecture.

Keep `ARCHITECTURE.md` for component responsibilities and design
decisions; use this file as its visual companion. Update both when an
architecture decision changes.
