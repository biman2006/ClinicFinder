import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.integrations.provider import ClinicDataProvider, ProviderError
from backend.integrations.osm import address_status, extract_osm_identity, osm_address_parts
from backend.schemas.directory import DirectoryBranchInput, DirectoryBranchRecord
from backend.schemas.provider import ClinicListing, ClinicSearchParams

logger = logging.getLogger(__name__)


class DirectoryStorageError(ProviderError):
    code = "DIRECTORY_UNAVAILABLE"


class ClinicDirectory:
    """Small local store for administrator-reviewed branch records."""

    def __init__(self, path: str | Path, *, initialize: bool = True) -> None:
        self.path = Path(path)
        if initialize:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS clinic_branches (
                    id TEXT PRIMARY KEY,
                    facility_name TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    facility_type TEXT NOT NULL,
                    address TEXT NOT NULL,
                    locality TEXT,
                    city TEXT,
                    postal_code TEXT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    phone TEXT,
                    website TEXT,
                    field_sources TEXT NOT NULL,
                    field_evidence TEXT NOT NULL DEFAULT '{}',
                    verification_method TEXT,
                    operating_status TEXT NOT NULL,
                    status TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    verified_at TEXT,
                    last_checked_at TEXT,
                    last_updated_at TEXT NOT NULL,
                    source_type TEXT,
                    source_id INTEGER,
                    source_data TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(clinic_branches)")
            }
            migrations = {
                "field_evidence": "ALTER TABLE clinic_branches ADD COLUMN field_evidence TEXT NOT NULL DEFAULT '{}'",
                "verification_method": "ALTER TABLE clinic_branches ADD COLUMN verification_method TEXT",
                "last_checked_at": "ALTER TABLE clinic_branches ADD COLUMN last_checked_at TEXT",
                "source_type": "ALTER TABLE clinic_branches ADD COLUMN source_type TEXT",
                "source_id": "ALTER TABLE clinic_branches ADD COLUMN source_id INTEGER",
                "source_data": "ALTER TABLE clinic_branches ADD COLUMN source_data TEXT NOT NULL DEFAULT '{}'",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_clinic_branches_source "
                "ON clinic_branches(source_type, source_id) "
                "WHERE source_type IS NOT NULL AND source_id IS NOT NULL"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS clinic_branch_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add(self, data: DirectoryBranchInput) -> DirectoryBranchRecord:
        now = _utc_now()
        record = DirectoryBranchRecord(
            id=str(uuid4()),
            **data.model_dump(),
            status="pending",
            verification_status="pending",
            last_updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO clinic_branches
                (id, facility_name, branch_name, facility_type, address,
                 locality, city, postal_code, latitude, longitude, phone,
                 website, field_sources, field_evidence, verification_method,
                 operating_status, status, verification_status, verified_at,
                 last_checked_at, last_updated_at, source_type, source_id, source_data)
                VALUES
                (:id, :facility_name, :branch_name, :facility_type, :address,
                 :locality, :city, :postal_code, :latitude, :longitude, :phone,
                 :website, :field_sources, :field_evidence, :verification_method,
                 :operating_status, :status, :verification_status, :verified_at,
                 :last_checked_at, :last_updated_at, :source_type, :source_id, :source_data)
                """,
                _row_values(record),
            )
            self._audit(connection, record.id, "created", "admin", record.model_dump_json())
        return record

    def list(self, include_deactivated: bool = False) -> list[DirectoryBranchRecord]:
        query = "SELECT * FROM clinic_branches"
        if not include_deactivated:
            query += " WHERE status != 'deactivated'"
        query += " ORDER BY last_updated_at DESC"
        with self._connect() as connection:
            return [
                _with_current_status(_record_from_row(row))
                for row in connection.execute(query)
            ]

    def update(
        self,
        branch_id: str,
        data: DirectoryBranchInput,
        *,
        verify: bool,
    ) -> DirectoryBranchRecord:
        now = _utc_now()
        values = data.model_dump()
        if verify and not values["field_evidence"]:
            raise ValueError("Verification requires field evidence.")
        status = "verified" if verify else "pending"
        verification_status = status
        verified_at = now if verify else None
        last_checked_at = now if verify else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE clinic_branches
                SET facility_name=:facility_name, branch_name=:branch_name,
                    facility_type=:facility_type, address=:address,
                    locality=:locality, city=:city, postal_code=:postal_code,
                    latitude=:latitude, longitude=:longitude, phone=:phone,
                    website=:website, field_sources=:field_sources,
                    field_evidence=:field_evidence,
                    verification_method=:verification_method,
                    operating_status=:operating_status, status=:status,
                    verification_status=:verification_status,
                    verified_at=:verified_at, last_checked_at=:last_checked_at,
                    last_updated_at=:last_updated_at
                WHERE id=:id
                """,
                {
                    **values,
                    "id": branch_id,
                    "field_sources": json.dumps(values["field_sources"]),
                    "field_evidence": json.dumps(values["field_evidence"]),
                    "status": status,
                    "verification_status": verification_status,
                    "verified_at": _serialize(verified_at),
                    "last_checked_at": _serialize(last_checked_at),
                    "last_updated_at": _serialize(now),
                },
            )
            if cursor.rowcount == 0:
                raise KeyError(branch_id)
            row = connection.execute(
                "SELECT * FROM clinic_branches WHERE id=?", (branch_id,)
            ).fetchone()
            self._audit(connection, branch_id, "updated", "admin", json.dumps(values))
        return _with_current_status(_record_from_row(row))

    def deactivate(self, branch_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE clinic_branches
                SET status='deactivated', last_updated_at=?
                WHERE id=?
                """,
                (_serialize(_utc_now()), branch_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(branch_id)
            self._audit(connection, branch_id, "deactivated", "admin", "{}")

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        branch_id: str,
        action: str,
        actor: str,
        details: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO clinic_branch_audit
            (branch_id, action, actor, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (branch_id, action, actor, details, _serialize(_utc_now())),
        )

    def audit(self, branch_id: str) -> list[dict[str, str]]:
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT action, actor, details, created_at
                    FROM clinic_branch_audit
                    WHERE branch_id=?
                    ORDER BY created_at ASC
                    """,
                    (branch_id,),
                )
            ]

    def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        results: list[ClinicListing] = []
        counts = {
            "records": 0,
            "status_eligible": 0,
            "outside_radius": 0,
            "accepted": 0,
        }
        for record in self.list():
            counts["records"] += 1
            record = _with_current_status(record)
            osm_identity = extract_osm_identity(
                record.source_type,
                record.source_id,
                record.field_evidence,
                record.source_data,
            )
            is_imported = osm_identity is not None
            if record.status == "deactivated" or (
                not is_imported
                and (record.verification_status != "verified" or record.status != "verified")
            ):
                continue
            counts["status_eligible"] += 1
            distance = _distance_km(
                params.latitude, params.longitude, record.latitude, record.longitude
            )
            if distance > params.radius_km:
                counts["outside_radius"] += 1
                continue
            address_parts = osm_address_parts(record.source_data) if is_imported else {}
            address = address_parts.get("address") or record.address
            if (
                is_imported
                and not address_parts.get("address")
                and address
                and address.strip() == (address_parts.get("postal_code") or "")
            ):
                address = None
            locality = address_parts.get("locality") or record.locality
            district = address_parts.get("district") or record.district
            city = address_parts.get("city") or record.city
            postal_code = address_parts.get("postal_code") or record.postal_code
            status_parts = (
                address_parts
                if is_imported
                else {
                    "address": address,
                    "full_address": address,
                    "locality": locality,
                    "district": district,
                    "city": city,
                    "postal_code": postal_code,
                }
            )
            results.append(
                ClinicListing(
                    clinic_id=record.id,
                    name=_display_name(record.facility_name, record.branch_name),
                    facility_type=record.facility_type,
                    address=address,
                    locality=locality,
                    district=district,
                    city=city,
                    postal_code=postal_code,
                    address_status=address_status(status_parts),
                    latitude=record.latitude,
                    longitude=record.longitude,
                    phone=record.phone,
                    website=record.website,
                    distance_km=distance,
                    operating_status=record.operating_status,
                    data_sources=(
                        ["OpenStreetMap bulk import"]
                        if is_imported
                        else ["ClinicFinder directory"]
                    ),
                    source_data=record.source_data,
                    field_sources=record.field_sources,
                    field_evidence=record.field_evidence,
                    verification_method=record.verification_method,
                    last_checked_at=record.last_checked_at,
                    last_verified_at=record.verified_at,
                    last_updated_at=record.last_updated_at,
                    source_type=osm_identity[0] if osm_identity else "directory",
                    source_id=osm_identity[1] if osm_identity else None,
                    verification_status="unverified" if is_imported else "verified",
                )
            )
            counts["accepted"] += 1
        logger.info(
            "Directory clinic search candidate counts",
            extra={"candidate_counts": counts},
        )
        return results

    def upsert_imported(
        self, data: DirectoryBranchInput
    ) -> tuple[DirectoryBranchRecord, str]:
        """Insert or refresh one OSM record without changing verified records.

        The ``protected_verified`` outcome is also counted as a skipped
        duplicate by the importer for backward-compatible reporting.
        """
        if data.source_type is None or data.source_id is None:
            raise ValueError("Imported records require a stable OSM source identity.")
        now = _utc_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM clinic_branches WHERE source_type=? AND source_id=?",
                (data.source_type, data.source_id),
            ).fetchone()
            if row is not None:
                existing = _record_from_row(row)
                if existing.verification_status == "verified" or existing.status == "verified":
                    return existing, "protected_verified"
                values = _row_values(
                    DirectoryBranchRecord(
                        id=existing.id,
                        **data.model_dump(),
                        status="pending",
                        verification_status="pending",
                        last_updated_at=now,
                    )
                )
                connection.execute(
                    """
                    UPDATE clinic_branches SET facility_name=:facility_name,
                    branch_name=:branch_name, facility_type=:facility_type,
                    address=:address, locality=:locality, city=:city,
                    postal_code=:postal_code, latitude=:latitude, longitude=:longitude,
                    phone=:phone, website=:website, field_sources=:field_sources,
                    field_evidence=:field_evidence, verification_method=:verification_method,
                    operating_status=:operating_status, last_updated_at=:last_updated_at,
                    source_data=:source_data
                    WHERE id=:id
                    """,
                    values,
                )
                self._audit(connection, existing.id, "import_updated", "osm-import", json.dumps(values))
                return _record_from_row(
                    connection.execute(
                        "SELECT * FROM clinic_branches WHERE id=?", (existing.id,)
                    ).fetchone()
                ), "updated"

            normalized_name = _normalize(f"{data.facility_name} {data.branch_name}")
            possible_duplicate = connection.execute(
                """
                SELECT * FROM clinic_branches
                WHERE status != 'deactivated'
                AND lower(replace(replace(facility_name || ' ' || branch_name, ' ', ''), '-', '')) = ?
                """,
                (normalized_name.replace(" ", ""),),
            ).fetchone()
            if possible_duplicate is not None:
                existing = _record_from_row(possible_duplicate)
                if existing.verification_status == "verified" or existing.status == "verified":
                    return existing, "protected_verified"

        return self.add(data), "imported"


