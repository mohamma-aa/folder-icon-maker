"""
i18n.py
=======
Bilingual string catalogue (Persian / English) for Folder Icon Maker
(formerly released as "RCFI GUI").

The UI language is:
  * auto-detected on first run (a Persian Windows -> Persian UI, anything
    else -> English), and
  * remembered in ``~/.folder_icon_maker.json`` once the user picks a
    language from the combo box in the header (the switch is live -- no
    restart needed).

Public API
----------
    load_pref()      -> load the saved language (or auto-detect the first time)
    current()        -> active language code ("fa" / "en")
    set_lang(code)   -> switch + persist; returns True if the language changed
    T(key, **kw)     -> translated (and optionally formatted) string
    status(code)     -> localized display text for a job status code
    template_desc()  -> {template name: description} in the active language
    template_name()  -> localized display name of one template
    template_key_from_display() -> map a display name back to the internal key
    LANG_NAMES       -> {"fa": "فارسی", "en": "English"}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

__all__ = ["LANG_NAMES", "T", "current", "load_pref", "set_lang",
           "status", "template_desc", "template_name",
           "template_key_from_display"]

PREF_FILE = Path.home() / ".folder_icon_maker.json"
# Pre-rename location (releases before 2.3.0, when the app was "RCFI GUI").
LEGACY_PREF_FILE = Path.home() / ".rcfi_gui.json"

LANG_NAMES = {"fa": "فارسی", "en": "English"}

# --------------------------------------------------------------------------- #
# UI strings
# --------------------------------------------------------------------------- #
STRINGS: dict = {
    "fa": {
        "app_name": "آیکون‌ساز پوشه",
        "app_title": "آیکون‌ساز پوشه  -  ابزار آیکون پوشه برای ویندوز",
        "app_subtitle": ("ساخت آیکون پوشه از تصویر درون هر زیرپوشه، با قالب‌های "
                         "Original RightClick Folder Icon Tools"),
        "mode_batch": "حالت دسته‌ای",
        "mode_single": "حالت تکی",
        "settings": "تنظیمات",
        "source_folder": "پوشه مبدأ:",
        "target_folder": "پوشه هدف:",
        "image_path": "تصویر:",
        "browse": "انتخاب پوشه…",
        "browse_image": "انتخاب تصویر…",
        "dlg_browse_image": "انتخاب تصویر برای آیکون",
        "scan": "پویش (Scan)",
        "template_label": "قالب:",
        "recursive": "شامل زیرپوشه‌ها (بازگشتی)",
        "overwrite": "بازنویسی آیکون‌های موجود",
        "refresh_explorer": "پاک‌سازی کش و رفرش اکسپلورر در پایان",
        "preview_frame": "پیش‌نمایش قالب",
        "gallery": "پیش‌نمایش همه قالب‌ها",
        "tree_frame": "زیرپوشه‌ها و تصاویر یافت‌شده",
        "tree_frame_single": "هدف انتخاب‌شده",
        "col_folder": "پوشه",
        "col_image": "تصویر",
        "col_status": "وضعیت",
        "generate": "تولید و اعمال آیکون‌ها",
        "status_ready": "آماده",
        "status_processing": "در حال پردازش…",
        "status_done": "تمام شد",
        "log_frame": "گزارش",
        "log_start": "برای شروع، یک پوشه مبدأ انتخاب کنید.",
        "dlg_browse_title": "انتخاب پوشه مبدأ",
        "err_invalid_root": "پوشه مبدأ نامعتبر است.",
        "err_invalid_image": "فایل تصویر معتبر نیست.",
        "err_need_both": "هر دو مورد (پوشه و تصویر) را انتخاب کنید.",
        "log_scan_single": "۱ پوشه پیدا شد (با تصویر).",
        "no_image_item": "• بدون تصویر: {folder}",
        "preview_error": "خطا در پیش‌نمایش: {err}",
        "scan_first": "ابتدا یک پوشه را پویش کنید.",
        "error_msg": "خطا: {err}",
        "icon_created": "آیکون ساخته شد → {ico}",
        "ico_reused": "آیکون موجود سالم است → {ico}",
        "icon_applied": " | اعمال شد",
        "apply_error": " | خطا در اعمال: {err}",
        "already_exists": "از قبل موجود (رد شد)",
        "warn_no_im": ("• هشدار: آیمج‌مجیک پیدا نشد — همه‌ی قالب‌ها همان آیکون "
                       "عمومی جایگزین را می‌سازند. برای قالب‌های واقعی، "
                       "آیمج‌مجیک را نصب کنید یا نسخه‌ی پرتابل آن را در "
                       "پوشه‌ی rcfi_assets\\resources بگذارید (هنگام ساخت، "
                       "داخل exe بسته‌بندی می‌شود)."),
        "cache_cleared": "• کش تامبنیل/آیکون پاک شد و اکسپلورر رفرش شد.",
        "refresh_status": "• رفرش اکسپلورر: {st}",
        "refresh_error": "• رفرش اکسپلورر خطا: {err}",
        "btn_refresh_explorer": "پاک‌سازی کش + رفرش اکسپلورر",
        "refresh_confirm_title": "رفرش اکسپلورر",
        "refresh_confirm": ("اکسپلورر بسته و دوباره اجرا می‌شود تا آیکون‌های "
                            "جدید حتماً نمایش داده شوند.\n"
                            "همه‌ی پنجره‌های اکسپلورر بسته می‌شوند و نوار "
                            "وظیفه چند لحظه خاموش و روشن می‌شود.\n\n"
                            "ادامه می‌دهید؟"),
        "refresh_started": "• در حال پاک‌سازی کش آیکون و رفرش اکسپلورر…",
        "refresh_done": "• کش آیکون پاک و اکسپلورر ری‌استارت شد.",
        "btn_remove_icons": "حذف آیکون‌ها (desktop.ini)",
        "remove_confirm_title": "حذف آیکون پوشه‌ها",
        "remove_confirm": ("desktop.ini فایل مخفی‌ای است که ویندوز تنظیمات "
                           "سفارشی هر پوشه را در آن نگه می‌دارد — از جمله "
                           "آیکونی که همین برنامه ساخته و اعمال کرده است. "
                           "برای هر پوشهٔ فهرست‌شده، مدخل IconResource از "
                           "desktop.ini حذف می‌شود و پوشه به شکل عادی "
                           "ویندوز برمی‌گردد.\n"
                           "اگر desktop.ini فقط متعلق به همین برنامه باشد، "
                           "کل فایل هم پاک می‌شود؛ اگر تنظیمات دیگری در آن "
                           "باشد (FolderType، توضیح و ...) فقط خط آیکون "
                           "برداشته می‌شود و بقیه حفظ می‌شود.\n"
                           "خود فایل folder.ico حذف نمی‌شود.\n\n"
                           "ادامه می‌دهید؟"),
        "remove_confirm_ico": ("desktop.ini فایل مخفی‌ای است که ویندوز تنظیمات "
                               "سفارشی هر پوشه را در آن نگه می‌دارد — از جمله "
                               "آیکونی که همین برنامه ساخته و اعمال کرده است. "
                               "برای هر پوشهٔ فهرست‌شده، مدخل IconResource از "
                               "desktop.ini حذف می‌شود و پوشه به شکل عادی "
                               "ویندوز برمی‌گردد؛ و چون گزینهٔ حذف folder.ico "
                               "فعال است، فایل folder.ico داخل هر پوشه هم پاک "
                               "می‌شود (اگر تصویر اصلی را دیگر ندارید، این "
                               "فایل تنها نسخهٔ باقی‌ماندهٔ آیکون است).\n\n"
                               "ادامه می‌دهید؟"),
        "remove_ico_chk": "هنگام «حذف آیکون‌ها»، فایل folder.ico هم پاک شود",
        "icon_removed": "آیکون حذف شد (desktop.ini پاک‌سازی شد)",
        "no_icon_here": "آیکونی از این برنامه در desktop.ini نبود — فایل دست‌نخورده ماند",
        "ico_kept_foreign": " | folder.ico بیگانه دست‌نخورده ماند (ساختهٔ این برنامه نبود)",
        "ico_deleted": " | folder.ico هم حذف شد",
        "ico_delete_error": " | خطا در حذف folder.ico: {err}",
        "global_error": "خطای کلی در پردازش: {err}",
        "log_done": "— پردازش به پایان رسید —",
    },
    "en": {
        "app_name": "Folder Icon Maker",
        "app_title": "Folder Icon Maker  -  Folder Icon Tool for Windows",
        "app_subtitle": ("Create a folder icon from the image inside each "
                         "sub-folder, using the original RightClick Folder "
                         "Icon Tools templates"),
        "mode_batch": "Batch mode",
        "mode_single": "Single mode",
        "settings": "Settings",
        "source_folder": "Source folder:",
        "target_folder": "Target folder:",
        "image_path": "Image:",
        "browse": "Browse…",
        "browse_image": "Choose image…",
        "dlg_browse_image": "Choose the icon image",
        "scan": "Scan",
        "template_label": "Template:",
        "recursive": "Include sub-folders (recursive)",
        "overwrite": "Overwrite existing icons",
        "refresh_explorer": "Clear cache & refresh Explorer when done",
        "preview_frame": "Template preview",
        "gallery": "Preview all templates",
        "tree_frame": "Sub-folders & images found",
        "tree_frame_single": "Selected target",
        "col_folder": "Folder",
        "col_image": "Image",
        "col_status": "Status",
        "generate": "Generate & apply icons",
        "status_ready": "Ready",
        "status_processing": "Processing…",
        "status_done": "Done",
        "log_frame": "Log",
        "log_start": "To get started, choose a source folder.",
        "dlg_browse_title": "Select source folder",
        "err_invalid_root": "Invalid source folder.",
        "err_invalid_image": "Invalid image file.",
        "err_need_both": "Select both a folder and an image.",
        "log_scan_single": "1 folder found (with images).",
        "no_image_item": "• No image: {folder}",
        "preview_error": "Preview error: {err}",
        "scan_first": "Scan a folder first.",
        "error_msg": "error: {err}",
        "icon_created": "icon created → {ico}",
        "ico_reused": "existing valid folder.ico → {ico}",
        "icon_applied": " | applied",
        "apply_error": " | apply error: {err}",
        "already_exists": "already exists (skipped)",
        "warn_no_im": ("• Warning: ImageMagick was not found — every template "
                       "will produce the same generic fallback icon. Install "
                       "ImageMagick, or put a portable magick.exe into "
                       "rcfi_assets\\resources (packed into the exe at "
                       "build time)."),
        "cache_cleared": "• Icon/thumbnail cache cleared and Explorer refreshed.",
        "refresh_status": "• Explorer refresh: {st}",
        "refresh_error": "• Explorer refresh error: {err}",
        "btn_refresh_explorer": "Clear cache & refresh Explorer",
        "refresh_confirm_title": "Refresh Explorer",
        "refresh_confirm": ("Explorer will be closed and restarted so the new "
                            "icons definitely show up.\n"
                            "All Explorer windows will close and the taskbar "
                            "blinks for a moment.\n\n"
                            "Continue?"),
        "refresh_started": "• Clearing the icon cache and refreshing Explorer…",
        "refresh_done": "• Icon cache cleared and Explorer restarted.",
        "btn_remove_icons": "Remove icons (desktop.ini)",
        "remove_confirm_title": "Remove folder icons",
        "remove_confirm": ("desktop.ini is the hidden file Windows uses to "
                           "store a folder's custom settings — including the "
                           "icon this app created and applied.  For every "
                           "listed folder the IconResource entry is "
                           "removed from desktop.ini and the folder returns "
                           "to the normal Windows look.\n"
                           "If desktop.ini belongs to this app alone the "
                           "whole file is deleted; if it holds other "
                           "settings (FolderType, InfoTip, ...) only the "
                           "icon line is taken out and the rest survives.\n"
                           "The folder.ico file itself is kept.\n\n"
                           "Continue?"),
        "remove_confirm_ico": ("desktop.ini is the hidden file Windows uses to "
                               "store a folder's custom settings — including "
                               "the icon this app created and applied.  For "
                               "every listed folder the IconResource "
                               "entry is removed from desktop.ini and the "
                               "folder returns to the normal Windows look; "
                               "and because \"also delete folder.ico\" is "
                               "ticked, the folder.ico inside each folder is "
                               "deleted too (if you no longer have the "
                               "original image, this file is the only "
                               "remaining copy of the icon).\n\n"
                               "Continue?"),
        "remove_ico_chk": "When removing icons, also delete the folder.ico file",
        "icon_removed": "icon removed (desktop.ini cleaned)",
        "no_icon_here": "no icon of this app in desktop.ini — file left untouched",
        "ico_kept_foreign": " | foreign folder.ico left untouched (not made by this app)",
        "ico_deleted": " | folder.ico deleted too",
        "ico_delete_error": " | error deleting folder.ico: {err}",
        "global_error": "Processing error: {err}",
        "log_done": "— Processing finished —",
    },
}

# Localized display text for the raw job-status codes used by icon_engine.
_STATUS: dict = {
    "fa": {
        "pending": "در انتظار",
        "no-image": "بدون تصویر",
        "ok": "انجام شد",
        "reused": "موجود (استفاده شد)",
        "skipped": "رد شد",
        "error": "خطا",
        "applied-error": "خطای اعمال",
        "removed": "حذف شد",
        "no-icon": "آیکونی نبود",
    },
    "en": {
        "pending": "pending",
        "no-image": "no image",
        "ok": "done",
        "reused": "reused",
        "skipped": "skipped",
        "error": "error",
        "applied-error": "apply error",
        "removed": "removed",
        "no-icon": "no icon",
    },
}

# Per-template description shown under the live preview.
TEMPLATE_DESC: dict = {
    "fa": {
        "(none)": "تصویر بدون تغییر، در یک مربع ۱:۱ (بدون برش).",
        "(Shadow Only)": "تصویر با سایه نرم، در مرکز مربع.",
        "Square": "تصویر کشیده‌شده در یک مربع ۱:۱، کاملاً بدون برش (بدون پس‌زمینه).",
        "DVDBox Dark": "قالب جعبه DVD تیره با دیسک نیمه‌بیرون.",
        "DVDBox Light": "قالب جعبه DVD روشن با دیسک نیمه‌بیرون.",
        "DVDCase Bluray": "قالب کیس Blu-ray.",
        "DVDCase Transparent Plastic": "قالب کیس پلاستیکی شفاف.",
        "DiscArt": "قالب دیسک (DiscArt).",
    },
    "en": {
        "(none)": "Image unchanged, fitted inside a 1:1 square (no crop).",
        "(Shadow Only)": "Image with a soft drop shadow, centered in the square.",
        "Square": "Image stretched into an exact 1:1 square, no cropping "
                  "(no background).",
        "DVDBox Dark": "Dark DVD box template with a half-out disc.",
        "DVDBox Light": "Light DVD box template with a half-out disc.",
        "DVDCase Bluray": "Blu-ray case template.",
        "DVDCase Transparent Plastic": "Transparent plastic case template.",
        "DiscArt": "Disc label template (DiscArt).",
    },
}

# Localized display names of the templates.  The internal keys (the names
# used by the engine, desktop.ini and the code) ALWAYS stay Latin -- only
# what the user sees in the combo box and the gallery is translated.
TEMPLATE_NAMES: dict = {
    "fa": {
        "(none)": "بدون قالب",
        "(Shadow Only)": "فقط سایه",
        "Square": "مربع",
        "DVDBox Dark": "جعبه DVD تیره",
        "DVDBox Light": "جعبه DVD روشن",
        "DVDCase Bluray": "کیس بلوری",
        "DVDCase Transparent Plastic": "کیس پلاستیکی شفاف",
        "DiscArt": "لیبل دیسک",
    },
}

_current: str | None = None


# --------------------------------------------------------------------------- #
# language selection / persistence
# --------------------------------------------------------------------------- #
def detect_default() -> str:
    """Guess the UI language from the OS locale (Persian -> fa, else en)."""
    loc = ""
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
                loc = buf.value
        except Exception:
            loc = ""
    if not loc:
        try:
            import locale
            import warnings
            with warnings.catch_warnings():
                # getdefaultlocale() is deprecated since 3.11 but still
                # works everywhere; silence the noise until a real
                # cross-platform replacement is adopted.
                warnings.simplefilter("ignore", DeprecationWarning)
                loc = locale.getdefaultlocale()[0] or ""
        except Exception:
            loc = ""
    return "fa" if loc.lower().startswith("fa") else "en"


def load_pref() -> str:
    """Load the saved language choice; fall back to OS auto-detection.

    Users of the pre-rename releases kept their choice in
    ``~/.rcfi_gui.json``; when the new file does not exist yet, that
    choice is migrated over once instead of silently resetting the
    language to the auto-detected default."""
    global _current
    lang = ""
    try:
        data = json.loads(PREF_FILE.read_text(encoding="utf-8"))
        lang = str(data.get("lang", "")).lower()
    except Exception:
        lang = ""
    if not lang:
        try:
            legacy = json.loads(
                LEGACY_PREF_FILE.read_text(encoding="utf-8"))
            migrated = str(legacy.get("lang", "")).lower()
            if migrated in LANG_NAMES:
                lang = migrated
                try:      # carry the choice over to the new location
                    PREF_FILE.write_text(
                        json.dumps({"lang": lang}, ensure_ascii=False),
                        encoding="utf-8")
                except Exception:
                    pass  # migration must never break the app
        except Exception:
            pass
    _current = lang if lang in LANG_NAMES else detect_default()
    return _current


def current() -> str:
    if _current is None:
        load_pref()
    return _current  # type: ignore[return-value]


def save_pref() -> None:
    try:
        PREF_FILE.write_text(
            json.dumps({"lang": current()}, ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass  # saving the preference must never break the app


def set_lang(lang: str) -> bool:
    """Switch the active language and persist the choice."""
    global _current
    if lang not in LANG_NAMES or lang == current():
        return False
    _current = lang
    save_pref()
    return True


# --------------------------------------------------------------------------- #
# translation helpers
# --------------------------------------------------------------------------- #
def T(key: str, **kw) -> str:
    """Return the translated string for *key* in the active language."""
    text = STRINGS.get(current(), {}).get(key) \
        or STRINGS["en"].get(key) or key
    return text.format(**kw) if kw else text


def status(code: str) -> str:
    """Localize a raw job-status code for display in the tree column."""
    return _STATUS.get(current(), _STATUS["en"]).get(code, code)


def template_desc() -> dict:
    """Return {template name: description} in the active language."""
    return TEMPLATE_DESC.get(current(), TEMPLATE_DESC["en"])


def template_name(name: str) -> str:
    """Localized display name of a template (internal names stay Latin)."""
    return TEMPLATE_NAMES.get(current(), {}).get(name, name)


def template_key_from_display(display: str) -> str:
    """Map a localized template display name back to its internal key."""
    for key, label in TEMPLATE_NAMES.get(current(), {}).items():
        if label == display:
            return key
    return display  # already an internal key (or an unknown name)
