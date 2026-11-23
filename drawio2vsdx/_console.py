"""Console encoding: Windows consoles/pipes default to cp1252/cp1251; paths and page names are Unicode."""

import sys


def utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
