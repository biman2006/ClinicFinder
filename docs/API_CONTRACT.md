# API Contract Draft

Base path: `/api/v1`. Exact schemas are proposals until confirmed.

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
