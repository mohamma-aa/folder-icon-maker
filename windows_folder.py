"""
windows_folder.py
=================
Apply a generated ``.ico`` as the icon of a Windows folder by writing a
``desktop.ini`` file and setting the required file attributes.

Key gotchas handled here (these are the usual reasons a folder icon "does not
apply"):

* ``IconResource`` is written as a **relative** path (just the icon file name,
  e.g. ``folder.ico,0``).  The icon file is saved *inside* the folder, so the
  whole folder stays portable: copy/move it to another PC and the icon keeps
  working.  (An absolute path would break the moment the folder is moved.)
* **Only the ``IconResource`` entry is written/updated.**  Any other
  settings an existing ``desktop.ini`` may carry -- ``FolderType``, view
  state, ``InfoTip``, localized file names, ... -- are preserved, and when
  an icon is removed the file is deleted only if nothing else is left in
  it.  (The previous behaviour replaced the whole file.)
* **Never destroy data we could not read.**  If an existing
  ``desktop.ini`` cannot be read/decoded, the write/remove path stops
  with a clear error instead of overwriting or deleting it.  New content
  is always written to a temp file first and moved over the target in
  one atomic step, so a crash can never leave a truncated file behind.
* The target folder needs the **ReadOnly** attribute (Explorer only reads
  ``desktop.ini`` for folders that are ReadOnly/System).
* ``desktop.ini`` must be **Hidden + System**.
* ``desktop.ini`` is written as **UTF-16LE with BOM** -- the Unicode
  format Microsoft documents for it.  UTF-8 (even with a BOM) can be
  misread by the Windows shell and garble localized text such as
  ``LocalizedResourceName`` or a non-ASCII ``InfoTip``; existing files
  of any encoding are still read and merged losslessly.
* **Attribute changes are checked and reversible.**  ``SetFileAttributesW``
  returns 0 on failure -- the old code never looked at it, so a failed
  Hidden/System change was silently reported as success.  Failures now
  raise, and any attribute stripped for a replace is restored when the
  operation does not complete.  A failure *after* the desktop.ini write
  (ReadOnly on the folder, Hidden+System on the file) also rolls the
  file back to its previous raw bytes and attributes -- or removes it
  again when this tool had just created it.
* The folder's **ReadOnly flag is only taken back if this tool set it**.
  When ``apply_folder_icon`` has to ADD ReadOnly (Explorer only reads
  desktop.ini on ReadOnly/System folders), it records that fact inside
  desktop.ini itself (``RCFI-SetReadOnly=1``); the remove path clears the
  flag only when that marker is present AND the file was ours alone --
  a ReadOnly flag the folder already had before is never touched.
* Explorer is refreshed **once at the end of the whole run**
  (``refresh_explorer``), not per folder -- the per-folder
  ``SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST | SHCNF_FLUSH)``
  broadcast forces the
  whole shell to rebuild its associations and made large batches very slow.
  Pass ``notify=True`` to force an immediate per-folder notification
  (useful for one-off single-folder tools).

This module is Windows-only. On other platforms ``is_supported()`` returns
False so the GUI can disable the option gracefully.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

__all__ = ["is_supported", "apply_folder_icon", "remove_folder_icon",
           "refresh_explorer"]

FILE_ATTRIBUTE_READONLY = 0x1
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_NORMAL = 0x80


def is_supported() -> bool:
    return sys.platform.startswith("win")


def _ini_path(folder: str) -> str:
    return os.path.join(folder, "desktop.ini")


ICON_ENTRY = "IconResource"   # the only desktop.ini key this tool ever changes
MARKER_ENTRY = "RCFI-SetReadOnly"   # records "we added the folder ReadOnly flag"


def _is_marker_entry(line: str) -> bool:
    """True ONLY for the exact ``RCFI-SetReadOnly=...`` marker entry."""
    stripped = line.strip()
    if stripped.startswith((";", "#")):
        return False
    key, sep, _value = stripped.partition("=")
    return bool(sep) and key.strip().lower() == MARKER_ENTRY.lower()


def _is_icon_entry(line: str) -> bool:
    """True ONLY for the exact ``IconResource=...`` entry.

    The key name is compared exactly: a ``startswith`` match would also
    catch keys like ``IconResourceExtra`` and silently replace or drop
    them."""
    stripped = line.strip()
    if stripped.startswith((";", "#")):      # comment lines are never keys
        return False
    key, sep, _value = stripped.partition("=")
    return bool(sep) and key.strip().lower() == ICON_ENTRY.lower()


def _read_ini_lines(path: str) -> list[str] | None:
    """Read desktop.ini as a list of lines, tolerating the encodings
    Windows tools actually write (UTF-16 with BOM, UTF-16LE without BOM,
    UTF-8 with BOM, ANSI).

    The encoding is picked from the BOM when there is one; without a BOM,
    NUL bytes in the raw data mean BOM-less UTF-16LE (a naive UTF-8 decode
    would turn that into silent NUL soup), and everything else is tried as
    UTF-8 then ANSI.  Returns None when the file cannot be read or decoded
    into plausible ini text -- callers must then STOP instead of writing
    back settings they never really parsed (a lossy lenient decode would
    silently corrupt them)."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        encodings = ("utf-16",)           # the BOM decides the byte order
    elif raw.startswith(b"\xef\xbb\xbf"):
        encodings = ("utf-8-sig",)
    elif b"\x00" in raw[:4096]:
        # No BOM but NUL bytes -> BOM-less UTF-16LE (some third-party
        # tools write desktop.ini like that).
        encodings = ("utf-16-le",)
    else:
        encodings = ("utf-8", "mbcs")
    for enc in encodings:
        try:
            text = raw.decode(enc)
        except (UnicodeError, LookupError):
            continue
        # Plausibility guard: NUL (binary soup / mis-decoded UTF-16),
        # U+FFFD (lossy mapping) or any other control character means the
        # codec did not really produce readable settings -- refuse the
        # file rather than merging garbage back into it.
        if "\x00" in text or "\ufffd" in text or any(
                c < " " and c not in "\t\r\n" for c in text):
            continue
        return text.splitlines()
    return None


