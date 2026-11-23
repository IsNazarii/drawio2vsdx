"""Structural checks of a .vsdx package (brief §7.1 item 1).

Used by the test-suite and available as ``python -m drawio2vsdx.validate FILE...``.
LibreOffice is more forgiving than Visio, so these checks catch the "repair" class
of problems that no renderer would show.
"""

from __future__ import annotations

import io
import posixpath
import sys
import zipfile
from pathlib import Path

from lxml import etree

from ._console import utf8_stdio
from .writer.xmlutil import NS_CT, NS_R, NS_RELS, NS_VISIO, REL_DOCUMENT

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)
_V = f"{{{NS_VISIO}}}"


def _rels_name(part: str) -> str:
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def _source_of_rels(rels: str) -> str:
    d, f = posixpath.split(rels)
    return posixpath.join(posixpath.dirname(d), f[: -len(".rels")])


def check_vsdx(source: Path | bytes) -> list[str]:
    """Return a list of problems (empty == OK)."""
    problems: list[str] = []
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        return [f"not a zip file: {exc}"]
    names = [i.filename for i in zf.infolist() if not i.is_dir()]
    if len(names) != len(set(names)):
        problems.append("duplicate zip entries")
    if "[Content_Types].xml" not in names:
        return problems + ["missing [Content_Types].xml"]

    xml: dict[str, etree._Element] = {}
    for n in names:
        if n.endswith((".xml", ".rels")):
            try:
                xml[n] = etree.fromstring(zf.read(n), _PARSER)
            except etree.XMLSyntaxError as exc:
                problems.append(f"{n}: not well-formed XML: {exc}")
    if problems:
        return problems

    # Content types
    ct = xml["[Content_Types].xml"]
    defaults = {d.get("Extension", "").lower() for d in ct.iterchildren(f"{{{NS_CT}}}Default")}
    overrides = {o.get("PartName", "").lstrip("/"): o.get("ContentType") for o in ct.iterchildren(f"{{{NS_CT}}}Override")}
    for n in names:
        if n == "[Content_Types].xml":
            continue
        base_name = posixpath.basename(n)
        ext = base_name.rsplit(".", 1)[-1].lower() if "." in base_name else ""
        if n not in overrides and ext not in defaults:
            problems.append(f"{n}: no content type")
    for o in overrides:
        if o not in names:
            problems.append(f"[Content_Types].xml: Override for missing part /{o}")

    # Relationships
    rel_ids: dict[str, set[str]] = {}
    for n in names:
        if not n.endswith(".rels"):
            continue
        src = _source_of_rels(n)
        base = posixpath.dirname(src)
        if n != "_rels/.rels" and src not in names:
            problems.append(f"{n}: rels for missing part {src}")
        ids: set[str] = set()
        for rel in xml[n].iterchildren(f"{{{NS_RELS}}}Relationship"):
            rid = rel.get("Id")
            if rid in ids:
                problems.append(f"{n}: duplicate relationship Id {rid}")
            ids.add(rid)
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target", "")
            resolved = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(base, target))
            if resolved not in names:
                problems.append(f"{n}: {rid} -> missing part {resolved}")
        rel_ids[src] = ids
    root_rels = xml.get("_rels/.rels")
    if root_rels is None or not any(r.get("Type") == REL_DOCUMENT for r in root_rels):
        problems.append("_rels/.rels: no Visio document relationship")

    # r:id references inside parts
    rid_attr = f"{{{NS_R}}}id"
    for n, root in xml.items():
        if n.endswith(".rels"):
            continue
        for el in root.iter():
            rid = el.get(rid_attr) if isinstance(el.tag, str) else None
            if rid is not None and rid not in rel_ids.get(n, set()):
                problems.append(f"{n}: r:id {rid} has no relationship")

    # Visio specifics
    for n, root in xml.items():
        local = etree.QName(root).localname
        if local == "Pages":
            ids, pnames = set(), set()
            for p in root.iterchildren(f"{_V}Page"):
                if p.get("ID") in ids:
                    problems.append(f"{n}: duplicate page ID {p.get('ID')}")
                ids.add(p.get("ID"))
                key = (p.get("NameU") or "").lower()
                if key in pnames:
                    problems.append(f"{n}: duplicate page name {p.get('NameU')!r}")
                pnames.add(key)
        elif local in ("PageContents", "MasterContents"):
            shape_ids: set[str] = set()
            for s in root.iter(f"{_V}Shape"):
                sid = s.get("ID")
                if sid in shape_ids:
                    problems.append(f"{n}: duplicate shape ID {sid}")
                shape_ids.add(sid)
            for c in root.iter(f"{_V}Connect"):
                for attr in ("FromSheet", "ToSheet"):
                    if c.get(attr) not in shape_ids:
                        problems.append(f"{n}: Connect {attr}={c.get(attr)} refers to a missing shape")
    return problems


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    argv = sys.argv[1:] if argv is None else argv
    bad = 0
    for arg in argv:
        problems = check_vsdx(Path(arg))
        print(f"{arg}: {'OK' if not problems else 'FAILED'}")
        for p in problems:
            print("  -", p)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
