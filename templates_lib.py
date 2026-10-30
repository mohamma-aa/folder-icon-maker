"""
templates_lib.py
=================
Self-contained "folder icon" template engine built on Pillow.

Each template is a pure-Python function that takes a source PIL image and
returns a square RGBA image (default 512x512) ready to be saved as a .ico.

No external binaries (ImageMagick) are required.

Templates available
--------------------
  plain      - fit image to a square (no frame)
  rounded    - square image with rounded corners
  circle     - circular crop
  shadow     - image with a soft drop shadow
  polaroid   - white photo card with an optional caption
  filmstrip  - black film strip with sprocket holes
  frame      - image inside a rounded border frame
  folder     - image clipped into a 3D "folder" shape
  overlay    - user supplied PNG frame composited over the image

The original RCFI project used ImageMagick + overlay PNGs; this module
re-implements the idea in pure Python and additionally draws every built-in
template programmatically so the tool works out of the box.
"""

from __future__ import annotations

import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

__all__ = ["TEMPLATES", "apply_template", "list_templates", "get_template"]


# --------------------------------------------------------------------------- #
# Low level helpers
# --------------------------------------------------------------------------- #
def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize *img* so it covers (w, h) and center-crop the overflow."""
    img = img.convert("RGBA")
    iw, ih = img.size
    if iw == 0 or ih == 0:
        return Image.new("RGBA", (w, h), (0, 0, 0, 0))
    scale = max(w / iw, h / ih)
    nw, nh = max(1, int(round(iw * scale))), max(1, int(round(ih * scale)))
    im = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return im.crop((x, y, x + w, y + h))


def _rounded_mask(w: int, h: int, r: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return mask


def _circle_mask(w: int, h: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, w - 1, h - 1], fill=255)
    return mask


def _drop_shadow_in_canvas(im: Image.Image, size: int, offset=(0, 0.03),
                           blur=0.03, opacity=170) -> Image.Image:
    """Draw *im* centered inside a transparent *size*x*size* canvas with a
    soft drop shadow beneath it (shadow follows the image's alpha shape)."""
    im = im.convert("RGBA")
    inner = im.size[0]
    pad = (size - inner) // 2
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sx, sy = int(size * offset[0]), int(size * offset[1])
    shp = Image.new("RGBA", (inner, inner), (0, 0, 0, opacity))
    shp.putalpha(im.split()[3].point(lambda a: int(a * opacity / 255)))
    shp = shp.filter(ImageFilter.GaussianBlur(max(1, int(size * blur))))
    base.paste(shp, (pad + sx, pad + sy), shp)
    base.paste(im, (pad, pad), im)
    return base


# --------------------------------------------------------------------------- #
# Caption / text helpers
# --------------------------------------------------------------------------- #
def _find_font(size: int):
    """Return a TrueType font if one exists that can render the caption,
    otherwise fall back to PIL's built-in bitmap font."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for f in candidates:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _prepare_text(text: str) -> str:
    """Reshape + bidify RTL scripts (Persian/Arabic) when the optional
    ``arabic-reshaper`` and ``python-bidi`` packages are available."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        if any("\u0600" <= c <= "\u06FF" or "\u0750" <= c <= "\u077F" for c in text):
            return get_display(arabic_reshaper.reshape(text))
    except Exception:
        pass
    return text


def _draw_caption(draw: ImageDraw.ImageDraw, box, text: str, max_size: int,
                  color=(40, 40, 40, 255)):
    """Draw *text* centered inside *box*, shrinking the font to fit the width."""
    text = _prepare_text(text)
    if not text.strip():
        return
    size = max_size
    font = _find_font(size)
    while size > 8:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= (box[2] - box[0]) and h <= (box[3] - box[1]):
            break
        size -= 1
        font = _find_font(size)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = box[0] + ((box[2] - box[0]) - w) // 2 - bbox[0]
    y = box[1] + ((box[3] - box[1]) - h) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=color)


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
def _t_plain(img, size, caption, opts):
    return _cover(img, size, size)


def _t_rounded(img, size, caption, opts):
    r = int(size * 0.14)
    im = _cover(img, size, size)
    im.putalpha(_rounded_mask(size, size, r))
    return im


def _t_circle(img, size, caption, opts):
    im = _cover(img, size, size)
    im.putalpha(_circle_mask(size, size))
    return im


def _t_shadow(img, size, caption, opts):
    pad = int(size * 0.12)
    inner = size - 2 * pad
    im = _cover(img, inner, inner)
    return _drop_shadow_in_canvas(im, size, offset=(0, 0.03),
                                  blur=0.03, opacity=170)


def _t_polaroid(img, size, caption, opts):
    bg = Image.new("RGBA", (size, size), (250, 250, 248, 255))
    pad = int(size * 0.06)
    top = int(size * 0.05)
    bottom = int(size * 0.24) if caption else int(size * 0.06)
    box = (pad, top, size - pad, size - bottom)
    im = _cover(img, box[2] - box[0], box[3] - box[1])
    bg.paste(im, box)
    d = ImageDraw.Draw(bg)
    d.rectangle(box, outline=(210, 210, 205, 255), width=max(1, int(size * 0.004)))
    if caption:
        _draw_caption(d, (pad, size - bottom, size - pad, size - int(size * 0.03)),
                      caption, int(size * 0.07))
    return bg


