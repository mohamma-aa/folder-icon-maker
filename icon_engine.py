"""
icon_engine.py
=============
Core logic for Folder Icon Maker (formerly "RCFI GUI"):

  * Discover a parent folder's sub-folders.
  * For each sub-folder, find the "best" image living *inside* that folder.
  * Render the image through a template and save it as ``folder.ico``.
  * (Windows only) wire the .ico into desktop.ini so Explorer shows it.

ImageMagick renders the faithful templates when it is available; without
it the app still runs, but every template then produces the same generic
Pillow fallback icon.
"""

from __future__ import annotations

import os
import re
import sys

from PIL import Image

import rcfi_templates

__all__ = [
    "IMAGE_EXTS", "find_image_in_folder", "get_target_folders",
    "make_ico_for_folder", "render_preview",
]

# Image formats accepted as icon artwork.  The core set renders everywhere
# (ImageMagick + the pure-Pillow fallback); SVG/AVIF/HEIC depend on the
# delegates compiled into the ImageMagick binary -- the portable magick.exe
# ships with them, and if a build lacks one the tool reports a clear error.
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".dib",
    ".webp", ".tif", ".tiff", ".gif", ".tga", ".avif", ".heic",
    ".heif", ".svg",
}

# Keywords that hint an image is the *main* artwork for a folder.
PREFERRED = ["poster", "cover", "folder", "main", "artwork", "icon",
             "thumb", "banner", "front", "key", "show"]
# Keywords that hint an image is *not* the main artwork (logo, disc, back...).
EXCLUDED = ["logo", "clearart", "disc", "back", "spine", "sample", "watermark"]

# Hidden / system folders that recursive scans must never descend into.
_SKIP_DIRS = {".git", "$recycle.bin", "system volume information"}

# FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM (Windows) -- folders that
# the OS manages are hidden via the attribute, not via their name, so the
# name-based filters above are not enough on Windows.
_FA_HIDDEN_SYSTEM = 0x2 | 0x4


def _win_hidden_or_system(path: str) -> bool:
    """True when *path* carries the Windows Hidden or System attribute.

    On non-Windows platforms -- and whenever the attribute cannot be
    queried -- this returns False ("not hidden"), so nothing is
    over-filtered and the behaviour elsewhere stays unchanged."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(
            os.path.normpath(path))
    except Exception:                              # noqa: BLE001
        return False
    if attrs == 0xFFFFFFFF:      # INVALID_FILE_ATTRIBUTES
        return False
    return bool(attrs & _FA_HIDDEN_SYSTEM)


def _is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


def find_image_in_folder(folder: str, recursive: bool = False) -> str | None:
    """Return the path of the most appropriate image inside *folder*.

    When *recursive* is True the search also dives into sub-folders of
    *folder* (handy when the artwork lives one level deeper).
    """
    found = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            # don't descend into hidden / system folders (by name AND by
            # the actual Windows file attributes)
            dirs[:] = [d for d in dirs
                       if not d.startswith(".")
                       and d.lower() not in _SKIP_DIRS
                       and not _win_hidden_or_system(os.path.join(root, d))]
            for f in files:
                if _is_image(f):
                    found.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(folder)):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and _is_image(f):
                found.append(p)
    if not found:
        return None

    def rank(p: str) -> int:
        # Token match on non-alphanumeric separators, so "monkey" no longer
        # matches "key", "domain-map" no longer matches "main" and
        # "Discovery" is no longer penalised as disc art — whole words only.
        toks = set(re.findall(r"[a-z0-9]+", os.path.basename(p).lower()))
        score = 0
        for kw in PREFERRED:
            if kw in toks:
                score += 10
        for kw in EXCLUDED:
            if kw in toks:
                score -= 6
        return score

    # Highest rank first; ties are broken by path so the picked image is
    # deterministic across runs and filesystems (os.walk order is not).
    found.sort(key=lambda p: (-rank(p), p))
    return found[0]


def get_target_folders(root: str, recursive: bool = False) -> list:
    """Return the folders that should receive an icon.

    Default: the *immediate* sub-folders of *root* (the use-case the user
    described: a parent folder containing several sub-folders).
    When *recursive* is True, every directory in the tree is a target.
    """
    dirs = []
    for entry in os.scandir(root):
        if not entry.is_dir() or entry.name.startswith(".") \
                or entry.name.lower() in _SKIP_DIRS:
            continue
        try:      # st_file_attributes exists on Windows only
            fa = entry.stat(follow_symlinks=False).st_file_attributes
        except (AttributeError, OSError):
            fa = 0
        if fa & _FA_HIDDEN_SYSTEM:
            continue
        dirs.append(entry.path)
    if recursive:
        for dp, dn, _fn in os.walk(root):
            dn[:] = [d for d in dn
                     if not d.startswith(".")
                     and d.lower() not in _SKIP_DIRS
                     and not _win_hidden_or_system(os.path.join(dp, d))]
            for d in dn:
                dirs.append(os.path.join(dp, d))
    # de-duplicate (walk already includes immediate sub-folders) and sort
    seen, out = set(), []
    for d in dirs:
        rp = os.path.normpath(d)
        if rp not in seen:
            seen.add(rp)
            out.append(d)
    return sorted(out)


def render_preview(image_path: str, template: str, size: int = 256,
                   **opts) -> Image.Image:
    """Render a small preview of *template* applied to *image_path*.

    Uses a private ``mkstemp`` file (never ``mktemp`` -- that one is
    racy) and honours *size*; the temp file is always removed.
    """
    import tempfile
    fd, out = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        rcfi_templates.apply_template(
            template, image_path, out,
            folder=os.path.dirname(image_path) or ".",
            size=str(size))
        with Image.open(out) as im:
            return im.convert("RGBA")
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


def _valid_ico(path: str) -> bool:
    """Full ICO sanity check, run before the temp file replaces the real
    ``folder.ico``.

    Three layers, so a truncated renderer output can no longer destroy a
    working icon:
      1. the 6-byte header (type = 1, at least one directory entry),
      2. every directory entry: the embedded image must have a non-zero
         size and its offset+size must lie completely inside the file --
         a file that contains only the header (or entries pointing past
         EOF) fails here,
      3. Pillow must actually decode the file (``verify()``) -- the
         payloads are really images, not leftover bytes.

    Deliberately NOT checked: that the embedded sizes match a fixed
    expected list.  The ImageMagick path and the pure-Pillow fallback
    legitimately produce different size sets, and a "wrong" size set
    still yields a perfectly valid icon -- rejecting it would break the
    no-ImageMagick fallback for no real gain."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return False
    if len(data) < 6 + 16 or data[:4] != b"\x00\x00\x01\x00":
        return False                      # no room for one entry / bad magic
    count = int.from_bytes(data[4:6], "little")
    dir_end = 6 + count * 16
    if count < 1 or dir_end > len(data):
        return False
    for i in range(count):
        entry = data[6 + 16 * i: 6 + 16 * (i + 1)]
        img_size = int.from_bytes(entry[8:12], "little")
        img_off = int.from_bytes(entry[12:16], "little")
        if img_size == 0 or img_off < dir_end \
                or img_off + img_size > len(data):
            return False                  # empty or out-of-bounds payload
    try:
        with Image.open(path) as im:
            im.verify()                   # really decodable image data
    except Exception:                     # noqa: BLE001
        return False
    return True


