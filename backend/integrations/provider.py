from abc import ABC, abstractmethod

from backend.schemas.provider import ClinicListing, ClinicSearchParams


class ProviderError(Exception):
    """Safe, structured error for provider failures."""

    code = "PROVIDER_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderUnavailableError(ProviderError):
    code = "PROVIDER_UNAVAILABLE"


class ProviderResponseError(ProviderError):
    code = "PROVIDER_INVALID_RESPONSE"


class ClinicDataProvider(ABC):
    @abstractmethod
    async def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        """Return normalized, unverified listings for validated search input."""
