from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.core.config import ProviderSettings
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
                exception=exc,
            )
            raise ProviderUnavailableError(
                "The clinic data provider could not be reached."
            ) from exc
        except httpx.RequestError as exc:
            _log_provider_failure(
                "network_error",
                self.settings.overpass_endpoint,
                exception=exc,
            )
            raise ProviderUnavailableError(
                "The clinic data provider could not be reached."
            ) from exc
        except httpx.HTTPStatusError as exc:
            _log_provider_failure(
                "upstream_http_error",
                self.settings.overpass_endpoint,
                status_code=exc.response.status_code,
                exception=exc,
            )
            raise ProviderUnavailableError(
                "The clinic data provider returned an unsuccessful response."
            ) from exc
        except ValueError as exc:
            _log_provider_failure(
                "malformed_json",
                self.settings.overpass_endpoint,
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
            if source_type not in {"node", "way"} or not isinstance(source_id, int):
                continue
            source_key = (source_type, source_id)
            if source_key in seen:
                continue
            listing = parse_osm_element(element)
            if listing is not None:
                seen.add(source_key)
                results.append(listing)
        return results


def _log_provider_failure(
    category: str,
    endpoint: str,
    *,
    status_code: int | None = None,
    exception: Exception,
) -> None:
    parsed_endpoint = urlsplit(endpoint)
    logger.warning(
        "Overpass provider request failed",
        extra={
            "provider_failure_category": category,
            "provider_exception_type": type(exception).__name__,
            "provider_http_status": status_code,
            "provider_endpoint": (
                f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
                f"{parsed_endpoint.path or '/'}"
            ),
        },
    )


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


def parse_osm_element(element: Mapping[str, Any]) -> ClinicListing | None:
    tags = element.get("tags")
    if not isinstance(tags, Mapping):
        tags = {}
    name = _tag_text(tags, "name")
    if not name:
        return None

    source_type = element["type"]
    coordinates = _coordinates_for_element(element, source_type)
    return ClinicListing(
        name=name,
        address=_address_from_tags(tags),
        latitude=coordinates[0],
        longitude=coordinates[1],
        phone=_first_tag(tags, "phone", "contact:phone"),
        website=_first_tag(tags, "website", "contact:website"),
        services=_services_from_tags(tags),
        data_sources=["OpenStreetMap"],
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
        return float(latitude), float(longitude)
    return None, None


def _address_from_tags(tags: Mapping[str, Any]) -> str | None:
    parts = [
        _tag_text(tags, "addr:housenumber"),
        _tag_text(tags, "addr:street"),
        _tag_text(tags, "addr:suburb"),
        _tag_text(tags, "addr:city"),
        _tag_text(tags, "addr:postcode"),
    ]
    address = ", ".join(part for part in parts if part)
    return address or None


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