def make_ico_for_folder(folder: str, image_path: str, template: str,
                        size: int = 256,
                        ico_name: str = "folder.ico",
                        existing: str = "skip", **opts) -> dict:
    """Create ``folder/<ico_name>`` from *image_path* through *template*.

    Uses the exact original ImageMagick templates (via ``rcfi_templates``),
    which reproduce the GitHub project output.

    The .ico is ALWAYS written as a full multi-resolution set
    (256 -> 16 px -- the ICO format maximum): Windows picks the right
    size for every zoom level itself, so there is nothing to choose and
    the icon is always as sharp as the format allows.  *size* is kept
    for API compatibility and ignored.

    *existing* controls behaviour when the .ico already exists:
        "skip"     -> keep a VALID existing .ico and report status
                      "reused" (the caller can still wire it into
                      desktop.ini); a corrupt one is re-rendered
        "overwrite"-> replace it unconditionally

    The render goes to a TEMP file first (name still ends in ``.ico`` so
    ImageMagick picks the right format from the extension) and is only
    moved over the real ``folder.ico`` after a full validation (structure
    + Pillow decode, see ``_valid_ico``) -- a renderer crash, a timeout
    or a truncated output can no longer destroy the previous icon.

    Returns a result dict: {folder, image, ico, status, error}.
    """
    ico_path = os.path.join(folder, ico_name)
    if os.path.exists(ico_path) and existing == "skip":
        if _valid_ico(ico_path):
            # A VALID .ico is already there: report it as "reused" so the
            # caller can still wire it into desktop.ini without forcing a
            # fresh render.  (Returning plain "skipped" here made a first
            # run that generated the .ico but failed to write desktop.ini
            # impossible to finish without ticking Overwrite.)
            return {"folder": folder, "image": image_path, "ico": ico_path,
                    "status": "reused", "error": None}
        # A corrupt .ico would only ever display as a broken icon: fall
        # through and re-render over it -- the temp+validate dance below
        # still keeps the old file when the new render fails.

    # An old .ico may be read-only (e.g. the folder was extracted from a ZIP
    # or copied from read-only media); clear that so the renderer can replace
    # it instead of failing with Errno 13.
    if os.path.exists(ico_path):
        try:
            os.chmod(ico_path, 0o666)
        except OSError:
            pass

    stem = ico_name[:-4] if ico_name.lower().endswith(".ico") else ico_name
    tmp_path = os.path.join(folder, f"{stem}.rcfi-tmp.ico")
    try:
        try:
            rcfi_templates.apply_template(
                template, image_path, tmp_path, folder=folder,
                size=rcfi_templates.DEFAULT_SIZES)
            if not _valid_ico(tmp_path):
                raise ValueError(
                    f"renderer produced an invalid .ico file "
                    f"({ico_name}) for '{folder}'")
            os.replace(tmp_path, ico_path)
        except BaseException:
            # Never leave the temp file (or a half-rendered icon) behind;
            # the PREVIOUS folder.ico stays untouched on any failure.
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        return {"folder": folder, "image": image_path, "ico": ico_path,
                "status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"folder": folder, "image": image_path, "ico": ico_path,
                "status": "error", "error": str(exc)}
