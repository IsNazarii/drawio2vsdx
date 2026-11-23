"""Generate synthetic feature fixtures (one feature per file) into tests/fixtures/features.

Run: python tests/fixtures/make_fixtures.py
The generated files are committed; rerun after changing this script.
"""

from __future__ import annotations

import base64
import struct
import urllib.parse
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent / "features"


def compress(xml: str) -> str:
    """Inverse of draw.io Graph.decompress: encodeURIComponent -> deflateRaw -> base64."""
    quoted = urllib.parse.quote(xml, safe="-_.!~*'()")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = comp.compress(quoted.encode("ascii")) + comp.flush()
    return base64.b64encode(raw).decode("ascii")


def model(cells: str, **attrs: str) -> str:
    base = {"dx": "800", "dy": "600", "grid": "1", "gridSize": "10", "page": "1", "pageWidth": "850", "pageHeight": "1100"}
    base.update(attrs)
    a = " ".join(f'{k}="{v}"' for k, v in base.items())
    return f'<mxGraphModel {a}><root><mxCell id="0"/><mxCell id="1" parent="0"/>{cells}</root></mxGraphModel>'


def mxfile(*diagrams: tuple[str, str, str], compressed: bool = False) -> str:
    parts = []
    for i, (did, name, m) in enumerate(diagrams):
        body = compress(m) if compressed else m
        parts.append(f'<diagram id="{did}" name="{name}">{body}</diagram>')
    return '<mxfile host="drawio2vsdx-fixtures" version="24.7.17">' + "".join(parts) + "</mxfile>"


RECT = '<mxCell id="r1" value="Box" style="rounded=0;whiteSpace=wrap;html=1;" vertex="1" parent="1"><mxGeometry x="100" y="80" width="120" height="60" as="geometry"/></mxCell>'

GROUP = (
    '<mxCell id="g1" value="" style="group" vertex="1" connectable="0" parent="1"><mxGeometry x="200" y="150" width="200" height="100" as="geometry"/></mxCell>'
    '<mxCell id="a" value="A" style="rounded=0;whiteSpace=wrap;html=1;" vertex="1" parent="g1"><mxGeometry width="80" height="40" as="geometry"/></mxCell>'
    '<mxCell id="b" value="B" style="ellipse;whiteSpace=wrap;html=1;" vertex="1" parent="g1"><mxGeometry x="120" y="60" width="80" height="40" as="geometry"/></mxCell>'
)

USEROBJ = (
    '<object label="Router-1" id="dev1" ip="10.0.0.1" model="ISR4331">'
    '<mxCell style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1"><mxGeometry x="40" y="40" width="100" height="50" as="geometry"/></mxCell>'
    "</object>"
)

LAYERS_MODEL = (
    '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
    '<mxCell id="L2" value="Overlay" parent="0"/>'
    '<mxCell id="L3" value="Hidden" parent="0" visible="0"/>'
    '<mxCell id="x" value="base" style="rounded=0;" vertex="1" parent="1"><mxGeometry x="10" y="10" width="50" height="50" as="geometry"/></mxCell>'
    '<mxCell id="y" value="over" style="ellipse;" vertex="1" parent="L2"><mxGeometry x="100" y="10" width="50" height="50" as="geometry"/></mxCell>'
    '<mxCell id="z" value="hidden" style="ellipse;" vertex="1" parent="L3"><mxGeometry x="200" y="10" width="50" height="50" as="geometry"/></mxCell>'
    "</root></mxGraphModel>"
)


def png_with_text(keyword: str, text: str) -> bytes:
    """Minimal 1x1 white PNG with a tEXt chunk (what draw.io writes for .drawio.png)."""

    def chunk(ctype: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"tEXt", keyword.encode("latin-1") + b"\x00" + text.encode("latin-1"))
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def svg_with_content(xml: str) -> str:
    from xml.sax.saxutils import quoteattr

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="300px" height="200px" viewBox="0 0 300 200" content={quoteattr(xml)}>'
        '<rect x="100" y="80" width="120" height="60" fill="#fff" stroke="#000"/></svg>\n'
    )


FIXTURES: dict[str, str | bytes] = {
    "empty.drawio": mxfile(("p1", "Page-1", model(""))),
    "empty-diagram-element.drawio": '<mxfile host="x"><diagram id="p1" name="Page-1"></diagram></mxfile>',
    "one-page.drawio": mxfile(("p1", "Page-1", model(RECT))),
    "multipage-compressed.drawio": mxfile(
        ("p1", "Overview", model(RECT)),
        ("p2", "Схема мережі", model(GROUP)),
        ("p3", "Empty", model("")),
        compressed=True,
    ),
    "bare-model.xml": model(RECT),
    "embedded-svg.drawio.svg": svg_with_content(mxfile(("p1", "SVG page", model(RECT)), compressed=True)),
    "embedded-png.drawio.png": png_with_text("mxfile", urllib.parse.quote(mxfile(("p1", "PNG page", model(RECT))), safe="-_.!~*'()")),
    "group.drawio": mxfile(("p1", "Group", model(GROUP))),
    "userobject.drawio": mxfile(("p1", "Data", model(USEROBJ))),
    "layers.drawio": mxfile(("p1", "Layers", LAYERS_MODEL)),
    "cyrillic.drawio": mxfile(("p1", "Сторінка 1", model(RECT.replace('value="Box"', 'value="Комутатор ядра"')))),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in FIXTURES.items():
        path = OUT / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        print("wrote", path.relative_to(OUT.parent.parent.parent))


if __name__ == "__main__":
    main()
