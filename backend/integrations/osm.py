import re
from collections.abc import Mapping
from typing import Any


OSM_ELEMENT_TYPES = frozenset({"node", "way", "relation"})
_OSM_ID_PATTERN = re.compile(r"(?:^|[\s:/])(?:osm:)?(node|way|relation)/(\d+)(?:$|[\s])", re.IGNORECASE)


def normalize_osm_identity(
    source_type: Any,
    source_id: Any,
) -> tuple[str, int] | None:
    if not isinstance(source_type, str):
        return None
    normalized_type = source_type.strip().casefold().removeprefix("osm:")
    if normalized_type not in OSM_ELEMENT_TYPES:
        return None
    if isinstance(source_id, bool):
        return None
    try:
        normalized_id = int(source_id)
    except (TypeError, ValueError):
        return None
    return (normalized_type, normalized_id) if normalized_id > 0 else None


def extract_osm_identity(
    source_type: Any,
    source_id: Any,
    field_evidence: Mapping[str, Any] | None = None,
    source_data: Mapping[str, Any] | None = None,
) -> tuple[str, int] | None:
    direct_identity = normalize_osm_identity(source_type, source_id)
    if direct_identity is not None:
        return direct_identity

    for values in (field_evidence or {}, source_data or {}):
        for value in values.values():
            if not isinstance(value, str):
                continue
            match = _OSM_ID_PATTERN.search(value.strip())
            if match:
                return match.group(1).casefold(), int(match.group(2))
    return None


def osm_address_parts(tags: Mapping[str, Any]) -> dict[str, str | None]:
    full = _tag_text(tags, "addr:full")
    return {
        "address": full
        or ", ".join(
            part
            for part in (
                _tag_text(tags, "addr:housenumber"),
                _tag_text(tags, "addr:street"),
                _first_tag(tags, "addr:suburb", "addr:locality", "addr:neighbourhood"),
                _first_tag(tags, "addr:city", "addr:town", "addr:municipality"),
            )
            if part
        )
        or None,
        "housenumber": _tag_text(tags, "addr:housenumber"),
        "street": _tag_text(tags, "addr:street"),
        "locality": _first_tag(tags, "addr:suburb", "addr:locality", "addr:neighbourhood"),
        "city": _first_tag(tags, "addr:city", "addr:town", "addr:municipality"),
        "postal_code": _first_tag(tags, "addr:postcode", "addr:postalcode"),
    }


def address_status(parts: Mapping[str, str | None]) -> str:
    if not any(parts.get(key) for key in ("address", "housenumber", "street", "locality", "city", "postal_code")):
        return "unknown"
    if parts.get("postal_code") and not any(
        parts.get(key) for key in ("address", "housenumber", "street", "locality", "city")
    ):
        return "incomplete"
    return "complete"


def _first_tag(tags: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _tag_text(tags, key)
        if value:
            return value
    return None


def _tag_text(tags: Mapping[str, Any], key: str) -> str | None:
    value = tags.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None
