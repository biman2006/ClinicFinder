"""Extract a reference-complete OSM PBF bounding box with PyOsmium only.

This is intentionally a streaming extractor. It does not build a Python
representation of the input file. PyOsmium keeps node locations in its native
location store, and BackReferenceWriter resolves the references needed by
selected ways when the output is closed.

The selection follows osmium-tool's complete_ways idea: nodes in the box and
ways with at least one node in the box are selected, while all nodes referenced
by selected ways are retained. Relations are retained when they directly
reference a selected node or way. Relations whose geometry is only implied by
indirect or unsupported members may not be selected.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import logging
import os
import time
from pathlib import Path
from typing import Any

try:
    import osmium
except ImportError:  # pragma: no cover - exercised by the actionable error
    osmium = None

logger = logging.getLogger(__name__)

DEFAULT_INPUT = Path("backend/data/eastern-zone-261011.osm.pbf")
DEFAULT_OUTPUT = Path("backend/data/kolkata.osm.pbf")
DEFAULT_BBOX = (88.05, 22.25, 88.75, 23.05)


class ExtractionError(RuntimeError):
    """Raised when PyOsmium cannot provide a safe extraction pipeline."""


def _require_pyosmium() -> Any:
    if osmium is None:
        raise ExtractionError(
            "PyOsmium is required. Install the project dependencies with "
            "the backend Python environment (pip install -r backend/requirements.txt)."
        )
    required = (
        "FileProcessor",
        "BackReferenceWriter",
    )
    missing = [name for name in required if not hasattr(osmium, name)]
    if not hasattr(osmium.FileProcessor, "with_locations"):
        missing.append("FileProcessor.with_locations")
    if missing:
        raise ExtractionError(
            "The installed PyOsmium does not support safe reference-complete "
            f"extraction; missing: {', '.join(missing)}."
        )
    return osmium


def _version() -> str:
    try:
        return importlib.metadata.version("osmium")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _inside(bbox: tuple[float, float, float, float], lon: float, lat: float) -> bool:
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def _way_intersects(
    obj: Any, bbox: tuple[float, float, float, float]
) -> bool:
    return any(
        _inside(bbox, node.lon, node.lat)
        for node in obj.nodes
        if node.location.valid()
    )


def extract_bbox(
    input_path: str | Path,
    output_path: str | Path,
    *,
    bbox: tuple[float, float, float, float] = DEFAULT_BBOX,
    progress_interval_seconds: float = 30.0,
) -> None:
    """Extract a reference-complete bbox without storing all objects in Python."""
    pyosmium = _require_pyosmium()
    if progress_interval_seconds <= 0:
        raise ValueError("Progress interval must be greater than zero.")
    if not (
        -180 <= bbox[0] < bbox[2] <= 180
        and -90 <= bbox[1] < bbox[3] <= 90
    ):
        raise ValueError("Bounding box must be west,south,east,north.")

    source = Path(input_path)
    destination = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"Input PBF does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".part" + destination.suffix)
    if temporary.exists():
        raise ExtractionError(f"Temporary output already exists: {temporary}")

    logger.info("Using PyOsmium %s", _version())
    logger.info("Starting streaming extraction: %s -> %s", source, destination)
    processed = 0
    selected = 0
    selected_refs: set[tuple[str, int]] = set()
    started = time.monotonic()
    last_progress = started

    def progress(force: bool = False) -> None:
        nonlocal last_progress
        now = time.monotonic()
        if not force and now - last_progress < progress_interval_seconds:
            return
        logger.info(
            "OSM extraction progress: %d objects processed, %d selected, "
            "%.1f seconds elapsed",
            processed,
            selected,
            now - started,
        )
        last_progress = now

    def write_selected(obj: Any) -> None:
        if obj.is_node():
            writer.add_node(pyosmium.osm.mutable.create_mutable_node(obj))
        elif obj.is_way():
            writer.add_way(pyosmium.osm.mutable.create_mutable_way(obj))
        elif obj.is_relation():
            writer.add_relation(pyosmium.osm.mutable.create_mutable_relation(obj))

    writer = pyosmium.BackReferenceWriter(
        temporary,
        source,
        overwrite=True,
        remove_tags=False,
        relation_depth=1,
    )
    writer_closed = False
    try:
        processor = pyosmium.FileProcessor(source).with_locations("flex_mem")
        for obj in processor:
            processed += 1
            progress()
            if obj.is_node() and _inside(bbox, obj.lon, obj.lat):
                write_selected(obj)
                selected += 1
                selected_refs.add(("n", int(obj.id)))
            elif obj.is_way() and _way_intersects(obj, bbox):
                write_selected(obj)
                selected += 1
                selected_refs.add(("w", int(obj.id)))
            elif obj.is_relation() and any(
                (member.type, int(member.ref)) in selected_refs
                for member in obj.members
                if member.type in {"n", "w", "r"}
            ):
                write_selected(obj)
                selected += 1
                selected_refs.add(("r", int(obj.id)))
        progress(force=True)
        writer.close()
        writer_closed = True
        os.replace(temporary, destination)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExtractionError(f"Could not extract OSM PBF: {exc}") from exc
    finally:
        try:
            if not writer_closed:
                writer.close()
        finally:
            if temporary.exists():
                temporary.unlink()
    logger.info(
        "OSM extraction complete: %d objects processed, %d selected, %.1f seconds elapsed",
        processed,
        selected,
        time.monotonic() - started,
    )


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        values = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Bounding box must be west,south,east,north."
        ) from exc
    if len(values) != 4:
        raise argparse.ArgumentTypeError(
            "Bounding box must be west,south,east,north."
        )
    return values  # type: ignore[return-value]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--bbox",
        type=_parse_bbox,
        default=DEFAULT_BBOX,
        help="west,south,east,north (default: 88.05,22.25,88.75,23.05)",
    )
    parser.add_argument("--progress-interval-seconds", type=float, default=30.0)
    args = parser.parse_args()
    extract_bbox(
        args.input,
        args.output,
        bbox=args.bbox,
        progress_interval_seconds=args.progress_interval_seconds,
    )


if __name__ == "__main__":
    main()
