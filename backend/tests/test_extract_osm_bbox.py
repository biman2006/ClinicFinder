from pathlib import Path

import osmium

from backend.scripts.extract_osm_bbox import extract_bbox


def test_extract_bbox_preserves_selected_objects_and_way_references(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.osm.pbf"
    output = tmp_path / "output.osm.pbf"
    writer = osmium.SimpleWriter(source)
    writer.add_node(osmium.osm.mutable.Node(id=1, location=(88.5, 22.5), tags={"name": "inside"}))
    writer.add_node(osmium.osm.mutable.Node(id=2, location=(90.0, 24.0)))
    writer.add_node(osmium.osm.mutable.Node(id=3, location=(89.0, 24.0)))
    writer.add_way(osmium.osm.mutable.Way(id=10, nodes=[1, 3], tags={"highway": "service"}))
    writer.close()

    extract_bbox(
        source,
        output,
        bbox=(88.0, 22.0, 88.75, 23.0),
        progress_interval_seconds=0.001,
    )

    seen: list[tuple[str, int]] = []

    class Reader(osmium.SimpleHandler):
        def node(self, obj):
            seen.append(("node", obj.id))

        def way(self, obj):
            seen.append(("way", obj.id))

    Reader().apply_file(output, locations=True)
    assert ("way", 10) in seen
    assert ("node", 1) in seen
    assert ("node", 3) in seen
    assert ("node", 2) not in seen
