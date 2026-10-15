import asyncio

import pytest

from backend.integrations.composite import CompositeClinicProvider
from backend.integrations.directory import DirectoryStorageError
from backend.integrations.provider import ProviderUnavailableError
from backend.schemas.provider import ClinicListing, ClinicSearchParams


class StubProvider:
    def __init__(self, result: list[ClinicListing] | Exception) -> None:
        self.result = result

    async def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def osm_listing(name: str = "Apollo Clinic") -> ClinicListing:
    return ClinicListing(
        name=name,
        address="1 Station Road",
        latitude=22.76,
        longitude=88.37,
        distance_km=0.3,
        data_sources=["OpenStreetMap"],
        source_type="node",
        source_id=42,
        field_evidence={"name": "osm:node/42"},
    )


def directory_listing() -> ClinicListing:
    return ClinicListing(
        clinic_id="branch-1",
        name="Apollo Clinic - Barrackpore",
        address="1 Station Road",
        latitude=22.7605,
        longitude=88.3705,
        distance_km=0.4,
        data_sources=["ClinicFinder directory"],
        source_type="directory",
        verification_status="verified",
        source_id=None,
        field_evidence={"name": "osm:node/42"},
    )


def second_directory_listing() -> ClinicListing:
    return directory_listing().model_copy(
        update={
            "clinic_id": "branch-2",
            "address": "2 Station Road",
            "source_data": {},
            "field_evidence": {},
        }
    )


def test_verified_directory_precedes_duplicate_osm_branch() -> None:
    results = asyncio.run(CompositeClinicProvider(
        [StubProvider([osm_listing()]), StubProvider([directory_listing()])]
    ).search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)))

    assert len(results) == 1
    assert results[0].clinic_id == "branch-1"
    assert set(results[0].data_sources) == {"OpenStreetMap", "ClinicFinder directory"}


def test_source_failure_does_not_hide_successful_source() -> None:
    results = asyncio.run(CompositeClinicProvider(
        [
            StubProvider(ProviderUnavailableError("OSM down")),
            StubProvider([directory_listing()]),
        ]
    ).search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)))

    assert [result.clinic_id for result in results] == ["branch-1"]


def test_empty_overpass_success_is_not_marked_unavailable() -> None:
    provider = CompositeClinicProvider(
        [StubProvider([]), StubProvider([directory_listing()])]
    )

    results = asyncio.run(
        provider.search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1))
    )

    assert len(results) == 1
    assert provider.last_source_status == {
        "stubprovider_1": "ok",
        "stubprovider_2": "ok",
    }


def test_directory_failure_does_not_hide_successful_osm_source() -> None:
    provider = CompositeClinicProvider(
        [
            StubProvider([osm_listing()]),
            StubProvider(DirectoryStorageError("database unavailable")),
        ]
    )

    results = asyncio.run(
        provider.search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1))
    )

    assert [result.name for result in results] == ["Apollo Clinic"]
    assert provider.last_source_status == {
        "stubprovider_1": "ok",
        "stubprovider_2": "error",
    }


def test_successful_empty_source_is_not_treated_as_total_failure() -> None:
    provider = CompositeClinicProvider(
        [
            StubProvider([]),
            StubProvider(DirectoryStorageError("database unavailable")),
        ]
    )

    results = asyncio.run(
        provider.search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1))
    )

    assert results == []
    assert provider.last_source_status == {
        "stubprovider_1": "ok",
        "stubprovider_2": "error",
    }


def test_similar_names_at_distinct_addresses_are_not_merged() -> None:
    results = asyncio.run(
        CompositeClinicProvider(
            [StubProvider([directory_listing(), second_directory_listing()])]
        ).search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1))
    )

    assert {result.clinic_id for result in results} == {"branch-1", "branch-2"}


def test_nearby_same_names_without_osm_identity_are_not_merged() -> None:
    first = directory_listing().model_copy(
        update={"clinic_id": "branch-1", "field_evidence": {}}
    )
    second = directory_listing().model_copy(
        update={
            "clinic_id": "branch-2",
            "latitude": 22.7601,
            "longitude": 88.3701,
            "field_evidence": {},
        }
    )

    results = asyncio.run(
        CompositeClinicProvider([StubProvider([first, second])]).search(
            ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
        )
    )

    assert {result.clinic_id for result in results} == {"branch-1", "branch-2"}


def test_osm_identity_from_field_evidence_deduplicates_conflicting_names() -> None:
    live = osm_listing("Shakambari Nursing Home").model_copy(
        update={"address": "11 Lake Road", "phone": "+91 99999", "field_evidence": {}}
    )
    imported = directory_listing().model_copy(
        update={
            "name": "Recovery Nursing Home Pvt Ltd - Recovery Nursing Home Pvt Ltd",
            "address": "11 Lake Road",
            "field_evidence": {"name": "osm:node/42"},
            "source_type": "directory",
            "source_id": None,
            "verification_status": "unverified",
        }
    )

    results = asyncio.run(
        CompositeClinicProvider([StubProvider([live, imported])]).search(
            ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)
        )
    )

    assert len(results) == 1
    assert results[0].source_type == "node"
    assert results[0].source_id == 42
    assert results[0].name == "Shakambari Nursing Home"
def test_all_source_failures_are_reported() -> None:
    provider = CompositeClinicProvider(
        [
            StubProvider(ProviderUnavailableError("OSM down")),
            StubProvider(ProviderUnavailableError("directory down")),
        ]
    )

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(provider.search(ClinicSearchParams(latitude=22.76, longitude=88.37, radius_km=1)))
