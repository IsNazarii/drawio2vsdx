"""``<mxGraphModel>`` -> IR :class:`~drawio2vsdx.ir.Page`.

Handles ``<object>``/``<UserObject>`` wrappers, layers (children of the root cell) and
resolves relative coordinates (groups, containers) into absolute page coordinates.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from ..ir import Cell, CellKind, Document, Layer, Page, Point, Rect
from .decode import RawDiagram, load_diagrams
from .style import is_true, parse_style

WRAPPER_TAGS = ("object", "UserObject")
# Wrapper attributes that are not user data.
_WRAPPER_RESERVED = {"id", "label", "placeholders"}


def _f(elem: etree._Element | None, name: str, default: float = 0.0) -> float:
    if elem is None:
        return default
    val = elem.get(name)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _point(elem: etree._Element) -> Point:
    return Point(_f(elem, "x"), _f(elem, "y"))


def _iter_cells(root: etree._Element):
    """Yield (mxCell element, wrapper element or None)."""
    for child in root:
        if not isinstance(child.tag, str):
            continue
        if child.tag == "mxCell":
            yield child, None
        elif child.tag in WRAPPER_TAGS:
            inner = child.find("mxCell")
            if inner is None:
                inner = etree.Element("mxCell")
            yield inner, child


def parse_model(raw: RawDiagram) -> Page:
    model = raw.model
    page = Page(
        id=raw.id,
        name=raw.name,
        page_width=_f(model, "pageWidth", 850.0),
        page_height=_f(model, "pageHeight", 1100.0),
        background=model.get("background") or None,
    )
    root = model.find("root")
    if root is None:
        return page

    root_id: str | None = None
    raw_geo: dict[str, etree._Element | None] = {}

    for elem, wrapper in _iter_cells(root):
        cid = (wrapper.get("id") if wrapper is not None else elem.get("id")) or ""
        parent = elem.get("parent")
        if root_id is None and parent is None:
            root_id = cid
            continue
        style = parse_style(elem.get("style"))
        if parent == root_id:
            page.layers.append(
                Layer(
                    id=cid,
                    name=(wrapper.get("label") if wrapper is not None else elem.get("value")) or "",
                    visible=elem.get("visible", "1") != "0",
                    locked=is_true(style, "locked"),
                )
            )
            continue

        if elem.get("edge") == "1":
            kind = CellKind.EDGE
        elif elem.get("vertex") == "1":
            kind = CellKind.VERTEX
        else:
            kind = CellKind.GROUP

        attrs: dict[str, str] = {}
        if wrapper is not None:
            value = wrapper.get("label", "")
            attrs = {k: v for k, v in wrapper.attrib.items() if k not in _WRAPPER_RESERVED}
            if wrapper.get("placeholders") is not None:
                attrs["placeholders"] = wrapper.get("placeholders", "")
        else:
            value = elem.get("value", "")

        geo = elem.find("mxGeometry")
        raw_geo[cid] = geo
        cell = Cell(
            id=cid,
            kind=kind,
            parent_id=parent,
            layer_id=None,
            value=value,
            style=style,
            attributes=attrs,
            visible=elem.get("visible", "1") != "0",
            collapsed=elem.get("collapsed") == "1",
            source_id=elem.get("source"),
            target_id=elem.get("target"),
        )
        if geo is not None:
            cell.rel_geometry = Rect(_f(geo, "x"), _f(geo, "y"), _f(geo, "width"), _f(geo, "height"))
            cell.relative = geo.get("relative") == "1"
        page.cells[cid] = cell

    layer_ids = {layer.id for layer in page.layers}
    # Children lists (document order == z-order) and top-level list.
    for cell in page.cells.values():
        if cell.parent_id in layer_ids:
            page.top_level.append(cell.id)
        elif cell.parent_id in page.cells:
            page.cells[cell.parent_id].children.append(cell.id)

    origin_cache: dict[str, Point] = {}

    def origin_of(cid: str | None, depth: int = 0) -> Point:
        """Absolute top-left of a container cell (layers have origin 0,0)."""
        if cid is None or cid not in page.cells or depth > 100:
            return Point(0.0, 0.0)
        if cid in origin_cache:
            return origin_cache[cid]
        c = page.cells[cid]
        po = origin_of(c.parent_id, depth + 1)
        g = c.rel_geometry or Rect()
        if c.kind == CellKind.EDGE:
            res = po  # children of edges (labels) are handled by the edge writer
        else:
            res = Point(po.x + g.x, po.y + g.y)
        origin_cache[cid] = res
        return res

    def layer_of(cid: str, depth: int = 0) -> str | None:
        c = page.cells.get(cid)
        if c is None or depth > 100:
            return None
        if c.parent_id in layer_ids:
            return c.parent_id
        return layer_of(c.parent_id, depth + 1) if c.parent_id else None

    for cell in page.cells.values():
        cell.layer_id = layer_of(cell.id)
        geo = raw_geo.get(cell.id)
        po = origin_of(cell.parent_id)
        parent = page.cells.get(cell.parent_id or "")
        if cell.kind == CellKind.EDGE:
            if geo is not None:
                for pt in geo.iterchildren("mxPoint"):
                    p = _point(pt)
                    absp = Point(po.x + p.x, po.y + p.y)
                    if pt.get("as") == "sourcePoint":
                        cell.source_point = absp
                    elif pt.get("as") == "targetPoint":
                        cell.target_point = absp
                    elif pt.get("as") == "offset":
                        cell.offset = p
                arr = geo.find("Array")
                if arr is not None and arr.get("as") == "points":
                    cell.points = [Point(po.x + p.x, po.y + p.y) for p in map(_point, arr.iterchildren("mxPoint"))]
            continue

        rg = cell.rel_geometry
        if rg is None:
            continue
        if geo is not None:
            off = geo.find("mxPoint[@as='offset']")
            if off is not None:
                cell.offset = _point(off)
        if cell.relative:
            if parent is not None and parent.kind == CellKind.EDGE:
                continue  # edge label: placed along the edge later
            pg = parent.geometry if parent is not None and parent.geometry else Rect()
            ox = cell.offset.x if cell.offset else 0.0
            oy = cell.offset.y if cell.offset else 0.0
            cell.geometry = Rect(pg.x + rg.x * pg.width + ox, pg.y + rg.y * pg.height + oy, rg.width, rg.height)
        else:
            cell.geometry = Rect(po.x + rg.x, po.y + rg.y, rg.width, rg.height)

    for layer in page.layers:
        if not layer.visible:
            for cell in page.cells.values():
                if cell.layer_id == layer.id:
                    cell.visible = False
    return page


def parse_file(path: Path) -> Document:
    doc = Document(source_path=str(path))
    for raw in load_diagrams(Path(path)):
        doc.pages.append(parse_model(raw))
    return doc
