from dataclasses import dataclass


@dataclass(frozen=True)
class LocalLocationSuggestion:
    name: str
    context: str
    latitude: float
    longitude: float
    aliases: tuple[str, ...]
    source: str
    source_type: str
    source_id: int
    precision: str = "approximate"

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "context": self.context,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "aliases": list(self.aliases),
            "source": self.source,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "precision": self.precision,
        }


# Coordinates and OSM identities were obtained from the existing Nominatim
# adapter on 2026-10-11. This small catalogue is intentionally not exhaustive.
KOLKATA_LOCATION_SUGGESTIONS = (
    LocalLocationSuggestion(
        "New Town",
        "Kolkata Metropolitan Area, North 24 Parganas, West Bengal",
        22.5882834,
        88.4734476,
        ("newtown", "new town"),
        "OpenStreetMap",
        "node",
        3320334805,
    ),
    LocalLocationSuggestion(
        "Biswa Bangla Gate",
        "Action Area I, New Town, North 24 Parganas, West Bengal",
        22.5786355,
        88.4720939,
        ("biswa bangla", "biswa bangla gate"),
        "OpenStreetMap",
        "relation",
        17304258,
    ),
    LocalLocationSuggestion(
        "Salt Lake (Bidhannagar)",
        "Kolkata Metropolitan Area, North 24 Parganas, West Bengal",
        22.590425,
        88.41692,
        ("salt lake", "bidhannagar"),
        "OpenStreetMap",
        "way",
        1104715041,
    ),
    LocalLocationSuggestion(
        "Sector V",
        "Bidhannagar, Kolkata Metropolitan Area, North 24 Parganas, West Bengal",
        22.5754543,
        88.4322569,
        ("sector v", "sector 5", "salt lake sector v"),
        "OpenStreetMap",
        "node",
        10792425145,
    ),
)


def normalize_suggestion_query(value: str) -> str:
    return " ".join(value.casefold().split())


def find_local_location_suggestions(query: str) -> list[LocalLocationSuggestion]:
    normalized = normalize_suggestion_query(query)
    if not normalized:
        return []
    exact = [
        suggestion
        for suggestion in KOLKATA_LOCATION_SUGGESTIONS
        if normalized in suggestion.aliases
    ]
    if exact:
        return exact
    return [
        suggestion
        for suggestion in KOLKATA_LOCATION_SUGGESTIONS
        if any(alias.startswith(normalized) for alias in suggestion.aliases)
    ]
