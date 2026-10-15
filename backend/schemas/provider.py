from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ClinicSearchParams(BaseModel):
    """Validated coordinate search input for provider adapters."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=50)


class ClinicListing(BaseModel):
    """Provider-neutral listing; provider data is not verification."""

    clinic_id: str | None = None
    name: str
    facility_type: Literal["clinic", "diagnostic_centre", "hospital", "unknown"] = "clinic"
    address: str | None = None
    locality: str | None = None
    district: str | None = None
    city: str | None = None
    postal_code: str | None = None
    address_status: Literal["complete", "incomplete", "unknown"] = "unknown"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = None
    website: str | None = None
    distance_km: float | None = None
    rating: None = None
    opening_status: Literal["unknown"] = "unknown"
    operating_status: Literal["operating", "closed", "unknown"] = "unknown"
    services: list[str] = Field(default_factory=list)
    doctors: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    source_data: dict[str, str] = Field(default_factory=dict)
    last_verified_at: datetime | None = None
    source_type: Literal["node", "way", "relation", "directory"]
    source_id: int | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)
    field_evidence: dict[str, str] = Field(default_factory=dict)
    verification_method: str | None = None
    last_checked_at: datetime | None = None
    last_updated_at: datetime | None = None
    verification_status: Literal["unverified", "pending", "verified", "stale"] = "unverified"


class ProviderResults(BaseModel):
    items: list[ClinicListing]
    result_status: Literal["complete", "partial", "no_matches"] = "complete"
    source_status: dict[str, Literal["ok", "unavailable", "invalid_response", "error"]] = Field(
        default_factory=dict
    )


class LocationSearchParams(BaseModel):
    query: str = Field(min_length=2, max_length=200)


class GeocodedLocation(BaseModel):
    display_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precision: Literal["approximate"] = "approximate"
    osm_type: str | None = None
    osm_id: int | None = None
    address_context: dict[str, str] = Field(default_factory=dict)


class GeocodingResults(BaseModel):
    items: list[GeocodedLocation]
