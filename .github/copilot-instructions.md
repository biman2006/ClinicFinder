# Copilot Instructions

- Follow `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/API_CONTRACT.md`.
- Do not invent requirements or external clinic, doctor, schedule, rating, review, medicine, or home-collection facts.
- Represent missing information as unknown/null, not as false/unavailable.
- Keep external provider integrations behind adapters.
- Never expose API keys in frontend code or commit secrets.
- Validate inputs with Pydantic and use SQLAlchemy parameterized ORM operations.
- Add tests for each behavior and failure path.
- Do not store symptom queries unless explicitly required and documented.
- Do not implement diagnosis, prescriptions, emergency triage, or medicine recommendations.
- Keep changes small and avoid unrelated refactors.
- Explain assumptions and unresolved decisions before implementation.
