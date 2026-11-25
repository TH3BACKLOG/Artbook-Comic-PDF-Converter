# Artbook & Comic PDF Converter - Project Memory & Agent Guidelines

## 1. Project Overview & Scope
- **Repository**: [TH3BACKLOG/Artbook-Comic-PDF-Converter](https://github.com/TH3BACKLOG/Artbook-Comic-PDF-Converter)
- **Local Directory**: `C:\Users\mwlab\Desktop\Books\0. Artbook-Comic-PDF-Converter`
- **Parent Library Workspace**: `C:\Users\mwlab\Desktop\Books`
- **Primary Function**:
  1. Batch convert image scan folders (JPG, PNG, WEBP, etc.) into high-quality, perfectly paginated artbook/comic PDFs.
  2. Directly translate existing PDF artbooks/comics (Japanese/raw scans) into English without requiring manual image extraction.
  3. Optional translation engine: Speech bubble detection via OCR / Vision models, in-place text replacement/typesetting, and companion reading guides (`.md` / `.txt`).

---

## 2. Environment & System Specifics
- **OS**: Windows 10/11 64-bit
- **Python Executable**: `C:\Python314\python.exe` (Python 3.14.5)
- **CRITICAL WindowsApps Warning**:
  - `C:\Users\mwlab\AppData\Local\Microsoft\WindowsApps\python.exe` is a Microsoft Store alias stub that fails with `Access is denied.`
  - Always invoke `C:\Python314\python.exe` directly or use `py -3` in scripts, batch files, and commands.
- **Installed Dependencies**:
  - `pillow>=10.0.0` (v12.3.0 installed)
  - `pypdfium2>=4.0.0` (v5.15.2 installed)
  - Optional OCR/Vision: `easyocr` (PyTorch-based) or local Ollama vision models (e.g. `llama3.2-vision`, `minicpm-v`).

---

## 3. Architecture & File Breakdown

### `start.bat` (Interactive Launcher)
- Primary entry point for GUI.
- Uses explicit label jumping (`goto :FOUND_PYTHON`, `:LAUNCH_GUI`) to prevent CMD variable expansion syntax bugs.
- Bypasses WindowsApps stub by probing `C:\Python314\python.exe`, `py -3`, `py`, then system paths.
- Automatically initializes `logs\` directory.
- Logs launches to `logs\startup.log` and captures non-zero exit codes into `logs\error.log`.
- Pauses on failure so terminal errors remain visible to the user.

### `convert_folders_to_pdf.bat` (Quick Converter)
- Runs `folder_to_pdf.py` in interactive mode.
- Probes Python similarly to `start.bat`.

### `gui.py` (Desktop GUI)
- Built with Tkinter and ttk with a modern dark slate palette.
- **Dual-Tab Notebook**:
  - `📁 Image Book Folders`: Discovers directories containing images across the library, shows image counts, and converts them to PDFs.
  - `📄 Existing PDF Files`: Discovers raw `.pdf` files in the library (excluding already translated companions) with an `➕ Add PDF File(s)...` manual picker.
- **Dynamic Action Button**: Automatically shifts between `🚀 Convert Selected Folders to PDF` and `🌐 Translate Selected PDF Files` based on active tab.
- **Dual Progress Bars**: Real-time per-page status (Current Item) and multi-item batch status (Overall Batch).
- **DPI Presets**: 200 DPI (Default / crisp & fast), 300 DPI (Ultra Sharp), 150 DPI (Compact).
- **Logging Hooks**: `sys.excepthook` and `threading.excepthook` intercept uncaught exceptions, log full tracebacks to `logs\error.log`, and present friendly UI alert dialogs.
- **Activity Log**: Appends operational events to `logs\activity.log`.

### `translator.py` (Translation Engine)
- **PDF Translation Pipeline**:
  - `get_pdf_page_count(pdf_path: Path) -> int`
  - `render_pdf_page_to_image(doc_or_path, page_idx, dpi=200) -> Image.Image`: High-speed memory rendering via `pypdfium2`.
  - `translate_pdf_file(...)`: Renders pages on demand, streams intermediate typeset images to `tempfile.TemporaryDirectory` (flat memory footprint), and outputs `<Book_Title> [English Translated].pdf` and/or companion guides.
- **Image Translation Pipeline**:
  - `translate_and_typeset_image(...)` & `translate_page(...)`: Accepts file paths (`Path`, `str`) or in-memory `PIL.Image.Image` objects directly.
  - OCR detection via EasyOCR or Ollama bounding box prompts.
  - In-place white-out bubble cleaning and centered autowrapped English typesetting with dynamic font scaling.

### `folder_to_pdf.py` (CLI & Core Logic)
- `find_book_folders(...)`: Discovers folders with valid image files.
- `find_pdf_files(...)`: Discovers existing PDFs, ignoring `[English Translated]` files.
- `create_pdf_from_folder(...)`: Natural alphanumeric sorting, Pillow image optimization, RGB conversion, and PDF compilation.
- CLI arguments: `--translate`, `--translate-mode {replace,guide,both}`, `--src-lang`, `--dest-lang`, `--engine`, `--dpi`.

### `logs/` (Diagnostics)
- `startup.log`: Timestamped launches from `start.bat`.
- `activity.log`: Application events from GUI sessions.
- `error.log`: Detailed tracebacks from application crashes or batch failures.

---

## 4. Key Conventions & Rules for Future Work
1. **Preserve Originals**: Never overwrite or delete original scans, raw PDFs, or un-translated archives. Translations must always be output as companion files (e.g. `<Title> [English Translated].pdf`).
2. **Memory Safety**: Do NOT load entire high-resolution artbook PDFs into RAM simultaneously. Always stream rendered pages using `tempfile.TemporaryDirectory` or process page-by-page.
3. **Windows Batch Scripts**:
   - Never use unquoted `&` in titles or echo statements in batch files (`&` acts as CMD command chaining).
   - Avoid complex nested `if (...) else (...)` blocks; use linear label jumping (`goto :LABEL`).
4. **Git Operations**:
   - Project repository branch: `main`.
   - Never commit binaries, `.pdf`, image folders, or `logs/*.log` files (ensured via `.gitignore`).
