"""OPC package writer. The package is built from a template ``.vsdx``.

Everything that is not a page (document.xml with stylesheets, masters, docProps,
theme ...) is copied from the template unchanged. Only pages, their rels, media and
the matching ``[Content_Types].xml`` overrides are regenerated. The first page of the
template provides the base ``PageSheet`` (so a template saved by Visio itself defines
the page defaults).
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from lxml import etree

from ..ir import Document
from .page import DEFAULT_SCALE, build_page_contents, build_page_sheet, compute_layout
from .xmlutil import CT_PAGE, NS_CT, NS_R, NS_RELS, NSMAP, REL_PAGE, REL_PAGES, to_bytes, v

PAGES_DIR = "visio/pages/"
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False)


@dataclass
class WriteOptions:
    scale: float = DEFAULT_SCALE
    use_page_size: bool = False
    template: Path | None = None


@dataclass
class _Template:
    parts: dict[str, bytes] = field(default_factory=dict)  # zip name -> bytes, in template order

    @classmethod
    def load(cls, path: Path | None) -> "_Template":
        if path is None:
            data = resources.files("drawio2vsdx.template").joinpath("blank.vsdx").read_bytes()
        else:
            data = Path(path).read_bytes()
        t = cls()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    t.parts[info.filename] = zf.read(info)
        return t

    def xml(self, name: str) -> etree._Element:
        return etree.fromstring(self.parts[name], _PARSER)


def _rels_name(part: str) -> str:
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def _find_pages_part(t: _Template) -> str:
    doc_rels = t.xml(_rels_name("visio/document.xml"))
    for rel in doc_rels:
        if rel.get("Type") == REL_PAGES:
            return posixpath.normpath(posixpath.join("visio", rel.get("Target")))
    raise ValueError("template has no pages relationship in visio/_rels/document.xml.rels")


def _template_page_sheet(t: _Template, pages_part: str) -> etree._Element | None:
    if pages_part not in t.parts:
        return None
    pages = t.xml(pages_part)
    page = pages.find(v("Page"))
    if page is None:
        return None
    return page.find(v("PageSheet"))


def write_vsdx(doc: Document, out: Path | io.BytesIO, options: WriteOptions | None = None) -> None:
    options = options or WriteOptions()
    t = _Template.load(options.template)
    pages_part = _find_pages_part(t)
    pages_dir = posixpath.dirname(pages_part) + "/"
    base_sheet = _template_page_sheet(t, pages_part)

    # Drop everything page-related from the template; it is regenerated below.
    parts = {n: b for n, b in t.parts.items() if not n.startswith(pages_dir) and not n.startswith("visio/media/")}

    ct = etree.fromstring(t.parts["[Content_Types].xml"], _PARSER)
    for ov in list(ct.iterchildren(f"{{{NS_CT}}}Override")):
        name = ov.get("PartName", "").lstrip("/")
        if name.startswith(pages_dir) and ov.get("ContentType") == CT_PAGE:
            ct.remove(ov)

    pages_root = etree.Element(v("Pages"), nsmap=NSMAP)
    pages_root.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    pages_rels = etree.Element(f"{{{NS_RELS}}}Relationships", nsmap={None: NS_RELS})

    names = unique_page_names([p.name for p in doc.pages])
    for i, page in enumerate(doc.pages, start=1):
        layout = compute_layout(page, options.scale, options.use_page_size)
        fname = f"page{i}.xml"
        rid = f"rId{i}"
        name = names[i - 1]
        pe = etree.SubElement(pages_root, v("Page"), ID=str(i - 1), NameU=name, Name=name)
        pe.append(build_page_sheet(base_sheet, layout))
        etree.SubElement(pe, v("Rel")).set(f"{{{NS_R}}}id", rid)
        etree.SubElement(pages_rels, f"{{{NS_RELS}}}Relationship", Id=rid, Type=REL_PAGE, Target=fname)

        parts[pages_dir + fname] = to_bytes(build_page_contents(page, layout))
        etree.SubElement(ct, f"{{{NS_CT}}}Override", PartName="/" + pages_dir + fname, ContentType=CT_PAGE)

    parts[pages_part] = to_bytes(pages_root)
    parts[_rels_name(pages_part)] = to_bytes(pages_rels)
    parts["[Content_Types].xml"] = to_bytes(ct)
    _fix_app_props(parts, doc)

    order = ["[Content_Types].xml"] + [n for n in parts if n != "[Content_Types].xml"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in order:
            zf.writestr(name, parts[name])
    data = buf.getvalue()
    if isinstance(out, io.BytesIO):
        out.write(data)
    else:
        Path(out).write_bytes(data)


def unique_page_names(names: list[str]) -> list[str]:
    """Visio requires unique (case-insensitive), non-empty page names; draw.io does not."""
    out: list[str] = []
    seen: set[str] = set()
    for i, name in enumerate(names, start=1):
        base = (name or "").strip() or f"Page-{i}"
        cand, n = base, 2
        while cand.lower() in seen:
            cand, n = f"{base} ({n})", n + 1
        seen.add(cand.lower())
        out.append(cand)
    return out


def _fix_app_props(parts: dict[str, bytes], doc: Document) -> None:
    """Visio lists page names in docProps/app.xml; a stale list is dropped rather than kept wrong."""
    name = "docProps/app.xml"
    if name not in parts:
        return
    root = etree.fromstring(parts[name], _PARSER)
    changed = False
    for child in list(root):
        if etree.QName(child).localname in ("HeadingPairs", "TitlesOfParts"):
            root.remove(child)
            changed = True
    if changed:
        parts[name] = to_bytes(root)
