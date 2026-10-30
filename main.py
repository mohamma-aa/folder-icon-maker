"""
Folder Icon Maker  -  graphical folder-icon tool for Windows
============================================================
(formerly released as "RCFI GUI"; based on "RightClick Folder Icon Tools")

Two modes:

  * Batch  - select a parent folder that contains several sub-folders.  Each
    sub-folder is expected to hold an image *inside itself*; for every such
    folder the image is turned into a ``folder.ico`` (through one of the
    original project's templates) and - on Windows - wired into desktop.ini
    so Explorer shows it.
  * Single - pick one folder and one image explicitly; only that folder
    becomes an icon folder.

The templates are the EXACT ones from the GitHub project.  Every original
``templates/<Name>.bat`` is a layered ImageMagick command sequence; here each
template is reproduced as the *same* ImageMagick operands and executed directly
with the user's ``magick`` / ``convert`` binary -- so the output is identical to
the GitHub project **and no ``cmd.exe`` window pops up**.  If ImageMagick is
unavailable a pure-Python engine is used as a last resort.

Features
--------
  * Graphical, no command line needed.
  * Batch mode (whole tree in one click) + single mode (one folder + one image).
  * The original templates, ported faithfully to ImageMagick:
    ``(none)``, ``(Shadow Only)``, ``Square``, ``DVDBox Dark``,
    ``DVDBox Light``, ``DVDCase Bluray``, ``DVDCase Transparent Plastic``,
    ``DiscArt``.
  * Live template preview + a "preview all templates" gallery (cached renders).
  * Bilingual UI (Persian / English): auto-detected from the OS locale on
    first run, switchable live from the combo box in the header.  The
    switch re-renders EVERYTHING -- including the whole log history -- and
    template names get Persian display names (internal ids stay Latin).
  * Windows: apply the icons directly to the folders (immediately).

Run:   python main.py
Build: build.bat / build_dir.bat (Windows only -- folder icons are a
       Windows shell feature; build.sh just runs the CODE for development
       and testing on other systems).
"""

from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from PIL import Image, ImageDraw, ImageTk

import i18n
import icon_engine
import rcfi_templates
import windows_folder

# --------------------------------------------------------------------------- #
# Paths (work both as a script and when frozen by PyInstaller)
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE = Path(sys._MEIPASS)
    CACHE = Path(tempfile.gettempdir()) / "FolderIconMaker"
    CACHE.mkdir(parents=True, exist_ok=True)
    ASSETS = CACHE
else:
    BASE = HERE
    ASSETS = HERE / "assets"

ICO_NAME = "folder.ico"
PREVIEW_PX = 256
HEADER_H = 66

IMAGE_FILETYPES = [
    ("Images", "*.jpg *.jpeg *.jpe *.jfif *.png *.bmp *.dib *.gif *.webp "
               "*.tif *.tiff *.tga *.avif *.heic *.heif *.svg"),
    ("All files", "*.*"),
]

MODE_BATCH = "batch"
MODE_SINGLE = "single"

# --------------------------------------------------------------------------- #
# Modern theme palette
# --------------------------------------------------------------------------- #
BG = "#eef1f6"
CARD = "#ffffff"
BORDER = "#dbe2ee"
ACCENT = "#3b6ef5"
ACCENT_HOVER = "#2f5bd0"
ACCENT_DARK = "#274bb0"
TEXT = "#1f2733"
MUTED = "#6b7686"
SOFT = "#f3f6fb"
OK_GREEN = "#1a9e5c"
ERR_RED = "#d64545"


# --------------------------------------------------------------------------- #
# Theme / helpers
# --------------------------------------------------------------------------- #
def _apply_theme(root: tk.Tk):
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, bordercolor=BORDER,
                    borderwidth=1, relief="solid")
    style.configure("Header.TFrame", background=ACCENT)
    style.configure("Neutral.TFrame", background=SOFT, bordercolor=BORDER,
                    borderwidth=1, relief="solid")
    style.configure("TLabel", background=CARD, foreground=TEXT,
                    font=("Segoe UI", "10"))
    style.configure("Muted.TLabel", background=CARD, foreground=MUTED,
                    font=("Segoe UI", "10"))
    style.configure("Title.TLabel", background=ACCENT, foreground="white",
                    font=("Segoe UI", "15", "bold"))
    style.configure("Sub.TLabel", background=ACCENT, foreground="#dbe6ff",
                    font=("Segoe UI", "10"))
    style.configure("TButton", font=("Segoe UI", "10"), padding=6)
    style.configure("Accent.TButton", background=ACCENT, foreground="white",
                    borderwidth=0, font=("Segoe UI", "10", "bold"), padding=8)
    style.map("Accent.TButton",
              background=[("active", ACCENT_HOVER), ("disabled", "#b9c4d6")],
              foreground=[("disabled", "#eef2f8")])
    style.configure("Accent.Hover.TButton", background=ACCENT_HOVER,
                    foreground="white", borderwidth=0,
                    font=("Segoe UI", "10", "bold"), padding=8)
    # segmented mode-switcher buttons
    style.configure("Segment.TButton", background=CARD, foreground=TEXT,
                    bordercolor=BORDER, font=("Segoe UI", "10"),
                    padding=(14, 6))
    style.map("Segment.TButton",
              background=[("active", SOFT), ("disabled", CARD)],
              foreground=[("disabled", MUTED)])
    style.configure("Segment.Active.TButton", background=ACCENT,
                    foreground="white", borderwidth=0,
                    font=("Segoe UI", "10", "bold"), padding=(14, 6))
    style.map("Segment.Active.TButton",
              background=[("active", ACCENT_HOVER)])
    style.configure("TCheckbutton", background=CARD, foreground=TEXT,
                    font=("Segoe UI", "10"))
    style.configure("TCombobox", font=("Segoe UI", "10"))
    style.configure("Treeview", background=CARD, foreground=TEXT,
                    fieldbackground=CARD, font=("Segoe UI", "11"), rowheight=30)
    style.configure("Treeview.Heading", background="#e7ecf5", foreground=TEXT,
                    font=("Segoe UI", "11", "bold"))
    style.configure("TProgressbar", troughcolor="#e2e8f2", borderwidth=0,
                    background=ACCENT)
    style.configure("TLabelframe", background=CARD, foreground=TEXT,
                    bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=CARD, foreground=ACCENT_DARK,
                    font=("Segoe UI", "10", "bold"))
    style.configure("TScrollbar", background="#cdd6e6")


