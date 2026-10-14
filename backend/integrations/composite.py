import logging
from collections.abc import Iterable

from backend.integrations.osm import extract_osm_identity
from backend.integrations.provider import (
    ClinicDataProvider,
    ProviderError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from backend.schemas.provider import ClinicListing, ClinicSearchParams

logger = logging.getLogger(__name__)


class CompositeClinicProvider(ClinicDataProvider):
    def __init__(self, providers: Iterable[ClinicDataProvider]) -> None:
        self.providers = list(providers)
        self.last_source_status: dict[str, str] = {}

    async def search(self, params: ClinicSearchParams) -> list[ClinicListing]:
        results: list[ClinicListing] = []
        failures: list[ProviderError] = []
        self.last_source_status = {}
        for index, provider in enumerate(self.providers):
            source_name = _source_name(provider, index, self.providers)
            try:
                source_results = await provider.search(params)
                results.extend(source_results)
                self.last_source_status[source_name] = "ok"
            except ProviderError as exc:
                failures.append(exc)
                self.last_source_status[source_name] = _failure_status(exc)
                logger.warning(
                    "Clinic search source failed; continuing with other sources",
                    extra={
                        "provider_name": source_name,
                        "provider_error_code": exc.code,
                        "provider_failure_category": _failure_category(exc),
                    },
                )
        if not results and failures and len(failures) == len(self.providers):
            response_failure = next(
                (failure for failure in failures if isinstance(failure, ProviderResponseError)),
                None,
            )
            if response_failure is not None:
                response_failure.source_status = self.last_source_status
                raise response_failure
            error = ProviderUnavailableError("All clinic data sources failed.")
            error.source_status = self.last_source_status
            raise error from failures[0]
        return _merge_and_rank(results)


def _source_name(
    provider: ClinicDataProvider,
    index: int,
    providers: list[ClinicDataProvider],
) -> str:
    name = type(provider).__name__
    if "Overpass" in name:
        return "overpass"
    if "Directory" in name:
        return "directory"
    base_name = name.removesuffix("ClinicProvider").casefold()
    if sum(type(item) is type(provider) for item in providers) > 1:
        return f"{base_name}_{index + 1}"
    return base_name


def _failure_status(error: ProviderError) -> str:
    if isinstance(error, ProviderResponseError):
        return "invalid_response"
    if isinstance(error, ProviderUnavailableError):
        return "unavailable"
    return "error"


def _failure_category(error: ProviderError) -> str:
    return {
        "PROVIDER_UNAVAILABLE": "upstream_unavailable",
        "PROVIDER_INVALID_RESPONSE": "invalid_response",
        "DIRECTORY_UNAVAILABLE": "directory_unavailable",
    }.get(error.code, "provider_error")


def _merge_and_rank(items: list[ClinicListing]) -> list[ClinicListing]:
    merged: list[ClinicListing] = []
    for item in sorted(items, key=lambda listing: listing.distance_km or float("inf")):
        duplicate = next((existing for existing in merged if _same_identity(existing, item)), None)
        if duplicate is None:
            merged.append(item)
        else:
            merged[merged.index(duplicate)] = _merge_duplicate(duplicate, item)
    return sorted(merged, key=lambda listing: (listing.distance_km is None, listing.distance_km or 0))


def _same_identity(left: ClinicListing, right: ClinicListing) -> bool:
    left_identity = extract_osm_identity(
        left.source_type, left.source_id, left.field_evidence, left.source_data
    )
    right_identity = extract_osm_identity(
        right.source_type, right.source_id, right.field_evidence, right.source_data
    )
    if left_identity is not None or right_identity is not None:
        return left_identity is not None and left_identity == right_identity
    if (
        left.source_type == right.source_type == "directory"
        and left.clinic_id is not None
        and left.clinic_id == right.clinic_id
    ):
        return True
    return False


def _merge_duplicate(first: ClinicListing, second: ClinicListing) -> ClinicListing:
    preferred = max(
        (first, second),
        key=lambda listing: (
            _richness(listing),
            listing.verification_status == "verified",
            -(listing.distance_km or float("inf")),
        ),
    )
    other = second if preferred is first else first
    identity = extract_osm_identity(
        preferred.source_type, preferred.source_id, preferred.field_evidence, preferred.source_data
    ) or extract_osm_identity(
        other.source_type, other.source_id, other.field_evidence, other.source_data
    )
    if identity is not None:
        preferred.source_type, preferred.source_id = identity
    if _normalized_name(preferred.name) != _normalized_name(other.name):
        logger.warning(
            "OSM duplicate records have conflicting names; preserving preferred name",
            extra={"osm_source_type": identity[0] if identity else None, "osm_source_id": identity[1] if identity else None},
        )
    for field in ("address", "locality", "city", "postal_code", "phone", "website"):
        if getattr(preferred, field) is None and getattr(other, field) is not None:
            setattr(preferred, field, getattr(other, field))
    if not preferred.services and other.services:
        preferred.services = list(other.services)
    preferred.data_sources = list(dict.fromkeys(preferred.data_sources + other.data_sources))
    preferred.source_data = {**other.source_data, **preferred.source_data}
    preferred.field_sources = {**other.field_sources, **preferred.field_sources}
    preferred.field_evidence = {**other.field_evidence, **preferred.field_evidence}
    return preferred


def _richness(listing: ClinicListing) -> int:
    return sum(
        bool(getattr(listing, field))
        for field in ("address", "locality", "city", "postal_code", "phone", "website")
    ) + len(listing.services)


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())
