# 📚 Artbook & Comic PDF Converter + Japanese Scanlation Suite

A high-performance desktop application and command-line tool designed to convert folders of images (Japanese video game artbooks, manga, comics, and developer secret files) into pristine, high-quality PDFs.

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

- **🖥️ Desktop GUI with Dual Progress Bars**:
  - **Current Book Progress Bar**: Real-time tracking per-page as each image is processed.
  - **Overall Batch Progress Bar**: Real-time tracking across your entire library.
  - Recursive folder scanning to discover all books in seconds.
  - Custom output directory support.
  - Double-click launcher (`start.bat`).

- **🌐 Optional Translation & Scanlation (Japanese Books)**:
  - **100% Optional**: Disabled by default. Untranslated original PDFs are always preserved at maximum clarity.
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

### 3. Drag-and-Drop Batch Conversion
Drag any image folder directly onto **`convert_folders_to_pdf.bat`**.

### 4. Command Line Usage
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
├── folder_to_pdf.py           # Core conversion engine & CLI
├── translator.py              # Translation, OCR & Scanlation engine
├── gui.py                     # Desktop GUI with dual progress bars
├── start.bat                  # One-click launcher for GUI
├── convert_folders_to_pdf.bat # Drag-and-drop batch converter
├── requirements.txt           # Python dependencies
└── README.md                  # Documentation
```

---

## 📜 License
MIT License. Free for personal and commercial use.
