# API Contract Draft

Base path: `/api/v1`. Exact schemas are proposals until confirmed.

## GET `/clinics/search`

The current provider integration exposes a coordinate-based evaluation endpoint.
It does not geocode text locations and does not accept symptom text.

Query parameters:

- `latitude`: number from -90 to 90
- `longitude`: number from -180 to 180
- `radius_km`: number greater than 0 and no greater than 50

The response is:

```json
{
  "items": [
    {
      "clinic_id": null,
      "name": "source-provided clinic name",
      "facility_type": "clinic",
      "address": null,
      "locality": null,
      "city": null,
      "postal_code": null,
      "address_status": "unknown",
      "latitude": null,
      "longitude": null,
      "phone": null,
      "website": null,
      "distance_km": null,
      "rating": null,
      "opening_status": "unknown",
      "operating_status": "unknown",
      "services": [],
      "doctors": [],
      "match_reasons": [],
      "data_sources": ["OpenStreetMap"],
      "source_data": {},
      "last_verified_at": null,
      "source_type": "node",
      "source_id": 123,
      "verification_status": "unverified"
    }
  ],
  "result_status": "complete",
  "source_status": {
    "overpass": "ok",
    "directory": "ok"
  }
}
```

`result_status` is `complete` when all configured sources succeeded,
`partial` when at least one source returned results while another source
failed, and `no_matches` when the configured sources completed but no eligible
branch matched the radius. `source_status` reports `ok`, `unavailable`,
`invalid_response`, or `error` per source. A successful empty directory is
not treated as a provider failure.

OpenStreetMap/Overpass is supplementary. If it times out, returns HTTP 429 or
504, has a transport failure, or returns malformed data, verified directory
matches are still returned. SQLite failures are reported as a directory
source error and are never relabelled as Overpass failures. HTTP 503 is
returned only when every configured source fails; that response includes
`source_status` when available.

The response combines the OpenStreetMap adapter and the local directory. OSM
results remain `unverified`. Directory results are returned publicly only
after an authenticated administrator marks the branch `verified`; manually
added records remain `pending` until then. `field_sources`,
`last_updated_at`, and `operating_status` are populated only when stored by
the directory workflow. The directory uses actual stored branch coordinates,
not brand-name or locality assumptions.

Invalid query parameters return HTTP 422. If one source fails and another
returns results, the successful results are returned. Provider availability failures return
HTTP 503 and invalid provider responses return HTTP 502 with a safe `error`
object. Listings remain unverified and missing source fields remain unknown. Directory
records expose field evidence, verification method, and last-checked time;
verified records become `stale` after `CLINIC_DIRECTORY_STALE_AFTER_DAYS`
(180 by default) and are excluded from public search until re-verified.

## Authenticated clinic-directory administration

These endpoints are not public write APIs. They require
`Authorization: Bearer <CLINIC_ADMIN_TOKEN>` and are intended for an
authorized administrator behind an operationally protected deployment:

- `GET /admin/clinic-directory` - review pending, verified, or deactivated records.
- `POST /admin/clinic-directory` - add a branch as `pending`.
- `PUT /admin/clinic-directory/{id}?verify=true|false` - update a record; only
  `verify=true` changes it to `verified` and records the verification time.
- `POST /admin/clinic-directory/{id}/deactivate` - deactivate a record without
  deleting its history.
- `GET /admin/clinic-directory/{id}/audit` - review authenticated administrative
  create, update, and deactivation events.

Each record stores stable internal identity, facility/branch name, type,
coordinates, address/contact fields, per-field sources and evidence, verification
method/status, verification date, last-checked time, operating status, and
last-updated time. Verification requires non-empty field evidence. The default
SQLite path is `backend/data/clinic_directory.sqlite3` and can be changed with
`CLINIC_DIRECTORY_PATH`. Records must be re-checked and re-verified by an
administrator when their source becomes stale; deactivation is preferred over
destructive deletion.

## GET `/locations/search`

