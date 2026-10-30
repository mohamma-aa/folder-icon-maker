"""
rcfi_templates.py
=================
Faithful Python port of the original "RightClick Folder Icon Tools" templates.

Each template is the *same* layered ImageMagick command sequence as the
original ``templates/<Name>.bat`` and is executed directly with the user's
``magick`` / ``convert`` binary -- so the output is identical to the GitHub
project and **no ``cmd.exe`` window ever pops up**.

This build keeps the square / disc / case style templates (the ones that always
worked and apply to the folder icon immediately) plus a "Square" template that
stretches the picture into an exact 1:1 square without cropping.

Note: the original project's NFO-based metadata overlays (IMDb rating star,
rating and genre captions) are intentionally NOT ported -- the GUI never
exposed them, so ``star.png`` and the caption font are no longer needed.

Public API
----------
    locate_imagick()      -> path to magick/convert or None
    list_templates()      -> list of template ids
    apply_template(...)   -> runs ImageMagick; writes out_path
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import templates_lib  # pure-python fallback

# Suppress the child console window on Windows (no-op on other platforms).
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Hard cap per ImageMagick invocation so a stuck process can never hang the UI.
IM_TIMEOUT = 90


def _hidden_startupinfo():
    """Return (creationflags, startupinfo) that hide any child console window
    on Windows. Both are no-ops on other platforms, and the Windows-only
    ``STARTF_USESHOWWINDOW`` / ``SW_HIDE`` constants are only touched when we
    are actually on Windows.

    Using *both* ``CREATE_NO_WINDOW`` and a hidden ``STARTUPINFO`` is the
    most reliable way to guarantee no ``cmd.exe`` / console popup appears
    when ImageMagick runs.
    """
    if sys.platform != "win32":
        return 0, None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return CREATE_NO_WINDOW, si

__all__ = ["locate_imagick", "list_templates", "apply_template", "TEMPLATES"]

HERE = Path(__file__).resolve().parent
IMAGES = HERE / "rcfi_assets" / "images"
DEFAULT_SIZES = "256,128,96,64,48,40,32,24,16"

CANVAS = str(IMAGES / "- canvas.png")


def _img(name: str) -> str:
    return str(IMAGES / name)


# --------------------------------------------------------------------------- #
# ImageMagick discovery
# --------------------------------------------------------------------------- #
def _im_runs(binary: str) -> bool:
    """Return True only if *binary* is a working ImageMagick CLI."""
    flags, si = _hidden_startupinfo()
    try:
        r = subprocess.run([binary, "-version"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20,
                           creationflags=flags, startupinfo=si)
        return r.returncode == 0
    except Exception:
        return False


_IM_CACHE = None


def locate_imagick(force: bool = False) -> str | None:
    """Locate a working ImageMagick CLI, cached for the whole session.

    Probing (``-version``) every call would add a subprocess round-trip per
    folder/template during batch runs; caching keeps batch processing fast.
    """
    global _IM_CACHE
    if _IM_CACHE is not None and not force:
        return _IM_CACHE
    result = None
    # Prefer the modern `magick` CLI, then the legacy `convert` CLI.
    # Each candidate is probed so a binary that is present but broken / blocked
    # by AV does not slip through and crash mid-processing.
    for cand in ("magick", "magick.exe", "convert", "convert.exe"):
        p = shutil.which(cand)
        if p and _im_runs(p):
            result = p
            break
    # Bundled portable ImageMagick: whatever the portable package provides,
    # i.e. magick.exe plus (depending on the build) a folder of support
    # files right next to it.  ImageMagick resolves those files relative to
    # the exe, so both are simply kept together in rcfi_assets/resources/.
    if result is None:
        for name in ("magick.exe", "convert.exe"):
            bundled = HERE / "rcfi_assets" / "resources" / name
            if bundled.exists() and _im_runs(str(bundled)):
                result = str(bundled)
                break
    _IM_CACHE = result
    return result


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _find(folder: str, patterns) -> str | None:
    folder = folder or "."
    # glob.escape(): a literal folder name such as "Movie [2020]" must not
    # be interpreted as a glob character class.
    for pat in patterns:
        hits = sorted(glob.glob(os.path.join(glob.escape(folder), pat)))
        if hits:
            return hits[0]
    return None


def _layer(inner, compose="over"):
    """Wrap inner ops in a ``( ... ) -compose X -composite`` block."""
    return ["(", *inner, ")", "-compose", compose, "-composite"]


def _bg() -> list:
    return [CANVAS, "-scale", "512x512!", "-background", "none", "-extent", "512x512"]


# --------------------------------------------------------------------------- #
# (none)
# --------------------------------------------------------------------------- #
def t_none(inputfile, output, size, folder, tmp):
    if os.path.splitext(inputfile)[1].lower() == ".ico":
        shutil.copy(inputfile, output)
        return []
    return [[inputfile, "-resize", "512x512", "-background", "none",
             "-gravity", "CENTER", "-extent", "512x512",
             "-define", f"icon:auto-resize={size}", output]]


# --------------------------------------------------------------------------- #
# (Shadow Only)
# --------------------------------------------------------------------------- #
def t_shadow_only(inputfile, output, size, folder, tmp):
    return [[inputfile, "-resize", "490x490",
             "(", "+clone", "-background", "BLACK", "-shadow", "60x5+5+6.5", ")",
             "+swap", "-background", "none", "-layers", "merge",
             "-gravity", "CENTER", "-extent", "512x512",
             "-define", f"icon:auto-resize={size}", output]]


# --------------------------------------------------------------------------- #
# Square -- stretch the picture into an exact 1:1 square, no cropping
# --------------------------------------------------------------------------- #
def t_square_fit(inputfile, output, size, folder, tmp):
    # Stretch the picture into an exact 1:1 square -- no cropping, no background.
    # (a rectangular image simply gets its dimensions adjusted to a square)
    return [[inputfile, "-resize", "512x512!",
             "-define", f"icon:auto-resize={size}", output]]


# --------------------------------------------------------------------------- #
# DVDBox Dark / Light
# --------------------------------------------------------------------------- #
def _make_discart(inputfile, folder, tmp):
    """Build the disc-art image used by the DVD Box templates.

    Faithful to the original ``DVDBox *.bat`` ``LAYER-DISC`` block:

      * if a ``*discart.png`` already exists in the folder it is used as-is;
      * otherwise a disc art is generated from the poster image (the
        original ``generate-DiscArt`` behaviour) -- preferring a
        ``*poster*`` / ``*landscape*`` / ``*fanart*`` image and falling
        back to the chosen input image;
      * as a last resort the plain ``disc-vinyl.png`` is used.

    Returns a path to a 512x512 image that already carries the cover art.
    """
    explicit = _find(folder, ("*discart.png",))
    if explicit:
        return explicit
    src = (_find(folder, ("*poster*.jpg", "*landscape*.jpg", "*fanart*.jpg",
                          "*poster*.png", "*landscape*.png", "*fanart*.png"))
           or inputfile)
    try:
        out = os.path.join(tmp, "rcfi_discart.png")
        # t_discart() only *builds* the IM command list; apply_template() runs
        # it so a real disc-art PNG is produced (this is what the original
        # DiscArt.bat does when generate-DiscArt is enabled).
        apply_template("DiscArt", src, out, folder=folder,
                       size=DEFAULT_SIZES, tmp=tmp)
        if os.path.exists(out):
            return out
    except Exception:
        pass
    return _img("disc-vinyl.png")


def _dvdbox(inputfile, output, size, folder, tmp, light):
    frame = _img("dvdbox-light.png" if light else "dvdbox-dark.png")
    ops = _bg()
    # LAYER-DISC-IMAGE (the disc/CD shown half-outside the box, like the original)
    # The disc carries the cover art: a custom *discart.png is used as-is,
    # otherwise a disc art is generated from the poster (generate-DiscArt).
    disc = _make_discart(inputfile, folder, tmp)
    ops += _layer([
        disc, "-scale", "340x340!", "-background", "none",
        "-extent", "512x512-164-84",
        "(", "+clone", "-background", "BLACK", "-shadow", "100x1.3+2+2", ")",
        "+swap", "-background", "none", "-layers", "merge", "-extent", "512x512",
    ], "Over")
    ops += _layer([
        inputfile, "-scale", "340x483!", "-background", "none",
        "-gravity", "Northwest", "-geometry", "+7+11",
    ], "Over")
    ops += _layer([frame, "-resize", "512x512!"], "Over")
    ops += ["-define", f"icon:auto-resize={size}", output]
    return [ops]


def t_dvdbox_dark(inputfile, output, size, folder, tmp):
    return _dvdbox(inputfile, output, size, folder, tmp, light=False)


def t_dvdbox_light(inputfile, output, size, folder, tmp):
    return _dvdbox(inputfile, output, size, folder, tmp, light=True)


# --------------------------------------------------------------------------- #
# DVDCase Bluray / Transparent Plastic
# --------------------------------------------------------------------------- #
def _dvdcase(inputfile, output, size, folder, tmp, plastic):
    frame = _img("dvdcase-plastic.png" if plastic else "dvdcase-bluray.png")
    ops = _bg()
    if plastic:
        ops += _layer([
            inputfile, "-scale", "336x474!", "-gravity", "Northwest",
            "-geometry", "+108+14", _img("dvdcase-plastic-mask.png"),
        ], "over")
    else:
        ops += _layer([
            inputfile, "-scale", "340x438!", "-background", "none",
            "-gravity", "Northwest", "-geometry", "+78+48",
        ], "Over")
    ops += _layer([frame, "-resize", "512x512!"], "Over")
    if not plastic:
        ops += ["(", "+clone", "-background", "BLACK", "-shadow", "0x2+2+2.5", ")",
                "+swap", "-background", "none", "-layers", "merge",
                "-extent", "512x512"]
    ops += ["-define", f"icon:auto-resize={size}", output]
    return [ops]


def t_dvdcase_bluray(inputfile, output, size, folder, tmp):
    return _dvdcase(inputfile, output, size, folder, tmp, plastic=False)


def t_dvdcase_plastic(inputfile, output, size, folder, tmp):
    return _dvdcase(inputfile, output, size, folder, tmp, plastic=True)


# --------------------------------------------------------------------------- #
# DiscArt
# --------------------------------------------------------------------------- #
def t_discart(inputfile, output, size, folder, tmp):
    main, border = _img("DiscArt-Main.png"), _img("DiscArt-Border.png")
    trans, label = _img("DiscArt-Transparent.png"), _img("DiscArt-Label.png")
    logo = _img("DiscArt-Logo.png")
    ops = _bg()
    ops += _layer([inputfile, "-scale", "485x485!", "-gravity", "center", main], "over")
    ops += _layer([trans, "-scale", "512x512!"], "over")
    ops += _layer([label, "-scale", "512x512!"], "over")
    ops += _layer([logo, "-scale", "512x512!"], "over")
    ops += _layer([
        inputfile, "-scale", "900x900!", "-blur", "0x30",
        "-brightness-contrast", "0x30", border,
    ], "over")
    ops += ["-define", f"icon:auto-resize={size}", output]
    return [ops]


# --------------------------------------------------------------------------- #
# template registry
# --------------------------------------------------------------------------- #
TEMPLATE_ORDER = [
    "(none)", "(Shadow Only)", "Square",
    "DVDBox Dark", "DVDBox Light",
    "DVDCase Bluray", "DVDCase Transparent Plastic", "DiscArt",
]

PORTED = {
    "(none)": t_none,
    "(Shadow Only)": t_shadow_only,
    "Square": t_square_fit,
    "DVDBox Dark": t_dvdbox_dark,
    "DVDBox Light": t_dvdbox_light,
    "DVDCase Bluray": t_dvdcase_bluray,
    "DVDCase Transparent Plastic": t_dvdcase_plastic,
    "DiscArt": t_discart,
}


def list_templates() -> list:
    return list(TEMPLATE_ORDER)


# --------------------------------------------------------------------------- #
# main entry point
# --------------------------------------------------------------------------- #
def apply_template(name, input_path, out_path, *, folder=".",
                   size=DEFAULT_SIZES, tmp=None, im_binary=None):
    """Render *input_path* through template *name* to *out_path*.

    All templates are reproduced as the exact same ImageMagick command
    sequence and run directly with the user's ImageMagick binary -- no
    ``cmd.exe`` window is spawned.  If ImageMagick is unavailable a pure
    Python fallback is used.
    """
    im = im_binary or locate_imagick()
    fn = PORTED.get(name)
    if im and fn:
        own_tmp = tmp is None
        tmpdir = tmp or tempfile.mkdtemp(prefix="rcfi_")
        try:
            steps = fn(input_path, out_path, size, folder, tmpdir)
            flags, si = _hidden_startupinfo()
            for step in steps:
                # creationflags + hidden STARTUPINFO suppress the console
                # window on Windows; timeout guarantees a stuck invocation
                # can never hang the app.
                subprocess.run([im, *step], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=flags, startupinfo=si, timeout=IM_TIMEOUT)
            if not os.path.exists(out_path):
                raise RuntimeError(f"ImageMagick did not produce output for '{name}'")
            return out_path
        finally:
            # Remove our own working folder from %TEMP%; a caller-supplied
            # *tmp* remains the caller's responsibility.
            if own_tmp:
                shutil.rmtree(tmpdir, ignore_errors=True)
    # last-resort pure-python fallback
    from PIL import Image
    with Image.open(input_path) as im0:
        im0 = im0.convert("RGBA")
        res = templates_lib.apply_template("folder", im0, 512)
        res.save(out_path)
    return out_path


TEMPLATES = PORTED
