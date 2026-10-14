from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


FacilityType = Literal["clinic", "diagnostic_centre", "hospital"]
DirectoryStatus = Literal["pending", "verified", "stale", "deactivated"]


class DirectoryBranchInput(BaseModel):
    facility_name: str = Field(min_length=1, max_length=200)
    branch_name: str = Field(min_length=1, max_length=200)
    facility_type: FacilityType
    address: str = Field(max_length=500)
    locality: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=500)
    field_sources: dict[str, str] = Field(default_factory=dict)
    field_evidence: dict[str, str] = Field(default_factory=dict)
    verification_method: str | None = Field(default=None, max_length=200)
    operating_status: Literal["operating", "closed", "unknown"] = "unknown"
    source_type: Literal["node", "way", "relation"] | None = None
    source_id: int | None = Field(default=None, gt=0)
    source_data: dict[str, str] = Field(default_factory=dict)


class DirectoryBranchRecord(DirectoryBranchInput):
    id: str
    status: DirectoryStatus
    verification_status: Literal["pending", "verified", "stale"] = "pending"
    verified_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_updated_at: datetime
