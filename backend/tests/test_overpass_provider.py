import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from backend.core.config import ProviderSettings
from backend.integrations.overpass import OverpassClinicProvider, build_overpass_query
from backend.integrations.provider import ProviderResponseError, ProviderUnavailableError
from backend.schemas.provider import ClinicSearchParams


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def make_provider(
    handler: Callable[[httpx.Request], httpx.Response | Exception],
) -> OverpassClinicProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return OverpassClinicProvider(
        settings=ProviderSettings(
            overpass_endpoint="https://overpass.example/api/interpreter",
            provider_timeout_seconds=7,
        ),
        client=client,
    )


def search_params() -> ClinicSearchParams:
    return ClinicSearchParams(latitude=22.5726, longitude=88.3639, radius_km=5)


def response(elements: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json={"elements": elements})


def test_parses_node_and_normalizes_contact_fields() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 101,
                    "lat": 22.57,
                    "lon": 88.36,
                    "tags": {
                        "name": "Example Clinic",
                        "addr:street": "Park Street",
                        "addr:city": "Kolkata",
                        "contact:phone": " +91 123 ",
                        "contact:website": "https://example.test",
                        "healthcare:speciality": "general; dermatology",
                    },
                }
            ]
        )
    )

    results = run(provider.search(search_params()))

    assert results[0].model_dump(exclude_none=True) == {
        "name": "Example Clinic",
        "address": "Park Street, Kolkata",
        "latitude": 22.57,
        "longitude": 88.36,
        "phone": "+91 123",
        "website": "https://example.test",
        "services": ["general", "dermatology"],
        "opening_status": "unknown",
        "doctors": [],
        "match_reasons": [],
        "data_sources": ["OpenStreetMap"],
        "source_id": 101,
        "source_type": "node",
        "verification_status": "unverified",
    }


def test_parses_way_using_center_coordinates() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "way",
                    "id": 202,
                    "center": {"lat": 22.58, "lon": 88.37},
                    "tags": {"name": "Way Clinic"},
                }
            ]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.source_type == "way"
    assert result.source_id == 202
    assert (result.latitude, result.longitude) == (22.58, 88.37)


def test_missing_optional_tags_remain_null_or_empty() -> None:
    provider = make_provider(
        lambda request: response(
            [{"type": "node", "id": 303, "lat": 22.5, "lon": 88.3, "tags": {"name": "Minimal"}}]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.address is None
    assert result.phone is None
    assert result.website is None
    assert result.services == []


def test_malformed_provider_response_raises_structured_error() -> None:
    provider = make_provider(lambda request: httpx.Response(200, content=b"{not-json"))

    with pytest.raises(ProviderResponseError) as error:
        run(provider.search(search_params()))

    assert error.value.code == "PROVIDER_INVALID_RESPONSE"


def test_timeout_raises_provider_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = make_provider(handler)

    with pytest.raises(ProviderUnavailableError) as error:
        run(provider.search(search_params()))

    assert error.value.code == "PROVIDER_UNAVAILABLE"


def test_non_success_response_raises_provider_unavailable_error() -> None:
    provider = make_provider(lambda request: httpx.Response(503))

    with pytest.raises(ProviderUnavailableError) as error:
        run(provider.search(search_params()))

    assert error.value.code == "PROVIDER_UNAVAILABLE"


def test_duplicate_source_elements_are_deduplicated_without_name_merging() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {"type": "node", "id": 1, "lat": 22.5, "lon": 88.3, "tags": {"name": "Same"}},
                {"type": "node", "id": 1, "lat": 22.5, "lon": 88.3, "tags": {"name": "Same"}},
                {"type": "way", "id": 1, "center": {"lat": 22.6, "lon": 88.4}, "tags": {"name": "Same"}},
            ]
        )
    )

    results = run(provider.search(search_params()))

    assert [(item.source_type, item.source_id) for item in results] == [
        ("node", 1),
        ("way", 1),
    ]


def test_query_uses_validated_numeric_values_and_configured_timeout() -> None:
    query = build_overpass_query(search_params(), timeout_seconds=7)

    assert "[timeout:7]" in query
    assert "around:5000.0,22.5726,88.3639" in query
    assert "https://" not in query


def test_request_sets_json_accept_and_identifying_user_agent() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        return response([])

    provider = make_provider(handler)

    run(provider.search(search_params()))

    assert captured_headers["accept"] == "application/json"
    assert captured_headers["user-agent"] == "ClinicFinder/0.1 (provider evaluation)"
