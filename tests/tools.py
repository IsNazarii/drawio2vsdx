"""Locating and running external renderers used only by tests (draw.io Desktop, LibreOffice).

Lookup order for each tool: environment variable, PATH, then ``~/tools`` (see
``scripts/setup-dev-tools.sh``). Missing tools make the dependent tests skip.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path.home() / "tools"


def _first_existing(*cands: str | Path | None) -> Path | None:
    for c in cands:
        if not c:
            continue
        p = Path(c)
        if p.is_file() and os.access(p, os.X_OK):
            return p
        w = shutil.which(str(c))
        if w:
            return Path(w)
    return None


def drawio() -> Path | None:
    return _first_existing(
        os.environ.get("DRAWIO_PATH"),
        "drawio",
        TOOLS / "drawio" / "drawio",
        TOOLS / "drawio-current" / "squashfs-root" / "drawio",
        "/opt/drawio/drawio",
    )


def drawio_oracle() -> Path | None:
    """draw.io Desktop v26.0.16 - the last version with a VSDX exporter."""
    return _first_existing(os.environ.get("DRAWIO_ORACLE_PATH"), TOOLS / "drawio-26.0.16" / "squashfs-root" / "drawio")


def soffice() -> Path | None:
    return _first_existing(
        os.environ.get("SOFFICE_PATH"),
        "soffice",
        "libreoffice",
        TOOLS / "libreoffice" / "squashfs-root" / "AppRun",
    )


def _wrap_display(cmd: list[str]) -> list[str]:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        return ["xvfb-run", "-a", *cmd]
    return cmd


def run(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def drawio_export(exe: Path, src: Path, out: Path, fmt: str = "png", page_index: int | None = None, extra: list[str] | None = None) -> Path:
    cmd = [str(exe), "--no-sandbox", "-x", "-f", fmt, "-o", str(out)]
    if page_index is not None:
        cmd += ["-p", str(page_index)]
    cmd += (extra or []) + [str(src)]
    res = run(_wrap_display(cmd))
    if not out.exists():
        raise RuntimeError(f"draw.io export failed ({res.returncode}): {res.stderr[-2000:]}")
    return out


def soffice_png(exe: Path, vsdx: Path, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    profile = outdir / "lo-profile"
    cmd = [
        str(exe),
        f"-env:UserInstallation={profile.resolve().as_uri()}",
        "--headless",
        "--convert-to",
        "png",
        "--outdir",
        str(outdir),
        str(vsdx),
    ]
    res = run(cmd)
    if res.returncode == 81:  # first start: profile created, LibreOffice asks for a restart
        res = run(cmd)
    out = outdir / (vsdx.stem + ".png")
    if not out.exists():
        raise RuntimeError(f"LibreOffice conversion failed ({res.returncode}): {res.stdout[-1000:]} {res.stderr[-1000:]}")
    return out
