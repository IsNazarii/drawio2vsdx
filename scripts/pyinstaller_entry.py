"""Entry point for the PyInstaller one-file build (drawio2vsdx.exe)."""

import sys

from drawio2vsdx.cli import main

if __name__ == "__main__":
    sys.exit(main())