def _make_accent(btn: ttk.Button):
    btn.bind("<Enter>", lambda _e: btn.configure(style="Accent.Hover.TButton"))
    btn.bind("<Leave>", lambda _e: btn.configure(style="Accent.TButton"))


def _mix(c1: str, c2: str, t: float) -> str:
    """Linear blend between two #rrggbb colors (t=0 -> c1, t=1 -> c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t)
                                   for i in range(3))


@lru_cache(maxsize=8)
def _checker(size: int, c1=(235, 238, 243, 255), c2=(221, 227, 236, 255)):
    tile = max(6, size // 32)
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(0, size, tile):
        for x in range(0, size, tile):
            fill = c1 if ((x // tile + y // tile) % 2 == 0) else c2
            d.rectangle([x, y, x + tile - 1, y + tile - 1], fill=fill)
    return img


def ensure_sample() -> str:
    # Frozen exe: prefer the sample bundled inside _MEIPASS/assets over
    # anything lying in the temp cache (BASE == sys._MEIPASS when frozen).
    bundled = BASE / "assets" / "sample.png"
    if bundled.exists():
        return str(bundled)
    if (ASSETS / "sample.png").exists():
        return str(ASSETS / "sample.png")
    ASSETS.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(512):
        t = i / 511
        d.line([(i, 0), (i, 512)], fill=(
            int(60 + 160 * t), int(120 + 80 * (1 - t)),
            int(200 + 40 * t), 255))
    d.ellipse([150, 150, 362, 362], fill=(255, 214, 92, 255))
    d.ellipse([200, 200, 312, 312], fill=(240, 120, 70, 255))
    img.save(ASSETS / "sample.png")
    return str(ASSETS / "sample.png")


# Rendered previews are cached per (image, template, scale) so switching
# back and forth between templates (and re-opening the gallery) is instant.
# Filled from background render threads -> every access is lock-guarded.
_PREVIEW_CACHE: dict = {}
_PREVIEW_CACHE_MAX = 24
_PREVIEW_CACHE_LOCK = threading.Lock()


def render_to_pil(image_path: str, template: str, scale: int = PREVIEW_PX):
    """Render the template to a PIL image (checkerboard composited) WITHOUT
    touching Tk -- safe to call from a background thread."""
    key = (str(image_path), template, scale)
    with _PREVIEW_CACHE_LOCK:
        cached = _PREVIEW_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    fd, out = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    folder = os.path.dirname(image_path) or "."
    try:
        rcfi_templates.apply_template(
            template, image_path, out, folder=folder, size="256")
        if not os.path.exists(out) or os.path.getsize(out) == 0:
            raise RuntimeError("no output produced")
        with Image.open(out) as im:
            im = im.convert("RGBA").resize((scale, scale), Image.LANCZOS)
        # composite over a checkerboard so transparency is visible
        bg = _checker(scale).copy()
        bg.paste(im, (0, 0), im)
        with _PREVIEW_CACHE_LOCK:
            if len(_PREVIEW_CACHE) >= _PREVIEW_CACHE_MAX:
                _PREVIEW_CACHE.pop(next(iter(_PREVIEW_CACHE)))
            _PREVIEW_CACHE[key] = bg
        return bg.copy()
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        i18n.load_pref()
        self.root.title(i18n.T("app_title"))
        self.root.minsize(780, 690)
        self.root.configure(background=BG)
        try:
            self.root.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass
        icon = BASE / "assets" / "icon.ico"
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except Exception:
                pass

        self.queue = queue.Queue()
        # Background render threads never touch Tk directly: they put PIL
        # results on this queue and the main-thread poller applies them.
        self.preview_q = queue.Queue()
        self.targets: list[dict] = []
        self.photos: list = []
        self.sample = ensure_sample()
        self.preview_source: str | None = None
        self.busy = False

        self.root_path = tk.StringVar()
        self.single_folder = tk.StringVar()
        self.single_image = tk.StringVar()
        self.template_key = "(none)"    # internal template id (always Latin)
        self.template = tk.StringVar()  # localized display name for the combo
        self.recursive = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)
        self.refresh_expl = tk.BooleanVar(value=True)
        self.mode_var = tk.StringVar(value=MODE_BATCH)
        # Structured log history: entries survive a live language switch and
        # are re-rendered in the new language when the UI is rebuilt.
        #   ("k", tag, prefix, [(key, kwargs), ...])  -> translated line
        #   ("t", tag, text)                          -> raw, final text
        self._log_history = [("k", None, None, [("log_start", {})])]
        self.lang_var = tk.StringVar(value=i18n.LANG_NAMES[i18n.current()])

        self._build_ui()
        self._update_preview()
        # main-thread poller for preview/gallery render results
        self.root.after(60, self._poll_preview)

    # ----------------------------- UI -------------------------------------- #
    def _build_ui(self):
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        root.rowconfigure(4, weight=1)

        self._build_header(root)
        self._build_options(root)
        self._build_main_area(root)
        self._build_action_bar(root)
        self._build_log(root)
        self._apply_mode_ui()

    # --------------------------------------------------------------------- #
    def _build_header(self, root):
        """Gradient header with app icon, title, subtitle and language picker.
        Falls back to a flat frame on exotic Tk builds."""
        try:
            canvas = tk.Canvas(root, height=HEADER_H, highlightthickness=0,
                               bd=0, background=ACCENT)
            canvas.grid(row=0, column=0, sticky="ew")

            def _paint(_event=None):
                canvas.delete("bg")
                w = max(canvas.winfo_width(), 50)
                steps = 32
                for i in range(steps):
                    y0 = int(HEADER_H * i / steps)
                    y1 = int(HEADER_H * (i + 1) / steps)
                    col = _mix(ACCENT, ACCENT_DARK, i / (steps - 1))
                    canvas.create_rectangle(0, y0, w, y1, fill=col,
                                            outline=col, tags="bg")
                canvas.tag_lower("bg")
                canvas.coords("icon", 18, HEADER_H / 2)
                canvas.coords("title", 64, 19)
                canvas.coords("subtitle", 64, 41)
                canvas.coords("lang", w - 14, HEADER_H / 2)

            canvas.bind("<Configure>", _paint)

            photo = None
            try:
                ic = Image.open(BASE / "assets" / "icon.ico").resize(
                    (34, 34), Image.LANCZOS)
                photo = ImageTk.PhotoImage(ic)
                self._hdr_photo = photo  # keep a reference alive
            except Exception:
                photo = None
            if photo is not None:
                canvas.create_image(18, HEADER_H / 2, image=photo,
                                    anchor="w", tags="icon")
            canvas.create_text(64, 19, text=i18n.T("app_name"), anchor="w",
                               fill="white", font=("Segoe UI", 15, "bold"),
                               tags="title")
            canvas.create_text(64, 41, text=i18n.T("app_subtitle"), anchor="w",
                               fill="#d9e4ff", font=("Segoe UI", 10),
                               tags="subtitle")
            self.lang_box = ttk.Combobox(
                canvas, textvariable=self.lang_var,
                values=list(i18n.LANG_NAMES.values()),
                state="readonly", width=9, font=("Segoe UI", "10"))
            canvas.create_window(0, 0, window=self.lang_box,
                                 anchor="e", tags="lang")
            self.lang_box.bind("<<ComboboxSelected>>", self._change_lang)
            canvas.after(30, _paint)
        except Exception:
            hdr = ttk.Frame(root, style="Header.TFrame")
            hdr.grid(row=0, column=0, sticky="ew")
            hdr.columnconfigure(1, weight=1)
            ttk.Label(hdr, text=i18n.T("app_name"),
                      style="Title.TLabel").grid(
                row=0, column=1, sticky="w", pady=(8, 0))
            ttk.Label(hdr, text=i18n.T("app_subtitle"),
                      style="Sub.TLabel").grid(row=1, column=1, sticky="w")
            self.lang_box = ttk.Combobox(
                hdr, textvariable=self.lang_var,
                values=list(i18n.LANG_NAMES.values()),
                state="readonly", width=9, font=("Segoe UI", "10"))
            self.lang_box.grid(row=0, column=2, sticky="e",
                               padx=(10, 14), pady=(8, 0))
            self.lang_box.bind("<<ComboboxSelected>>", self._change_lang)

    # --------------------------------------------------------------------- #
    def _build_options(self, root):
        o = ttk.LabelFrame(root, text=i18n.T("settings"), padding=12,
                           style="Card.TFrame")
        o.grid(row=1, column=0, sticky="ew", padx=12, pady=(12, 0))
        o.columnconfigure(0, weight=1)

        # mode switcher (segmented control)
        seg = ttk.Frame(o, style="Card.TFrame")
        seg.grid(row=0, column=0, sticky="w")
        self.btn_batch = ttk.Button(seg, text=i18n.T("mode_batch"),
                                    style="Segment.TButton", takefocus=False,
                                    command=lambda: self._set_mode(MODE_BATCH))
        self.btn_batch.grid(row=0, column=0, padx=(0, 6))
        self.btn_single = ttk.Button(seg, text=i18n.T("mode_single"),
                                     style="Segment.TButton", takefocus=False,
                                     command=lambda: self._set_mode(MODE_SINGLE))
        self.btn_single.grid(row=0, column=1)

        # batch source row
        self.batch_bar = ttk.Frame(o, style="Card.TFrame")
        self.batch_bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.batch_bar.columnconfigure(1, weight=1)
        ttk.Label(self.batch_bar,
                  text=i18n.T("source_folder")).grid(row=0, column=0,
                                                     padx=(0, 6))
        self.path_entry = ttk.Entry(self.batch_bar, textvariable=self.root_path)
        self.path_entry.grid(row=0, column=1, sticky="ew")
        self.path_entry.bind("<Return>", lambda _e: self.scan())
        self.browse_btn = ttk.Button(self.batch_bar, text=i18n.T("browse"),
                                     command=self.browse_batch)
        self.browse_btn.grid(row=0, column=2, padx=6)
        self.scan_btn = ttk.Button(self.batch_bar, text=i18n.T("scan"),
                                   command=self.scan)
        self.scan_btn.grid(row=0, column=3)

        # single-mode rows (folder + image), same grid cell as batch_bar
        self.single_bar = ttk.Frame(o, style="Card.TFrame")
        self.single_bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.single_bar.columnconfigure(1, weight=1)
        ttk.Label(self.single_bar,
                  text=i18n.T("target_folder")).grid(row=0, column=0,
                                                     padx=(0, 6))
        self.single_folder_entry = ttk.Entry(self.single_bar,
                                             textvariable=self.single_folder)
        self.single_folder_entry.grid(row=0, column=1, sticky="ew")
        self.single_folder_entry.bind("<Return>", lambda _e: self.scan())
        ttk.Button(self.single_bar, text=i18n.T("browse"),
                   command=self.browse_single_folder).grid(row=0, column=2,
                                                           padx=6)
        ttk.Label(self.single_bar,
                  text=i18n.T("image_path")).grid(row=1, column=0,
                                                  padx=(0, 6), pady=(8, 0))
        self.single_image_entry = ttk.Entry(self.single_bar,
                                            textvariable=self.single_image)
        self.single_image_entry.grid(row=1, column=1, sticky="ew",
                                     pady=(8, 0))
        self.single_image_entry.bind("<Return>", lambda _e: self.scan())
        ttk.Button(self.single_bar, text=i18n.T("browse_image"),
                   command=self.browse_single_image).grid(row=1, column=2,
                                                          padx=6, pady=(8, 0))

        # template row -- there is NO size selector on purpose: a folder.ico
        # is always written as a full multi-resolution set (16-256 px, the
        # ICO format maximum) and Windows picks the right size itself.
        ts = ttk.Frame(o, style="Card.TFrame")
        ts.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(ts, text=i18n.T("template_label")).grid(row=0, column=0,
                                                          padx=(0, 6))
        self.tpl_combo = ttk.Combobox(
            ts, textvariable=self.template,
            values=[i18n.template_name(t)
                    for t in rcfi_templates.list_templates()],
            state="readonly", width=22)
        self.tpl_combo.grid(row=0, column=1, padx=(0, 16))
        self.tpl_combo.bind("<<ComboboxSelected>>",
                            lambda e: self._on_template())
        self._sync_template_display()

        # options checkboxes (2 x 2)
        ck = ttk.Frame(o, style="Card.TFrame")
        ck.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.recursive_chk = ttk.Checkbutton(ck, text=i18n.T("recursive"),
                                             variable=self.recursive,
                                             command=self.scan_if_ready)
        self.recursive_chk.grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(ck, text=i18n.T("overwrite"),
                        variable=self.overwrite).grid(row=0, column=1,
                                                      sticky="w", padx=(18, 0))
        self.refresh_chk = ttk.Checkbutton(ck, text=i18n.T("refresh_explorer"),
                                           variable=self.refresh_expl)
        if not windows_folder.is_supported():
            self.refresh_chk.configure(state="disabled")
        self.refresh_chk.grid(row=1, column=0, sticky="w", pady=(6, 0))
        # Only used by the "Remove icons" button: also delete the generated
        # folder.ico file (off by default -- the .ico may be the only
        # remaining copy of the artwork).
        self.remove_ico_var = tk.BooleanVar(value=False)
        self.remove_ico_chk = ttk.Checkbutton(
            ck, text=i18n.T("remove_ico_chk"),
            variable=self.remove_ico_var)
        if not windows_folder.is_supported():
            self.remove_ico_chk.configure(state="disabled")
        self.remove_ico_chk.grid(row=1, column=1, sticky="w", padx=(18, 0),
                                 pady=(6, 0))

    # --------------------------------------------------------------------- #
    def _build_main_area(self, root):
        main = ttk.Frame(root)
        main.grid(row=2, column=0, sticky="nsew", padx=12, pady=(12, 0))
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        pv = ttk.LabelFrame(main, text=i18n.T("preview_frame"), padding=12,
                            style="Card.TFrame")
        pv.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        pv.rowconfigure(1, weight=1)
        pv.columnconfigure(0, weight=1)
        self._pv_host = ttk.Frame(pv, style="Neutral.TFrame", width=PREVIEW_PX,
                                  height=PREVIEW_PX)
        self._pv_host.grid(row=0, column=0, pady=(0, 8))
        self._pv_host.update_idletasks()
        self.preview_canvas = tk.Label(self._pv_host, background=SOFT,
                                       borderwidth=0)
        self.preview_canvas.place(relx=0.5, rely=0.5, anchor="center")
        self.tpl_desc = ttk.Label(pv, text="", wraplength=PREVIEW_PX,
                                  style="Muted.TLabel")
        self.tpl_desc.grid(row=1, column=0, pady=(6, 8), sticky="n")
        ttk.Button(pv, text=i18n.T("gallery"),
                   command=self.gallery).grid(row=2, column=0, pady=(4, 0))

        self.tree_frame = ttk.LabelFrame(main, text=i18n.T("tree_frame"),
                                         padding=8, style="Card.TFrame")
        self.tree_frame.grid(row=0, column=1, sticky="nsew")
        self.tree_frame.rowconfigure(0, weight=1)
        self.tree_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self.tree_frame, columns=("image", "status"),
            show="tree headings", height=14, selectmode="browse")
        self.tree.heading("#0", text=i18n.T("col_folder"))
        self.tree.heading("image", text=i18n.T("col_image"))
        self.tree.heading("status", text=i18n.T("col_status"))
        self.tree.column("#0", width=170, anchor="w")
        self.tree.column("image", width=180, anchor="w")
        self.tree.column("status", width=90, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical",
                            command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

    # --------------------------------------------------------------------- #
    def _build_action_bar(self, root):
        b = ttk.Frame(root)
        b.grid(row=3, column=0, sticky="ew", padx=12, pady=(12, 0))
        b.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(b, maximum=1, value=0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.gen_btn = ttk.Button(b, text=i18n.T("generate"),
                                  command=self.generate, style="Accent.TButton",
                                  state="disabled")
        _make_accent(self.gen_btn)
        self.gen_btn.grid(row=0, column=1)
        # Manual undo: remove the icon wiring (desktop.ini) from every
        # scanned folder -- ONLY after an explicit confirmation dialog.
        self.remove_btn = ttk.Button(b, text=i18n.T("btn_remove_icons"),
                                     command=self.remove_icons,
                                     state="disabled")
        self.remove_btn.grid(row=0, column=2, padx=(10, 0))
        # Manual "clear icon cache & refresh Explorer" -- for when some
        # folders still show the old icon after a run (the shell sometimes
        # lags behind; closing all Explorer windows / restarting it helps).
        self.refresh_btn = ttk.Button(b, text=i18n.T("btn_refresh_explorer"),
                                      command=self.refresh_now)
        self.refresh_btn.grid(row=0, column=3, padx=(10, 0))
        if not windows_folder.is_supported():
            self.refresh_btn.configure(state="disabled")
        self.status_var = tk.StringVar(value=i18n.T("status_ready"))
        ttk.Label(b, textvariable=self.status_var,
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=4,
                                             sticky="w", pady=(6, 0))

    # --------------------------------------------------------------------- #
    def _build_log(self, root):
        logf = ttk.LabelFrame(root, text=i18n.T("log_frame"), padding=8,
                              style="Card.TFrame")
        logf.grid(row=4, column=0, sticky="nsew", padx=12, pady=(12, 12))
        logf.rowconfigure(0, weight=1)
        logf.columnconfigure(0, weight=1)
        self.log = scrolledtext.ScrolledText(
            logf, height=8, font=("Consolas", "10"),
            background="#fbfcfe", foreground=TEXT, borderwidth=0)
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.tag_configure("ok", foreground=OK_GREEN)
        self.log.tag_configure("err", foreground=ERR_RED)
        # Re-render the whole history in the ACTIVE language -- this is what
        # makes a live language switch translate the log completely.
        for entry in self._log_history:
            self._append_log(self._render_entry(entry), entry[1])

    # --------------------------- mode -------------------------------------- #
    def _apply_mode_ui(self):
        """Sync the segmented buttons, panels and option states with mode_var."""
        batch = self.mode_var.get() == MODE_BATCH
        self.btn_batch.configure(style="Segment.Active.TButton" if batch
                                 else "Segment.TButton")
        self.btn_single.configure(style="Segment.TButton" if batch
                                  else "Segment.Active.TButton")
        if batch:
            self.single_bar.grid_remove()
            self.batch_bar.grid()
        else:
            self.batch_bar.grid_remove()
            self.single_bar.grid()
        self.tree_frame.configure(text=i18n.T("tree_frame" if batch
                                               else "tree_frame_single"))
        self.recursive_chk.configure(state="normal" if batch else "disabled")

    def _set_mode(self, mode):
        if self.busy or mode == self.mode_var.get():
            return
        self.mode_var.set(mode)
        self._apply_mode_ui()
        self.scan()

    # --------------------------- callbacks -------------------------------- #
    def browse_batch(self):
        p = filedialog.askdirectory(title=i18n.T("dlg_browse_title"))
        if p:
            self.root_path.set(p)
            self.scan()

    def browse_single_folder(self):
        p = filedialog.askdirectory(title=i18n.T("dlg_browse_title"))
        if p:
            self.single_folder.set(p)
            self.scan()

    def browse_single_image(self):
        p = filedialog.askopenfilename(title=i18n.T("dlg_browse_image"),
                                       filetypes=IMAGE_FILETYPES)
        if p:
            self.single_image.set(p)
            self.scan()

    def scan_if_ready(self):
        if self.mode_var.get() == MODE_BATCH and self.root_path.get().strip():
            self.scan()

    def scan(self):
        if self.busy:
            return
        if self.mode_var.get() == MODE_SINGLE:
            self._scan_single()
        else:
            self._scan_batch()

    def _scan_batch(self):
        root = self.root_path.get().strip()
        if not root or not os.path.isdir(root):
            self.targets = []
            self.preview_source = None
            self._populate_tree()
            self.gen_btn.configure(state="disabled")
            self.remove_btn.configure(state="disabled")
            self._update_preview()
            if root:
                self.log_key("err_invalid_root")
            return
        self.targets = []
        for f in icon_engine.get_target_folders(root, self.recursive.get()):
            img = icon_engine.find_image_in_folder(f)
            self.targets.append({
                "folder": f, "image": img,
                "ico": os.path.join(f, ICO_NAME),
                "status": "pending" if img else "no-image",
            })
        self._after_scan()

    def _scan_single(self):
        folder = self.single_folder.get().strip()
        img = self.single_image.get().strip()
        self.targets = []
        self.preview_source = None
        ok = False
        if folder and img:
            if not os.path.isdir(folder):
                self.log_key("err_invalid_root")
            elif not os.path.isfile(img):
                self.log_key("err_invalid_image")
            else:
                self.targets = [{
                    "folder": folder, "image": img,
                    "ico": os.path.join(folder, ICO_NAME),
                    "status": "pending",
                }]
                self.preview_source = img
                ok = True
        elif folder or img:
            self.log_key("err_need_both")
        if ok:
            self.log_key("log_scan_single")
        self._after_scan(enable=ok)

    def _after_scan(self, enable: bool | None = None):
        self._populate_tree()
        has_img = any(t["image"] for t in self.targets)
        if enable is None:
            enable = has_img
        self.gen_btn.configure(state="normal" if enable else "disabled")
        # Removing icons does not need an image -- any scanned target works.
        if windows_folder.is_supported():
            self.remove_btn.configure(
                state="normal" if self.targets else "disabled")
        if self.targets:
            self.tree.selection_set(self.tree.get_children()[0])
        else:
            self.preview_source = None
        self._update_preview()

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        for t in self.targets:
            img = os.path.basename(t["image"]) if t["image"] else "—"
            self.tree.insert("", "end",
                             values=(img, i18n.status(t["status"])),
                             text=os.path.basename(t["folder"]))

    def _sync_template_display(self):
        """Show the localized name of the current template in the combo."""
        self.template.set(i18n.template_name(self.template_key))

    def _on_template(self):
        self.template_key = i18n.template_key_from_display(self.template.get())
        self.tpl_desc.configure(
            text=i18n.template_desc().get(self.template_key, ""))
        self._update_preview()

    def _on_tree_select(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if 0 <= idx < len(self.targets) and self.targets[idx]["image"]:
            self.preview_source = self.targets[idx]["image"]
        else:
            self.preview_source = None
        self._update_preview()

    def _update_preview(self):
        name = self.template_key
        self.tpl_desc.configure(text=i18n.template_desc().get(name, ""))
        src = self.preview_source or self.sample
        if not src or not os.path.exists(src):
            return
        # Render off the GUI thread so the interface never freezes while
        # ImageMagick runs. A token cancels stale renders if the user
        # switches templates quickly.
        self._preview_token = getattr(self, "_preview_token", 0) + 1
        token = self._preview_token

        def _work():
            try:
                pil = render_to_pil(src, name)
            except Exception as exc:  # noqa: BLE001
                self.preview_q.put(("preview", (token, None, exc)))
                return
            self.preview_q.put(("preview", (token, pil, None)))

        threading.Thread(target=_work, daemon=True).start()

    def _show_preview(self, pil):
        try:
            photo = ImageTk.PhotoImage(pil)
        except Exception:
            return
        self.photos.append(photo)
        if len(self.photos) > 64:  # bound the PhotoImage cache
            self.photos = self.photos[-32:]
        self.preview_canvas.configure(image=photo)

    def _poll_preview(self):
        """Apply queued render results on the Tk main thread. Runs forever."""
        try:
            while True:
                kind, payload = self.preview_q.get_nowait()
                if kind == "preview":
                    token, pil, exc = payload
                    if exc is not None:
                        self.log_key("preview_error", err=exc)
                    elif token == getattr(self, "_preview_token", None) \
                            and pil is not None:
                        self._show_preview(pil)
                elif kind == "gallery":
                    cell, pil, name, exc = payload
                    if exc is not None:
                        self._gallery_error(cell, name, exc)
                    elif pil is not None:
                        self._gallery_set(cell, pil, name)
                elif kind == "log":
                    self.log_entry(payload)
                elif kind == "refresh_btn_enable":
                    self.refresh_btn.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(60, self._poll_preview)

    # ----------------------------- gallery -------------------------------- #
    def gallery(self):
        win = tk.Toplevel(self.root)
        win.title(i18n.T("gallery"))
        win.transient(self.root)
        win.configure(background=BG)
        src = self.preview_source or self.sample
        frame = ttk.Frame(win, padding=12, style="Card.TFrame")
        frame.grid(sticky="nsew")
        cells = []
        for i, name in enumerate(rcfi_templates.list_templates()):
            cell = ttk.Frame(frame, style="Card.TFrame", padding=8)
            cell.grid(row=i // 3, column=i % 3, padx=8, pady=8)
            cells.append((cell, name))

        # Render every template in a background thread; cells fill in
        # progressively so the gallery window never blocks the UI. Results
        # go through the queue and are applied on the Tk main thread.
        def _work():
            for cell, name in cells:
                try:
                    pil = render_to_pil(src, name, scale=128)
                    self.preview_q.put(("gallery", (cell, pil, name, None)))
                except Exception as exc:  # noqa: BLE001
                    self.preview_q.put(("gallery", (cell, None, name, exc)))

        threading.Thread(target=_work, daemon=True).start()
        win.photos = self.photos

    def _gallery_set(self, cell, pil, name):
        if not cell.winfo_exists():
            return
        try:
            photo = ImageTk.PhotoImage(pil)
        except Exception:
            return
        self.photos.append(photo)
        host = ttk.Frame(cell, style="Neutral.TFrame", width=128, height=128)
        host.grid(row=0, column=0)
        host.update_idletasks()
        lbl = tk.Label(host, image=photo, background=SOFT, borderwidth=0)
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(cell, text=i18n.template_name(name),
                  style="Muted.TLabel").grid(row=1, column=0, pady=(6, 0))

    def _gallery_error(self, cell, name, exc):
        if not cell.winfo_exists():
            return
        ttk.Label(cell, text=f"{i18n.template_name(name)}\n{exc}",
                  style="Muted.TLabel").grid(row=0, column=0, padx=8, pady=8)

    # ----------------------------- generate ------------------------------- #
    def generate(self):
        if self.busy:
            return
        if not self.targets:
            messagebox.showinfo(i18n.T("app_name"), i18n.T("scan_first"))
            return
        self.busy = True
        self.gen_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.progress.configure(maximum=max(1, len(self.targets)), value=0)
        self.status_var.set(i18n.T("status_processing"))
        if not rcfi_templates.locate_imagick():
            # Every template would now silently degrade to the same generic
            # Pillow fallback icon -- tell the user instead of hiding it.
            self.log_key("warn_no_im", "err")
        # Read every tkinter value HERE, in the GUI thread: tkinter
        # variables are Tcl objects and are not safe to touch from a
        # background thread.  The worker receives plain Python values.
        existing = "overwrite" if self.overwrite.get() else "skip"
        refresh = bool(self.refresh_expl.get())
        # The template too: the combo could be changed while the batch is
        # running -- capture the value before the thread starts.  The
        # internal Latin key -- NOT the (localized) combo display name: the
        # engine only knows the key.  In the Persian UI the display name is
        # e.g. «جعبه DVD تیره»; passing that made every generation silently
        # fall back to the generic Pillow icon.
        template = self.template_key
        # Freeze the template combo so what runs is what the user sees.
        self.tpl_combo.configure(state="disabled")
        threading.Thread(target=self._worker,
                         args=(existing, refresh, template),
                         daemon=True).start()
        self._pump()

    def _worker(self, existing: str, refresh: bool, template: str):
        """The batch worker -- runs OFF the GUI thread.

        Every tkinter value is read in ``generate`` (GUI thread) and
        passed in as a plain argument: ``existing`` is "overwrite"/
        "skip", ``refresh`` mirrors the refresh-Explorer checkbox and
        ``template`` is the internal Latin template key."""
        try:
            total = len(self.targets)
            # Applying the icon IS the whole point of this app -- on Windows
            # it always runs; there is no toggle for it any more.
            apply_on = windows_folder.is_supported()

            # One folder's work, run off the GUI thread (pool threads).
            # Every folder's result is logged as a STRUCTURED entry
            # (translated keys + plain values) so a later language switch
            # can re-render the whole log in the other language.
            def _process(t):
                folder = t["folder"]
                prefix = os.path.basename(folder)
                if not t["image"]:
                    return ("no-image", folder,
                            ("k", None, None,
                             [("no_image_item", {"folder": folder})]))
                try:
                    # size is fixed: every .ico is written as the full
                    # multi-resolution set (256->16 px); nothing to choose.
                    res = icon_engine.make_ico_for_folder(
                        folder, t["image"], template, existing=existing)
                except Exception as exc:  # noqa: BLE001
                    return ("error", folder,
                            ("k", "err", prefix,
                             [("error_msg", {"err": exc})]))
                status = res["status"]
                tag = None
                segs = []
                if status in ("ok", "reused"):
                    segs.append(("icon_created" if status == "ok"
                                 else "ico_reused",
                                 {"ico": os.path.basename(res["ico"])}))
                    tag = "ok"
                    if apply_on:
                        try:
                            # notify=False: NO shell notification per folder --
                            # Explorer is refreshed ONCE after the whole batch
                            # (per-folder ASSOCCHANGED broadcasts made large
                            # batches very slow and could interrupt them).
                            windows_folder.apply_folder_icon(folder,
                                                             res["ico"],
                                                             notify=False)
                            segs.append(("icon_applied", {}))
                        except Exception as exc:  # noqa: BLE001
                            status = "applied-error"
                            tag = "err"
                            segs.append(("apply_error", {"err": exc}))
                elif status == "skipped":
                    segs.append(("already_exists", {}))
                else:
                    tag = "err"
                    segs.append(("error_msg", {"err": res["error"]}))
                return (status, folder, ("k", tag, prefix, segs))

            done = 0
            # Process folders concurrently -- worker count follows the CPU
            # so a large batch finishes fast without oversubscribing cores.
            workers = min(max(1, total), max(2, os.cpu_count() or 2), 8)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [ex.submit(_process, t) for t in self.targets]
                for fut in as_completed(futures):
                    done += 1
                    status, folder, entry = fut.result()
                    self.queue.put(("status", folder, status))
                    self.queue.put(("log", entry))
                    self.queue.put(("progress", done, total))

            # End-of-run: clear the cache and refresh Explorer so the new
            # folder icons become visible right away (Windows only).
            if refresh and windows_folder.is_supported():
                try:
                    res = windows_folder.refresh_explorer()
                    st = res.get("status")
                    if st == "ok":
                        self.queue.put(
                            ("log", self._mk_entry("cache_cleared", "ok")))
                    else:
                        self.queue.put(
                            ("log", self._mk_entry("refresh_status", st=st)))
                except Exception as exc:  # noqa: BLE001
                    self.queue.put(
                        ("log", self._mk_entry("refresh_error", "err",
                                               err=exc)))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(
                ("log", self._mk_entry("global_error", "err", err=exc)))
        finally:
            self.queue.put(("done",))

    def _pump(self):
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, done, total = item
                    self.progress.configure(value=done)
                    self.status_var.set(f"{done}/{total}")
                elif kind == "status":
                    _, folder, status = item
                    try:
                        for i, t in enumerate(self.targets):
                            if t["folder"] == folder:
                                kids = self.tree.get_children()
                                if 0 <= i < len(kids):
                                    self.tree.set(kids[i], "status",
                                                  i18n.status(status))
                                break
                    except Exception:
                        pass
                elif kind == "log":
                    self.log_entry(item[1])
                elif kind == "done":
                    self.busy = False
                    self.gen_btn.configure(state="normal")
                    self.scan_btn.configure(state="normal")
                    self.browse_btn.configure(state="normal")
                    self.tpl_combo.configure(state="readonly")
                    if windows_folder.is_supported():
                        self.remove_btn.configure(state="normal")
                    self.status_var.set(i18n.T("status_done"))
                    self.log_key("log_done", "ok")
                    return
        except queue.Empty:
            pass
        if self.busy:
            self.root.after(80, self._pump)

    # --------------------- manual explorer refresh ------------------------- #
    def refresh_now(self):
        """Clear the icon cache and restart Explorer on demand.

        Some folders can still show the old icon for a while after a run --
        the Windows shell sometimes lags behind (closing every Explorer
        window helps too).  This button does the hard refresh at any time:
        icon/thumbnail cache cleared, cache rebuilt and Explorer restarted
        after a confirmation, so every pending icon shows up immediately.
        """
        if not windows_folder.is_supported():
            return
        if not messagebox.askyesno(i18n.T("refresh_confirm_title"),
                                   i18n.T("refresh_confirm")):
            return
        self.refresh_btn.configure(state="disabled")

        def _work():
            self.preview_q.put(("log", self._mk_entry("refresh_started")))
            try:
                res = windows_folder.refresh_explorer(restart=True)
                st = res.get("status")
                if st == "ok":
                    self.preview_q.put(
                        ("log", self._mk_entry("refresh_done", "ok")))
                else:
                    self.preview_q.put(
                        ("log", self._mk_entry("refresh_status", "err",
                                               st=st)))
            except Exception as exc:  # noqa: BLE001
                self.preview_q.put(
                    ("log", self._mk_entry("refresh_error", "err", err=exc)))
            self.preview_q.put(("refresh_btn_enable", None))

        threading.Thread(target=_work, daemon=True).start()

    # --------------------------- remove icons ------------------------------ #
    def remove_icons(self):
        """Undo the icon wiring (desktop.ini) for every scanned folder.

        This deletes things, so it ONLY runs after an explicit
        confirmation dialog that spells out exactly what is removed and
        what is kept -- nothing happens silently.  The generated
        folder.ico files are only deleted too when the user opted in via
        the checkbox next to the overwrite option."""
        if self.busy or not windows_folder.is_supported():
            return
        if not self.targets:
            messagebox.showinfo(i18n.T("app_name"), i18n.T("scan_first"))
            return
        # tkinter values are read HERE in the GUI thread (same policy as
        # generate); the worker receives plain Python values only.
        del_ico = bool(self.remove_ico_var.get())
        msg_key = "remove_confirm_ico" if del_ico else "remove_confirm"
        if not messagebox.askyesno(i18n.T("remove_confirm_title"),
                                   i18n.T(msg_key)):
            return
        self.busy = True
        self.gen_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        self.browse_btn.configure(state="disabled")
        self.remove_btn.configure(state="disabled")
        self.tpl_combo.configure(state="disabled")
        self.progress.configure(maximum=max(1, len(self.targets)), value=0)
        self.status_var.set(i18n.T("status_processing"))
        threading.Thread(target=self._remove_worker, args=(del_ico,),
                         daemon=True).start()
        self._pump()

    def _remove_worker(self, del_ico: bool):
        """Runs OFF the GUI thread; values arrive as plain arguments."""
        try:
            total = len(self.targets)
            done = 0
            for t in self.targets:
                done += 1
                folder = t["folder"]
                prefix = os.path.basename(folder)
                try:
                    res = windows_folder.remove_folder_icon(folder)
                    if res.get("status") == "not_found":
                        # desktop.ini holds other settings only (or the
                        # folder has none at all): this app never iconned
                        # it, so nothing was touched -- say so and move on.
                        segs = [("no_icon_here", {})]
                        tag, status = "ok", "no-icon"
                    else:
                        segs = [("icon_removed", {})]
                        tag, status = "ok", "removed"
                    if del_ico and res.get("status") != "not_found":
                        ico = t.get("ico") or os.path.join(folder, ICO_NAME)
                        try:
                            os.remove(ico)
                            segs.append(("ico_deleted", {}))
                        except FileNotFoundError:
                            pass
                        except OSError as exc:  # noqa: BLE001
                            segs.append(("ico_delete_error", {"err": exc}))
                            tag, status = "err", "error"
                    elif del_ico:
                        # desktop.ini was not this app's (not_found): any
                        # folder.ico in that folder was made by something
                        # else.  Deleting it would destroy foreign data
                        # right after the log said "left untouched".
                        ico = t.get("ico") or os.path.join(folder, ICO_NAME)
                        if os.path.exists(ico):
                            segs.append(("ico_kept_foreign", {}))
                    self.queue.put(("log", ("k", tag, prefix, segs)))
                except Exception as exc:  # noqa: BLE001
                    status = "error"
                    self.queue.put(
                        ("log", ("k", "err", prefix,
                                 [("error_msg", {"err": exc})])))
                self.queue.put(("status", folder, status))
                self.queue.put(("progress", done, total))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(
                ("log", self._mk_entry("global_error", "err", err=exc)))
        finally:
            self.queue.put(("done",))

    # ----------------------------- misc ------------------------------------ #
    def _change_lang(self, _evt=None):
        """Live-switch the UI language (Persian <-> English), no restart."""
        if self.busy:
            self.lang_var.set(i18n.LANG_NAMES[i18n.current()])
            return
        name = self.lang_var.get()
        code = next((c for c, n in i18n.LANG_NAMES.items() if n == name), None)
        if not code or not i18n.set_lang(code):
            return
        self.root.title(i18n.T("app_title"))
        for child in self.root.winfo_children():
            child.destroy()
        self._build_ui()
        # Re-attach state that lived in the old widgets.
        if self.targets:
            self._populate_tree()
            has_img = any(t["image"] for t in self.targets)
            self.gen_btn.configure(state="normal" if has_img else "disabled")
            if windows_folder.is_supported():
                self.remove_btn.configure(state="normal")
            kids = self.tree.get_children()
            if kids:
                self.tree.selection_set(kids[0])
        self._update_preview()

    # ------------------ language-proof logging ------------------------------ #
    @staticmethod
    def _mk_entry(key: str, tag: str | None = None, **kw):
        """Build one structured (re-renderable) log entry."""
        return ("k", tag, None, [(key, kw)])

    @staticmethod
    def _render_entry(entry) -> str:
        """Render one log entry in the ACTIVE language."""
        if entry[0] == "t":
            return entry[2]
        _kind, _tag, prefix, segs = entry
        text = f"• {prefix}: " if prefix else ""
        return text + "".join(i18n.T(key, **kw) for key, kw in segs)

    def _append_log(self, text: str, tag: str | None):
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")

    def log_entry(self, entry):
        """Store + display one structured log entry."""
        self._log_history.append(entry)
        if len(self._log_history) > 400:  # keep the history bounded
            del self._log_history[:200]
        self._append_log(self._render_entry(entry), entry[1])

    def log_key(self, key: str, tag: str | None = None, prefix=None, **kw):
        """Log one translatable catalogue line (survives language switches)."""
        self.log_entry(("k", tag, prefix, [(key, kw)]))


def main():
    i18n.load_pref()
    root = tk.Tk()

    def _report_err(exc_type, exc_value, exc_tb):
        import traceback
        from pathlib import Path as _P
        err = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            # Persist to a writable, stable location (NOT the frozen
            # _MEIPASS temp dir, which is deleted on exit) so a crash inside
            # the .exe can actually be inspected later.
            logdir = _P(tempfile.gettempdir()) / "FolderIconMaker"
            logdir.mkdir(parents=True, exist_ok=True)
            with open(logdir / "error.log", "a", encoding="utf-8") as fh:
                fh.write(err + "\n")
        except Exception:
            pass

    root.report_callback_exception = _report_err
    _apply_theme(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
