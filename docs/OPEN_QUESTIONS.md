# Open Questions — Outstanding Decisions

## Confirmed decisions
- [x] Product goal: public-facing service.
- [x] Initial geography: Kolkata, West Bengal, India.
- [x] Initial platform: responsive web app.
- [x] Appointment booking: later phase.
- [x] Medicine scope: both pharmacy presence and specific medicine stock.
- [ ] Clinic-data provider: undecided; must be chosen after terms/cost/coverage evaluation.

## Product and launch
- [ ] Which languages are required at launch (e.g. English, Bengali, Hindi)?
- [ ] Is device geolocation required in the first MVP, or is typed location enough?
- [ ] What launch boundary counts as “Kolkata” for search and distance calculations?
- [ ] Who will own support, listing corrections, and abuse reports after public launch?

## Data sources and verification — release blocker
- [ ] Which provider/source will supply place listings, geocoding, ratings/reviews, and opening hours?
- [ ] What are the provider's current terms, pricing, attribution, caching/storage limits, and quotas?
- [ ] Will clinics be contacted/onboarded to verify doctors, services, home collection, pharmacy presence, and hours?
- [ ] How often will each changeable claim be refreshed, and what happens when it expires?
- [ ] What source will provide specific medicine stock, and how frequently can it update? Without a reliable source, stock must be labelled unavailable as a feature or omitted—not guessed.
- [ ] Are external ratings/reviews permitted for display and retention under the selected source's terms?

## Symptoms and search
- [ ] Which initial symptom/condition-to-specialty mappings are in scope, and who reviews them?
- [ ] Will users enter free text, choose from a curated list, or both?
- [ ] What reviewed emergency/urgent-care message will be shown for the launch area?
- [ ] Confirm the default that symptom search text is not persisted.

## Booking (deferred)
- [ ] Will clinic staff manage slots, an external scheduling provider supply them, or clinics manually confirm requests?
- [ ] Is patient account creation required?
- [ ] What minimal booking data is required?
- [ ] Cancellation/rescheduling rules, notifications, timezone, and confirmation semantics?

## Engineering and operations
- [ ] Hosting provider and budget?
- [ ] Expected traffic and uptime needs?
- [ ] Is PostgreSQL acceptable, and is PostGIS needed for the chosen geographic queries?
- [ ] Authentication/admin access model for clinic verification?
- [ ] Privacy notice, data retention/deletion, incident response and backup/restore procedure?
- [ ] Who will review compliance and provider terms before public launch?
