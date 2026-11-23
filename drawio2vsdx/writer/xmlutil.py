"""Namespaces and small helpers for building Visio XML."""

from __future__ import annotations

from lxml import etree

NS_VISIO = "http://schemas.microsoft.com/office/visio/2012/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"

REL_PAGES = "http://schemas.microsoft.com/visio/2010/relationships/pages"
REL_PAGE = "http://schemas.microsoft.com/visio/2010/relationships/page"
REL_MASTER = "http://schemas.microsoft.com/visio/2010/relationships/master"
REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
REL_DOCUMENT = "http://schemas.microsoft.com/visio/2010/relationships/document"

CT_PAGE = "application/vnd.ms-visio.page+xml"
CT_PAGES = "application/vnd.ms-visio.pages+xml"

NSMAP = {None: NS_VISIO, "r": NS_R}


def v(tag: str) -> str:
    return f"{{{NS_VISIO}}}{tag}"


def fmt(value: float | int | str) -> str:
    """Format a cell value the way Visio does (no exponent, trimmed zeros)."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if value != value:  # NaN
        return "0"
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def cell(parent: etree._Element, name: str, value, unit: str | None = None, formula: str | None = None) -> etree._Element:
    el = etree.SubElement(parent, v("Cell"), N=name, V=fmt(value))
    if unit:
        el.set("U", unit)
    if formula:
        el.set("F", formula)
    return el


def set_cell(parent: etree._Element, name: str, value, unit: str | None = None) -> etree._Element:
    """Set (or create) a direct child ``<Cell N=name>``."""
    for el in parent.iterchildren(v("Cell")):
        if el.get("N") == name:
            el.set("V", fmt(value))
            el.attrib.pop("F", None)
            if unit:
                el.set("U", unit)
            return el
    return cell(parent, name, value, unit)


def to_bytes(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
