import asyncio
import logging

import httpx

from backend.core.config import ProviderSettings
from backend.integrations.directory import ClinicDirectory, DirectoryClinicProvider
from backend.integrations.overpass import OverpassClinicProvider
from backend.schemas.directory import DirectoryBranchInput
from backend.schemas.provider import ClinicSearchParams


def test_overpass_successful_empty_response_logs_zero_candidates(
    caplog, monkeypatch
) -> None:
    class EmptyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[object]]:
            return {"elements": []}

    async def post(*args, **kwargs) -> EmptyResponse:
        return EmptyResponse()

    client = httpx.AsyncClient()
    monkeypatch.setattr(client, "post", post)
    provider = OverpassClinicProvider(
        ProviderSettings(provider_timeout_seconds=1),
        client=client,
    )
    caplog.set_level(logging.INFO)

    try:
        results = asyncio.run(
            provider.search(
                ClinicSearchParams(latitude=22.3456, longitude=88.5634, radius_km=10)
            )
        )
    finally:
        asyncio.run(client.aclose())

    assert results == []
    record = next(
        record
        for record in caplog.records
        if record.message == "Overpass clinic search candidate counts"
    )
    assert record.candidate_counts == {
        "raw_elements": 0,
        "category_filtered": 0,
        "valid_identity": 0,
        "parsed": 0,
        "missing_name": 0,
        "invalid_coordinates": 0,
        "outside_radius": 0,
        "duplicate_identity": 0,
        "accepted": 0,
    }


def test_directory_search_applies_radius_to_imported_records(tmp_path, caplog) -> None:
    directory = ClinicDirectory(tmp_path / "directory.sqlite3")
    directory.upsert_imported(
        DirectoryBranchInput(
            facility_name="Nearby Clinic",
            branch_name="Main",
            facility_type="clinic",
            address="Nearby",
            latitude=22.3456,
            longitude=88.5634,
            source_type="node",
            source_id=123,
            source_data={"name": "Nearby Clinic"},
        )
    )
    directory.upsert_imported(
        DirectoryBranchInput(
            facility_name="Distant Clinic",
            branch_name="Main",
            facility_type="clinic",
            address="Distant",
            latitude=22.5,
            longitude=88.5,
            source_type="node",
            source_id=456,
            source_data={"name": "Distant Clinic"},
        )
    )
    caplog.set_level(logging.INFO)

    results = asyncio.run(
        DirectoryClinicProvider(directory).search(
            ClinicSearchParams(latitude=22.3456, longitude=88.5634, radius_km=10)
        )
    )

    assert [result.name for result in results] == ["Nearby Clinic - Main"]
    record = next(
        record
        for record in caplog.records
        if record.message == "Directory clinic search candidate counts"
    )
    assert record.candidate_counts == {
        "records": 2,
        "status_eligible": 2,
        "outside_radius": 1,
        "accepted": 1,
    }
