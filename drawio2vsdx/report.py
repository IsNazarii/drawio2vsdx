"""Conversion report: everything that was dropped, simplified or approximated."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class Level(str, Enum):
    INFO = "info"
    APPROX = "approx"  # converted, but simplified
    WARNING = "warning"  # partially lost
    UNSUPPORTED = "unsupported"  # not converted at all
    ERROR = "error"


@dataclass
class Entry:
    level: Level
    code: str
    message: str
    file: str | None = None
    page: str | None = None
    cell: str | None = None


@dataclass
class Report:
    entries: list[Entry] = field(default_factory=list)
    file: str | None = None  # current input file, stamped on new entries

    def add(self, level: Level, code: str, message: str, page: str | None = None, cell: str | None = None) -> None:
        self.entries.append(Entry(level, code, message, self.file, page, cell))

    def count(self, *levels: Level) -> int:
        return sum(1 for e in self.entries if e.level in levels)

    @property
    def has_warnings(self) -> bool:
        return self.count(Level.APPROX, Level.WARNING, Level.UNSUPPORTED) > 0

    def to_json(self) -> str:
        rows = [{**asdict(e), "level": e.level.value} for e in self.entries]
        return json.dumps({"entries": rows}, ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = ["# drawio2vsdx report", ""]
        if not self.entries:
            lines.append("No simplifications or losses.")
            return "\n".join(lines) + "\n"
        lines += ["| level | code | file | page | cell | message |", "|---|---|---|---|---|---|"]
        for e in self.entries:
            cells = [e.level.value, e.code, e.file or "", e.page or "", e.cell or "", e.message]
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        return "\n".join(lines) + "\n"

    def write(self, path: Path) -> None:
        text = self.to_json() if path.suffix.lower() == ".json" else self.to_markdown()
        path.write_text(text, encoding="utf-8")
