# Data Model Proposal

This is a conceptual model; it is not a migration file. Confirm booking, verification, and provider choices before implementation.

## ClinicFinder directory branch

The MVP uses SQLite because the repository had no existing persistence layer.
The `clinic_branches` table stores a stable internal UUID, official facility
and branch names, facility type (`clinic`, `diagnostic_centre`, or `hospital`),
complete address fields, coordinates, phone/website when confirmed, a JSON
map of field-level sources, operating status, `pending | verified |
deactivated` lifecycle, verification timestamp, and last-updated timestamp.
Manually entered rows participate in public search only after verification.
Offline OpenStreetMap import rows may participate as explicitly unverified
source listings, while remaining pending and never being presented as
administrator-verified or operational.

The correction process is: update the source-backed fields, keep the record
pending, confirm the actual branch and coordinates, then verify it again.
Records that cannot be re-confirmed are deactivated rather than silently
retained.

## Clinic
- `id`: UUID primary key
- `name`: required
- `address`: nullable until verified
- `locality`, `city`, `postal_code`: nullable provider address components
- `address_status`: `complete | incomplete | unknown`; a postal-code-only
  value is incomplete
- `latitude`, `longitude`: nullable numeric values
- `phone`, `website`: nullable
- `source_data`: provider payload fields retained for traceability
- `listing_status`: `draft | pending_verification | verified | suspended`
- `created_at`, `updated_at`

## DataClaim
Represents one changeable claim such as “home sample collection offered”.
- `id`, `clinic_id`
- `claim_type`: `home_collection | diagnostic_test | pharmacy_service | opening_hours | doctor_affiliation`
- `claim_value`: typed value or normalized JSON
- `status`: `available | unavailable | unknown`
- `source_type`: `provider | clinic_submitted | admin_verified | user_reported`
- `source_reference`: nullable
- `verified_at`, `expires_at`
- `created_at`, `updated_at`

## Doctor
- `id`, `clinic_id`, `name`
- `specialty_id`: nullable until verified
- `verification_status`
- `source_type`, `verified_at`

## Specialty
- `id`, `canonical_name`, `description`
- optional synonym mapping table with review/version metadata

## Later booking entities
`User`, `AppointmentSlot`, `Appointment`, and `BookingEvent` should be designed only after deciding whether slots are managed by clinic staff, an external scheduling system, or a manual request workflow.

## Data integrity rules
- Unknown is different from unavailable.
- A doctor should not be associated with a clinic without a source or verification path.
- A slot must belong to a doctor/clinic and have an explicit timezone.
- Confirmed bookings must be protected against double-booking at database level.
- External provider IDs must not be treated as internal primary keys.
