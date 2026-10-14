import asyncio
from collections.abc import Mapping
import logging
import re
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.core.config import ProviderSettings
from backend.integrations.provider import ProviderResponseError, ProviderUnavailableError
from backend.schemas.provider import GeocodedLocation, LocationSearchParams


logger = logging.getLogger(__name__)

# These are confirmed user spellings for Kolkata locality/landmark searches.
# Landmarks are intentionally kept as landmarks; they are not converted to a
# broader locality or assigned invented coordinates.
KOLKATA_LOCATION_ALIASES = {
    "new town": "New Town, Kolkata, West Bengal, India",
    "newtown": "New Town, Kolkata, West Bengal, India",
    "biswa bangla": "Biswa Bangla Gate, New Town, Kolkata, West Bengal, India",
    "biswa bangla gate": "Biswa Bangla Gate, New Town, Kolkata, West Bengal, India",
}


class NominatimGeocoder:
    def __init__(
        self,
        settings: ProviderSettings | None = None,
        client: httpx.AsyncClient | None = None,
        rate_limit_interval: float | None = None,
    ) -> None:
        self.settings = settings or ProviderSettings.from_environment()
        self._client = client or httpx.AsyncClient(
            timeout=self.settings.geocoding_timeout_seconds
        )
        self._owns_client = client is None
        self._rate_limit_interval = (
            self.settings.geocoding_min_interval_seconds
            if rate_limit_interval is None
            else rate_limit_interval
        )
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_at: float | None = None
        self._cache: dict[str, list[GeocodedLocation]] = {}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(
        self, params: LocationSearchParams
    ) -> list[GeocodedLocation]:
        query = normalize_location_query(params.query)
        provider_query = expand_kolkata_location_alias(query)
        cache_key = provider_query.casefold()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        await self._wait_for_rate_limit()
        try:
            response = await self._client.get(
                self.settings.nominatim_endpoint,
                params={
                    "q": provider_query,
                    "format": "jsonv2",
                    "limit": 5,
                    "addressdetails": 1,
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ClinicFinder/0.1 (provider evaluation)",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            _log_failure("timeout", self.settings.nominatim_endpoint, exc)
            raise ProviderUnavailableError(
                "The location provider could not be reached."
            ) from exc
        except httpx.RequestError as exc:
            _log_failure("network_error", self.settings.nominatim_endpoint, exc)
            raise ProviderUnavailableError(
                "The location provider could not be reached."
            ) from exc
        except httpx.HTTPStatusError as exc:
            _log_failure(
                "upstream_http_error",
                self.settings.nominatim_endpoint,
                exc,
                status_code=exc.response.status_code,
            )
            raise ProviderUnavailableError(
                "The location provider returned an unsuccessful response."
            ) from exc
        except ValueError as exc:
            _log_failure("malformed_json", self.settings.nominatim_endpoint, exc)
            raise ProviderResponseError(
                "The location provider returned malformed JSON."
            ) from exc

        if not isinstance(payload, list):
            raise ProviderResponseError("The location provider returned an invalid payload.")

        locations: list[GeocodedLocation] = []
        for item in payload:
            location = _parse_result(item)
            if location is not None:
                locations.append(location)
        if payload and not locations:
            raise ProviderResponseError("The location provider returned invalid results.")
        self._cache[cache_key] = list(locations)
        return locations

    async def _wait_for_rate_limit(self) -> None:
        async with self._rate_limit_lock:
            if self._last_request_at is not None:
                elapsed = time.monotonic() - self._last_request_at
                delay = self._rate_limit_interval - elapsed
                if delay > 0:
                    await asyncio.sleep(delay)
            self._last_request_at = time.monotonic()


def _parse_result(item: Any) -> GeocodedLocation | None:
    if not isinstance(item, Mapping):
        return None
    display_name = item.get("display_name")
    latitude = _finite_float(item.get("lat"))
    longitude = _finite_float(item.get("lon"))
    if not isinstance(display_name, str) or not display_name.strip():
        return None
    if latitude is None or longitude is None:
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    osm_type = item.get("osm_type")
    osm_id = item.get("osm_id")
    address_context = _address_context(item.get("address"))
    return GeocodedLocation(
        display_name=display_name.strip(),
        latitude=latitude,
        longitude=longitude,
        osm_type=osm_type if isinstance(osm_type, str) else None,
        osm_id=osm_id if isinstance(osm_id, int) else None,
        address_context=address_context,
    )


def normalize_location_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip().casefold()


def expand_kolkata_location_alias(query: str) -> str:
    return KOLKATA_LOCATION_ALIASES.get(query, query)


def _address_context(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    keys = (
        "neighbourhood",
        "suburb",
        "city_district",
        "town",
        "city",
        "state_district",
        "state",
        "country",
        "postcode",
    )
    return {
        key: item.strip()
        for key in keys
        if isinstance(item := value.get(key), str) and item.strip()
    }


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def _log_failure(
    category: str,
    endpoint: str,
    exception: Exception,
    *,
    status_code: int | None = None,
) -> None:
    parsed_endpoint = urlsplit(endpoint)
    logger.warning(
        "Nominatim geocoding request failed",
        extra={
            "geocoding_failure_category": category,
            "geocoding_exception_type": type(exception).__name__,
            "geocoding_http_status": status_code,
            "geocoding_endpoint": (
                f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
                f"{parsed_endpoint.path or '/'}"
            ),
        },
    )
