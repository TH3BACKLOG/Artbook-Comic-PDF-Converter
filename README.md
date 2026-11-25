# 📚 Artbook & Comic PDF Converter + Japanese Scanlation Suite

A high-performance desktop application and command-line tool designed to convert folders of images (Japanese video game artbooks, manga, comics, and developer secret files) into pristine, high-quality PDFs, and **translate existing PDF files directly**.

Includes an **optional Japanese translation & scanlation engine** that can generate companion translation guides or typeset English directly into speech bubbles!

---

## ✨ Features

- **⚡ Folder-to-PDF Conversion**:
  - Automatically names the output PDF after its folder (`<Folder_Name>.pdf`).
  - Converts entire folders in a fraction of a second.
  - Natural page sorting (`Page 1, 2, ... 9, 10` instead of `1, 10, 2`).
  - Full support for `.jpg`, `.png`, `.webp`, `.bmp`, `.tif`, and `.jp2`.
  - Fixes EXIF rotation tags and RGBA/palette transparency (pure white background).
  - Maximum visual clarity: 100% quality with zero chroma subsampling (`subsampling=0`).

- **📄 Direct PDF File Translation**:
  - Translate **existing PDF files** directly without manual page extraction!
  - Powered by high-speed `pypdfium2` rendering with configurable resolution (200 DPI recommended, 300 DPI ultra-sharp).
  - Translates page-by-page and compiles a translated PDF: `<Book_Title> [English Translated].pdf`.
  - Memory-safe page streaming ensures seamless translation even for 300+ page books.

- **🖥️ Desktop GUI with Dual-Tab Interface & Dual Progress Bars**:
  - **📁 Image Book Folders Tab**: Scan and batch convert image folders to PDF.
  - **📄 Existing PDF Files Tab**: Scan and select existing PDFs (or click `➕ Add PDF File(s)...` to browse any PDF).
  - **Current Item Progress Bar**: Real-time per-page tracking as each page is rendered and translated.
  - **Overall Batch Progress Bar**: Real-time tracking across your entire book collection.
  - Double-click launcher (`start.bat`).

- **🌐 Optional Translation & Scanlation (Japanese Books & PDFs)**:
  - **100% Optional**: Disabled by default for folder conversion. Untranslated original files are always preserved at maximum clarity.
  - **In-Place Scanlation**: Automatically erases original Japanese characters and typesets translated English inside speech bubbles (`<Name> [English Translated].pdf`).
  - **Companion Guides**: Generates readable Markdown (`.md`) and text (`.txt`) translation companion books.
  - **Engines Supported**:
    - Zero-config Free Online Google Translation (no API key required).
    - Local Vision AI via [Ollama](https://ollama.com) (`llama3.2-vision`) for private offline translation.
    - EasyOCR and Tesseract OCR integration.

- **🗂️ Drag-and-Drop Windows Support**:
  - Drag one or multiple image folders directly onto `convert_folders_to_pdf.bat`.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Launch Desktop GUI
Double-click **`start.bat`** or run:
```bash
python gui.py
```
- In the GUI, switch between the **📁 Image Book Folders** and **📄 Existing PDF Files** tabs.
- Select your items and click **🚀 Convert** or **🌐 Translate**.

### 3. Translate an Existing PDF via CLI
Translate a Japanese PDF artbook:
```bash
python folder_to_pdf.py "path/to/my_book.pdf" --translate
```

With custom translation mode (e.g. generate both translated PDF and companion guide):
```bash
python folder_to_pdf.py "path/to/my_book.pdf" --translate --translate-mode both
```

### 4. Folder to PDF Conversion via CLI
Convert a single folder:
```bash
python folder_to_pdf.py "path/to/my_book_folder"
```

Batch convert all folders in current directory:
```bash
python folder_to_pdf.py -a
```

Recursive conversion into a custom output folder:
```bash
python folder_to_pdf.py -a -r -o "D:\MyPDFs"
```

---

## 🛠️ Project Structure

```text
├── folder_to_pdf.py           # Core conversion engine, PDF discovery & CLI
├── translator.py              # Translation, pypdfium2 rendering, OCR & Scanlation engine
├── gui.py                     # Desktop GUI with Dual Tabs (Folders & PDFs) and dual progress bars
├── start.bat                  # One-click launcher for GUI with auto-dependency check
├── convert_folders_to_pdf.bat # Drag-and-drop batch converter
├── requirements.txt           # Python dependencies (Pillow, pypdfium2, etc.)
└── README.md                  # Documentation
```

---

## 📜 License
MIT License. Free for personal and commercial use.
