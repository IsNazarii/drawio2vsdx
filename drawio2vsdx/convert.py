"""High-level API: draw.io file -> .vsdx file."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from .ir import Document
from .reader.parse import parse_file
from .report import Level, Report
from .writer.package import WriteOptions, write_vsdx


class ConversionError(Exception):
    pass


@dataclass
class ConvertOptions:
    pages: str = "all"
    write: WriteOptions = field(default_factory=WriteOptions)


def select_pages(doc: Document, spec: str) -> Document:
    """``all`` | ``1,3`` | ``2-4`` | ``Name`` | mixed, comma separated (1-based indices)."""
    spec = (spec or "all").strip()
    if spec.lower() == "all":
        return doc
    chosen: list[int] = []
    by_name = {p.name: i for i, p in enumerate(doc.pages)}
    for token in (t.strip() for t in spec.split(",")):
        if not token:
            continue
        if token in by_name:
            idx = [by_name[token]]
        elif token.isdigit():
            idx = [int(token) - 1]
        elif "-" in token and all(part.strip().isdigit() for part in token.split("-", 1)):
            a, b = (int(part) for part in token.split("-", 1))
            idx = list(range(a - 1, b))
        else:
            raise ConversionError(f"--pages: no page named '{token}'")
        for i in idx:
            if not 0 <= i < len(doc.pages):
                raise ConversionError(f"--pages: page {i + 1} does not exist (document has {len(doc.pages)})")
            if i not in chosen:
                chosen.append(i)
    if not chosen:
        raise ConversionError("--pages selects no pages")
    return Document(pages=[doc.pages[i] for i in chosen], source_path=doc.source_path)


def convert(src: Path, dst: Path | io.BytesIO, options: ConvertOptions | None = None, report: Report | None = None) -> Report:
    options = options or ConvertOptions()
    report = report if report is not None else Report()
    doc = select_pages(parse_file(src), options.pages)

    # Stage 0: shapes are not written yet. Never lose anything silently.
    for page in doc.pages:
        n = sum(1 for c in page.cells.values())
        if n:
            report.add(Level.UNSUPPORTED, "not-implemented", f"{n} cell(s) not converted yet (stage 0: pages only)", page=page.name)

    write_vsdx(doc, dst, options.write)
    return report
