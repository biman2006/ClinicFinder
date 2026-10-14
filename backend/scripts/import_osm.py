"""Import healthcare features from a locally downloaded OpenStreetMap PBF.

This module deliberately has no network code. The input file must be downloaded
separately and is processed with PyOsmium in a streaming fashion.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from backend.integrations.directory import ClinicDirectory
from backend.integrations.osm import osm_address_parts
from backend.schemas.directory import DirectoryBranchInput

logger = logging.getLogger(__name__)
try:
    import osmium
except ImportError:  # pragma: no cover - exercised by the actionable runtime error
    osmium = None

# This is a deliberately broad working bbox, not a claim that it is the
# official Kolkata Metropolitan Area boundary. Replace it with an approved
# polygon/bbox for production imports.
DEFAULT_BOUNDARY = "22.25,88.05,23.05,88.75"
OSM_SOURCE = "OpenStreetMap bulk import"


@dataclass(frozen=True)
class Boundary:
    south: float
    west: float
    north: float
    east: float

    @classmethod
    def from_text(cls, value: str) -> "Boundary":
        try:
            south, west, north, east = (float(item.strip()) for item in value.split(","))
        except ValueError as exc:
            raise ValueError("Boundary must be south,west,north,east.") from exc
        if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
            raise ValueError("Boundary coordinates are invalid.")
        return cls(south, west, north, east)

    def contains(self, latitude: float, longitude: float) -> bool:
        return self.south <= latitude <= self.north and self.west <= longitude <= self.east


@dataclass
class ImportReport:
    total_features_examined: int = 0
    healthcare_features_found: int = 0
    selected_category: str | None = None
    category_matches: int = 0
    category_excluded: int = 0
    outside_boundary: int = 0
    missing_coordinates: int = 0
    unnamed_features: int = 0
    invalid_features: int = 0
    conversion_errors: int = 0
    records_eligible_for_import: int = 0
    records_imported: int = 0
    updated_records: int = 0
    duplicates_skipped: int = 0
    protected_verified_records: int = 0
    invalid_geometries: int = 0
    category_counts: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_features_examined": self.total_features_examined,
            "healthcare_features_found": self.healthcare_features_found,
            "selected_category": self.selected_category,
            "category_matches": self.category_matches,
            "category_excluded": self.category_excluded,
            "outside_boundary": self.outside_boundary,
            "missing_coordinates": self.missing_coordinates,
            "unnamed_features": self.unnamed_features,
            "invalid_features": self.invalid_features,
            "conversion_errors": self.conversion_errors,
            "records_eligible_for_import": self.records_eligible_for_import,
            "records_imported": self.records_imported,
            "updated_records": self.updated_records,
            "duplicates_skipped": self.duplicates_skipped,
            "protected_verified_records": self.protected_verified_records,
            "invalid_geometries": self.invalid_geometries,
            "category_counts": dict(sorted(self.category_counts.items())),
            "errors": self.errors,
        }


def import_pbf(
    input_path: str | Path,
    directory: ClinicDirectory,
    *,
    boundary: Boundary,
    category: str | None = None,
    dry_run: bool = False,
    progress_interval_seconds: float = 30.0,
) -> ImportReport:
    """Stream a PBF into the directory and return a machine-readable report."""
    if progress_interval_seconds <= 0:
        raise ValueError("Progress interval must be greater than zero.")
    try:
        import osmium
    except ImportError as exc:
        raise RuntimeError(
            "The osmium package is required for PBF imports; install backend/requirements.txt."
        ) from exc

    report = ImportReport(selected_category=category)
    importer = _PbfHandler(
        directory,
        boundary,
        report,
        dry_run,
        category,
        progress_interval_seconds,
    )
    try:
        importer.apply_file(str(input_path), locations=True)
    except OSError as exc:
        raise RuntimeError(f"Could not read OSM PBF: {input_path}") from exc
    importer.log_progress(force=True)
    return report


def import_features(
    features: Any,
    directory: ClinicDirectory,
    *,
    boundary: Boundary,
    category: str | None = None,
    dry_run: bool = False,
) -> ImportReport:
    """Import normalized feature mappings; useful for deterministic tests/tools."""
    report = ImportReport(selected_category=category)
    for feature in features:
        report.total_features_examined += 1
        tags = feature.get("tags") if isinstance(feature, Mapping) else None
        if not isinstance(tags, Mapping) or category_for_tags(tags) is None:
            continue
        report.healthcare_features_found += 1
        feature_category = category_for_tags(tags)
        if category is not None and feature_category != category:
            report.category_excluded += 1
            continue
        report.category_matches += 1
        coordinates = _coordinates(feature)
        if coordinates[0] is None:
            report.invalid_geometries += 1
            report.missing_coordinates += 1
            continue
        if not boundary.contains(*coordinates):
            report.outside_boundary += 1
            continue
        if _tag(tags, "name") is None:
            report.unnamed_features += 1
            continue
        try:
            data = feature_to_directory_input(feature)
            report.records_eligible_for_import += 1
            report.category_counts[data.facility_type] += 1
            if dry_run:
                continue
            _, outcome = directory.upsert_imported(data)
            if outcome == "imported":
                report.records_imported += 1
            elif outcome == "updated":
                report.updated_records += 1
            else:
                report.duplicates_skipped += 1
                if outcome == "protected_verified":
                    report.protected_verified_records += 1
        except (ValueError, TypeError, OSError) as exc:
            report.conversion_errors += 1
            report.errors.append(f"{feature.get('type')}/{feature.get('id')}: {exc}")
    return report


class _PbfHandler(osmium.SimpleHandler if osmium is not None else object):
    def __init__(
        self,
        directory: ClinicDirectory,
        boundary: Boundary,
        report: ImportReport,
        dry_run: bool,
        category: str | None,
        progress_interval_seconds: float = 30.0,
    ) -> None:
        super().__init__()
        self.directory = directory
        self.boundary = boundary
        self.report = report
        self.dry_run = dry_run
        self.category = category
        self.progress_interval_seconds = progress_interval_seconds
        self._started_at = time.monotonic()
        self._last_progress_at = self._started_at

    def node(self, obj: Any) -> None:
        self._handle(obj, "node", _location(obj))

    def way(self, obj: Any) -> None:
        self._handle(obj, "way", _way_location(obj))

    def relation(self, obj: Any) -> None:
        # Relation geometry is not guaranteed by SimpleHandler. Do not invent a
        # centroid; relation records without a reliable location are reported.
        self._handle(obj, "relation", None)

    def _handle(self, obj: Any, source_type: str, location: tuple[float, float] | None) -> None:
        self.report.total_features_examined += 1
        self.log_progress()
        tags = {str(key): str(value) for key, value in obj.tags}
        feature_category = category_for_tags(tags)
        if feature_category is None:
            return
        self.report.healthcare_features_found += 1
        if self.category is not None and feature_category != self.category:
            self.report.category_excluded += 1
            return
        self.report.category_matches += 1
        if location is None:
            self.report.invalid_geometries += 1
            self.report.missing_coordinates += 1
            return
        if not self.boundary.contains(*location):
            self.report.outside_boundary += 1
            return
        if _tag(tags, "name") is None:
            self.report.unnamed_features += 1
            return
        try:
            data = feature_to_directory_input(
                {"type": source_type, "id": int(obj.id), "tags": tags, "lat": location[0], "lon": location[1]}
            )
            self.report.records_eligible_for_import += 1
            self.report.category_counts[data.facility_type] += 1
            if self.dry_run:
                return
            _, outcome = self.directory.upsert_imported(data)
            if outcome == "imported":
                self.report.records_imported += 1
            elif outcome == "updated":
                self.report.updated_records += 1
            else:
                self.report.duplicates_skipped += 1
                if outcome == "protected_verified":
                    self.report.protected_verified_records += 1
        except (ValueError, TypeError, OSError) as exc:
            self.report.conversion_errors += 1
            self.report.errors.append(f"{source_type}/{obj.id}: {exc}")

    def log_progress(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_progress_at < self.progress_interval_seconds:
            return
        elapsed = now - self._started_at
        logger.info(
            "OSM import progress: %d objects processed in %.1f seconds",
            self.report.total_features_examined,
            elapsed,
        )
        self._last_progress_at = now


def feature_to_directory_input(feature: Mapping[str, Any]) -> DirectoryBranchInput:
    """Convert a testable normalized OSM feature mapping to directory input."""
    tags = feature.get("tags")
    if not isinstance(tags, Mapping):
        raise ValueError("OSM feature tags are missing.")
    source_type = feature.get("type")
    source_id = feature.get("id")
    if source_type not in {"node", "way", "relation"} or not isinstance(source_id, int):
        raise ValueError("OSM feature identity is invalid.")
    latitude, longitude = _coordinates(feature)
    if latitude is None or longitude is None:
        raise ValueError("OSM feature has no reliable coordinates.")
    name = _tag(tags, "name")
    category = category_for_tags(tags)
    if not name or category is None:
        raise ValueError("OSM feature is not a named healthcare feature.")
    address_parts = osm_address_parts(tags)
    address = address_parts["address"] or ""
    locality = address_parts["locality"]
    city = address_parts["city"]
    postal_code = address_parts["postal_code"]
    source_id_text = f"osm:{source_type}/{source_id}"
    source_fields = {
        "facility_name": "OpenStreetMap",
        "branch_name": "OpenStreetMap",
        "latitude": "OpenStreetMap",
        "longitude": "OpenStreetMap",
    }
    field_values = {
        "address": address,
        "locality": locality,
        "city": city,
        "postal_code": postal_code,
        "phone": _first_tag(tags, "phone", "contact:phone"),
        "website": _first_tag(tags, "website", "contact:website"),
    }
    for key, value in field_values.items():
        if value:
            source_fields[key] = "OpenStreetMap"
    return DirectoryBranchInput(
        facility_name=name,
        branch_name=_tag(tags, "branch") or name,
        facility_type=category,
        address=address,
        locality=locality,
        city=city,
        postal_code=postal_code,
        latitude=latitude,
        longitude=longitude,
        phone=field_values["phone"],
        website=field_values["website"],
        field_sources=source_fields,
        field_evidence={key: source_id_text for key in source_fields},
        source_type=source_type,
        source_id=source_id,
        source_data={key: value for key, value in tags.items() if value.strip()},
    )


def category_for_tags(tags: Mapping[str, Any]) -> str | None:
    value = (_first_tag(tags, "healthcare", "amenity") or "").casefold()
    if value in {"hospital"}:
        return "hospital"
    if value in {"diagnostic_centre", "diagnostic_center", "laboratory", "lab"}:
        return "diagnostic_centre"
    if value in {"clinic", "doctors", "doctor", "medical_centre", "medical_center"}:
        return "clinic"
    return None


def _coordinates(feature: Mapping[str, Any]) -> tuple[float | None, float | None]:
    latitude = feature.get("lat")
    longitude = feature.get("lon")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        latitude, longitude = float(latitude), float(longitude)
        if (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            return latitude, longitude
    return None, None


def _location(obj: Any) -> tuple[float, float] | None:
    location = getattr(obj, "location", None)
    return _coordinates({"lat": getattr(location, "lat", None), "lon": getattr(location, "lon", None)})


def _way_location(obj: Any) -> tuple[float, float] | None:
    locations = [
        location
        for node in getattr(obj, "nodes", [])
        for location in [_location(node)]
        if location is not None
    ]
    if not locations:
        return None
    return (
        sum(item[0] for item in locations) / len(locations),
        sum(item[1] for item in locations) / len(locations),
    )


def _tag(tags: Mapping[str, Any], key: str) -> str | None:
    value = tags.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _first_tag(tags: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _tag(tags, key)
        if value:
            return value
    return None


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Local .osm.pbf file")
    parser.add_argument("--database", default="backend/data/clinic_directory.sqlite3")
    parser.add_argument("--boundary", default=DEFAULT_BOUNDARY, help="south,west,north,east")
    parser.add_argument(
        "--category",
        choices=("clinic", "hospital", "diagnostic_centre"),
        help="Import only records in this category.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--progress-interval-seconds",
        type=float,
        default=30.0,
        help="Log processed-object progress at this interval (default: 30).",
    )
    parser.add_argument("--report", type=Path, help="Write JSON report to this path")
    args = parser.parse_args()
    report = import_pbf(
        args.input,
        ClinicDirectory(args.database, initialize=not args.dry_run),
        boundary=Boundary.from_text(args.boundary),
        category=args.category,
        dry_run=args.dry_run,
        progress_interval_seconds=args.progress_interval_seconds,
    )
    output = json.dumps(report.as_dict(), indent=2)
    print(output)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
