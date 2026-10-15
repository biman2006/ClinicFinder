from pathlib import Path

import asyncio
import json
import logging

import osmium
import pytest

from backend.integrations.directory import ClinicDirectory, DirectoryClinicProvider
from backend.schemas.directory import DirectoryBranchInput
from backend.schemas.provider import ClinicSearchParams
from backend.scripts.import_osm import (
    Boundary,
    _PbfHandler,
    category_for_tags,
    feature_to_directory_input,
    import_features,
    import_pbf,
)


def feature(
    source_id: int = 10,
    *,
    healthcare: str = "clinic",
    latitude: float = 22.57,
    longitude: float = 88.36,
    name: str = "Example Clinic",
) -> dict[str, object]:
    return {
        "type": "node",
        "id": source_id,
        "lat": latitude,
        "lon": longitude,
        "tags": {
            "name": name,
            "healthcare": healthcare,
            "addr:street": "Park Street",
            "phone": "+91 12345",
        },
    }


@pytest.fixture
def osm_node_fixture() -> dict[str, object]:
    return feature(source_id=99, name="Fixture Clinic")


def test_pbf_handler_reports_progress_without_reading_a_pbf(
    tmp_path: Path,
    osm_node_fixture: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    from types import SimpleNamespace

    report = import_features([], directory, boundary=Boundary.from_text("22,88,23,89"))
    handler = _PbfHandler(
        directory,
        Boundary.from_text("22,88,23,89"),
        report,
        dry_run=True,
        category="clinic",
        progress_interval_seconds=0.001,
    )
    obj = SimpleNamespace(
        id=osm_node_fixture["id"],
        tags=list(osm_node_fixture["tags"].items()),
        location=SimpleNamespace(
            lat=osm_node_fixture["lat"], lon=osm_node_fixture["lon"]
        ),
    )
    with caplog.at_level(logging.INFO):
        handler.node(obj)
        handler.log_progress(force=True)

    assert report.total_features_examined == 1
    assert report.records_eligible_for_import == 1
    assert "1 objects processed" in caplog.text


def test_import_is_idempotent_and_keeps_source_identity(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    first = import_features(
        [feature()], directory, boundary=Boundary.from_text("22,88,23,89")
    )
    second = import_features(
        [feature()], directory, boundary=Boundary.from_text("22,88,23,89")
    )

    assert first.records_imported == 1
    assert second.duplicates_skipped == 0
    assert second.updated_records == 1
    assert len(directory.list(include_deactivated=True)) == 1
    record = directory.list(include_deactivated=True)[0]
    assert record.source_type == "node"
    assert record.source_id == 10
    assert record.source_data["healthcare"] == "clinic"


def test_import_normalization_preserves_district_without_mapping_to_city() -> None:
    data = feature_to_directory_input(
        {
            **feature(),
            "tags": {
                "name": "Repose Clinic and Research Centre",
                "healthcare": "clinic",
                "addr:district": "Kolkata",
                "addr:full": "20/C, Broad Street,(Ballygunge)",
                "addr:postcode": "700019",
            },
        }
    )

    assert data.address == "20/C, Broad Street,(Ballygunge)"
    assert data.district == "Kolkata"
    assert data.locality is None
    assert data.city is None
    assert data.postal_code == "700019"


def test_verified_record_is_not_downgraded_by_reimport(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    import_features([feature()], directory, boundary=Boundary.from_text("22,88,23,89"))
    record = directory.list(include_deactivated=True)[0]
    input_data = DirectoryBranchInput(**record.model_dump(exclude={
        "id", "status", "verification_status", "verified_at", "last_checked_at",
        "last_updated_at", "field_evidence",
    }), field_evidence={"name": "admin confirmation"})
    verified = directory.update(
        record.id,
        input_data,
        verify=True,
    )

    report = import_features(
        [feature(name="Changed OSM Name")],
        directory,
        boundary=Boundary.from_text("22,88,23,89"),
    )

    assert report.duplicates_skipped == 1
    assert directory.list(include_deactivated=True)[0].facility_name == verified.facility_name
    assert directory.list(include_deactivated=True)[0].field_evidence == {
        "name": "admin confirmation"
    }
    assert report.protected_verified_records == 1


def test_import_pbf_fixture_preserves_osm_identity_and_clinic_filter(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "fixture.osm.pbf"
    writer = osmium.SimpleWriter(input_path)
    writer.add_node(
        osmium.osm.mutable.Node(
            id=101,
            location=(88.36, 22.57),
            tags={"name": "Fixture Clinic", "healthcare": "clinic"},
        )
    )
    writer.add_node(
        osmium.osm.mutable.Node(
            id=102,
            location=(88.37, 22.58),
            tags={"name": "Fixture Hospital", "amenity": "hospital"},
        )
    )
    writer.close()

    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    report = import_pbf(
        input_path,
        directory,
        boundary=Boundary.from_text("22,88,23,89"),
        category="clinic",
    )

    assert report.healthcare_features_found == 2
    assert report.category_matches == 1
    assert report.records_imported == 1
    record = directory.list(include_deactivated=True)[0]
    assert (record.source_type, record.source_id) == ("node", 101)
    assert record.verification_status == "pending"


def test_import_boundary_invalid_geometry_categories_and_dry_run(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    features = [
        feature(1, healthcare="hospital"),
        feature(2, healthcare="laboratory", latitude=22.58),
        feature(3, healthcare="doctors", latitude=22.59),
        feature(4, latitude=24.0),
        feature(5, latitude=float("nan")),
    ]
    report = import_features(
        features,
        directory,
        boundary=Boundary.from_text("22.5,88.2,22.7,88.5"),
        dry_run=True,
    )

    assert report.total_features_examined == 5
    assert report.healthcare_features_found == 5
    assert report.category_matches == 5
    assert report.records_eligible_for_import == 3
    assert report.records_imported == 0
    assert report.invalid_geometries == 1
    assert report.missing_coordinates == 1
    assert report.outside_boundary == 1
    assert report.category_counts == {"clinic": 1, "diagnostic_centre": 1, "hospital": 1}
    assert directory.list(include_deactivated=True) == []


@pytest.mark.parametrize(
    "tags",
    [
        {"healthcare": "doctor"},
        {"healthcare": "doctors"},
        {"amenity": "doctors"},
    ],
)
def test_doctor_tags_are_intentionally_imported_as_clinics(
    tags: dict[str, str],
) -> None:
    assert category_for_tags(tags) == "clinic"


@pytest.mark.parametrize(
    ("selected_category", "expected_name"),
    [
        ("clinic", "Clinic"),
        ("hospital", "Hospital"),
        ("diagnostic_centre", "Diagnostic"),
    ],
)
def test_category_filter_imports_only_selected_category(
    tmp_path: Path, selected_category: str, expected_name: str
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    report = import_features(
        [
            feature(1, healthcare="clinic", name="Clinic"),
            feature(2, healthcare="hospital", name="Hospital"),
            feature(3, healthcare="laboratory", name="Diagnostic"),
        ],
        directory,
        boundary=Boundary.from_text("22,88,23,89"),
        category=selected_category,
    )

    assert report.healthcare_features_found == 3
    assert report.category_matches == 1
    assert report.records_eligible_for_import == 1
    assert report.records_imported == 1
    assert [record.facility_name for record in directory.list()] == [expected_name]


def test_dry_run_does_not_modify_existing_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "directory.sqlite3"
    directory = ClinicDirectory(database)
    before = database.read_bytes()

    report = import_features(
        [feature()],
        directory,
        boundary=Boundary.from_text("22,88,23,89"),
        dry_run=True,
    )

    assert report.records_eligible_for_import == 1
    assert report.records_imported == 0
    assert database.read_bytes() == before


def test_report_contains_distinct_category_counts(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    report = import_features(
        [feature(1), feature(2, healthcare="hospital")],
        directory,
        boundary=Boundary.from_text("22,88,23,89"),
        category="clinic",
        dry_run=True,
    )

    payload = report.as_dict()
    assert payload["healthcare_features_found"] == 2
    assert payload["category_matches"] == 1
    assert payload["records_eligible_for_import"] == 1
    assert payload["records_imported"] == 0
    assert json.loads(json.dumps(payload))["selected_category"] == "clinic"


def test_report_exposes_category_and_name_exclusions(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    unnamed = feature(1, name="")
    unnamed["tags"] = {key: value for key, value in unnamed["tags"].items() if key != "name"}
    report = import_features(
        [
            feature(2, healthcare="hospital"),
            unnamed,
            feature(3, latitude=24.0),
        ],
        directory,
        boundary=Boundary.from_text("22.5,88.2,22.7,88.5"),
        category="clinic",
        dry_run=True,
    )

    assert report.healthcare_features_found == 3
    assert report.category_excluded == 1
    assert report.category_matches == 2
    assert report.unnamed_features == 1
    assert report.outside_boundary == 1
    assert report.records_eligible_for_import == 0
    assert report.records_imported == 0


def test_eligible_count_is_per_osm_object_and_write_dedup_is_separate(
    tmp_path: Path,
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    report = import_features(
        [feature(1), feature(1)],
        directory,
        boundary=Boundary.from_text("22,88,23,89"),
    )

    assert report.category_matches == 2
    assert report.records_eligible_for_import == 2
    assert report.records_imported == 1
    assert report.updated_records == 1
    assert report.duplicates_skipped == 0
    assert len(directory.list(include_deactivated=True)) == 1


def test_imported_records_are_searchable_as_unverified_local_results(
    tmp_path: Path,
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    import_features([feature()], directory, boundary=Boundary.from_text("22,88,23,89"))

    results = asyncio.run(
        DirectoryClinicProvider(directory).search(
            ClinicSearchParams(latitude=22.57, longitude=88.36, radius_km=1)
        )
    )

    assert len(results) == 1
    assert results[0].verification_status == "unverified"
    assert results[0].source_type == "node"
