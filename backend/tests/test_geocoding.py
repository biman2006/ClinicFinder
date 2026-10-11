import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.locations import get_geocoder
from backend.core.config import ProviderSettings
from backend.integrations.geocoding import NominatimGeocoder
from backend.integrations.provider import ProviderResponseError, ProviderUnavailableError
from backend.main import app
from backend.schemas.provider import LocationSearchParams


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def make_geocoder(
    handler: Callable[[httpx.Request], httpx.Response],
) -> NominatimGeocoder:
    return NominatimGeocoder(
        settings=ProviderSettings(
            nominatim_endpoint="https://nominatim.example/search",
            geocoding_timeout_seconds=5,
            geocoding_min_interval_seconds=0,
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limit_interval=0,
    )


def params() -> LocationSearchParams:
    return LocationSearchParams(query="New Town, Kolkata")


def test_successfully_parses_geocoding_results() -> None:
    geocoder = make_geocoder(
        lambda request: httpx.Response(
            200,
            json=[
                {
                    "display_name": "New Town, Kolkata, West Bengal, India",
                    "lat": "22.58",
                    "lon": "88.48",
                    "osm_type": "relation",
                    "osm_id": 123,
                }
            ],
        )
    )

    results = run(geocoder.search(params()))

    assert results[0].display_name.startswith("New Town")
    assert (results[0].latitude, results[0].longitude) == (22.58, 88.48)
    assert results[0].precision == "approximate"


def test_no_matches_returns_empty_results() -> None:
    geocoder = make_geocoder(lambda request: httpx.Response(200, json=[]))

    assert run(geocoder.search(params())) == []


def test_malformed_result_payload_raises_response_error() -> None:
    geocoder = make_geocoder(
        lambda request: httpx.Response(200, json=[{"display_name": "Missing coordinates"}])
    )

    with pytest.raises(ProviderResponseError):
        run(geocoder.search(params()))


def test_timeout_raises_provider_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    geocoder = make_geocoder(handler)

    with pytest.raises(ProviderUnavailableError):
        run(geocoder.search(params()))


def test_upstream_error_raises_provider_unavailable_error() -> None:
    geocoder = make_geocoder(lambda request: httpx.Response(503))

    with pytest.raises(ProviderUnavailableError):
        run(geocoder.search(params()))


class StubGeocoder:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results

    async def search(self, params: LocationSearchParams) -> list[dict[str, Any]]:
        return self.results


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_location_endpoint_returns_ambiguous_matches(client: TestClient) -> None:
    geocoder = StubGeocoder(
        [
            {
                "display_name": "Springfield A",
                "latitude": 1,
                "longitude": 2,
                "precision": "approximate",
            },
            {
                "display_name": "Springfield B",
                "latitude": 3,
                "longitude": 4,
                "precision": "approximate",
            },
        ]
    )
    app.dependency_overrides[get_geocoder] = lambda: geocoder
    try:
        response = client.get("/locations/search", params={"query": "Springfield"})
    finally:
        app.dependency_overrides.pop(get_geocoder, None)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_location_endpoint_rejects_short_query(client: TestClient) -> None:
    response = client.get("/locations/search", params={"query": "x"})

    assert response.status_code == 422
