"""IR page -> ``visio/pages/pageN.xml`` and its ``PageSheet``.

Stage 0: pages are written with correct size and no shapes yet.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from lxml import etree

from ..ir import Page, Rect
from .xmlutil import NSMAP, set_cell, v

DEFAULT_SCALE = 40 * 2.54  # px per inch; mxVsdxUtils (importer) and VsdxExport.CONVERSION_FACTOR
PAGE_MARGIN_PX = 20.0


@dataclass
class PageLayout:
    """Mapping from draw.io page pixels to Visio page inches."""

    scale: float  # px per inch
    origin_x: float  # draw.io x that maps to Visio x = 0
    origin_y: float  # draw.io y that maps to the top edge of the Visio page
    width_in: float
    height_in: float

    def x(self, px: float) -> float:
        return (px - self.origin_x) / self.scale

    def y(self, py: float) -> float:
        # draw.io Y grows down from the top; Visio Y grows up from the bottom.
        return self.height_in - (py - self.origin_y) / self.scale

    def length(self, px: float) -> float:
        return px / self.scale


def compute_layout(page: Page, scale: float = DEFAULT_SCALE, use_page_size: bool = False) -> PageLayout:
    bounds = page.content_bounds()
    if use_page_size or bounds is None:
        box = Rect(0, 0, page.page_width, page.page_height)
        if bounds is not None:
            box = box.union(bounds)
    else:
        m = PAGE_MARGIN_PX
        box = Rect(bounds.x - m, bounds.y - m, bounds.width + 2 * m, bounds.height + 2 * m)
    return PageLayout(
        scale=scale,
        origin_x=box.x,
        origin_y=box.y,
        width_in=max(box.width, 1.0) / scale,
        height_in=max(box.height, 1.0) / scale,
    )


def build_page_sheet(template_sheet: etree._Element | None, layout: PageLayout) -> etree._Element:
    sheet = deepcopy(template_sheet) if template_sheet is not None else etree.Element(v("PageSheet"), nsmap=NSMAP)
    set_cell(sheet, "PageWidth", layout.width_in)
    set_cell(sheet, "PageHeight", layout.height_in)
    set_cell(sheet, "PageScale", 1, "IN_F")
    set_cell(sheet, "DrawingScale", 1, "IN_F")
    return sheet


def build_page_contents(page: Page, layout: PageLayout) -> etree._Element:
    root = etree.Element(v("PageContents"), nsmap=NSMAP)
    root.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    # Shapes / Connects are added by later stages; Visio accepts an empty PageContents.
    return root
