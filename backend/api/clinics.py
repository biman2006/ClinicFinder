from collections.abc import Generator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.integrations.overpass import OverpassClinicProvider
from backend.integrations.provider import (
    ClinicDataProvider,
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from backend.schemas.provider import ClinicSearchParams, ProviderResults


router = APIRouter(prefix="/clinics", tags=["clinics"])

_provider: ClinicDataProvider | None = None


def get_clinic_provider() -> Generator[ClinicDataProvider, None, None]:
    global _provider
    if _provider is None:
        _provider = OverpassClinicProvider()
    yield _provider


@router.get("/search", response_model=ProviderResults)
async def search_clinics(
    params: ClinicSearchParams = Depends(),
    provider: ClinicDataProvider = Depends(get_clinic_provider),
) -> ProviderResults | JSONResponse:
    try:
        items = await provider.search(params)
    except ProviderUnavailableError as exc:
        return _provider_error(503, exc)
    except ProviderResponseError as exc:
        return _provider_error(502, exc)
    except ProviderError as exc:
        return _provider_error(502, exc)

    return ProviderResults(items=items)


def _provider_error(status_code: int, error: ProviderError) -> JSONResponse:
    public_messages = {
        "PROVIDER_UNAVAILABLE": "The clinic data provider is temporarily unavailable.",
        "PROVIDER_INVALID_RESPONSE": "The clinic data provider returned an invalid response.",
        "PROVIDER_ERROR": "The clinic data provider could not process the search.",
    }
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error.code,
                "message": public_messages.get(error.code, public_messages["PROVIDER_ERROR"]),
            }
        },
    )
