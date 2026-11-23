"""Load a draw.io file of any supported container format and return decoded diagrams.

Supported inputs:
* ``.drawio`` / ``.xml``: ``<mxfile>`` with plain or compressed ``<diagram>`` children,
  or a bare ``<mxGraphModel>``;
* ``.drawio.svg`` / ``.svg``: ``<svg content="<mxfile ...>">``;
* ``.drawio.png`` / ``.png``: PNG with a ``tEXt``/``zTXt``/``iTXt`` chunk named
  ``mxfile`` (current draw.io) or ``mxGraphModel`` (old versions).

Compressed diagrams are: base64 -> raw deflate -> URL-decoding (``decodeURIComponent``),
mirroring ``Graph.decompress`` in draw.io.
"""

from __future__ import annotations

import base64
import binascii
import struct
import urllib.parse
import zlib
from dataclasses import dataclass
from pathlib import Path

from lxml import etree


class DecodeError(Exception):
    """Input file could not be understood as a draw.io diagram."""


@dataclass
class RawDiagram:
    id: str
    name: str
    model: etree._Element  # <mxGraphModel>


_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, remove_blank_text=True)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _parse_xml(data: bytes | str, what: str) -> etree._Element:
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        return etree.fromstring(data.strip(), _PARSER)
    except etree.XMLSyntaxError as exc:
        raise DecodeError(f"{what}: invalid XML ({exc})") from exc


def decompress_diagram(text: str) -> str:
    """Decode a compressed ``<diagram>`` payload into XML text."""
    text = text.strip()
    try:
        raw = base64.b64decode(text, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise DecodeError(f"diagram is not valid base64 ({exc})") from exc
    try:
        inflated = zlib.decompress(raw, -15)
    except zlib.error as exc:
        raise DecodeError(f"diagram is not valid deflate data ({exc})") from exc
    # draw.io: decodeURIComponent(bytesToString(inflateRaw(...))) - bytes map 1:1 to chars.
    return urllib.parse.unquote(inflated.decode("latin-1"))


def read_png_text_chunks(data: bytes) -> dict[str, str]:
    """Return text chunks of a PNG (keyword -> text). Later chunks win."""
    if not data.startswith(PNG_SIGNATURE):
        raise DecodeError("not a PNG file")
    pos = len(PNG_SIGNATURE)
    out: dict[str, str] = {}
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"tEXt":
            key, _, val = body.partition(b"\x00")
            out[key.decode("latin-1")] = val.decode("latin-1")
        elif ctype == b"zTXt":
            key, _, rest = body.partition(b"\x00")
            # rest[0] is the compression method (0 = zlib)
            out[key.decode("latin-1")] = zlib.decompress(rest[1:]).decode("latin-1")
        elif ctype == b"iTXt":
            key, _, rest = body.partition(b"\x00")
            comp_flag, _comp_method = rest[0], rest[1]
            rest = rest[2:]
            _lang, _, rest = rest.partition(b"\x00")
            _tkey, _, text = rest.partition(b"\x00")
            if comp_flag:
                text = zlib.decompress(text)
            out[key.decode("latin-1")] = text.decode("utf-8")
        elif ctype == b"IEND":
            break
    return out


def _mxfile_from_png(data: bytes) -> etree._Element:
    chunks = read_png_text_chunks(data)
    for key in ("mxfile", "mxGraphModel"):
        if key in chunks:
            text = chunks[key]
            if not text.lstrip().startswith("<"):
                text = urllib.parse.unquote(text)
            return _parse_xml(text, f"PNG chunk {key}")
    raise DecodeError("PNG has no embedded draw.io diagram (no 'mxfile' text chunk)")


def _mxfile_from_svg(root: etree._Element) -> etree._Element:
    content = root.get("content")
    if not content:
        raise DecodeError("SVG has no embedded draw.io diagram (no 'content' attribute)")
    content = content.strip()
    if not content.startswith("<"):
        # Some versions store the attribute base64-encoded.
        try:
            content = base64.b64decode(content).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
            raise DecodeError("SVG 'content' attribute is not XML") from exc
    return _parse_xml(content, "SVG content")


def _local(tag: object) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def load_root(path: Path) -> etree._Element:
    """Return the top-level ``<mxfile>`` or ``<mxGraphModel>`` element of a file."""
    data = Path(path).read_bytes()
    if data.startswith(PNG_SIGNATURE):
        return _mxfile_from_png(data)
    root = _parse_xml(data, str(path))
    if _local(root.tag) == "svg":
        return _mxfile_from_svg(root)
    return root


def load_diagrams(path: Path) -> list[RawDiagram]:
    root = load_root(path)
    tag = _local(root.tag)
    if tag == "mxGraphModel":
        return [RawDiagram(id="page-1", name="Page-1", model=root)]
    if tag != "mxfile":
        raise DecodeError(f"{path}: unexpected root element <{tag}>, expected <mxfile>")
    diagrams: list[RawDiagram] = []
    for i, d in enumerate(root.iterchildren("diagram"), start=1):
        name = d.get("name") or f"Page-{i}"
        did = d.get("id") or f"page-{i}"
        model = d.find("mxGraphModel")
        if model is None:
            text = (d.text or "").strip()
            if not text:
                # Empty diagram: treat as an empty model.
                model = etree.Element("mxGraphModel")
                etree.SubElement(etree.SubElement(model, "root"), "mxCell", id="0")
            else:
                model = _parse_xml(decompress_diagram(text), f"{path}: diagram '{name}'")
                if _local(model.tag) != "mxGraphModel":
                    raise DecodeError(f"{path}: diagram '{name}' does not contain <mxGraphModel>")
        diagrams.append(RawDiagram(id=did, name=name, model=model))
    if not diagrams:
        raise DecodeError(f"{path}: <mxfile> contains no <diagram>")
    return diagrams
