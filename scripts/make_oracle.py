"""Export every feature fixture with draw.io Desktop v26.0.16 (last version with VSDX export)
into tests/oracle/ (brief §7.1 item 5). Development only (Ubuntu).

    python scripts/make_oracle.py [--drawio PATH]

Note: ``drawio -x -f vsdx`` support in the CLI of v26.0.16 is [VERIFY]; failures are listed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import tools  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drawio", type=Path, default=tools.drawio_oracle())
    args = ap.parse_args()
    if args.drawio is None:
        print("draw.io v26.0.16 not found: set DRAWIO_ORACLE_PATH or run scripts/setup-dev-tools.sh")
        return 1
    out_dir = ROOT / "tests" / "oracle"
    out_dir.mkdir(exist_ok=True)
    failed = 0
    for src in sorted((ROOT / "tests" / "fixtures" / "features").iterdir()):
        if src.suffix == ".py":
            continue
        out = out_dir / (src.name.split(".")[0] + ".vsdx")
        try:
            tools.drawio_export(args.drawio, src, out, fmt="vsdx", extra=["--all-pages"])
            print("ok  ", out.name)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print("FAIL", src.name, exc)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
