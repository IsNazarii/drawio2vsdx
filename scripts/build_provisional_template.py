"""Build the *provisional* ``drawio2vsdx/template/blank.vsdx``.

The brief asks for a blank drawing saved by Visio itself. Until the author provides
one, the template is built from the skeleton embedded in draw.io's former VSDX
exporter (``VsdxExport.js``, jgraph/drawio v24.7.17, Apache-2.0), which draw.io used
to produce files that Visio opened. One empty page is added so the writer always
finds a base ``PageSheet``.

Usage::

    python scripts/build_provisional_template.py path/to/VsdxExport.js
    # VsdxExport.js: https://raw.githubusercontent.com/jgraph/drawio/v24.7.17/src/main/webapp/js/diagramly/vsdx/VsdxExport.js
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "drawio2vsdx" / "template" / "blank.vsdx"

PAGES_XML = (
    "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
    "<Pages xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
    "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' xml:space='preserve'>"
    "<Page ID='0' NameU='Page-1' Name='Page-1'><PageSheet LineStyle='0' FillStyle='0' TextStyle='0'>"
    "<Cell N='PageWidth' V='8.5'/><Cell N='PageHeight' V='11'/>"
    "<Cell N='ShdwOffsetX' V='0.125'/><Cell N='ShdwOffsetY' V='-0.125'/>"
    "<Cell N='PageScale' V='1' U='IN_F'/><Cell N='DrawingScale' V='1' U='IN_F'/>"
    "<Cell N='DrawingSizeType' V='0'/><Cell N='DrawingScaleType' V='0'/>"
    "<Cell N='InhibitSnap' V='0'/><Cell N='UIVisibility' V='0'/><Cell N='ShdwType' V='0'/>"
    "<Cell N='ShdwObliqueAngle' V='0'/><Cell N='ShdwScaleFactor' V='1'/>"
    "<Cell N='DrawingResizeType' V='1'/><Cell N='PageShapeSplit' V='1'/>"
    "</PageSheet><Rel r:id='rId1'/></Page></Pages>"
)
PAGES_RELS = (
    "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
    "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
    "<Relationship Id='rId1' Type='http://schemas.microsoft.com/visio/2010/relationships/page' Target='page1.xml'/>"
    "</Relationships>"
)
PAGE1 = (
    "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
    "<PageContents xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
    "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' xml:space='preserve'/>"
)


def _js_string(s: str) -> str:
    q, i, buf = s[0], 1, []
    while s[i] != q:
        if s[i] == "\\":
            buf.append({"n": "\n", "t": "\t"}.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            buf.append(s[i])
            i += 1
    return "".join(buf)


def extract_skeleton(js: str) -> dict[str, str]:
    start = js.index("var files = {")
    end = js.index("};", start)
    files: dict[str, str] = {}
    for line in js[start:end].splitlines()[1:]:
        m = re.match(r'\s*"([^"]+)"\s*:\s*(.*)$', line)
        if m:
            files[m.group(1)] = _js_string(m.group(2).strip())
    return files


def main() -> None:
    js = Path(sys.argv[1]).read_text(encoding="utf-8")
    files = extract_skeleton(js)
    files["visio/pages/pages.xml"] = PAGES_XML
    files["visio/pages/_rels/pages.xml.rels"] = PAGES_RELS
    files["visio/pages/page1.xml"] = PAGE1
    order = ["[Content_Types].xml"] + sorted(k for k in files if k != "[Content_Types].xml")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in order:
            zf.writestr(name, files[name].encode("utf-8"))
    print(f"wrote {OUT} ({len(files)} parts)")


if __name__ == "__main__":
    main()
