# Changelog — تاریخچهٔ تغییرات Folder Icon Maker (پیش‌تر: RCFI GUI)

All notable changes to this project are documented in this file.
تمام تغییرات مهم پروژه در همین فایل ثبت می‌شود — در هر نسخه، اول انگلیسی و بعد فارسی.

## [2.3.0] — 2026-10-31

### English
- **The project has a new, self-explanatory name: Folder Icon Maker**
  (formerly "RCFI GUI"). The old name was an abbreviation of the upstream
  project (RCFI = RightClick Folder Icon), not a description of what the
  app does — the new one says it directly, in Persian too (آیکون‌ساز پوشه).
  This changes the window title and header, the dialog titles, the exe
  name (`dist\FolderIconMaker.exe`), the dev launcher
  (`FolderIconMaker.bat`, renamed from `RCFI-GUI.bat`) and the user-data
  locations (`~/.folder_icon_maker.json`, `%TEMP%\FolderIconMaker\`).
  The upstream credit (and the RCFI acronym inside `desktop.ini`'s
  internal `RCFI-SetReadOnly` marker) stays unchanged.
- **`desktop.ini` is now written as UTF-16LE with BOM** — the Unicode
  format Microsoft documents for it.  UTF-8 (even with a BOM) can be
  misread by the Windows shell and garble localized text such as
  `LocalizedResourceName` or a non-ASCII `InfoTip`.  Existing files of
  any encoding (UTF-16, UTF-8, ANSI) are still read and merged
  losslessly, and a file whose content cannot be decoded safely is still
  refused, never overwritten — the reader additionally treats NUL or
  U+FFFD in the decoded text as "undecodable" instead of merging garbage
  back into the file.
- **Per-template artist credits corrected** (found by the fourth review):
  the upstream project's own template scripts DO map templates to
  artists.  Verified from the upstream `templates/*.bat` headers:
  `DVDBox Dark`, `DVDBox Light` and `DVDCase Transparent Plastic` are
  em1l's artwork; `DVDCase Bluray` is saikuro's.  The incorrect
  "upstream does not map templates to artists, so credit is collective"
  claim was removed from both READMEs and from
  `THIRD_PARTY_LICENSES.txt`; `DiscArt` keeps the upstream collective
  credit (its script names no single artist), and `(none)` /
  `(Shadow Only)` are noted as plain ImageMagick compositions with no
  PSD artwork.
- **Code cleanups from the fourth review**: dead imports removed
  (`templates_lib` in `icon_engine.py`, `math` in `templates_lib.py`);
  the unused `token` parameter of `_show_preview` dropped; the preview
  cache is now guarded by a lock (it is filled from background render
  threads); when several images score equally, the pick is now
  deterministic (alphabetical tie-break) instead of following the
  filesystem's `os.walk` order; and `requirements.txt` upper-bounds
  Pillow (`>=10.0,<13`) for reproducible builds.
- **New: "Remove icons" button** — the manual undo for generated folder
  icons, next to the generate button. It only runs after an explicit
  confirmation dialog that explains exactly what happens: the
  `IconResource` entry is taken out of every scanned folder's
  `desktop.ini`; the file itself is deleted only when it belongs to this
  app alone; other settings survive; and the generated `folder.ico` is
  kept unless the new "also delete the folder.ico file" checkbox is
  ticked (it is off by default, because the .ico may be the only
  remaining copy of the artwork). The button is disabled on non-Windows
  systems, works with no image selected, and every folder's outcome is
  logged (and re-rendered on a language switch, like the rest of the
  log).
- **Fixes from the third external code review** (all five recommended
  items):
  1. `SetFileAttributesW` results are now checked — the API returns 0 on
     failure and the old code never looked, so a failed Hidden/System or
     ReadOnly change was silently reported as success. Failures now
     surface with a clear error.
  2. `desktop.ini` is read **before** any attribute is touched (reading
     works on Hidden/System files), and attributes stripped for the
     atomic replace are restored if the operation fails — a failed run
     can no longer leave a previously Hidden/System file sitting there
     as Normal.
  3. The folder's ReadOnly flag is only cleared again when **this tool
     was the one that set it**: applying an icon to a folder without the
     flag records `RCFI-SetReadOnly=1` inside `desktop.ini`, and the
     remove path honours that marker — a ReadOnly flag the folder
     already had before is never touched.
  4. The icon render now goes to a temporary file first and is only
     moved over `folder.ico` after a header check — an ImageMagick
     crash or timeout can no longer destroy the previous icon.
  5. The selected template is captured in the GUI thread before the
     worker thread starts (and the template combo is frozen while a run
     is in progress), so changing the template mid-run can no longer
     make a batch start with a different template than the one shown.
- **Fixes from the fifth external code review** (pre-release pass):
  1. The temporary `folder.ico` is now **fully validated** before it may
     replace the previous icon: header, every directory entry (non-zero
     image size, offset+size completely inside the file) and a real
     Pillow decode.  The old 6-byte header check could be passed by a
     truncated, header-only file -- a broken render can no longer
     destroy a working icon.
  2. **"Remove icons" no longer touches foreign `desktop.ini` files**:
     a file without `IconResource` and without this app's
     `RCFI-SetReadOnly` marker is reported as "no icon" and left
     byte-for-byte untouched (previously it was needlessly rewritten --
     and re-encoded to UTF-16 -- or, when it held only a section
     header, even deleted).
  3. **Failed applies roll back**: if setting the folder's ReadOnly flag
     or desktop.ini's Hidden+System attributes fails after the file was
     written, the previous `desktop.ini` is restored byte-for-byte (with
     its original attributes), or removed again when this tool had just
     created it, and the folder keeps its previous attributes.
  4. Scans and target lists also exclude folders whose **Windows
     Hidden/System attributes** are set (previously only names were
     filtered, which misses OS-managed folders).
  5. Users of the pre-rename releases keep their language: when
     `~/.folder_icon_maker.json` does not exist yet, the saved choice is
     migrated from `~/.rcfi_gui.json` instead of resetting to the
     auto-detected default.
- **Docs**: the build section no longer suggests building for
  Linux/macOS — the app is Windows-only (folder icons are a Windows
  shell feature). The intro of both READMEs explains the name history
  (RCFI = RightClick Folder Icon, the upstream project the old name
  abbreviated); version badges show 2.3.0.
- **Foreign `folder.ico` is no longer deleted** (seventh review): the
  "remove icons" action deletes `folder.ico` only when the folder's
  `desktop.ini` was actually written by this app. When the result is
  `not_found` (the file holds other programs' settings or none at
  all), any `folder.ico` in that folder was made by something else and
  is now left untouched, with its own log line (`ico_kept_foreign`),
  instead of being silently destroyed right after "left untouched" was
  logged.
- **"Remove icons" now fully undoes folders this app iconned from
  scratch** (seventh review): the `[ViewState]` boilerplate this tool
  itself writes (`Mode=`, `Vid=`, `FolderType=Generic`) no longer
  counts as a foreign setting, so a `desktop.ini` containing nothing
  but the icon entry, the marker and that boilerplate is deleted and
  the folder's ReadOnly flag is taken back — as the confirmation
  dialog always promised. Real settings (InfoTip,
  LocalizedResourceName, `Mode=2`, `FolderType=Documents`, ...) still
  keep the file alive.
- **`.gitignore`**: the whole `rcfi_assets/resources/` folder is
  ignored now (previously only `*.exe` directly inside it), so the
  portable ImageMagick DLLs and config files cannot be committed by
  accident.
- **A valid existing `folder.ico` is now applied without a re-render**
  (pre-release review): when `folder.ico` already exists and Overwrite
  is off, the engine reported `skipped` and the GUI wrote no
  `desktop.ini` at all -- so a first run that generated the icon but
  failed to write `desktop.ini` (e.g. the file was locked) could never
  be completed by re-running with default options.  The engine now
  validates the existing file and reports `reused`, and the icon is
  wired into `desktop.ini` as usual; only a corrupt file is re-rendered.

### فارسی
- **پروژه نام جدید و گویاتری گرفت: Folder Icon Maker (آیکون‌ساز پوشه)** —
  پیش‌تر «RCFI GUI». نام قبلی مخفف پروژهٔ بالادستی بود (RCFI = RightClick
  Folder Icon)، نه توصیف کار برنامه — نام جدید مستقیماً کاربرد را می‌گوید.
  این تغییر شامل عنوان پنجره و هدر، عنوان پنجره‌های دیالوگ، نام فایل
  اجرایی (`dist\FolderIconMaker.exe`)، لانچر توسعه‌ای
  (`FolderIconMaker.bat`، تغییرنام‌یافته از `RCFI-GUI.bat`) و محل‌های
  دادهٔ کاربر (`~/.folder_icon_maker.json`، `%TEMP%\FolderIconMaker\`)
  است. اعتبار بالادستی (و مخفف RCFI داخل نشانگر داخلی
  `RCFI-SetReadOnly` در desktop.ini) بدون تغییر مانده است.
- **`desktop.ini` حالا با UTF-16LE و BOM نوشته می‌شود** — قالب یونیکدی که
  مایکروسافت برای desktop.ini مستند کرده است. UTF-8 (حتی با BOM) ممکن است
  توسط پوستهٔ ویندوز بدست خوانده شود و متن‌های بومی‌شده مثل
  `LocalizedResourceName` یا `InfoTip` غیرASCII را خراب کند. فایل‌های
  موجود با هر کدگذاری (UTF-16، UTF-8، ANSI) همچنان بدونِ‌هیچ‌اتلافی
  خوانده و ادغام می‌شوند و فایلی که محتوایش امن رمزگشایی نشود همچنان رد
  می‌شود و هرگز بازنویسی نمی‌شود — گیرنده علاوه بر آن، NUL یا U+FFFD در
  متن رمزگشایی‌شده را «قابل رمزگشایی نیست» حساب می‌کند تا دادهٔ آشغال به
  فایل برنگردد.
- **اصلاح اعتبار هنرمندان به‌تفکیک قالب** (یافتهٔ بازبینی چهارم):
  اسکریپت‌های قالبِ خودِ پروژهٔ بالادستی هر قالب را به هنرمندش نگاشت
  می‌کنند. طبق بررسی مستقیم سرصفحه‌های `templates/*.bat` بالادستی:
  آثار `DVDBox Dark`، `DVDBox Light` و `DVDCase Transparent Plastic`
  از em1l و `DVDCase Bluray` از saikuro است. ادعای نادرست «بالادستی
  قالب‌ها را به هنرمند نگاشته نکرده، پس کردیت جمعی است» از هر دو README
  و از `THIRD_PARTY_LICENSES.txt` حذف شد؛ `DiscArt` اعتبار جمعی
  بالادستی را نگه می‌دارد (اسکریپتش هنرمند مشخصی را نام نمی‌برد) و
  `(none)` / `(Shadow Only)` به‌عنوان ترکیب سادهٔ ImageMagick بدون PSD
  یادداشت شده‌اند.
- **پاک‌سازی‌های کدی از بازبینی چهارم**: حذف importهای مرده
  (`templates_lib` در `icon_engine.py` و `math` در `templates_lib.py`)؛
  حذف پارامتر بلااستفادهٔ `token` از `_show_preview`؛ قفل‌شدنِ کش
  پیش‌نمایش (از تردهای رندر پس‌زمینه پر می‌شود)؛ انتخاب قطعیِ تصویر
  هنگام تساوی امتیازها (جای‌گزینی الفبایی به‌جای ترتیب `os.walk` فایل
  سیستم)؛ و محدودکردن نسخهٔ Pillow در `requirements.txt` (`>=10.0,<13`)
  برای ساخت بازتولیدپذیر.
- **جدید: دکمهٔ «حذف آیکون‌ها»** — برگرداندنِ دستی آیکون‌های ساخته‌شده،
  کنار دکمهٔ تولید. این کار فقط بعد از یک پنجرهٔ تأیید صریح انجام می‌شود
  که دقیقاً توضیح می‌دهد چه اتفاقی می‌افتد: مدخل `IconResource` از
  `desktop.ini` هر پوشهٔ فهرست‌شده برداشته می‌شود؛ اگر فایل فقط متعلق به
  همین برنامه باشد کل فایل هم پاک می‌شود؛ بقیهٔ تنظیمات حفظ می‌شوند؛ و
  فایل ساخته‌شدهٔ `folder.ico` سر جایش می‌ماند مگر اینکه چک‌باکس جدید
  «هنگام حذف، فایل folder.ico هم پاک شود» فعال باشد (به‌طور پیش‌فرض خاموش
  است، چون ممکن است این فایل تنها نسخهٔ باقی‌ماندهٔ تصویر باشد). دکمه روی
  سیستم‌های غیرویندوزی غیرفعال است، بدون انتخاب تصویر هم کار می‌کند و
  نتیجهٔ هر پوشه در گزارش ثبت می‌شود (مثل بقیهٔ گزارش، با تعویض زبان
  دوباره رندر می‌شود).
- **اصلاحات دور سوم بازبینی خارجی کد** (هر پنج مورد پیشنهادی):
  ۱. نتیجهٔ `SetFileAttributesW` حالا بررسی می‌شود — این تابع در صورت
     شکست صفر برمی‌گرداند و کد قبلی نگاهش نمی‌کرد؛ شکستِ تغییر صفات
     Hidden/System یا ReadOnly بی‌سروصدا «موفق» گزارش می‌شد. حالا شکست‌ها
     با خطای روشن به کاربر می‌رسد.
  ۲. `desktop.ini` **قبل از** دست‌زدن به صفات خوانده می‌شود (خواندن روی
     فایل Hidden/System کار می‌کند) و اگر عملیات شکست بخورد، صفات
     برداشته‌شده برای جایگزینی اتمیک به حالت اول برمی‌گردند — اجرای
     ناموفق دیگر نمی‌تواند فایلی را که Hidden/System بوده به‌صورت عادی
     رها کند.
  ۳. پرچم ReadOnly پوشه فقط وقتی پس گرفته می‌شود که **خودِ این برنامه آن
     را گذاشته باشد**: هنگام اعمال آیکون روی پوشه‌ای که این پرچم را
     نداشت، مقدار `RCFI-SetReadOnly=1` داخل `desktop.ini` ثبت می‌شود و
     مسیر حذف به آن نشانگر احترام می‌گذارد — ReadOnly‌ای که پوشه از قبل
     داشته هرگز دست‌نخورده می‌ماند.
  ۴. رندر آیکون حالا اول در یک فایل موقت انجام می‌شود و فقط بعد از
     بررسی هدر (header) جای `folder.ico` می‌نشیند — کرش یا تایم‌اوتِ
     ImageMagick دیگر نمی‌تواند آیکون قبلی را نابود کند.
  ۵. قالب انتخاب‌شده در thread رابط گرافیکی و قبل از ساخت thread کارگر
     ثبت می‌شود (و فهرست قالب‌ها حین پردازش قفل می‌شود) تا تغییر قالب
     در میانهٔ کار نتواند دسته‌ای با قالبی متفاوت از آنچه نمایش داده
     می‌شود آغاز کند.
- **اصلاحات دور پنجم بازبینی خارجی کد** (پیش از انتشار):
  ۱. فایل موقت `folder.ico` حالا **کامل اعتبارسنجی می‌شود** پیش از
     جایگزینی آیکون قبلی: هدر، همهٔ مدخل‌های فهرست (اندازهٔ ناصفر،
     آفست+اندازهٔ کاملاً درون فایل) و رمزگشایی واقعی با Pillow. بررسی
     قبلیِ ۶بایتی را می‌شد با یک فایل ناقصِ فقط-هدر دور زد — خروجی خراب
     دیگر نمی‌تواند آیکون سالم قبلی را نابود کند.
  ۲. **«حذف آیکون‌ها» دیگر به desktop.iniهای بیگانه دست نمی‌زند**:
     فایلی که نه `IconResource` دارد و نه نشانگر `RCFI-SetReadOnly` این
     برنامه، به‌عنوان «آیکونی نبود» گزارش و بایت‌به‌بایت دست‌نخورده
     می‌ماند (قبلاً بی‌دلیل بازنویسی — و به UTF-16 بازکدگذاری — می‌شد و
     اگر فقط سرصفحهٔ بخش داشت حتی حذف می‌شد).
  ۳. **اعمال ناموفق برمی‌گردد**: اگر پس از نوشتن فایل، تنظیم ReadOnly
     پوشه یا صفات Hidden+System مربوط به desktop.ini شکست بخورد،
     `desktop.ini` قبلی بایت‌به‌بایت (با صفات اصلی‌اش) برمی‌گردد — یا اگر
     همین برنامه تازه ساخته بودش حذف می‌شود — و پوشه هم صفات قبلی‌اش را
     نگه می‌دارد.
  ۴. پویش‌ها و فهرست اهداف حالا پوشه‌هایی را هم کنار می‌گذارند که صفات
     **Hidden/System ویندوز** را دارند (قبلاً فقط نام‌ها فیلتر می‌شد، که
     پوشه‌های مدیریت‌شده توسط سیستم را از دست می‌داد).
  ۵. کاربران نسخه‌های پیش از تغییرنام زبانشان حفظ می‌شود: وقتی
     `~/.folder_icon_maker.json` هنوز وجود ندارد، انتخاب ذخیره‌شده از
     `~/.rcfi_gui.json` منتقل می‌شود و زبان به‌جای reset شدن به
     تشخیص خودکار، همان انتخاب قبلی می‌ماند.
- **مستندات**: بخش ساخت دیگر پیشنهاد ساخت برای لینوکس/macOS نمی‌دهد —
  برنامه فقط برای ویندوز است (آیکون پوشه یک قابلیت پوستهٔ ویندوز است) و
  `build.sh` حالا صریحاً «ابزار اجرا/آزمایش کد برای توسعه‌دهنده» معرفی
  شده، نه ساخت برنامه. معنی نام پروژه (RCFI = RightClick Folder Icon) در
  مقدمهٔ هر دو README توضیح داده شد؛ بج نسخه 2.3.0 را نشان می‌دهد.
- **folder.ico بیگانه دیگر حذف نمی‌شود** (بازبینی هفتم): کنش «حذف
  آیکون‌ها» فایل `folder.ico` را فقط زمانی پاک می‌کند که desktop.ini
  آن پوشه واقعاً ساختهٔ همین برنامه باشد. وقتی نتیجه `not_found` است
  (فایل فقط تنظیمات برنامه‌های دیگر را دارد یا اصلاً چیزی ندارد)، هر
  `folder.ico` داخل آن پوشه ساختهٔ چیز دیگری است و حالا دست‌نخورده
  می‌ماند و پیام جداگانهٔ خودش را در لاگ می‌گیرد (`ico_kept_foreign`)،
  نه اینکه درست بعد از پیام «دست‌نخورده ماند» بی‌صدا نابود شود.
- **«حذف آیکون‌ها» حالا پوشه‌هایی که این برنامه از صفر آیکون‌دار کرده
  را کامل برمی‌گرداند** (بازبینی هفتم): بسته‌بولت `[ViewState]` که خود
  این برنامه می‌نویسد (`Mode=`، `Vid=`، `FolderType=Generic`) دیگر
  تنظیمات بیگانه حساب نمی‌شود؛ پس desktop.iniای که جز ورودی آیکون،
  نشانگر و همین بسته‌بولت چیز دیگری نداشته باشد حذف می‌شود و فلگ
  ReadOnly پوشه هم پس گرفته می‌شود — همان‌طور که دیالوگ تأیید همیشه
  وعده می‌داد. تنظیمات واقعی (InfoTip، LocalizedResourceName،
  `Mode=2`، `FolderType=Documents` و ...) مثل قبل فایل را زنده نگه
  می‌دارند.
- **`.gitignore`**: حالا کل پوشهٔ `rcfi_assets/resources/` نادیده
  گرفته می‌شود (قبلاً فقط `*.exe` مستقیم داخل آن)، تا DLLها و فایل‌های
  پیکربندی ImageMagick قابل‌حمل تصادفی commit نشوند.
- **`folder.ico` موجودِ سالم حالا بدون رندر دوباره اعمال می‌شود**
  (بازبینی پیش از انتشار): وقتی `folder.ico` از قبل وجود دارد و
  Overwrite خاموش است، موتور «skipped» برمی‌گرداند و GUI هیچ
  `desktop.ini`ای نمی‌نوشت — پس اجرای اولی که آیکون را ساخته بود ولی
  نوشتن desktop.ini در آن شکست خورده بود (مثلاً فایل قفل بود) با اجرای
  دوباره و گزینه‌های پیش‌فرض هرگز کامل نمی‌شد. حالا موتور فایل موجود را
  اعتبارسنجی می‌کند، «reused» برمی‌گرداند و آیکون مثل همیشه در
  desktop.ini اعمال می‌شود؛ فقط فایل خراب دوباره رندر می‌شود.

## [2.2.1] — 2026-10-30

### English
- **The log now follows the live language switch** — every log line is
  stored in a structured form and re-rendered in the active language, so
  switching the language switches the *whole* log together with the UI —
  no more mixed-language log lines.
- **Persian display names for the templates** — in the Persian UI the
  template combo box and the gallery now show Persian names (e.g.
  «جعبه DVD تیره»); the internal names used by the engine and
  `desktop.ini` deliberately stay Latin, so nothing breaks.
- **Bigger small UI fonts** — the smaller labels and list text are easier
  to read.
- **Docs**: the 6 screenshots were retaken on this build (language-aware
  logo, Persian template names); LICENSE cleaned to a pure MIT text with
  both copyright lines; `THIRD_PARTY_LICENSES.txt` now includes the full
  license texts — among them the verbatim ImageMagick license and the
  five template artists credited by the upstream project — and is
  bundled into the exe by the build scripts.

- **READMEs**: they now start with a clickable table of contents, and a
  short note that they were written with the help of AI. The portable
  `magick.exe` paragraph now states the two real ways the binary reaches
  the app (packed into the exe at build time, or ImageMagick installed on
  the system). The unneeded `make_samples.py` was removed — the app
  recreates its sample poster itself, and a test folder can simply be
  made by hand in Explorer. The "part of my file-organizing toolset"
  line is dropped for now — this is the account's first published
  project; it can come back once more tools are released.
- **Bug fixes**: in the Persian UI, icon generation passed the localized
  template display name (e.g. «جعبه DVD تیره») to the engine instead of
  the internal Latin key, so every generated icon silently degraded to
  the generic fallback icon even with ImageMagick installed (previews
  were unaffected — they already used the key). Generation now always
  uses the internal key — verified for all 8 templates in both
  languages. `desktop.ini` is no longer rewritten wholesale: only the
  `IconResource` entry is written/updated and every other setting in an
  existing file (FolderType, view state, InfoTip, localized names, ...)
  is preserved; removing an icon deletes the file only when nothing
  else is left in it.
- **Fixes from the second external code review**: `SHCNE_ASSOCCHANGED`
  is now raised with `SHCNF_IDLIST`, exactly as Microsoft's
  `SHChangeNotify` documentation requires -- it used to be sent with
  `SHCNF_PATH`, which the shell may silently drop (stale icons).
  `desktop.ini` handling is hardened: an existing file that cannot be
  read is never overwritten or deleted any more -- both paths stop with
  a clear error instead; every write first goes to a temp file that is
  moved over the target atomically, so a crash can no longer leave a
  truncated `desktop.ini` behind; and the icon entry is matched by its
  exact key name, so unrelated keys such as `IconResourceExtra` are
  never replaced or dropped.  The generate worker no longer touches
  tkinter variables from the background thread -- the overwrite /
  refresh-Explorer checkbox states are read in the GUI thread and
  passed to it as plain values.

### فارسی
- **گزارش (لاگ) حالا کامل با تعویض زبان جابه‌جا می‌شود** — هر خطِ گزارش
  به‌صورت ساخت‌یافته ذخیره می‌شود و در زبان فعال دوباره رندر می‌شود؛ پس
  با تعویض زبان، **کل گزارش** همراه بقیهٔ رابط عوض می‌شود و دیگر خط
  دوزبانه‌ای در گزارش نمی‌ماند.
- **نام فارسی قالب‌ها** — در زبان فارسی، فهرست کشویی قالب‌ها و گالری،
  نام‌های فارسی را نشان می‌دهند (مثل «جعبه DVD تیره»)؛ نام‌های داخلی
  که در کد و `desktop.ini` استفاده می‌شوند عمداً لاتین مانده‌اند تا
  هیچ‌چیز خراب نشود.
- **فونت‌های ریز بزرگ‌تر** — خوانایی برچسب‌های کوچک و متن فهرست‌ها
  بهتر شد.
- **مستندات**: هر ۶ اسکرین‌شات روی همین نسخه دوباره گرفته شد (لوگوی
  زبان‌پیرو، نام قالب‌های فارسی)؛ LICENSE به متن خالص MIT با هر دو خط
  کپی‌رایت تبدیل شد؛ `THIRD_PARTY_LICENSES.txt` حالا متن کامل
  لایسنس‌ها را دارد — از جمله متن واژه‌به‌واژهٔ لایسنس ImageMagick و
  نام پنج هنرمندی که پروژهٔ بالادستی برای قالب‌های PSD اعتبار می‌داند —
  و اسکریپت‌های ساخت آن را داخل exe می‌گذارند.

- **READMEها**: حالا با فهرست مطالب کلیک‌خور شروع می‌شوند و یادداشت کوتاه
  «نوشته‌شده با کمک هوش مصنوعی» دارند. بند `magick.exe` پرتابل بازنویسی شد
  تا دو راه واقعی رسیدن باینری به برنامه را روشن کند (بسته‌بندی داخل exe
  هنگام ساخت، یا نصب ImageMagick روی سیستم). فایل غیرضروری
  `make_samples.py` حذف شد — خود برنامه پوستر نمونه را از نو می‌سازد و
  پوشهٔ آزمایشی را هم می‌شود ساده در اکسپلورر ساخت. جملهٔ «بخش «آیکون
  پوشه» از مجموعه ابزارهای مرتب‌سازی فایل من» فعلاً حذف شده — این اولین
  پروژهٔ منتشرشده در این حساب است و بعداً با انتشار ابزارهای دیگر
  می‌تواند برگردد.
- **رفع اشکال**: در رابط فارسی، هنگام ساخت آیکون به‌جای شناسهٔ داخلی قالب،
  نام نمایشیِ ترجمه‌شده (مثل «جعبه DVD تیره») به موتور پاس داده می‌شد؛
  در نتیجه همهٔ آیکون‌های ساخته‌شده بی‌سروصدا به آیکون عمومی فال‌بک
  تبدیل می‌شدند، حتی با ImageMagick نصب‌شده (پیش‌نمایش‌ها متأثر نبودند —
  آن‌ها از قبل شناسهٔ داخلی را می‌گرفتند). حالا ساخت همیشه شناسهٔ داخلی
  را می‌فرستد — برای هر ۸ قالب در هر دو زبان آزمایش شده است.
  `desktop.ini` هم دیگر یک‌جا بازنویسی نمی‌شود: فقط خط `IconResource`
  نوشته/به‌روز می‌شود و بقیهٔ تنظیمات فایل موجود (FolderType، حالت
  نمایش، InfoTip، نام‌های بومی‌شده و ...) حفظ می‌شود؛ حذف آیکون هم فقط
  وقتی کل فایل را پاک می‌کند که چیز دیگری در آن نمانده باشد.
- **اصلاحات دور دوم بازبینی خارجی کد**: اعلان `SHCNE_ASSOCCHANGED` حالا
  طبق مستندات مایکروسافت با `SHCNF_IDLIST` فرستاده می‌شود — قبلاً با
  `SHCNF_PATH` ارسال می‌شد که پوستهٔ ویندوز ممکن بود بی‌صدا نادیده
  بگیرد (آیکون‌های کهنه باقی می‌ماندند).  مدیریت `desktop.ini`
  سخت‌گیرانه‌تر شد: اگر فایل موجود خوانده نشود، دیگر بازنویسی یا
  حذف نمی‌شود و هر دو مسیر با خطای روشن متوقف می‌شوند؛ همهٔ
  نوشتن‌ها اول در یک فایل موقت انجام و بعد به‌صورت اتمیک جایگزین
  می‌شوند تا کرش دیگر نتواند `desktop.ini` نصفه‌کاره جا بگذارد؛ و
  خط آیکون با تطابق دقیق نام کلید پیدا می‌شود تا کلیدهای بی‌ربط
  مثل `IconResourceExtra` هیچ‌وقت جایگزین یا حذف نشوند.  کارگر
  (worker) ساخت هم دیگر از thread پس‌زمینه به متغیرهای tkinter
  دست‌رسی ندارد — وضعیت چک‌باکس‌های «بازنویسی» و «رفرش
  اکسپلورر» در thread رابط گرافیکی خوانده و به‌صورت مقدار ساده به آن
  پاس داده می‌شود.

## [2.2.0] — 2026-10-30

### English
- **Much faster, safer batches** — Explorer is no longer refreshed after
  every single folder (that per-folder shell broadcast made big batches
  very slow and could interrupt them). The icon/thumbnail cache is
  cleared and Explorer is refreshed **once, after the whole batch
  finishes**.
- **New button: "Clear cache & refresh Explorer"** — if some folders
  still show the old icon after a run (the shell sometimes catches up
  late; keeping all Explorer windows closed helps), press it any time:
  the icon cache is cleared and Explorer is restarted after a
  confirmation, so every pending icon appears immediately.
- **The size selector is gone** — it had no effect: a `folder.ico` always
  stores every size from 16 to 256 px (the ICO format maximum) and
  Windows picks the right one automatically. Icons are now always
  written at maximum quality; the internal 512 px path (which could
  produce invalid `.ico` files) was removed too.

### فارسی
- **پردازش دسته‌ای خیلی سریع‌تر و مطمئن‌تر** — دیگر بعد از تک‌تک پوشه‌ها
  اکسپلورر رفرش نمی‌شود (همین نوتیفیکیشنِ به‌ازای هر پوشه، دسته‌های بزرگ
  را خیلی کند می‌کرد و می‌توانست کار را مختل کند). حالا کش آیکون/تامبنیل
  **فقط یک بار، در پایان کل پردازش** پاک و اکسپلورر رفرش می‌شود.
- **دکمه‌ی جدید: «پاک‌سازی کش + رفرش اکسپلورر»** — اگر بعد از پایان کار
  بعضی پوشه‌ها هنوز آیکون قدیمی را نشان می‌دهند (پوسته‌ی ویندوز گاهی
  دیرتر به‌روز می‌شود؛ بستن همه‌ی پنجره‌های اکسپلورر هم کمک می‌کند)، هر
  وقت خواستید این دکمه را بزنید: کش آیکون پاک و — بعد از یک تأیید —
  اکسپلورر ری‌استارت می‌شود تا همه‌ی آیکون‌های در انتظار فوراً نمایش
  داده شوند.
- **کادر «اندازه» حذف شد** — اثری نداشت: هر `folder.ico` همیشه همه‌ی
  اندازه‌های ۱۶ تا ۲۵۶ پیکسل (سقف فرمت ICO) را داخل خودش دارد و ویندوز
  به‌طور خودکار اندازه‌ی درست را برمی‌دارد. حالا آیکون‌ها همیشه با
  بیشترین کیفیت نوشته می‌شوند؛ مسیر داخلی ۵۱۲ پیکسل (که می‌توانست فایل
  ICO نامعتبر بسازد) هم حذف شد.

## [2.1.1] — 2026-10-30

### English
- **Honest "no ImageMagick" behaviour** — the docs say it straight:
  ImageMagick is required for the faithful templates; without it every
  template produces the same generic fallback icon, and the app logs a
  clear warning when that happens (it used to happen silently).
- **Icon size capped at 256 px** — the ICO format maximum. The old 512
  option could fail depending on the ImageMagick build, and Explorer
  never uses more than 256 for folder icons anyway.
- **Folder names with brackets** (e.g. `Movie [2020]`) now find their
  side images (disc art, logo) correctly.
- **The bundled sample poster is now actually used by the exe** —
  previously the frozen build regenerated a generic demo image instead.
- **Recursive scans skip hidden/system folders** (`.git`,
  `$RECYCLE.BIN`, `System Volume Information`).
- **Temp files cleaned up** — the per-icon working folder in `%TEMP%`
  is removed after each icon.
- **Smarter image picking** — filenames are matched by whole words, so
  `Discovery` is no longer treated as disc art and `monkey` no longer
  counts as "key" art.
- **Antivirus-friendly build** — UPX compression is off (a common source
  of false positives).
- **Docs**: corrected inaccurate claims, added upstream template
  credits, a trademark notice and the origin of the sample poster.

### فارسی
- **رفتار «بدون ImageMagick» شفاف شد** — مستندات صادقانه می‌گویند:
  ImageMagick برای قالب‌های واقعی لازم است؛ بدون آن همه‌ی قالب‌ها خروجی
  عمومی یکسانی می‌سازند و برنامه حالا در لاگ هشدار واضح ثبت می‌کند
  (قبلاً بی‌صدا اتفاق می‌افتاد).
- **سقف اندازه‌ی آیکون روی ۲۵۶ پیکسل** — سقف فرمت ICO؛ گزینه‌ی قدیمی ۵۱۲
  بسته به نسخه‌ی ImageMagick می‌توانست شکست بخورد و اکسپلورر هم برای
  آیکون پوشه هرگز بیش از ۲۵۶ استفاده نمی‌کند.
- **نام پوشه‌های دارای کروشه** (مثل `Movie [2020]`) حالا تصاویر جانبی
  (دیسک‌آرت، لوگو) را درست پیدا می‌کنند.
- **پوستر نمونه‌ی همراه، حالا واقعاً داخل exe استفاده می‌شود** — قبلاً
  نسخه‌ی فریزشده به‌جای آن یک تصویر دموی عمومی می‌ساخت.
- **پویش بازگشتی از پوشه‌های مخفی/سیستمی رد می‌شود** (`.git`،
  `$RECYCLE.BIN`، `System Volume Information`).
- **فایل‌های موقت پاک می‌شوند** — پوشه‌ی کاری هر آیکون در `%TEMP%` بعد
  از هر آیکون حذف می‌شود.
- **انتخاب تصویر هوشمندتر** — نام فایل‌ها با کلمه‌ی کامل مطابقت داده
  می‌شوند؛ دیگر `Discovery` دیسک‌آرت حساب نمی‌شود و `monkey` تصویر
  «کلیدی» نیست.
- **ساخت سازگار با آنتی‌ویروس** — فشرده‌سازی UPX خاموش است (منبع رایج
  هشدارهای کاذب).
- **مستندات**: ادعاهای نادرست اصلاح، اعتبار قالب‌های بالادستی، نکته‌ی
  علامت تجاری و منشأ پوستر نمونه اضافه شد.

## [2.1] — 2026-10-29

### English
- **`Square` template**: the image is stretched to an exact 1:1 square —
  no cropping, no blurred background. (Previously it was filled with a
  blurred backdrop.)
- **Disc in `DVDBox Dark` / `DVDBox Light`**: the half-out disc now
  carries the image (poster) itself — exactly like the original project
  (if a manual `*discart.png` exists it is used; otherwise the disc art
  is built from the case).
- **Fixed "Permission denied" when applying icons**: if `desktop.ini`
  already exists (especially Hidden/System from a previous run or
  another tool), its attributes are stripped first and the content is
  fully rewritten (with retries for files momentarily locked by
  OneDrive/antivirus).
- **Removed the "Apply icon to folder" checkbox**: applying is the
  purpose of the app and always happens on Windows.
- **Wider format support**: JPE, JFIF, DIB, AVIF, HEIC/HEIF and SVG
  added to the input formats (auto-scan and file dialog).

### فارسی
- **قالب `Square` (مربع)**: تصویر به یک مربع دقیق ۱:۱ کشیده می‌شود —
  بدون برش و بدون پس‌زمینه‌ی تار. (قبلاً با پس‌زمینه‌ی بلور پر می‌شد.)
- **دیسک در `DVDBox Dark` / `DVDBox Light`**: دیسکِ نیمه‌بیرون حالا خودِ
  تصویر (پوستر) را نشان می‌دهد — دقیقاً مثل پروژه‌ی اصلی (اگر
  `*discart.png` دستی وجود داشته باشد همان استفاده می‌شود؛ وگرنه
  دیسک‌آرت از روی کیس ساخته می‌شود).
- **رفع خطای «Permission denied» هنگام اعمال آیکون**: اگر `desktop.ini`
  از قبل وجود داشته باشد (مخصوصاً Hidden/System از اجرای قبلی یا ابزار
  دیگر)، اول خصیصه‌هایش برداشته می‌شود و محتوا کاملاً بازنویسی می‌شود
  (با تلاش مجدد برای فایل‌هایی که لحظه‌ای توسط OneDrive/آنتی‌ویروس قفل
  شده‌اند).
- **چک‌باکس «اعمال آیکون روی پوشه» حذف شد**: اعمال، هدف اصلی برنامه
  است و در ویندوز همیشه انجام می‌شود.
- **پشتیبانی گسترده‌تر از فرمت‌ها**: JPE، JFIF، DIB، AVIF، HEIC/HEIF و
  SVG به فرمت‌های ورودی اضافه شدند (پویش خودکار و پنجره‌ی انتخاب فایل).
