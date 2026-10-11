from dataclasses import dataclass
import os


DEFAULT_OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 20.0
DEFAULT_NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
DEFAULT_GEOCODING_TIMEOUT_SECONDS = 10.0
DEFAULT_GEOCODING_MIN_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class ProviderSettings:
    overpass_endpoint: str = DEFAULT_OVERPASS_ENDPOINT
    provider_timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS
    nominatim_endpoint: str = DEFAULT_NOMINATIM_ENDPOINT
    geocoding_timeout_seconds: float = DEFAULT_GEOCODING_TIMEOUT_SECONDS
    geocoding_min_interval_seconds: float = DEFAULT_GEOCODING_MIN_INTERVAL_SECONDS

    @classmethod
    def from_environment(cls) -> "ProviderSettings":
        endpoint = os.getenv("CLINIC_PROVIDER_OVERPASS_ENDPOINT", DEFAULT_OVERPASS_ENDPOINT)
        timeout_value = os.getenv(
            "CLINIC_PROVIDER_TIMEOUT_SECONDS",
            str(DEFAULT_PROVIDER_TIMEOUT_SECONDS),
        )
        try:
            timeout = float(timeout_value)
        except ValueError as exc:
            raise ValueError("CLINIC_PROVIDER_TIMEOUT_SECONDS must be a number") from exc
        if not endpoint.strip():
            raise ValueError("CLINIC_PROVIDER_OVERPASS_ENDPOINT must not be empty")
        if timeout <= 0:
            raise ValueError("CLINIC_PROVIDER_TIMEOUT_SECONDS must be greater than zero")
        geocoding_endpoint = os.getenv(
            "CLINIC_GEOCODING_NOMINATIM_ENDPOINT",
            DEFAULT_NOMINATIM_ENDPOINT,
        )
        geocoding_timeout_value = os.getenv(
            "CLINIC_GEOCODING_TIMEOUT_SECONDS",
            str(DEFAULT_GEOCODING_TIMEOUT_SECONDS),
        )
        interval_value = os.getenv(
            "CLINIC_GEOCODING_MIN_INTERVAL_SECONDS",
            str(DEFAULT_GEOCODING_MIN_INTERVAL_SECONDS),
        )
        try:
            geocoding_timeout = float(geocoding_timeout_value)
            interval = float(interval_value)
        except ValueError as exc:
            raise ValueError(
                "Geocoding timeout and interval settings must be numbers"
            ) from exc
        if not geocoding_endpoint.strip():
            raise ValueError("CLINIC_GEOCODING_NOMINATIM_ENDPOINT must not be empty")
        if geocoding_timeout <= 0:
            raise ValueError("CLINIC_GEOCODING_TIMEOUT_SECONDS must be greater than zero")
        if interval < 0:
            raise ValueError("CLINIC_GEOCODING_MIN_INTERVAL_SECONDS must not be negative")
        return cls(
            overpass_endpoint=endpoint,
            provider_timeout_seconds=timeout,
            nominatim_endpoint=geocoding_endpoint,
            geocoding_timeout_seconds=geocoding_timeout,
            geocoding_min_interval_seconds=interval,
        )
