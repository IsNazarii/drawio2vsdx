from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS / "fixtures"))

FEATURES = TESTS / "fixtures" / "features"
REAL = TESTS / "fixtures" / "real"
SUFFIXES = (".drawio", ".xml", ".drawio.svg", ".drawio.png")


def all_fixtures() -> list[Path]:
    files = [p for p in sorted(FEATURES.iterdir()) if p.name.endswith(SUFFIXES)]
    if REAL.is_dir():
        files += [p for p in sorted(REAL.rglob("*")) if p.name.endswith(SUFFIXES)]
    return files


@pytest.fixture(params=all_fixtures(), ids=lambda p: p.name)
def fixture_file(request) -> Path:
    return request.param
