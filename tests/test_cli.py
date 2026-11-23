from __future__ import annotations

import json
import shutil

from conftest import FEATURES

from drawio2vsdx.cli import main


def test_single_file_default_output(tmp_path):
    src = tmp_path / "a.drawio.svg"
    shutil.copy(FEATURES / "embedded-svg.drawio.svg", src)
    assert main([str(src), "-q"]) == 0
    assert (tmp_path / "a.vsdx").is_file()


def test_folder_recursive_with_report(tmp_path):
    (tmp_path / "in" / "sub").mkdir(parents=True)
    shutil.copy(FEATURES / "empty.drawio", tmp_path / "in" / "e.drawio")
    shutil.copy(FEATURES / "one-page.drawio", tmp_path / "in" / "sub" / "o.drawio")
    rep = tmp_path / "r.json"
    assert main([str(tmp_path / "in"), "-r", "-o", str(tmp_path / "out"), "--report", str(rep), "-q"]) == 0
    assert (tmp_path / "out" / "e.vsdx").is_file() and (tmp_path / "out" / "sub" / "o.vsdx").is_file()
    entries = json.loads(rep.read_text(encoding="utf-8"))["entries"]
    assert any(e["code"] == "not-implemented" and e["file"].endswith("o.drawio") for e in entries)


def test_exit_codes(tmp_path):
    bad = tmp_path / "bad.drawio"
    bad.write_text("nope", encoding="utf-8")
    assert main([str(bad), "-q"]) == 1
    assert main([str(tmp_path / "missing.drawio"), "-q"]) == 1
    assert main([str(FEATURES / "empty.drawio"), "-o", str(tmp_path / "e.vsdx"), "--strict-warnings", "-q"]) == 0
    assert main([str(FEATURES / "one-page.drawio"), "-o", str(tmp_path / "o.vsdx"), "--strict-warnings", "-q"]) == 2
    assert main([str(FEATURES / "one-page.drawio"), "-o", str(tmp_path / "s.vsdx"), "--strict", "-q"]) == 1
    assert not (tmp_path / "s.vsdx").exists()


def test_output_collision(tmp_path):
    (tmp_path / "in").mkdir()
    shutil.copy(FEATURES / "empty.drawio", tmp_path / "in" / "x.drawio")
    shutil.copy(FEATURES / "embedded-svg.drawio.svg", tmp_path / "in" / "x.drawio.svg")
    assert main([str(tmp_path / "in"), "-o", str(tmp_path / "out"), "-q"]) == 1
