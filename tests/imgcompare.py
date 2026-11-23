"""Image similarity for render tests (numpy + Pillow only)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 256


def _load(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("L")
    # Crop to content so that margins/page size differences do not dominate.
    arr = np.asarray(img)
    mask = arr < 250
    if mask.any():
        ys, xs = np.where(mask)
        img = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return np.asarray(img.resize((SIZE, SIZE), Image.LANCZOS), dtype=np.float64)


def ssim(a: Path, b: Path) -> float:
    """Mean SSIM over 8x8 windows (Wang et al. 2004 constants)."""
    x, y = _load(a), _load(b)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    w = 8
    xs = x.reshape(SIZE // w, w, SIZE // w, w).swapaxes(1, 2).reshape(-1, w * w)
    ys = y.reshape(SIZE // w, w, SIZE // w, w).swapaxes(1, 2).reshape(-1, w * w)
    mx, my = xs.mean(1), ys.mean(1)
    vx, vy = xs.var(1), ys.var(1)
    cov = ((xs - mx[:, None]) * (ys - my[:, None])).mean(1)
    s = ((2 * mx * my + c1) * (2 * cov + c2)) / ((mx**2 + my**2 + c1) * (vx + vy + c2))
    return float(s.mean())


def is_blank(path: Path) -> bool:
    arr = np.asarray(Image.open(path).convert("L"))
    return bool((arr >= 250).all())
