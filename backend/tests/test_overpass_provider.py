import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from backend.core.config import ProviderSettings
from backend.integrations.osm import address_status
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


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        ({}, "unknown"),
        ({"street": "Beltola Road"}, "incomplete"),
        ({"postal_code": "700001"}, "incomplete"),
        ({"district": "Kolkata"}, "incomplete"),
        ({"housenumber": "52/2B", "street": "Hazra Road"}, "complete"),
        ({"full_address": "20/C, Broad Street,(Ballygunge)"}, "complete"),
    ],
)
def test_address_status_classification(parts: dict[str, str], expected: str) -> None:
    assert address_status(parts) == expected


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

    result = results[0]
    assert result.name == "Example Clinic"
    assert result.address == "Park Street, Kolkata"
    assert result.city == "Kolkata"
    assert result.address_status == "incomplete"
    assert result.phone == "+91 123"
    assert result.website == "https://example.test"
    assert result.services == ["general", "dermatology"]
    assert result.data_sources == ["OpenStreetMap"]
    assert result.source_data["addr:city"] == "Kolkata"
    assert result.source_id == 101
    assert result.source_type == "node"
    assert result.verification_status == "unverified"
    assert result.distance_km is not None and result.distance_km < 1


def test_preserves_district_separately_from_city_and_locality() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 111,
                    "lat": 22.57,
                    "lon": 88.36,
                    "tags": {
                        "name": "Repose Clinic and Research Centre",
                        "addr:district": "Kolkata",
                        "addr:full": "20/C, Broad Street,(Ballygunge)",
                        "addr:postcode": "700019",
                    },
                }
            ]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.address == "20/C, Broad Street,(Ballygunge)"
    assert result.district == "Kolkata"
    assert result.locality is None
    assert result.city is None
    assert result.postal_code == "700019"
    assert result.address_status == "complete"


def test_preserves_explicit_locality_without_inference() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 112,
                    "lat": 22.57,
                    "lon": 88.36,
                    "tags": {
                        "name": "Locality Clinic",
                        "addr:suburb": "Ballygunge",
                        "addr:district": "Kolkata",
                    },
                }
            ]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.locality == "Ballygunge"
    assert result.district == "Kolkata"
    assert result.city is None


def test_records_without_address_administrative_tags_remain_null() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 113,
                    "lat": 22.57,
                    "lon": 88.36,
                    "tags": {
                        "name": "Unclassified Address Clinic",
                        "addr:street": "Hazra Road",
                        "addr:housenumber": "52/2B",
                        "addr:postcode": "700019",
                    },
                }
            ]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.address == "52/2B, Hazra Road"
    assert result.locality is None
    assert result.district is None
    assert result.city is None


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


def test_parses_relation_using_center_coordinates() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "relation",
                    "id": 203,
                    "center": {"lat": 22.58, "lon": 88.37},
                    "tags": {"name": "Relation Clinic"},
                }
            ]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.source_type == "relation"
    assert result.source_id == 203
    assert (result.latitude, result.longitude) == (22.58, 88.37)


def test_invalid_coordinates_are_skipped() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 204,
                    "lat": 999,
                    "lon": 88.37,
                    "tags": {"name": "Invalid Clinic"},
                }
            ]
        )
    )

    assert run(provider.search(search_params())) == []


def test_missing_optional_tags_remain_null_or_empty() -> None:
    provider = make_provider(
        lambda request: response(
            [{"type": "node", "id": 303, "lat": 22.57, "lon": 88.36, "tags": {"name": "Minimal"}}]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.address is None
    assert result.phone is None
    assert result.website is None
    assert result.services == []


def test_elements_without_names_are_skipped_without_fabricating_names() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 304,
                    "lat": 22.57,
                    "lon": 88.36,
                    "tags": {"amenity": "clinic"},
                }
            ]
        )
    )

    assert run(provider.search(search_params())) == []


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


@pytest.mark.parametrize("status_code", [429, 503, 504])
def test_non_success_response_raises_provider_unavailable_error(
    status_code: int,
) -> None:
    provider = make_provider(lambda request: httpx.Response(status_code))

    with pytest.raises(ProviderUnavailableError) as error:
        run(provider.search(search_params()))

    assert error.value.code == "PROVIDER_UNAVAILABLE"


@pytest.mark.parametrize(
    ("status_code", "category"),
    [(429, "rate_limited"), (504, "gateway_timeout")],
)
def test_http_failures_log_safe_status_category(
    status_code: int,
    category: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = make_provider(lambda request: httpx.Response(status_code))

    with caplog.at_level("WARNING"):
        with pytest.raises(ProviderUnavailableError):
            run(provider.search(search_params()))

    record = next(record for record in caplog.records if record.message == "Overpass provider request failed")
    assert record.provider_failure_category == category
    assert record.provider_http_status == status_code
    assert record.provider_response_content_type is None
    assert record.provider_exception_type == "HTTPStatusError"
    assert record.provider_query_length > 0


def test_duplicate_source_elements_are_deduplicated_without_name_merging() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {"type": "node", "id": 1, "lat": 22.57, "lon": 88.36, "tags": {"name": "Same"}},
                {"type": "node", "id": 1, "lat": 22.57, "lon": 88.36, "tags": {"name": "Same"}},
                {"type": "way", "id": 1, "center": {"lat": 22.6, "lon": 88.4}, "tags": {"name": "Same"}},
            ]
        )
    )

    results = run(provider.search(search_params()))

    assert [(item.source_type, item.source_id) for item in results] == [
        ("node", 1),
        ("way", 1),
    ]


def test_filters_provider_results_outside_requested_radius() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 404,
                    "lat": 22.7,
                    "lon": 88.5,
                    "tags": {"name": "Outside"},
                }
            ]
        )
    )

    assert run(provider.search(search_params())) == []


def test_marks_pin_only_address_as_incomplete() -> None:
    provider = make_provider(
        lambda request: response(
            [
                {
                    "type": "node",
                    "id": 505,
                    "lat": 22.57,
                    "lon": 88.36,
                    "tags": {"name": "Pin Only", "addr:postcode": "700001"},
                }
            ]
        )
    )

    result = run(provider.search(search_params()))[0]

    assert result.address is None
    assert result.postal_code == "700001"
    assert result.postal_code == "700001"
    assert result.address_status == "incomplete"


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
