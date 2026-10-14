# Clinic Discovery Platform

Public-facing responsive website planned for Kolkata, West Bengal. The clinic data provider remains undecided. Appointment booking is deferred. Medicine scope includes pharmacy presence and specific medicine stock, but stock display is blocked until a reliable data source/update process is selected.

## Documentation
Start with `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/OPEN_QUESTIONS.md`, and `docs/IMPLEMENTATION_ROADMAP.md`.

## Current implementation step
The FastAPI backend exposes coordinate-based clinic search backed by a
composite of the OpenStreetMap/Overpass evaluation adapter and an empty by
default, SQLite-backed directory of administrator-verified branches, plus
Nominatim location resolution. OSM listings are explicitly unverified.
Directory records are pending until authenticated administrator review; no
clinic record is fabricated from a provider brand name.

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

If port 5500 is already occupied or returns an empty response, use another
local port, for example:

```bash
python -m http.server 5501 --directory frontend
```

Then open `http://127.0.0.1:5501`. Ports 5500 and 5501 are allowed by the
development API CORS configuration.

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

The location field also loads a small local Kolkata suggestion catalogue once
from `GET /locations/suggestions`; filtering while typing is performed in the
browser and never calls Nominatim. The catalogue currently covers New Town,
Newtown, Biswa Bangla Gate, Salt Lake/Bidhannagar, and Sector V using stored
OpenStreetMap identities and coordinates captured through the existing
Nominatim integration. It is not an exhaustive Kolkata locality directory.

The symptom/specialty and home-collection fields remain visible but are not
sent to the current clinic-search endpoint.

Do not use invented clinic data in a public release. Confirm provider terms, privacy/security, data verification, and operational responsibilities before launch.

## Provider foundation evaluation

The backend includes internal provider adapters and an OpenStreetMap/Overpass
implementation in `backend/integrations/`. The coordinate-based endpoint is
`GET /clinics/search` with `latitude`, `longitude`, and `radius_km` query
parameters. The frontend resolves text locations through the separate
geocoding endpoint before calling this route.
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
The adapter preserves raw OSM tags in `source_data`, separates locality/city/
postal-code fields, labels postal-code-only addresses as incomplete, calculates
distance with geographic coordinates, filters out-of-radius results, and
deduplicates repeated OSM element identities. Doctor names, consultation
hours, ratings and patient reviews remain unavailable until a verified source
and data model are approved; the frontend displays them as not available rather
than inventing values.

Overpass is supplementary to the local directory. Search responses include
`result_status` and per-source `source_status` metadata. A successful local
search is returned even if Overpass is unavailable; the frontend does not show
an outage message when usable listings are present. A retry is appropriate
when all sources fail or when no local match exists and the supplementary
Overpass source was unavailable. The implementation does not retry public
Overpass requests automatically or cache transient failures.

## Offline OpenStreetMap bulk import

The repeatable importer is `backend/scripts/import_osm.py`. It never downloads
data and is not called by application startup or clinic search. Obtain a
`.osm.pbf` extract separately from an authorized source and run from the
repository root:

For a practical Kolkata-area source, use the BBBike Extract Service or HOT
Export Tool to request a custom `.osm.pbf` for the configured box. Alternatively
download the Eastern India regional extract and clip it before importing. The
`osmium` command uses `LEFT,BOTTOM,RIGHT,TOP` order (west,south,east,north);
the importer boundary uses `south,west,north,east`:

```powershell
osmium extract `
  --bbox=88.05,22.25,88.75,23.05 `
  --strategy=complete_ways `
  eastern-zone.osm.pbf `
  -o kolkata.osm.pbf
```

`complete_ways` makes the clipped file retain every node referenced by an
included way, including nodes just outside the box. This is required because
the importer resolves way node locations to calculate its existing way
centroid. PyOsmium's `locations=True` does not make a large regional PBF seek
directly to the boundary; it still scans the input stream, so configuring a
boundary alone does not avoid reading the whole file. Do not use a
reference-incomplete/simple extract for this importer unless its way node
locations have been preserved.