The location-resolution endpoint accepts one user-submitted area or address
query. It is called only when the user submits the search form; it is not an
autocomplete endpoint.

Query parameter:

- `query`: trimmed text between 2 and 200 characters

Successful response:

```json
{
  "items": [
    {
      "display_name": "New Town, Kolkata, West Bengal, India",
      "latitude": 22.58,
      "longitude": 88.48,
      "precision": "approximate",
      "osm_type": "relation",
      "osm_id": 123,
      "address_context": {
        "city": "Kolkata",
        "state": "West Bengal",
        "country": "India"
      }
    }
  ]
}
```

The frontend must show all returned matches and require the user to select a
match when more than one is returned. It must not silently choose an
unrelated location. The selected coordinates represent an approximate area
location, not the user's exact position, and are then passed to
`GET /clinics/search`.

The backend normalizes whitespace and case for cache keys and recognizes only
the documented Kolkata aliases `New Town`, `Newtown`, `Biswa Bangla`, `Biswa
Bangla Gate`, `Salt Lake`, `Bidhannagar`, and `Sector V`. These aliases expand
into scoped Nominatim queries; the
Biswa Bangla aliases remain landmark queries and are never converted into
invented locality coordinates. Successful responses, including empty results,
are cached for the lifetime of the geocoder instance. External requests remain
one-shot, application-rate-limited, and are not autocomplete or bulk requests.

No matches return an empty `items` collection. Invalid input returns HTTP 422,
provider availability failures return HTTP 503, and invalid provider
responses return HTTP 502.

## GET `/locations/suggestions`

This local-catalogue endpoint does not contact Nominatim. The frontend loads
the small Kolkata catalogue once, then filters it locally while the user types.
Each item includes a display name, administrative context, coordinates,
OpenStreetMap source identity, and approximate precision. The catalogue is
maintained separately from provider search and is not exhaustive; users can
submit any other location through `/locations/search`.

## POST `/search/clinics`
Request example:
```json
{
  "location": {
    "type": "text",
    "value": "user-provided location"
  },
  "query": {
    "type": "symptom_or_condition",
    "value": "user-provided search text"
  },
  "radius_km": 5,
  "filters": {
    "specialties": [],
    "open_now": false,
    "home_collection": "any"
  }
}
```

For a location coordinate request, use a separately validated coordinate shape and require appropriate permission in the client. Do not accept arbitrary unbounded radius values.

Response shape:
```json
{
  "items": [
    {
      "clinic_id": "internal-id-or-null-for-provider-only-result",
      "name": "source-provided clinic name",
      "address": null,
      "distance_km": null,
      "rating": null,
      "opening_status": "unknown",
      "services": [],
      "doctors": [],
      "match_reasons": [],
      "data_sources": [],
      "last_verified_at": null
    }
  ],
  "query_interpretation": {
    "candidate_specialties": [],
    "disclaimer": "This search is informational and does not diagnose a condition."
  },
  "next_page_token": null
}
```

The example deliberately uses unknown/null values where data is not established. Never fill those fields with fabricated data. `address_status`
is `incomplete` when the only address component is a postal code; clients must
not present that value as a complete street address. `source_data` retains the
raw provider tags for traceability and is not a verification claim.

For coordinate-bearing listings, `distance_km` is calculated with geographic
distance from the requested coordinates. Listings without coordinates or
outside the requested radius are excluded from the response, even if the
provider returned them.

## GET `/clinics/{clinic_id}`
Returns normalized clinic details, source/freshness metadata, and services.

## Error response proposal
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed.",
    "request_id": "generated-request-id"
  }
}
```

## Later appointment endpoints
- `GET /doctors/{doctor_id}/slots?date=YYYY-MM-DD`
- `POST /appointments`
- `GET /appointments/{appointment_id}`
- `POST /appointments/{appointment_id}/cancel`

Before these endpoints are implemented, define authentication, authorization, patient data minimization, slot ownership, concurrency, confirmation semantics, cancellation policy, and audit requirements.
