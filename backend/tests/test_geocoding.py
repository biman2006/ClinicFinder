import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.integrations.geocoding as geocoding_module
from backend.api.locations import get_geocoder
from backend.core.config import ProviderSettings
from backend.integrations.geocoding import (
    NominatimGeocoder,
    expand_kolkata_location_alias,
    normalize_location_query,
)
from backend.integrations.local_locations import find_local_location_suggestions
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
                    "address": {
                        "town": "New Town",
                        "city": "Kolkata",
                        "state": "West Bengal",
                        "country": "India",
                    },
                }
            ],
        )
    )

    results = run(geocoder.search(params()))

    assert results[0].display_name.startswith("New Town")
    assert (results[0].latitude, results[0].longitude) == (22.58, 88.48)
    assert results[0].precision == "approximate"
    assert results[0].address_context["city"] == "Kolkata"


@pytest.mark.parametrize(
    ("query", "expanded"),
    [
        ("New Town", "New Town, Kolkata, West Bengal, India"),
        ("  NEWTOWN  ", "New Town, Kolkata, West Bengal, India"),
        ("Biswa Bangla", "Biswa Bangla Gate, New Town, Kolkata, West Bengal, India"),
        ("Biswa Bangla Gate", "Biswa Bangla Gate, New Town, Kolkata, West Bengal, India"),
    ],
)
def test_kolkata_location_aliases_are_normalized_and_scoped(
    query: str, expanded: str
) -> None:
    assert expand_kolkata_location_alias(normalize_location_query(query)) == expanded


def test_alias_query_is_sent_once_and_success_is_cached() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "display_name": "New Town, Kolkata, West Bengal, India",
                    "lat": "22.58",
                    "lon": "88.48",
                }
            ],
        )

    geocoder = make_geocoder(handler)

    first = run(geocoder.search(LocationSearchParams(query=" Newtown ")))
    second = run(geocoder.search(LocationSearchParams(query="new town")))

    assert first == second
    assert len(requests) == 1
    assert requests[0].url.params["q"] == "New Town, Kolkata, West Bengal, India"


def test_unknown_and_empty_provider_results_remain_empty() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[])

    geocoder = make_geocoder(handler)

    assert run(geocoder.search(LocationSearchParams(query="Unknown Kolkata place"))) == []
    assert run(geocoder.search(LocationSearchParams(query=" unknown   kolkata place "))) == []
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("newtown", "New Town"),
        ("NEW TOWN", "New Town"),
        ("biswa bangla", "Biswa Bangla Gate"),
        ("salt lake", "Salt Lake (Bidhannagar)"),
        ("sector 5", "Sector V"),
    ],
)
def test_local_suggestion_catalogue_matches_aliases(
    query: str, expected: str
) -> None:
    results = find_local_location_suggestions(query)

    assert [result.name for result in results] == [expected]
    assert results[0].latitude is not None
    assert results[0].longitude is not None


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


def test_upstream_rate_limit_raises_provider_unavailable_error() -> None:
    geocoder = make_geocoder(lambda request: httpx.Response(429))

    with pytest.raises(ProviderUnavailableError):
        run(geocoder.search(params()))


def test_geocoder_waits_between_external_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(geocoding_module.asyncio, "sleep", fake_sleep)
    geocoder = NominatimGeocoder(
        settings=ProviderSettings(
            nominatim_endpoint="https://nominatim.example/search",
            geocoding_timeout_seconds=5,
            geocoding_min_interval_seconds=1,
        ),
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
        ),
        rate_limit_interval=1,
    )

    run(geocoder.search(LocationSearchParams(query="first place")))
    run(geocoder.search(LocationSearchParams(query="second place")))

    assert sleep_calls
    assert sleep_calls[0] >= 0


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


def test_local_suggestions_endpoint_does_not_use_geocoder(client: TestClient) -> None:
    response = client.get("/locations/suggestions", params={"query": "newtown"})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["name"] == "New Town"
    assert item["source"] == "OpenStreetMap"
    assert item["latitude"] == 22.5882834
