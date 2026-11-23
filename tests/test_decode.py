from __future__ import annotations

import pytest
from conftest import FEATURES

from drawio2vsdx.reader.decode import DecodeError, decompress_diagram, load_diagrams, read_png_text_chunks
from make_fixtures import compress


def test_compress_roundtrip_unicode():
    xml = '<mxGraphModel><root><mxCell id="0" value="Привіт &amp; 100% ✓"/></root></mxGraphModel>'
    assert decompress_diagram(compress(xml)) == xml


@pytest.mark.parametrize(
    "name,pages",
    [
        ("empty.drawio", ["Page-1"]),
        ("empty-diagram-element.drawio", ["Page-1"]),
        ("multipage-compressed.drawio", ["Overview", "Схема мережі", "Empty"]),
        ("bare-model.xml", ["Page-1"]),
        ("embedded-svg.drawio.svg", ["SVG page"]),
        ("embedded-png.drawio.png", ["PNG page"]),
        ("cyrillic.drawio", ["Сторінка 1"]),
    ],
)
def test_load_formats(name, pages):
    diagrams = load_diagrams(FEATURES / name)
    assert [d.name for d in diagrams] == pages
    for d in diagrams:
        assert d.model.tag == "mxGraphModel"


def test_png_chunks():
    chunks = read_png_text_chunks((FEATURES / "embedded-png.drawio.png").read_bytes())
    assert "mxfile" in chunks


@pytest.mark.parametrize(
    "content",
    [b"not xml at all", b"<html/>", b"<mxfile/>", b'<svg xmlns="http://www.w3.org/2000/svg"/>', b"\x89PNG\r\n\x1a\n"],
)
def test_bad_inputs_raise_decode_error(tmp_path, content):
    p = tmp_path / "bad.drawio"
    p.write_bytes(content)
    with pytest.raises(DecodeError):
        load_diagrams(p)