If the `osmium` command-line tool is unavailable, use the bundled PyOsmium
extractor instead. It streams the input and writes a reference-complete PBF
without loading all objects into Python memory:

```powershell
python -m backend.scripts.extract_osm_bbox `
  --input "backend/data/eastern-zone-261011.osm.pbf" `
  --output "backend/data/kolkata.osm.pbf" `
  --bbox "88.05,22.25,88.75,23.05"
```

The script preserves IDs, tags, object types, and nodes referenced by selected
ways. It retains relations that directly reference selected nodes, ways, or
previously selected relations. Relations whose geometry is only implied by
unsupported or indirect members may not be included; the clinic importer
already reports relations without reliable geometry rather than inventing a
location.

```bash
python -m backend.scripts.import_osm `
  --input "data/kolkata.osm.pbf" `
  --database "backend/data/clinic_directory.sqlite3" `
  --boundary "22.25,88.05,23.05,88.75" `
  --category clinic `
  --report "data/last-osm-import.json"
```

Progress is logged every 30 seconds by default; use
`--progress-interval-seconds` to change that interval. Use `--dry-run` to
inspect counts without changing SQLite. The default
boundary is a configurable working bounding box around the Kolkata
metropolitan target area (south, west, north, east); it is not an official
Kolkata city, district, or KMDA boundary and does not claim complete coverage.
Use an approved boundary for production. Features require a name, supported
healthcare tag, and reliable coordinates. Node, way, and relation identities
are preserved; relation geometry that cannot be resolved by pyosmium is
reported and skipped. `clinic`/`doctors` map to clinic, `hospital` to
hospital, and `diagnostic_centre`/`laboratory` to diagnostic centre. Missing
source fields remain empty or unknown.

Imports are idempotent by OSM element identity, retain raw source tags,
timestamps, field evidence, and audit entries, and never delete records absent
from a later extract. Imported records remain unverified and are not treated
as operating or administrator-confirmed. Matching verified directory records
are preserved and counted as both skipped duplicates and
`protected_verified_records`. The JSON report includes examined features,
eligible healthcare features, imports, updates, duplicate skips, protected
verified records, invalid geometries, category counts, and errors.

Each directory upsert is committed independently. If a later object fails,
earlier records remain valid; inspect the report/errors and safely rerun the
same PBF. Stable `(source_type, source_id)` identities make that recovery
idempotent: existing unverified OSM records are refreshed, while verified
records remain protected. The importer does not delete records absent from a
later extract.

Pass `--category clinic`, `--category hospital`, or
`--category diagnostic_centre` to restrict the import. Reports distinguish all
healthcare features discovered, records matching the selected category,
records eligible for import, and records actually written. Stage counters also
identify category exclusions, out-of-boundary features, missing coordinates,
unnamed features, and conversion errors. Counts before database upsert are
counts of OSM objects, not deduplicated branches; actual duplicate handling is
reported separately. In dry-run mode the actual-write count is zero.

OpenStreetMap data is © OpenStreetMap contributors and is available under the
ODbL. Distributed database extracts must retain required attribution and
comply with ODbL/share-alike obligations. Review current extract-provider,
the PyOsmium (`osmium`) package, and OpenStreetMap licensing terms before publication.

## Directory administration

Set `CLINIC_ADMIN_TOKEN` in the server environment before using the
authenticated `/admin/clinic-directory` endpoints documented in
[`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Set
`CLINIC_DIRECTORY_PATH` to move the SQLite file. Add records only after
confirming the actual facility branch, address, and coordinates from an
authorized source. New records are pending; use the review/update endpoint
with `verify=true` only after confirmation. Deactivate stale or unconfirmed
records rather than deleting their provenance.

The audit and its evidence limits are recorded in
[`docs/SEARCH_AUDIT.md`](docs/SEARCH_AUDIT.md). It does not claim that Apollo,
Jibok, or Suraksha has a branch at every searched location.
Candidate live-source checks and the permitted manual-import workflow are
recorded in [`docs/SOURCE_EVALUATION.md`](docs/SOURCE_EVALUATION.md). No
provider website is scraped without documented permission.
