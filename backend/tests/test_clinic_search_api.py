from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.api.clinics import get_clinic_provider
from backend.integrations.provider import ProviderResponseError, ProviderUnavailableError
from backend.main import app
from backend.schemas.provider import ClinicListing, ClinicSearchParams


class StubProvider:
    def __init__(self, result: list[ClinicListing] | Exception) -> None:
        self.result = result
        self.received_params: ClinicSearchParams | None = None

    async def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        self.received_params = params
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def listing() -> ClinicListing:
    return ClinicListing(
        name="Example Clinic",
        latitude=22.57,
        longitude=88.36,
        data_sources=["OpenStreetMap"],
        source_type="node",
        source_id=101,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def override_provider(provider: StubProvider):
    def dependency() -> StubProvider:
        return provider

    app.dependency_overrides[get_clinic_provider] = dependency
    return provider


def clear_provider_override() -> None:
    app.dependency_overrides.pop(get_clinic_provider, None)


def test_search_returns_normalized_provider_results(client: TestClient) -> None:
    provider = override_provider(StubProvider([listing()]))
    try:
        response = client.get(
            "/clinics/search",
            params={"latitude": 22.5726, "longitude": 88.3639, "radius_km": 5},
        )
    finally:
        clear_provider_override()

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Example Clinic"
    assert response.json()["items"][0]["source_type"] == "node"
    assert response.json()["items"][0]["source_id"] == 101
    assert response.json()["items"][0]["verification_status"] == "unverified"
    assert provider.received_params == ClinicSearchParams(
        latitude=22.5726, longitude=88.3639, radius_km=5
    )


@pytest.mark.parametrize(
    "params",
    [
        {"latitude": 91, "longitude": 88, "radius_km": 5},
        {"latitude": 22, "longitude": 181, "radius_km": 5},
        {"latitude": 22, "longitude": 88, "radius_km": 0},
        {"latitude": 22, "longitude": 88, "radius_km": 51},
    ],
)
def test_search_rejects_invalid_parameters(
    client: TestClient, params: dict[str, float]
) -> None:
    response = client.get("/clinics/search", params=params)

    assert response.status_code == 422


def test_search_maps_provider_timeout_to_safe_503(client: TestClient) -> None:
    override_provider(StubProvider(ProviderUnavailableError("internal detail")))
    try:
        response = client.get(
            "/clinics/search",
            params={"latitude": 22, "longitude": 88, "radius_km": 5},
        )
    finally:
        clear_provider_override()

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "PROVIDER_UNAVAILABLE",
            "message": "The clinic data provider is temporarily unavailable.",
        }
    }


def test_search_maps_provider_response_error_to_safe_502(client: TestClient) -> None:
    override_provider(StubProvider(ProviderResponseError("malformed response")))
    try:
        response = client.get(
            "/clinics/search",
            params={"latitude": 22, "longitude": 88, "radius_km": 5},
        )
    finally:
        clear_provider_override()

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "PROVIDER_INVALID_RESPONSE",
            "message": "The clinic data provider returned an invalid response.",
        }
    }


def test_health_endpoint_is_unchanged(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clinic-discovery-api"}
