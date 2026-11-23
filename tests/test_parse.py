from __future__ import annotations

from conftest import FEATURES

from drawio2vsdx.ir import CellKind
from drawio2vsdx.reader.parse import parse_file
from drawio2vsdx.reader.style import STYLE_NAMES, parse_style


def test_parse_style():
    s = parse_style("ellipse;shape=cloud;whiteSpace=wrap;html=1;fillColor=#dae8fc;")
    assert s["shape"] == "cloud" and s["fillColor"] == "#dae8fc" and s[STYLE_NAMES] == "ellipse"
    assert parse_style(None) == {} and parse_style("") == {}


def test_group_children_absolute():
    page = parse_file(FEATURES / "group.drawio").pages[0]
    g, a, b = page.cells["g1"], page.cells["a"], page.cells["b"]
    assert g.children == ["a", "b"] and page.top_level == ["g1"]
    assert (a.geometry.x, a.geometry.y) == (200, 150)
    assert (b.geometry.x, b.geometry.y, b.geometry.width) == (320, 210, 80)
    assert a.layer_id == "1"
    bounds = page.content_bounds()
    assert (bounds.x, bounds.y, bounds.right, bounds.bottom) == (200, 150, 400, 250)


def test_userobject_attributes():
    cell = parse_file(FEATURES / "userobject.drawio").pages[0].cells["dev1"]
    assert cell.value == "Router-1" and cell.kind == CellKind.VERTEX
    assert cell.attributes == {"ip": "10.0.0.1", "model": "ISR4331"}


def test_layers():
    page = parse_file(FEATURES / "layers.drawio").pages[0]
    assert [(l.name, l.visible) for l in page.layers] == [("", True), ("Overlay", True), ("Hidden", False)]
    assert page.cells["y"].layer_id == "L2"
    assert page.cells["z"].visible is False
    assert page.top_level == ["x", "y", "z"]
