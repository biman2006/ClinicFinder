from collections.abc import Generator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.integrations.geocoding import NominatimGeocoder
from backend.integrations.provider import (
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from backend.schemas.provider import GeocodingResults, LocationSearchParams


router = APIRouter(prefix="/locations", tags=["locations"])
_geocoder: NominatimGeocoder | None = None


def get_geocoder() -> Generator[NominatimGeocoder, None, None]:
    global _geocoder
    if _geocoder is None:
        _geocoder = NominatimGeocoder()
    yield _geocoder


@router.get("/search", response_model=GeocodingResults)
async def search_locations(
    params: LocationSearchParams = Depends(),
    geocoder: NominatimGeocoder = Depends(get_geocoder),
) -> GeocodingResults | JSONResponse:
    try:
        items = await geocoder.search(params)
    except ProviderUnavailableError as exc:
        return _error(503, exc, "The location provider is temporarily unavailable.")
    except ProviderResponseError as exc:
        return _error(502, exc, "The location provider returned an invalid response.")
    except ProviderError as exc:
        return _error(502, exc, "The location search could not be completed.")
    return GeocodingResults(items=items)


def _error(status_code: int, error: ProviderError, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": error.code, "message": message}},
    )
