from collections.abc import Mapping
import logging
from math import asin, cos, radians, sin, sqrt
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.core.config import ProviderSettings
from backend.integrations.osm import address_status, osm_address_parts
from backend.integrations.provider import (
    ClinicDataProvider,
    ProviderResponseError,
    ProviderUnavailableError,
)
from backend.schemas.provider import ClinicListing, ClinicSearchParams


logger = logging.getLogger(__name__)


class OverpassClinicProvider(ClinicDataProvider):
    def __init__(
        self,
        settings: ProviderSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or ProviderSettings.from_environment()
        self._client = client or httpx.AsyncClient(
            timeout=self.settings.provider_timeout_seconds
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        query = build_overpass_query(params, self.settings.provider_timeout_seconds)
        try:
            response = await self._client.post(
                self.settings.overpass_endpoint,
                data={"data": query},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ClinicFinder/0.1 (provider evaluation)",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            _log_provider_failure(
                "timeout",
                self.settings.overpass_endpoint,
                query_length=len(query),
                exception=exc,
            )
            raise ProviderUnavailableError(
                "The clinic data provider could not be reached."
            ) from exc
        except httpx.RequestError as exc:
            _log_provider_failure(
                "network_error",
                self.settings.overpass_endpoint,
                query_length=len(query),
                exception=exc,
            )
            raise ProviderUnavailableError(
                "The clinic data provider could not be reached."
            ) from exc
        except httpx.HTTPStatusError as exc:
            _log_provider_failure(
                _http_failure_category(exc.response.status_code),
                self.settings.overpass_endpoint,
                status_code=exc.response.status_code,
                query_length=len(query),
                exception=exc,
            )
            raise ProviderUnavailableError(
                "The clinic data provider returned an unsuccessful response."
            ) from exc
        except ValueError as exc:
            _log_provider_failure(
                "malformed_json",
                self.settings.overpass_endpoint,
                query_length=len(query),
                exception=exc,
            )
            raise ProviderResponseError(
                "The clinic data provider returned malformed JSON."
            ) from exc

        if not isinstance(payload, Mapping) or not isinstance(
            payload.get("elements"), list
        ):
            raise ProviderResponseError("The clinic data provider returned an invalid payload.")

        results: list[ClinicListing] = []
        seen: set[tuple[str, int]] = set()
        for element in payload["elements"]:
            if not isinstance(element, Mapping):
                continue
            source_type = element.get("type")
            source_id = element.get("id")
            if source_type not in {"node", "way", "relation"} or not isinstance(source_id, int):
                continue
            source_key = (source_type, source_id)
            if source_key in seen:
                continue
            listing = parse_osm_element(
                element,
                origin_latitude=params.latitude,
                origin_longitude=params.longitude,
            )
            if listing is not None:
                if listing.distance_km is None or listing.distance_km > params.radius_km:
                    continue
                seen.add(source_key)
                results.append(listing)
        return results


def _log_provider_failure(
    category: str,
    endpoint: str,
    *,
    status_code: int | None = None,
    query_length: int | None = None,
    exception: Exception,
) -> None:
    parsed_endpoint = urlsplit(endpoint)
    logger.warning(
        "Overpass provider request failed",
        extra={
            "provider_failure_category": category,
            "provider_exception_type": type(exception).__name__,
            "provider_http_status": status_code,
            "provider_query_length": query_length,
            "provider_endpoint": (
                f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
                f"{parsed_endpoint.path or '/'}"
            ),
        },
    )


def _http_failure_category(status_code: int) -> str:
    if status_code == 429:
        return "rate_limited"
    if status_code == 504:
        return "gateway_timeout"
    if 500 <= status_code <= 599:
        return "upstream_server_error"
    return "upstream_http_error"


def build_overpass_query(
    params: ClinicSearchParams, timeout_seconds: float = 20
) -> str:
    radius_m = params.radius_km * 1000
    latitude = params.latitude
    longitude = params.longitude
    query_timeout = max(1, int(timeout_seconds))
    return (
        f"[out:json][timeout:{query_timeout}];"
        "("
        f'nwr["amenity"="clinic"](around:{radius_m},{latitude},{longitude});'
        f'nwr["healthcare"="clinic"](around:{radius_m},{latitude},{longitude});'
        ");"
        "out center tags;"
    )


def parse_osm_element(
    element: Mapping[str, Any],
    *,
    origin_latitude: float | None = None,
    origin_longitude: float | None = None,
) -> ClinicListing | None:
    tags = element.get("tags")
    if not isinstance(tags, Mapping):
        tags = {}
    name = _tag_text(tags, "name")
    if not name:
        return None

    source_type = element["type"]
    coordinates = _coordinates_for_element(element, source_type)
    distance_km = None
    if coordinates[0] is not None and coordinates[1] is not None:
        distance_km = _distance_km(
            coordinates[0],
            coordinates[1],
            origin_latitude,
            origin_longitude,
        )
    address_parts = osm_address_parts(tags)
    return ClinicListing(
        name=name,
        address=address_parts["address"],
        locality=address_parts["locality"],
        city=address_parts["city"],
        postal_code=address_parts["postal_code"],
        address_status=address_status(address_parts),
        latitude=coordinates[0],
        longitude=coordinates[1],
        phone=_first_tag(tags, "phone", "contact:phone"),
        website=_first_tag(tags, "website", "contact:website"),
        services=_services_from_tags(tags),
        data_sources=["OpenStreetMap"],
        source_data={
            key: value
            for key, value in tags.items()
            if isinstance(value, str) and value.strip()
        },
        distance_km=distance_km,
        source_type=source_type,
        source_id=element["id"],
    )


def _coordinates_for_element(
    element: Mapping[str, Any], source_type: str
) -> tuple[float | None, float | None]:
    coordinates: Any = element if source_type == "node" else element.get("center")
    if not isinstance(coordinates, Mapping):
        return None, None
    latitude = coordinates.get("lat")
    longitude = coordinates.get("lon")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        latitude_value = float(latitude)
        longitude_value = float(longitude)
        if (
            latitude_value == latitude_value
            and longitude_value == longitude_value
            and abs(latitude_value) != float("inf")
            and abs(longitude_value) != float("inf")
            and -90 <= latitude_value <= 90
            and -180 <= longitude_value <= 180
        ):
            return latitude_value, longitude_value
    return None, None


def _distance_km(
    latitude: float,
    longitude: float,
    origin_latitude: float | None,
    origin_longitude: float | None,
) -> float | None:
    if origin_latitude is None or origin_longitude is None:
        return None
    earth_radius_km = 6371.0088
    latitude_delta = radians(latitude - origin_latitude)
    longitude_delta = radians(longitude - origin_longitude)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(origin_latitude))
        * cos(radians(latitude))
        * sin(longitude_delta / 2) ** 2
    )
    return round(earth_radius_km * 2 * asin(sqrt(haversine)), 3)


def _first_tag(tags: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _tag_text(tags, key)
        if value:
            return value
    return None


def _services_from_tags(tags: Mapping[str, Any]) -> list[str]:
    value = _first_tag(
        tags,
        "healthcare:speciality",
        "healthcare:specialty",
        "speciality",
        "specialty",
    )
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def _tag_text(tags: Mapping[str, Any], key: str) -> str | None:
    value = tags.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None
