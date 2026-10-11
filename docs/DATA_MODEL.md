# Data Model Proposal

This is a conceptual model; it is not a migration file. Confirm booking, verification, and provider choices before implementation.

## Clinic
- `id`: UUID primary key
- `name`: required
- `address`: nullable until verified
- `latitude`, `longitude`: nullable numeric values
- `phone`, `website`: nullable
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
