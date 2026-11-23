"""Render checks (brief §7.1 items 3-4). Skipped when the renderers are not installed.

* LibreOffice must convert every produced .vsdx to PNG without failing.
* For fixtures in SSIM_THRESHOLDS the LibreOffice render and the draw.io round-trip
  render (draw.io imports .vsdx) are compared with draw.io's own render of the source.
"""

from __future__ import annotations

import pytest
import tools
from conftest import FEATURES
from imgcompare import is_blank, ssim

from drawio2vsdx.convert import convert

pytestmark = pytest.mark.render

# fixture name -> minimal SSIM. Grows with every stage (stage 0: only empty pages are faithful).
SSIM_THRESHOLDS: dict[str, float] = {}
BLANK_EXPECTED = ["empty.drawio", "empty-diagram-element.drawio"]


@pytest.fixture(scope="module")
def soffice():
    exe = tools.soffice()
    if exe is None:
        pytest.skip("LibreOffice not found (set SOFFICE_PATH or run scripts/setup-dev-tools.sh)")
    return exe


@pytest.fixture(scope="module")
def drawio():
    exe = tools.drawio()
    if exe is None:
        pytest.skip("draw.io Desktop not found (set DRAWIO_PATH or run scripts/setup-dev-tools.sh)")
    return exe


def test_libreoffice_renders(fixture_file, soffice, tmp_path):
    out = tmp_path / "out.vsdx"
    convert(fixture_file, out)
    png = tools.soffice_png(soffice, out, tmp_path / "lo")
    assert png.stat().st_size > 0


@pytest.mark.parametrize("name", BLANK_EXPECTED)
def test_empty_renders_blank(name, soffice, tmp_path):
    out = tmp_path / "out.vsdx"
    convert(FEATURES / name, out)
    assert is_blank(tools.soffice_png(soffice, out, tmp_path / "lo"))


def test_drawio_roundtrip_imports(fixture_file, drawio, tmp_path):
    """draw.io must import what we write (second independent reader): same pages, same names.

    Exported as XML, not PNG: draw.io refuses to export an empty diagram to PNG.
    """
    from drawio2vsdx.reader.parse import parse_file

    out = tmp_path / "out.vsdx"
    convert(fixture_file, out)
    back = tools.drawio_export(drawio, out, tmp_path / "rt.drawio", fmt="xml", extra=["--uncompressed"])
    names = [p.name for p in parse_file(back).pages]
    assert names == [p.name for p in parse_file(fixture_file).pages]


@pytest.mark.parametrize("name,threshold", sorted(SSIM_THRESHOLDS.items()))
def test_ssim_against_drawio(name, threshold, soffice, drawio, tmp_path):
    src = FEATURES / name
    out = tmp_path / "out.vsdx"
    convert(src, out)
    ref = tools.drawio_export(drawio, src, tmp_path / "ref.png", page_index=1)
    lo = tools.soffice_png(soffice, out, tmp_path / "lo")
    rt = tools.drawio_export(drawio, out, tmp_path / "rt.png", page_index=1)
    assert ssim(ref, lo) >= threshold, "LibreOffice render differs from draw.io"
    assert ssim(ref, rt) >= threshold, "draw.io round-trip differs from draw.io"