def _merge_icon_entry(lines: list[str], ico_name: str,
                      mark_readonly: bool = False) -> list[str]:
    """Return *lines* with ONLY the IconResource entry replaced or inserted.

    Everything else in an existing desktop.ini (FolderType, view state,
    InfoTip, localized names, comments, ...) survives untouched -- the old
    code replaced the whole file and silently discarded such settings.

    ``mark_readonly`` records inside the file that THIS tool had to add
    the folder's ReadOnly flag (it was not set before).  An existing
    marker is always kept as-is -- it means an earlier run of this tool
    added the flag, and that fact must survive re-iconning."""
    icon_line = f"{ICON_ENTRY}={ico_name},0"
    # 1) replace the first existing entry, drop any later duplicates
    replaced = False
    out: list[str] = []
    for line in lines:
        if _is_icon_entry(line):
            if not replaced:
                out.append(icon_line)
                replaced = True
            continue
        out.append(line)
    if not replaced:
        # 2) no previous entry: insert right after [.ShellClassInfo]
        for i, line in enumerate(out):
            if line.strip().lower() == "[.shellclassinfo]":
                out = out[:i + 1] + [icon_line] + out[i + 1:]
                break
        else:
            # 3) the section itself is missing: prepend it
            out = ["[.ShellClassInfo]", icon_line] + out
    # Marker handling: never duplicate, never drop an existing one.
    if mark_readonly and not any(_is_marker_entry(l) for l in lines):
        i = next(i for i, l in enumerate(out) if _is_icon_entry(l))
        out = out[:i + 1] + [f"{MARKER_ENTRY}=1"] + out[i + 1:]
    return out


def _strip_icon_entry(lines: list[str]) -> tuple[list[str], bool, bool]:
    """(kept_lines, has_other_settings, we_set_readonly) with the
    IconResource line AND our own marker line removed.

    ``has_other_settings`` is True when a key=value line remains that
    this tool did not write itself -- i.e. the file is worth keeping
    even without the icon.  The view-state boilerplate this tool writes
    into a fresh desktop.ini (``Mode=`` / ``Vid=`` placeholders and
    ``FolderType=Generic``) does NOT count as a foreign setting: a file
    holding nothing but that was created by this tool alone, so the
    caller may delete it and take the ReadOnly flag back.  A real
    setting (InfoTip, LocalizedResourceName, an actual view mode such
    as ``Mode=2``, a different FolderType, ...) keeps the file alive,
    exactly as before.  ``we_set_readonly`` is True when the marker
    says this tool was the one that added the folder's ReadOnly flag
    (only then may the remove path take it back)."""
    we_set_readonly = any(_is_marker_entry(l) for l in lines)
    kept = [l for l in lines
            if not _is_icon_entry(l) and not _is_marker_entry(l)]
    leftover = [l for l in kept
                if l.strip() and not l.strip().startswith("[")]
    our_boilerplate = {"mode=", "vid=", "foldertype=generic"}
    foreign = [l for l in leftover
               if l.strip().lower() not in our_boilerplate]
    return kept, bool(foreign), we_set_readonly


