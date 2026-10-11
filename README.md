# Clinic Discovery Platform

Public-facing responsive website planned for Kolkata, West Bengal. The clinic data provider remains undecided. Appointment booking is deferred. Medicine scope includes pharmacy presence and specific medicine stock, but stock display is blocked until a reliable data source/update process is selected.

## Documentation
Start with `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/OPEN_QUESTIONS.md`, and `docs/IMPLEMENTATION_ROADMAP.md`.

## Current implementation step
A minimal FastAPI health endpoint and pytest test are included in `backend/`. This is a scaffold, not a complete application. No database, frontend, real clinic data, external provider, login, or booking is included yet.

## Run backend locally
From the repository root, use Python 3.11+ (or a compatible supported Python version):

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/health` and `http://127.0.0.1:8000/docs`. In a second terminal with the same environment activated, run `python -m pytest`.

## Run frontend locally

The frontend is plain HTML, CSS and JavaScript; it does not use `npm start`.
Start a static web server from the repository root in a second terminal:

```bash
python -m http.server 5500 --directory frontend
```

Then open `http://127.0.0.1:5500`. Keep the FastAPI server running on port
`8000`, because the frontend checks `GET http://127.0.0.1:8000/health` and
calls `GET /clinics/search` for live coordinate-based searches. Opening
`frontend/index.html` directly with a
`file://` URL is not the supported setup.

The frontend API base URL is configured in
`frontend/config.js` through `window.CLINICFINDER_CONFIG.apiBaseUrl`. Change
that value to the deployed FastAPI origin without adding secrets to the file.
The UI now resolves a submitted area/address through the backend
`GET /locations/search` endpoint. Nominatim is called only once per submitted
search, never for autocomplete. Ambiguous matches must be selected explicitly,
and returned coordinates are approximate area coordinates. Configure the
Nominatim endpoint, timeout, and minimum request interval with
`CLINIC_GEOCODING_NOMINATIM_ENDPOINT`,
`CLINIC_GEOCODING_TIMEOUT_SECONDS`, and
`CLINIC_GEOCODING_MIN_INTERVAL_SECONDS`. The public Nominatim service requires
an identifying User-Agent, attribution, ODbL consideration, and a maximum of
one request per second; review its current policy before public use.

The symptom/specialty and home-collection fields remain visible but are not
sent to the current clinic-search endpoint.

Do not use invented clinic data in a public release. Confirm provider terms, privacy/security, data verification, and operational responsibilities before launch.

## Provider foundation evaluation

The backend includes an internal provider adapter and an OpenStreetMap/Overpass
implementation in `backend/integrations/`. The coordinate-based evaluation
endpoint is `GET /clinics/search` with `latitude`, `longitude`, and
`radius_km` query parameters. The frontend resolves text locations through the
separate geocoding endpoint before calling this coordinate-based route.
Provider selection, verification workflows and public launch approval remain
pending.
Overpass results are unverified
listings, not proof that a clinic is operating or that its details are current.

The endpoint and HTTP/query timeout can be configured with
`CLINIC_PROVIDER_OVERPASS_ENDPOINT` and `CLINIC_PROVIDER_TIMEOUT_SECONDS`.
Tests use mocked HTTP responses and do not access the internet:

```bash
python -m pytest
```

OpenStreetMap data requires attribution and has ODbL obligations. Review the
current OpenStreetMap/Overpass usage and licensing terms before public use;
public Overpass instances do not provide production availability guarantees.
Missing contacts, addresses, specialties and other fields remain unknown.
