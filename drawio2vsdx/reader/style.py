"""draw.io style strings.

A style string is ``name1;name2;key=value;key2=value2``. Tokens without ``=`` are
named styles from the stylesheet (``ellipse``, ``text``, ``edgeLabel``, ``swimlane`` ...).

Default values (draw.io ``default.xml`` / ``Graph.js``) are resolved in stage 1; until
then :func:`parse_style` keeps named styles under the reserved key ``STYLE_NAMES`` so
that nothing is lost.
"""

from __future__ import annotations

STYLE_NAMES = "_styles"  # ';'-joined named styles, in order


def parse_style(style: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not style:
        return out
    names: list[str] = []
    for token in style.split(";"):
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            key, _, val = token.partition("=")
            out[key.strip()] = val.strip()
        else:
            names.append(token)
    if names:
        out[STYLE_NAMES] = ";".join(names)
    return out


def style_names(style: dict[str, str]) -> list[str]:
    raw = style.get(STYLE_NAMES, "")
    return [n for n in raw.split(";") if n]


def is_true(style: dict[str, str], key: str, default: bool = False) -> bool:
    val = style.get(key)
    if val is None:
        return default
    return val.strip() not in ("0", "false", "")


def get_float(style: dict[str, str], key: str, default: float) -> float:
    val = style.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default