def _t_filmstrip(img, size, caption, opts):
    bg = Image.new("RGBA", (size, size), (18, 18, 20, 255))
    bar = int(size * 0.16)
    inner_top, inner_bottom = bar, size - bar
    im = _cover(img, size, inner_bottom - inner_top)
    bg.paste(im, (0, inner_top))
    d = ImageDraw.Draw(bg)
    # sprocket holes
    hole = int(size * 0.045)
    gap = int(size * 0.05)
    n = max(3, size // (hole + gap))
    step = size / n
    for i in range(n):
        cx = int(i * step + step / 2 - hole / 2)
        d.rounded_rectangle([cx, int(bar * 0.28), cx + hole, int(bar * 0.28) + hole],
                            radius=hole // 3, fill=(120, 120, 120, 255))
        d.rounded_rectangle([cx, int(size - bar * 0.28 - hole), cx + hole, int(size - bar * 0.28)],
                            radius=hole // 3, fill=(120, 120, 120, 255))
    return bg


def _t_frame(img, size, caption, opts):
    border = int(size * 0.07)
    inner = size - 2 * border
    im = _cover(img, inner, inner)
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base.paste(im, (border, border))
    d = ImageDraw.Draw(base)
    r = int(size * 0.05)
    lw = max(2, int(size * 0.014))
    d.rounded_rectangle([border // 2, border // 2, size - 1 - border // 2, size - 1 - border // 2],
                        radius=r, outline=(255, 255, 255, 235), width=lw)
    d.rounded_rectangle([border // 2 + lw, border // 2 + lw,
                         size - 1 - border // 2 - lw, size - 1 - border // 2 - lw],
                        radius=max(1, r - lw), outline=(60, 60, 60, 120), width=max(1, lw // 2))
    return base


def _t_folder(img, size, caption, opts):
    accent = tuple(opts.get("folder_color", (74, 134, 196, 255)))
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    tab_h = int(size * 0.18)
    body_top = tab_h
    r = int(size * 0.06)
    # tab
    d.rounded_rectangle([int(size * 0.06), int(size * 0.04),
                         int(size * 0.42), body_top + int(size * 0.04)],
                        radius=int(size * 0.03), fill=accent)
    # body
    d.rounded_rectangle([0, body_top, size - 1, size - 1], radius=r, fill=accent)
    # image clipped into body
    pad = int(size * 0.06)
    box = (pad, body_top + pad, size - pad, size - pad)
    im = _cover(img, box[2] - box[0], box[3] - box[1])
    mask = _rounded_mask(box[2] - box[0], box[3] - box[1], int(size * 0.04))
    alpha = im.split()[3]
    im.putalpha(ImageChops.multiply(alpha, mask))
    base.paste(im, box, im)
    # subtle top highlight
    d.line([(int(size * 0.05), body_top + 2), (size - int(size * 0.05), body_top + 2)],
           fill=(255, 255, 255, 60), width=max(1, int(size * 0.004)))
    return base


def _t_overlay(img, size, caption, opts):
    overlay_path = opts.get("overlay")
    base = _cover(img, size, size)
    if overlay_path and os.path.exists(overlay_path):
        ov = Image.open(overlay_path).convert("RGBA").resize((size, size), Image.LANCZOS)
        base = Image.alpha_composite(base, ov)
    if caption:
        d = ImageDraw.Draw(base)
        _draw_caption(d, (int(size * 0.06), int(size * 0.7),
                          size - int(size * 0.06), size - int(size * 0.06)),
                      caption, int(size * 0.06))
    return base


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
TEMPLATES = {
    "plain": {
        "label": "ساده (Plain)",
        "desc": "تصویر را کاملاً در یک مربع جای می‌دهد، بدون قاب.",
        "caption": False,
        "fn": _t_plain,
    },
    "rounded": {
        "label": "گرد (Rounded)",
        "desc": "تصویر با گوشه‌های گرد.",
        "caption": False,
        "fn": _t_rounded,
    },
    "circle": {
        "label": "دایره (Circle)",
        "desc": "برش دایره‌ای از تصویر.",
        "caption": False,
        "fn": _t_circle,
    },
    "shadow": {
        "label": "سایه (Shadow)",
        "desc": "تصویر با سایه نرم پایین.",
        "caption": False,
        "fn": _t_shadow,
    },
    "polaroid": {
        "label": "پولاروید (Polaroid)",
        "desc": "کارت سفید عکس با زیرنویس نام پوشه.",
        "caption": True,
        "fn": _t_polaroid,
    },
    "filmstrip": {
        "label": "نوار فیلم (Film Strip)",
        "desc": "قالب سیاه فیلم با سوراخ‌های نوار.",
        "caption": False,
        "fn": _t_filmstrip,
    },
    "frame": {
        "label": "قاب (Frame)",
        "desc": "تصویر داخل یک قاب گرد با حاشیه.",
        "caption": False,
        "fn": _t_frame,
    },
    "folder": {
        "label": "پوشه (Folder)",
        "desc": "تصویر داخل شکل سه‌بعدی یک پوشه.",
        "caption": False,
        "fn": _t_folder,
    },
    "overlay": {
        "label": "لازم (Overlay PNG)",
        "desc": "ترکیب تصویر با یک قاب PNG دلخواه.",
        "caption": True,
        "fn": _t_overlay,
    },
}


def list_templates() -> list:
    return list(TEMPLATES.keys())


def get_template(name: str) -> dict:
    return TEMPLATES.get(name, TEMPLATES["plain"])


def apply_template(name: str, img: Image.Image, size: int = 512,
                   caption: str | None = None, **opts) -> Image.Image:
    """Apply template *name* to *img* and return a square RGBA image."""
    tpl = get_template(name)
    cap = caption if (caption and tpl.get("caption")) else None
    return tpl["fn"](img, size, cap, opts)
