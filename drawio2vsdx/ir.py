"""Intermediate representation (IR) between the draw.io reader and the Visio writer.

The IR is format-neutral on purpose: units are draw.io pixels, Y axis points down,
and every geometry is *absolute* on the page (already resolved through parents).
The writer is responsible for converting to Visio units and coordinate system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CellKind(str, Enum):
    VERTEX = "vertex"
    EDGE = "edge"
    GROUP = "group"  # vertex without own drawing, used only to group children


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def union(self, other: "Rect") -> "Rect":
        x = min(self.x, other.x)
        y = min(self.y, other.y)
        return Rect(x, y, max(self.right, other.right) - x, max(self.bottom, other.bottom) - y)


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Cell:
    id: str
    kind: CellKind
    parent_id: str | None
    layer_id: str | None
    value: str = ""
    style: dict[str, str] = field(default_factory=dict)
    # Geometry relative to the parent, exactly as stored in draw.io.
    rel_geometry: Rect | None = None
    # Absolute geometry on the page (pixels, Y down). None for edges without geometry.
    geometry: Rect | None = None
    relative: bool = False  # mxGeometry relative=1 (edge labels, relative children)
    offset: Point | None = None  # mxPoint as="offset"
    # Edge-specific
    source_id: str | None = None
    target_id: str | None = None
    source_point: Point | None = None  # absolute
    target_point: Point | None = None  # absolute
    points: list[Point] = field(default_factory=list)  # absolute waypoints
    # Data from <object>/<UserObject> wrappers (label excluded).
    attributes: dict[str, str] = field(default_factory=dict)
    visible: bool = True
    collapsed: bool = False
    children: list[str] = field(default_factory=list)  # ids, z-order


@dataclass
class Layer:
    id: str
    name: str
    visible: bool = True
    locked: bool = False


@dataclass
class Page:
    id: str
    name: str
    # Model attributes (pixels)
    page_width: float = 850.0
    page_height: float = 1100.0
    background: str | None = None
    layers: list[Layer] = field(default_factory=list)
    cells: dict[str, Cell] = field(default_factory=dict)  # insertion order == document order
    top_level: list[str] = field(default_factory=list)  # ids of layer children, z-order

    def content_bounds(self) -> Rect | None:
        """Bounding box of every visible cell with absolute geometry (pixels)."""
        box: Rect | None = None
        for cell in self.cells.values():
            for r in _cell_extent(cell):
                box = r if box is None else box.union(r)
        return box


def _cell_extent(cell: Cell) -> list[Rect]:
    out: list[Rect] = []
    if not cell.visible:
        return out
    if cell.kind == CellKind.EDGE:
        pts = [p for p in (cell.source_point, cell.target_point) if p is not None] + cell.points
        out.extend(Rect(p.x, p.y, 0, 0) for p in pts)
    elif cell.geometry is not None and not cell.relative:
        out.append(cell.geometry)
    return out


@dataclass
class Document:
    pages: list[Page] = field(default_factory=list)
    source_path: str | None = None
