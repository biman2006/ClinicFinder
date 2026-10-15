from datetime import timedelta
from pathlib import Path
import asyncio
import pytest

from backend.integrations.directory import ClinicDirectory, DirectoryClinicProvider
from backend.schemas.directory import DirectoryBranchInput
from backend.schemas.provider import ClinicSearchParams


def branch(name: str = "Apollo Clinic") -> DirectoryBranchInput:
    return DirectoryBranchInput(
        facility_name=name,
        branch_name="Barrackpore",
        facility_type="clinic",
        address="1 Station Road",
        locality="Barrackpore",
        city="Kolkata",
        postal_code="700120",
        latitude=22.76,
        longitude=88.37,
        field_sources={"address": "official branch confirmation"},
        field_evidence={"address": "https://clinic.example/branch"},
        verification_method="official branch directory review",
    )


def test_only_verified_directory_branches_are_searchable(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    pending = directory.add(branch())
    assert pending.verification_status == "pending"
    assert asyncio.run(DirectoryClinicProvider(directory).search(
        ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
    )) == []

    directory.update(pending.id, branch(), verify=True)
    results = asyncio.run(DirectoryClinicProvider(directory).search(
        ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
    ))

    assert len(results) == 1
    assert results[0].clinic_id == pending.id
    assert results[0].verification_status == "verified"
    assert results[0].field_sources["address"] == "official branch confirmation"


@pytest.mark.parametrize(
    ("address", "postal_code", "district", "expected_status"),
    [
        ("", None, None, "unknown"),
        ("", "700001", None, "incomplete"),
        ("Beltola Road", None, None, "complete"),
    ],
)
def test_manual_directory_address_status_uses_directory_address_field(
    tmp_path: Path,
    address: str,
    postal_code: str | None,
    district: str | None,
    expected_status: str,
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    input_data = branch().model_copy(
        update={
            "address": address,
            "locality": None,
            "city": None,
            "postal_code": postal_code,
            "district": district,
        }
    )
    record = directory.add(input_data)
    directory.update(record.id, input_data, verify=True)

    results = asyncio.run(
        DirectoryClinicProvider(directory).search(
            ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
        )
    )

    assert results[0].address_status == expected_status


def test_directory_filters_radius_and_preserves_similar_branches(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    first = directory.add(branch("Jibok Clinic"))
    second = directory.add(branch("Jibok Clinic"))
    directory.update(first.id, branch("Jibok Clinic"), verify=True)
    directory.update(
        second.id,
        branch("Jibok Clinic").model_copy(update={"latitude": 22.80}),
        verify=True,
    )

    results = asyncio.run(DirectoryClinicProvider(directory).search(
        ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=2)
    ))

    assert len(results) == 1
    assert results[0].clinic_id == first.id


def test_verification_requires_field_evidence(tmp_path: Path) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    record = directory.add(branch())

    with pytest.raises(ValueError):
        directory.update(
            record.id,
            branch().model_copy(update={"field_evidence": {}}),
            verify=True,
        )


def test_legacy_imported_record_recovers_osm_identity_and_fields(
    tmp_path: Path,
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    record = directory.add(
        branch("Sherwood Nursing Home").model_copy(
            update={
                "branch_name": "Sherwood Nursing Home",
                "address": "700001",
                "postal_code": "700001",
                "source_type": None,
                "source_id": None,
                "field_evidence": {"name": "osm:node/7050669492"},
                "source_data": {
                    "name": "Sherwood Nursing Home",
                    "addr:full": "12 Park Street, Kolkata",
                    "addr:postcode": "700001",
                    "phone": "+91 12345",
                },
            }
        )
    )

    results = asyncio.run(
        DirectoryClinicProvider(directory).search(
            ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
        )
    )

    assert record.verification_status == "pending"
    assert len(results) == 1
    assert results[0].source_type == "node"
    assert results[0].source_id == 7050669492
    assert results[0].name == "Sherwood Nursing Home"
    assert results[0].address == "12 Park Street, Kolkata"
    assert results[0].address_status == "complete"


def test_imported_directory_response_exposes_district_separately(
    tmp_path: Path,
) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    directory.upsert_imported(
        DirectoryBranchInput(
            facility_name="Repose Clinic and Research Centre",
            branch_name="Repose Clinic and Research Centre",
            facility_type="clinic",
            address="20/C, Broad Street,(Ballygunge)",
            postal_code="700019",
            latitude=22.76,
            longitude=88.37,
            district="Kolkata",
            source_type="node",
            source_id=909,
            source_data={
                "name": "Repose Clinic and Research Centre",
                "addr:district": "Kolkata",
                "addr:full": "20/C, Broad Street,(Ballygunge)",
                "addr:postcode": "700019",
            },
        )
    )

    results = asyncio.run(
        DirectoryClinicProvider(directory).search(
            ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
        )
    )

    assert len(results) == 1
    assert results[0].district == "Kolkata"
    assert results[0].locality is None
    assert results[0].city is None
    assert results[0].address == "20/C, Broad Street,(Ballygunge)"


def test_stale_verified_branch_is_not_publicly_searchable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINIC_DIRECTORY_STALE_AFTER_DAYS", "1")
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    record = directory.add(branch())
    verified = directory.update(record.id, branch(), verify=True)
    with directory._connect() as connection:
        connection.execute(
            "UPDATE clinic_branches SET last_checked_at=? WHERE id=?",
            ((verified.last_checked_at - timedelta(days=2)).isoformat(), record.id),
        )

    assert directory.list()[0].status == "stale"
    assert asyncio.run(
        DirectoryClinicProvider(directory).search(
            ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
        )
    ) == []