class DirectoryClinicProvider(ClinicDataProvider):
    def __init__(self, directory: ClinicDirectory) -> None:
        self.directory = directory

    async def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        try:
            return self.directory.search(params)
        except (OSError, sqlite3.Error) as exc:
            logger.exception("Clinic directory search failed")
            raise DirectoryStorageError("The clinic directory could not be read.") from exc


def _display_name(facility_name: str, branch_name: str) -> str:
    if _normalize(facility_name) == _normalize(branch_name):
        return facility_name
    return f"{facility_name} - {branch_name}"


def _row_values(record: DirectoryBranchRecord) -> dict[str, Any]:
    values = record.model_dump()
    values["field_sources"] = json.dumps(values["field_sources"])
    values["field_evidence"] = json.dumps(values["field_evidence"])
    values["source_data"] = json.dumps(values["source_data"])
    for key in ("verified_at", "last_checked_at", "last_updated_at"):
        values[key] = _serialize(values[key])
    return values


def _record_from_row(row: sqlite3.Row) -> DirectoryBranchRecord:
    values = dict(row)
    values["field_sources"] = json.loads(values["field_sources"])
    values["field_evidence"] = json.loads(values["field_evidence"] or "{}")
    values["source_data"] = json.loads(values["source_data"] or "{}")
    for key in ("verified_at", "last_checked_at", "last_updated_at"):
        values[key] = datetime.fromisoformat(values[key]) if values[key] else None
    return DirectoryBranchRecord(**values)


def _with_current_status(record: DirectoryBranchRecord) -> DirectoryBranchRecord:
    if (
        record.status == "verified"
        and record.last_checked_at is not None
        and record.last_checked_at < _utc_now() - timedelta(days=_stale_days())
    ):
        return record.model_copy(update={"status": "stale", "verification_status": "stale"})
    return record


def _stale_days() -> int:
    from backend.core.config import ProviderSettings

    return ProviderSettings.from_environment().directory_stale_after_days


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _distance_km(
    origin_latitude: float, origin_longitude: float, latitude: float, longitude: float
) -> float:
    latitude_delta = radians(latitude - origin_latitude)
    longitude_delta = radians(longitude - origin_longitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(origin_latitude))
        * cos(radians(latitude))
        * sin(longitude_delta / 2) ** 2
    )
    return round(6371.0088 * 2 * asin(sqrt(haversine)), 3)
