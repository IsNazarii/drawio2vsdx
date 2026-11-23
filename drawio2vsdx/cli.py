"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from ._console import utf8_stdio
from .convert import ConversionError, ConvertOptions, convert
from .reader.decode import DecodeError
from .report import Level, Report
from .writer.package import WriteOptions
from .writer.page import DEFAULT_SCALE

log = logging.getLogger("drawio2vsdx")

INPUT_SUFFIXES = (".drawio", ".dio", ".drawio.xml", ".drawio.svg", ".drawio.png")
EXIT_OK, EXIT_ERROR, EXIT_WARNINGS = 0, 1, 2


def _stem(path: Path) -> str:
    name = path.name
    for suffix in (".drawio.svg", ".drawio.png", ".drawio.xml", ".drawio", ".dio", ".xml", ".svg", ".png"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _collect_inputs(src: Path, recursive: bool) -> list[Path]:
    if src.is_file():
        return [src]
    if src.is_dir():
        it = src.rglob("*") if recursive else src.glob("*")
        return sorted(p for p in it if p.is_file() and p.name.lower().endswith(INPUT_SUFFIXES))
    raise FileNotFoundError(f"input not found: {src}")


def _output_for(src: Path, root: Path, out: Path | None, many: bool) -> Path:
    name = _stem(src) + ".vsdx"
    if out is None:
        return src.with_name(name)
    if many or out.is_dir() or out.suffix.lower() != ".vsdx":
        rel = src.parent.relative_to(root) if root.is_dir() else Path()
        return out / rel / name
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="drawio2vsdx", description="Convert draw.io diagrams to Visio .vsdx")
    p.add_argument("input", type=Path, help=".drawio/.xml/.drawio.svg/.drawio.png file or a folder")
    p.add_argument("-o", "--output", type=Path, help=".vsdx file or output folder")
    p.add_argument("-r", "--recursive", action="store_true", help="process folders recursively")
    p.add_argument("--pages", default="all", help="all | 1,3 | 2-4 | page name (default: all)")
    p.add_argument("--scale", type=float, default=DEFAULT_SCALE, help=f"pixels per inch (default {DEFAULT_SCALE:g})")
    p.add_argument("--page-size", action="store_true", help="use draw.io pageWidth/pageHeight instead of content bounds")
    p.add_argument("--template", type=Path, help="blank .vsdx saved by Visio to use as package template")
    p.add_argument("--report", type=Path, help="write a report (.json or .md) of simplified/lost elements")
    p.add_argument("--strict", action="store_true", help="fail on unsupported elements instead of warning")
    p.add_argument("--strict-warnings", action="store_true", help="exit with code 2 if anything was simplified")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = build_parser().parse_args(argv)
    level = logging.WARNING if args.quiet else logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    report = Report()
    try:
        inputs = _collect_inputs(args.input, args.recursive)
    except FileNotFoundError as exc:
        log.error("error: %s", exc)
        return EXIT_ERROR
    if not inputs:
        log.error("error: no draw.io files found in %s", args.input)
        return EXIT_ERROR

    options = ConvertOptions(
        pages=args.pages,
        write=WriteOptions(scale=args.scale, use_page_size=args.page_size, template=args.template),
    )
    failed = 0
    used: dict[Path, Path] = {}
    for src in inputs:
        dst = _output_for(src, args.input, args.output, many=len(inputs) > 1 or args.input.is_dir())
        report.file = str(src)
        key = dst.resolve()
        if key in used:
            report.add(Level.ERROR, "output-collision", f"{dst} is also the output of {used[key]}")
            log.error("error: %s: output %s already written for %s", src, dst, used[key])
            failed += 1
            continue
        used[key] = src
        before = len(report.entries)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            convert(src, dst, options, report)
        except (DecodeError, ConversionError) as exc:
            report.add(Level.ERROR, "input", str(exc))
            log.error("error: %s: %s", src, exc)
            failed += 1
            continue
        except PermissionError:
            report.add(Level.ERROR, "output-locked", f"cannot write {dst}")
            log.error("error: cannot write %s - is it open in Visio or another program?", dst)
            failed += 1
            continue
        new = report.entries[before:]
        if args.strict and any(e.level == Level.UNSUPPORTED for e in new):
            dst.unlink(missing_ok=True)
            log.error("error: %s: unsupported elements (--strict); see report", src)
            failed += 1
            continue
        log.info("%s -> %s", src, dst)
        for e in new:
            log.log(logging.WARNING if e.level != Level.INFO else logging.DEBUG, "  %s [%s] %s%s%s", e.level.value, e.code,
                    f"page '{e.page}' " if e.page else "", f"cell {e.cell}: " if e.cell else "", e.message)

    if args.report:
        report.write(args.report)
    if failed:
        return EXIT_ERROR
    if args.strict_warnings and report.has_warnings:
        return EXIT_WARNINGS
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
