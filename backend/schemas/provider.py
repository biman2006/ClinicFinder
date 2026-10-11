from typing import Literal

from pydantic import BaseModel, Field


class ClinicSearchParams(BaseModel):
    """Validated coordinate search input for provider adapters."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=50)


class ClinicListing(BaseModel):
    """Provider-neutral listing; provider data is not verification."""

    clinic_id: None = None
    name: str
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = None
    website: str | None = None
    distance_km: float | None = None
    rating: None = None
    opening_status: Literal["unknown"] = "unknown"
    services: list[str] = Field(default_factory=list)
    doctors: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    last_verified_at: None = None
    source_type: Literal["node", "way"]
    source_id: int
    verification_status: Literal["unverified"] = "unverified"


class ProviderResults(BaseModel):
    items: list[ClinicListing]


class LocationSearchParams(BaseModel):
    query: str = Field(min_length=2, max_length=200)


class GeocodedLocation(BaseModel):
    display_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precision: Literal["approximate"] = "approximate"
    osm_type: str | None = None
    osm_id: int | None = None


class GeocodingResults(BaseModel):
    items: list[GeocodedLocation]
