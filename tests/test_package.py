"""Structural checks (brief §7.1 item 1) on every fixture + writer specifics."""

from __future__ import annotations

import shutil
import zipfile

import pytest
from conftest import FEATURES
from lxml import etree

from drawio2vsdx.convert import ConversionError, ConvertOptions, convert
from drawio2vsdx.validate import check_vsdx
from drawio2vsdx.writer.package import unique_page_names
from drawio2vsdx.writer.page import DEFAULT_SCALE

V = "{http://schemas.microsoft.com/office/visio/2012/main}"


def _pages(vsdx):
    with zipfile.ZipFile(vsdx) as zf:
        root = etree.fromstring(zf.read("visio/pages/pages.xml"))
    out = []
    for p in root.iter(f"{V}Page"):
        cells = {c.get("N"): c.get("V") for c in p.find(f"{V}PageSheet").iter(f"{V}Cell")}
        out.append((p.get("NameU"), float(cells["PageWidth"]), float(cells["PageHeight"])))
    return out


def test_structure(fixture_file, tmp_path):
    out = tmp_path / "out.vsdx"
    convert(fixture_file, out)
    assert check_vsdx(out) == []


def test_template_itself_is_valid():
    from importlib import resources

    assert check_vsdx(resources.files("drawio2vsdx.template").joinpath("blank.vsdx").read_bytes()) == []


def test_multipage_names_and_sizes(tmp_path):
    out = tmp_path / "m.vsdx"
    convert(FEATURES / "multipage-compressed.drawio", out)
    pages = _pages(out)
    assert [p[0] for p in pages] == ["Overview", "Схема мережі", "Empty"]
    # Page 1: one 120x60 box + 20px margin on each side.
    assert pages[0][1] == pytest.approx(160 / DEFAULT_SCALE) and pages[0][2] == pytest.approx(100 / DEFAULT_SCALE)
    # Empty page falls back to draw.io page format (850x1100 px).
    assert pages[2][1] == pytest.approx(850 / DEFAULT_SCALE) and pages[2][2] == pytest.approx(1100 / DEFAULT_SCALE)
    with zipfile.ZipFile(out) as zf:
        assert {"visio/pages/page1.xml", "visio/pages/page2.xml", "visio/pages/page3.xml"} <= set(zf.namelist())


def test_page_selection(tmp_path):
    out = tmp_path / "s.vsdx"
    convert(FEATURES / "multipage-compressed.drawio", out, ConvertOptions(pages="3,Схема мережі"))
    assert [p[0] for p in _pages(out)] == ["Empty", "Схема мережі"]
    with pytest.raises(ConversionError):
        convert(FEATURES / "multipage-compressed.drawio", out, ConvertOptions(pages="7"))


def test_unique_page_names():
    assert unique_page_names(["A", "a", "", "A"]) == ["A", "a (2)", "Page-3", "A (3)"]


def test_unicode_and_spaces_in_path(tmp_path):
    d = tmp_path / "Документи" / "схема 1"
    d.mkdir(parents=True)
    src = d / "Назар діаграма.drawio"
    shutil.copy(FEATURES / "cyrillic.drawio", src)
    out = d / "вихід файл.vsdx"
    convert(src, out)
    assert check_vsdx(out) == []
    assert _pages(out)[0][0] == "Сторінка 1"


def test_validator_catches_problems(tmp_path):
    out = tmp_path / "x.vsdx"
    convert(FEATURES / "one-page.drawio", out)
    broken = tmp_path / "broken.vsdx"
    with zipfile.ZipFile(out) as zin, zipfile.ZipFile(broken, "w") as zout:
        for item in zin.infolist():
            if item.filename != "visio/pages/page1.xml":
                zout.writestr(item, zin.read(item))
    problems = check_vsdx(broken)
    assert any("page1.xml" in p for p in problems)