def _atomic_write_ini(path: str, content: str) -> None:
    """Write *content* to a temp file in the same directory and move it
    over *path* in one atomic step.

    The old code opened the destination directly with "w": a crash (or a
    full disk) halfway through left a truncated desktop.ini behind.  With
    write-to-temp + ``os.replace`` the previous content stays intact until
    the complete new content is ready.  The caller must have normalised
    the attributes of an existing destination file, because Windows
    refuses to replace a Hidden/System file."""
    tmp = os.path.join(os.path.dirname(path) or ".",
                       f"desktop.ini.rcfi-{os.getpid()}.tmp")
    try:
        # UTF-16LE with BOM -- the Unicode format Microsoft documents for
        # desktop.ini (shell reads it on every Windows version; UTF-8 can
        # garble localized names there).  Written explicitly as LE plus a
        # leading U+FEFF so the byte order never depends on the platform.
        with open(tmp, "w", encoding="utf-16-le", newline="") as f:
            f.write("\ufeff")
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        # Retry briefly: OneDrive / antivirus can hold the file for a
        # moment.
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                return
            except PermissionError as exc:
                if attempt == 3:
                    raise PermissionError(
                        f"cannot replace desktop.ini -- it is locked or "
                        f"access denied (OneDrive/antivirus may be "
                        f"blocking it): {exc}"
                    ) from exc
                time.sleep(0.2)
    except BaseException:
        # Never leave the temp file (or a half-done state) behind.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Atomically replace *path* with raw *data* (write-to-temp +
    ``os.replace``, with the same brief retry as ``_atomic_write_ini``).

    Used only by the rollback path, which must reproduce the previous
    file byte-for-byte -- re-encoding it would technically change a file
    this tool was supposed to leave alone."""
    tmp = os.path.join(os.path.dirname(path) or ".",
                       f"desktop.ini.rcfi-{os.getpid()}.tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.2)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _restore_ini_state(path: str, existed: bool,
                       prev_raw: bytes | None,
                       prev_attr: int | None) -> None:
    """Best-effort rollback of desktop.ini after a failed apply.

    Restores the previous raw bytes + attributes; when the file did not
    exist before, the freshly created one is removed again.  Every step
    is wrapped so a rollback that hits an error (locked file, ...) never
    masks the original failure."""
    try:
        if not existed:
            try:
                _set_attr(path, FILE_ATTRIBUTE_NORMAL)
            except OSError:
                pass
            try:
                os.remove(path)
            except OSError:
                pass
            return
        if prev_raw is None:
            return          # nothing was captured -- nothing to restore
        try:
            # Windows refuses to replace a Hidden/System file: normalise
            # first, put the original attributes back after the content.
            _set_attr(path, FILE_ATTRIBUTE_NORMAL)
            _atomic_write_bytes(path, prev_raw)
        except OSError:
            return
        _restore_attr(path, prev_attr if prev_attr is not None
                      else FILE_ATTRIBUTE_NORMAL)
    except Exception:       # noqa: BLE001
        pass


def _write_ini(folder: str, ico_name: str,
               mark_readonly: bool = False) -> None:
    path = _ini_path(folder)
    exists = os.path.exists(path)
    # READ FIRST, touch attributes LATER: open(..., "r") works on a
    # Hidden/System file, so nothing has to be stripped just to inspect
    # the content.  If the read fails we abort having modified NOTHING --
    # the old order (strip attrs, then read) could leave a previously
    # Hidden/System file behind as plain Normal after a failed run.
    if exists:
        existing = _read_ini_lines(path)
        if existing is None:
            # The file IS there but cannot be read/decoded.  Overwriting
            # it with our standard content would destroy whatever other
            # settings it holds -- refuse and surface a clear error
            # instead of silently discarding them.
            raise PermissionError(
                f"desktop.ini exists in '{folder}' but cannot be read -- "
                f"refusing to overwrite it (it may hold settings this "
                f"tool does not want to lose)")
    else:
        existing = None
    if existing is None:
        # Fresh file (no desktop.ini yet).  Relative icon path on purpose:
        # the icon lives inside this folder, so writing just its name
        # (e.g. "folder.ico,0") keeps the folder portable -- move or copy
        # it anywhere and the icon still resolves.  An absolute path would
        # break the moment the folder is relocated.
        content = (
            "[.ShellClassInfo]\r\n"
            f"{ICON_ENTRY}={ico_name},0\r\n"
            + (f"{MARKER_ENTRY}=1\r\n" if mark_readonly else "")
            + "[ViewState]\r\n"
            "Mode=\r\n"
            "Vid=\r\n"
            "FolderType=Generic\r\n"
        )
    else:
        content = "\r\n".join(
            _merge_icon_entry(existing, ico_name,
                              mark_readonly=mark_readonly)) + "\r\n"
    if not exists:
        _atomic_write_ini(path, content)
        return
    # Attributes are stripped only NOW, right before the replace -- Windows
    # refuses to replace a Hidden/System file.  If anything goes wrong the
    # original attributes are put back.
    orig = _get_attr(path)
    if orig is None or orig < 0:
        orig = FILE_ATTRIBUTE_NORMAL
    try:
        _set_attr(path, FILE_ATTRIBUTE_NORMAL)
        _atomic_write_ini(path, content)
    except BaseException:
        _restore_attr(path, orig)
        raise


def _k32():
    """kernel32 with strict prototypes (lazy -- Windows only)."""
    global _KERNEL32
    if _KERNEL32 is None:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        k.SetFileAttributesW.restype = wintypes.BOOL
        k.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        k.GetFileAttributesW.restype = wintypes.DWORD
        _KERNEL32 = k
    return _KERNEL32


_KERNEL32 = None


def _set_attr(path: str, attr: int) -> None:
    """Set file attributes, RAISING on failure (Windows).

    ``SetFileAttributesW`` returns 0 on error; the old code ignored the
    result, so a failed Hidden/System change was silently reported as a
    successful apply and Explorer never picked the icon up.  On
    non-Windows platforms this is a no-op -- the public functions never
    run there (``is_supported()`` gates them), but the ini helpers are
    also exercised directly on development machines."""
    if not sys.platform.startswith("win"):
        return
    if not _k32().SetFileAttributesW(path, attr):
        import ctypes
        raise ctypes.WinError(ctypes.get_last_error())


def _get_attr(path: str) -> int | None:
    """File attributes, or None when the call fails
    (``INVALID_FILE_ATTRIBUTES``) or the platform has no such API."""
    if not sys.platform.startswith("win"):
        return None
    res = _k32().GetFileAttributesW(path)
    if res == 0xFFFFFFFF:        # INVALID_FILE_ATTRIBUTES
        return None
    return res


def _restore_attr(path: str, attr: int) -> None:
    """Best-effort restore of *attr* after a failed operation."""
    try:
        _set_attr(path, attr)
    except OSError:
        pass


def _hidden():
    """(creationflags, startupinfo) that hide a child console on Windows."""
    if sys.platform != "win32":
        return 0, None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return subprocess.CREATE_NO_WINDOW, si


def _refresh_shell(folder: str) -> None:
    try:
        import ctypes
        shell32 = ctypes.windll.shell32
        SHCNE_UPDATEITEM = 0x00002000
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_PATH = 0x0005        # SHCNF_PATHW -- event carries a path
        SHCNF_IDLIST = 0x0000      # event carries PIDLs (NULL = all)
        SHCNF_FLUSH = 0x1000
        f = ctypes.c_wchar_p(folder)
        # UPDATEITEM is path-based, so SHCNF_PATH is correct here.
        shell32.SHChangeNotify(
            SHCNE_UPDATEITEM, SHCNF_PATH | SHCNF_FLUSH, f, None)
        # ASSOCCHANGED is documented (MSDN, SHChangeNotify) to be raised
        # with SHCNF_IDLIST -- and NULL IDLs so it applies to the whole
        # shell.  Sending it with SHCNF_PATH is undefined behaviour: the
        # shell may silently drop the notification and stale icons remain.
        shell32.SHChangeNotify(
            SHCNE_ASSOCCHANGED, SHCNF_IDLIST | SHCNF_FLUSH, None, None)
    except Exception:
        pass


def apply_folder_icon(folder: str, ico_path: str,
                      notify: bool = True) -> dict:
    """Wire *ico_path* as the icon of *folder* (Windows only).

    With ``notify=False`` no shell notification is sent: the caller
    refreshes Explorer **once after the whole batch** instead
    (``refresh_explorer``).  A per-folder
    ``SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_FLUSH)`` blocks until the
    entire shell has re-read its associations -- harmless for one folder,
    brutally slow for hundreds.
    """
    if not is_supported():
        raise NotImplementedError("Folder icon application is Windows-only.")
    folder = os.path.abspath(folder)
    ico_path = os.path.abspath(ico_path)

    # Folder: keep existing attributes and add ReadOnly (so Explorer reads
    # desktop.ini).  When the flag was NOT there before, record that fact
    # inside desktop.ini (RCFI-SetReadOnly=1) so remove_folder_icon can
    # undo exactly what WE did -- and never touch a ReadOnly flag the
    # folder already had.
    cur = _get_attr(folder)
    if cur is None or cur < 0:
        cur = FILE_ATTRIBUTE_NORMAL

    # Snapshot the previous desktop.ini (raw bytes + attributes) so a
    # failure AFTER the write can put everything back.  The icon entry is
    # the only thing this tool changes -- restoring the previous file
    # byte-for-byte therefore undoes the whole apply.
    path = _ini_path(folder)
    existed = os.path.exists(path)
    prev_raw = None
    prev_ini_attr = None
    if existed:
        prev_ini_attr = _get_attr(path)
        try:
            with open(path, "rb") as f:
                prev_raw = f.read()
        except OSError:
            prev_raw = None   # _write_ini will refuse to touch it anyway

    _write_ini(folder, os.path.basename(ico_path),
               mark_readonly=not cur & FILE_ATTRIBUTE_READONLY)

    try:
        try:
            _set_attr(folder, cur | FILE_ATTRIBUTE_READONLY)
        except OSError as exc:
            raise PermissionError(
                f"cannot set the ReadOnly attribute on '{folder}' -- Explorer "
                f"only reads desktop.ini from ReadOnly/System folders: {exc}"
            ) from exc
        try:
            _set_attr(path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        except OSError as exc:
            raise PermissionError(
                f"cannot mark desktop.ini in '{folder}' as Hidden+System -- "
                f"the icon may not be picked up: {exc}") from exc
    except BaseException:
        # Roll back, best effort: previous ini bytes + attributes and the
        # previous folder attributes, so a failed run leaves the folder
        # exactly as it was found.
        _restore_ini_state(path, existed, prev_raw, prev_ini_attr)
        _restore_attr(folder, cur)
        raise

    if notify:
        _refresh_shell(folder)
    return {"folder": folder, "ico": ico_path, "status": "ok"}


def remove_folder_icon(folder: str) -> dict:
    """Remove the icon entry from desktop.ini (Windows only).

    Only the exact ``IconResource`` line (and our own marker line) is
    taken out; any other settings in the file survive.  The file itself
    is deleted only when it was read successfully AND nothing meaningful
    is left in it (i.e. it was ours alone).  A ``desktop.ini`` that holds
    no ``IconResource`` and no ``RCFI-SetReadOnly`` marker at all was
    never written by this tool: it is reported as ``"not_found"`` and
    left byte-for-byte untouched.  The folder's ReadOnly flag
    is cleared only when our ``RCFI-SetReadOnly`` marker says this tool
    was the one that set it -- a flag the folder already had before is
    left untouched.  If the file cannot be read or rewritten, the
    function raises a clear error instead of destroying data."""
    if not is_supported():
        raise NotImplementedError("Folder icon removal is Windows-only.")
    folder = os.path.abspath(folder)
    path = _ini_path(folder)
    if not os.path.exists(path):
        _refresh_shell(folder)
        return {"folder": folder, "status": "ok"}
    # Read FIRST -- if this fails we abort having modified nothing (the
    # old order stripped attributes before reading, so a failed run could
    # leave a previously Hidden/System file sitting there as Normal).
    lines = _read_ini_lines(path)
    if lines is None:
        raise PermissionError(
            f"desktop.ini exists in '{folder}' but cannot be read -- "
            f"refusing to rewrite or delete it")
    if not any(_is_icon_entry(l) or _is_marker_entry(l) for l in lines):
        # The file holds other settings only (FolderType, InfoTip,
        # localized names, ...) -- an icon this tool never wrote.  Even a
        # rewrite-with-the-same-keys would re-encode it (e.g. to UTF-16),
        # and a header-only file would be deleted; both amount to
        # tampering with someone else's folder settings.  Report that
        # there is nothing of ours here and leave the file untouched.
        return {"folder": folder, "status": "not_found"}
    kept, has_other, we_set_readonly = _strip_icon_entry(lines)
    if has_other:
        # Other settings still live here (FolderType, view state,
        # localized names, ...): keep the file, minus the icon.  The
        # folder KEEPS its ReadOnly flag too -- Explorer only honors
        # desktop.ini on ReadOnly/System folders.
        orig = _get_attr(path)
        if orig is None or orig < 0:
            orig = FILE_ATTRIBUTE_NORMAL
        try:
            _set_attr(path, FILE_ATTRIBUTE_NORMAL)
            _atomic_write_ini(path,
                              "\r\n".join(kept).rstrip("\r\n") + "\r\n")
            _set_attr(path, FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
        except BaseException:
            _restore_attr(path, orig)
            raise
    else:
        # Nothing left but our own entry -> delete the file.  Deleting
        # works on a Hidden/System file, so no attribute stripping is
        # needed; if it fails, nothing was modified.
        try:
            os.remove(path)
        except OSError as exc:
            # The icon entry is still inside the file, so the folder
            # would keep showing the icon: reporting success would be
            # a lie.  Surface the failure instead.
            raise PermissionError(
                f"cannot delete desktop.ini in '{folder}' (it may be "
                f"locked by OneDrive/antivirus): {exc}") from exc
        if we_set_readonly:
            # Our marker says WE added ReadOnly when applying the icon --
            # only then is it ours to take back.
            cur = _get_attr(folder)
            if cur is None or cur < 0:
                cur = FILE_ATTRIBUTE_NORMAL
            try:
                _set_attr(folder, cur & ~FILE_ATTRIBUTE_READONLY)
            except OSError as exc:
                raise PermissionError(
                    f"icon entry removed, but the ReadOnly flag of "
                    f"'{folder}' could not be cleared: {exc}") from exc
    _refresh_shell(folder)
    return {"folder": folder, "status": "ok"}


def refresh_explorer(restart: bool = False) -> dict:
    """Best-effort refresh of Explorer + clear of the Shell icon/thumbnail
    cache, so newly applied folder icons become visible immediately.

    What it does (Windows only, never raises):
      * Deletes the cached ``iconcache_*.db`` / ``thumbcache_*.db`` databases
        in ``%LocalAppData%\\Microsoft\\Windows\\Explorer\\`` (best effort --
        they are often locked, so failures are ignored).
      * Rebuilds the icon cache via ``ie4uinit.exe -show`` (Windows 8+).
      * Notifies the shell to re-read everything.
      * Optionally (``restart=True``) restarts Explorer for a guaranteed
        repaint.  Kept off by default because killing Explorer is disruptive
        and can destabilise a running single-file executable.

    On non-Windows platforms this is a no-op returning
    ``{"status": "unsupported"}``.
    """
    if not is_supported():
        return {"status": "unsupported"}
    try:
        # 1) Delete the cached thumbnail / icon databases.
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            local = os.path.join(os.environ.get("USERPROFILE", ""),
                                 "AppData", "Local")
        expl = os.path.join(local, "Microsoft", "Windows", "Explorer")
        if os.path.isdir(expl):
            for name in os.listdir(expl):
                low = name.lower()
                if low.startswith("iconcache_") or low.startswith("thumbcache_"):
                    try:
                        os.remove(os.path.join(expl, name))
                    except OSError:
                        pass

        # 2) Rebuild the icon cache (Windows 8+).
        ie4 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                           "System32", "ie4uinit.exe")
        if os.path.exists(ie4):
            try:
                flags, si = _hidden()
                subprocess.run([ie4, "-show"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               creationflags=flags, startupinfo=si)
            except Exception:
                pass

        # 3) Tell the shell to re-read everything.
        _refresh_shell("C:\\")

        # 4) Hard refresh: restart Explorer (this is what makes folder icons
        #    reliably repaint). Explorer auto-restarts; we also nudge it.
        if restart:
            try:
                flags, si = _hidden()
                subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               creationflags=flags, startupinfo=si)
            except Exception:
                pass
            try:
                flags, si = _hidden()
                subprocess.Popen(["explorer.exe"],
                                 creationflags=flags, startupinfo=si)
            except Exception:
                pass

        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}
