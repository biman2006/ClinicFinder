from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.clinics import router as clinics_router
from backend.api.locations import router as locations_router

app = FastAPI(
    title="Clinic Discovery API",
    description="Clinic discovery API. Clinic data provider is not yet selected.",
    version="0.1.0",
)

app.include_router(clinics_router)
app.include_router(locations_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return a minimal health status without exposing configuration or secrets."""
    return {"status": "ok", "service": "clinic-discovery-api"}
