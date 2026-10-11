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
      "address": null,
      "latitude": null,
      "longitude": null,
      "phone": null,
      "website": null,
      "distance_km": null,
      "rating": null,
      "opening_status": "unknown",
      "services": [],
      "doctors": [],
      "match_reasons": [],
      "data_sources": ["OpenStreetMap"],
      "last_verified_at": null,
      "source_type": "node",
      "source_id": 123,
      "verification_status": "unverified"
    }
  ]
}
```

Invalid query parameters return HTTP 422. Provider availability failures return
HTTP 503 and invalid provider responses return HTTP 502 with a safe `error`
object. Listings remain unverified and missing source fields remain unknown.

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
      "osm_id": 123
    }
  ]
}
```

The frontend must show all returned matches and require the user to select a
match when more than one is returned. It must not silently choose an
unrelated location. The selected coordinates represent an approximate area
location, not the user's exact position, and are then passed to
`GET /clinics/search`.

No matches return an empty `items` collection. Invalid input returns HTTP 422,
provider availability failures return HTTP 503, and invalid provider
responses return HTTP 502.

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

The example deliberately uses unknown/null values where data is not established. Never fill those fields with fabricated data.

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
