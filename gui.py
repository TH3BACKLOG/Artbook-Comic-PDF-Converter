#!/usr/bin/env python3
"""
Artbook & Comic PDF Converter & Translator - Desktop GUI
A modern interface to scan folders, convert to high-quality PDFs, and translate Japanese books
and existing PDF files with real-time dual progress bars (Current Book & Overall Batch).
"""

import os
import sys
import time
import queue
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Ensure script directory is prioritized in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Logging configuration
LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG_PATH = LOGS_DIR / "error.log"
ACTIVITY_LOG_PATH = LOGS_DIR / "activity.log"


def log_exception(exc_type, exc_value, exc_traceback):
    """Logs unhandled exceptions to logs/error.log with full traceback and shows alert."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    err_msg = f"{timestamp} UNHANDLED EXCEPTION:\n{tb_text}\n" + ("=" * 70) + "\n"

    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(err_msg)
    except Exception:
        pass

    sys.stderr.write(err_msg)

    try:
        messagebox.showerror(
            "Application Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\nFull details have been saved to:\n{ERROR_LOG_PATH}"
        )
    except Exception:
        pass


# Register global exception hooks
sys.excepthook = log_exception
if hasattr(threading, "excepthook"):
    threading.excepthook = lambda args: log_exception(args.exc_type, args.exc_value, args.exc_traceback)

# Import core modules
import folder_to_pdf
import translator


class PDFConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Artbook & Comic PDF Converter & Translator")
        self.root.geometry("1040x770")
        self.root.minsize(900, 680)

        # Message queue for background worker updates
        self.log_queue = queue.Queue()
        self.is_processing = False

        # Discovered items
        self.discovered_folders = []
        self.discovered_pdfs = []

        # Current workspace (smart detect: if current folder has no books but parent does, use parent)
        cwd = Path.cwd()
        parent = cwd.parent
        if cwd != parent and not folder_to_pdf.find_image_folders(cwd, recursive=False) and not folder_to_pdf.find_pdf_files(cwd, recursive=False):
            if folder_to_pdf.find_image_folders(parent, recursive=False) or folder_to_pdf.find_pdf_files(parent, recursive=False):
                self.current_dir = parent
            else:
                self.current_dir = cwd
        else:
            self.current_dir = cwd

        self._setup_styles()
        self._build_ui()
        self._start_log_consumer()

        # Initial automatic scan of the current directory
        self.root.after(200, self.scan_books)

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Configure color palette and fonts
        style.configure(".", font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9, "bold"))
        style.configure("ProgressTitle.TLabel", font=("Segoe UI", 9, "bold"), foreground="#1e40af")
        style.configure("ProgressText.TLabel", font=("Segoe UI", 9))
        style.configure("ProgressPercent.TLabel", font=("Segoe UI", 9, "bold"), foreground="#059669")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), padding=5)

    def _build_ui(self):
        # Main layout container
        main_frame = ttk.Frame(self.root, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ==========================================
        # 1. TOP BAR: Directory Selector & Scan
        # ==========================================
        top_frame = ttk.LabelFrame(main_frame, text=" Workspace Directory ", padding="10")
        top_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top_frame, text="Folder:").pack(side=tk.LEFT, padx=(0, 5))
        self.dir_entry = ttk.Entry(top_frame)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.dir_entry.insert(0, str(self.current_dir))

        browse_btn = ttk.Button(top_frame, text="Browse...", command=self.browse_directory)
        browse_btn.pack(side=tk.LEFT, padx=3)

        scan_btn = ttk.Button(top_frame, text="🔍 Scan for Books & PDFs", style="Action.TButton", command=self.scan_books)
        scan_btn.pack(side=tk.LEFT, padx=(5, 0))

        # ==========================================
        # 2. MIDDLE SPLIT: Dual-Tab Items List & Settings
        # ==========================================
        middle_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        middle_paned.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # --- Left Pane: Dual-Tab Notebook for Folders & Existing PDFs ---
        self.left_notebook = ttk.Notebook(middle_paned)
        middle_paned.add(self.left_notebook, weight=3)

        # ----------------------------------------------------
        # Tab A: Image Book Folders
        # ----------------------------------------------------
        folder_tab = ttk.Frame(self.left_notebook, padding="6")
        self.left_notebook.add(folder_tab, text="  📁 Image Book Folders  ")

        columns_f = ("name", "images", "status")
        self.folder_tree = ttk.Treeview(folder_tab, columns=columns_f, show="headings", selectmode="extended")
        self.folder_tree.heading("name", text="Folder / Book Title")
        self.folder_tree.heading("images", text="Images")
        self.folder_tree.heading("status", text="Status")
        self.folder_tree.column("name", width=330)
        self.folder_tree.column("images", width=70, anchor=tk.CENTER)
        self.folder_tree.column("status", width=120, anchor=tk.CENTER)

        tree_scroll_f = ttk.Scrollbar(folder_tab, orient=tk.VERTICAL, command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=tree_scroll_f.set)

        self.folder_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tree_scroll_f.pack(side=tk.RIGHT, fill=tk.Y, before=self.folder_tree)

        folder_btn_bar = ttk.Frame(folder_tab)
        folder_btn_bar.pack(fill=tk.X, pady=(6, 0))

        ttk.Button(folder_btn_bar, text="Select All", command=lambda: self.folder_tree.selection_set(self.folder_tree.get_children())).pack(side=tk.LEFT, padx=2)
        ttk.Button(folder_btn_bar, text="Deselect All", command=lambda: self.folder_tree.selection_remove(self.folder_tree.get_children())).pack(side=tk.LEFT, padx=2)

        self.folder_count_lbl = ttk.Label(folder_btn_bar, text="0 folders found", font=("Segoe UI", 9, "italic"))
        self.folder_count_lbl.pack(side=tk.RIGHT, padx=5)

        # ----------------------------------------------------
        # Tab B: Existing PDF Files (Direct PDF Translation)
        # ----------------------------------------------------
        pdf_tab_view = ttk.Frame(self.left_notebook, padding="6")
        self.left_notebook.add(pdf_tab_view, text="  📄 Existing PDF Files  ")

        columns_p = ("name", "pages", "status")
        self.pdf_tree = ttk.Treeview(pdf_tab_view, columns=columns_p, show="headings", selectmode="extended")
        self.pdf_tree.heading("name", text="PDF Document Title")
        self.pdf_tree.heading("pages", text="Pages")
        self.pdf_tree.heading("status", text="Status")
        self.pdf_tree.column("name", width=330)
        self.pdf_tree.column("pages", width=70, anchor=tk.CENTER)
        self.pdf_tree.column("status", width=120, anchor=tk.CENTER)

        tree_scroll_p = ttk.Scrollbar(pdf_tab_view, orient=tk.VERTICAL, command=self.pdf_tree.yview)
        self.pdf_tree.configure(yscrollcommand=tree_scroll_p.set)

        self.pdf_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tree_scroll_p.pack(side=tk.RIGHT, fill=tk.Y, before=self.pdf_tree)

        pdf_btn_bar = ttk.Frame(pdf_tab_view)
        pdf_btn_bar.pack(fill=tk.X, pady=(6, 0))

        ttk.Button(pdf_btn_bar, text="Select All", command=lambda: self.pdf_tree.selection_set(self.pdf_tree.get_children())).pack(side=tk.LEFT, padx=2)
        ttk.Button(pdf_btn_bar, text="Deselect All", command=lambda: self.pdf_tree.selection_remove(self.pdf_tree.get_children())).pack(side=tk.LEFT, padx=2)
        ttk.Button(pdf_btn_bar, text="➕ Add PDF File(s)...", style="Action.TButton", command=self.add_custom_pdfs).pack(side=tk.LEFT, padx=6)

        self.pdf_count_lbl = ttk.Label(pdf_btn_bar, text="0 PDFs found", font=("Segoe UI", 9, "italic"))
        self.pdf_count_lbl.pack(side=tk.RIGHT, padx=5)

        self.left_notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        # --- Right Pane: Settings Notebook ---
        settings_notebook = ttk.Notebook(middle_paned)
        middle_paned.add(settings_notebook, weight=2)

        # Tab 1: PDF Options
        pdf_tab = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(pdf_tab, text="  PDF & Output Settings  ")

        ttk.Label(pdf_tab, text="Quality Preset:", style="SubHeader.TLabel").pack(anchor=tk.W, pady=(0, 4))
        self.quality_var = tk.IntVar(value=100)
        q_frame = ttk.Frame(pdf_tab)
        q_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Radiobutton(q_frame, text="100% Maximum Clarity (Lossless)", variable=self.quality_var, value=100).pack(anchor=tk.W)
        ttk.Radiobutton(q_frame, text="95% High Quality (Compressed)", variable=self.quality_var, value=95).pack(anchor=tk.W)
        ttk.Radiobutton(q_frame, text="85% Standard", variable=self.quality_var, value=85).pack(anchor=tk.W)

        ttk.Label(pdf_tab, text="PDF Translation Resolution (DPI):", style="SubHeader.TLabel").pack(anchor=tk.W, pady=(4, 2))
        self.dpi_var = tk.IntVar(value=200)
        dpi_frame = ttk.Frame(pdf_tab)
        dpi_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Radiobutton(dpi_frame, text="200 DPI (Recommended - Crisp & Fast)", variable=self.dpi_var, value=200).pack(anchor=tk.W)
        ttk.Radiobutton(dpi_frame, text="300 DPI (Ultra Sharp - High Detail Scans)", variable=self.dpi_var, value=300).pack(anchor=tk.W)
        ttk.Radiobutton(dpi_frame, text="150 DPI (Fast / Compact File Size)", variable=self.dpi_var, value=150).pack(anchor=tk.W)

        self.overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(pdf_tab, text="Overwrite existing output files", variable=self.overwrite_var).pack(anchor=tk.W, pady=(0, 6))

        ttk.Label(pdf_tab, text="Output Directory:", style="SubHeader.TLabel").pack(anchor=tk.W, pady=(4, 4))
        self.output_same_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(pdf_tab, text="Save alongside source book (Default)", variable=self.output_same_var, value=True, command=self._toggle_output_entry).pack(anchor=tk.W)
        ttk.Radiobutton(pdf_tab, text="Custom output directory:", variable=self.output_same_var, value=False, command=self._toggle_output_entry).pack(anchor=tk.W)

        out_box = ttk.Frame(pdf_tab)
        out_box.pack(fill=tk.X, pady=(4, 0))
        self.custom_output_entry = ttk.Entry(out_box, state=tk.DISABLED)
        self.custom_output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.custom_output_btn = ttk.Button(out_box, text="...", width=3, state=tk.DISABLED, command=self.browse_output_directory)
        self.custom_output_btn.pack(side=tk.LEFT)

        # Tab 2: Translation Options (Optional)
        self.trans_tab = ttk.Frame(settings_notebook, padding="10")
        settings_notebook.add(self.trans_tab, text="  Translator Settings  ")

        self.enable_trans_var = tk.BooleanVar(value=False)
        self.trans_check = ttk.Checkbutton(
            self.trans_tab,
            text="Enable Japanese Translation for Folder Conversion",
            variable=self.enable_trans_var,
            style="SubHeader.TLabel",
            command=self._toggle_translation_controls
        )
        self.trans_check.pack(anchor=tk.W, pady=(0, 6))

        # Output Mode Frame
        ttk.Label(self.trans_tab, text="Translation Output Mode:", style="SubHeader.TLabel").pack(anchor=tk.W, pady=(4, 2))
        self.trans_mode_var = tk.StringVar(value="replace")
        self.r_replace = ttk.Radiobutton(
            self.trans_tab,
            text="In-Place Scanlation (Typeset into speech bubbles)",
            variable=self.trans_mode_var,
            value="replace"
        )
        self.r_replace.pack(anchor=tk.W)
        self.r_guide = ttk.Radiobutton(
            self.trans_tab,
            text="Companion Guide (.md & .txt translation notes)",
            variable=self.trans_mode_var,
            value="guide"
        )
        self.r_guide.pack(anchor=tk.W)
        self.r_both = ttk.Radiobutton(
            self.trans_tab,
            text="Both (Translated PDF + Companion Guide)",
            variable=self.trans_mode_var,
            value="both"
        )
        self.r_both.pack(anchor=tk.W)

        lang_frame = ttk.Frame(self.trans_tab)
        lang_frame.pack(fill=tk.X, pady=(6, 6))
        ttk.Label(lang_frame, text="Source:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.src_lang_cb = ttk.Combobox(lang_frame, values=["Japanese (ja)", "Korean (ko)", "Chinese (zh)"], width=15)
        self.src_lang_cb.current(0)
        self.src_lang_cb.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(lang_frame, text="Target:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dest_lang_cb = ttk.Combobox(lang_frame, values=["English (en)", "Spanish (es)", "French (fr)", "German (de)"], width=15)
        self.dest_lang_cb.current(0)
        self.dest_lang_cb.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(self.trans_tab, text="Translation Engine:", style="SubHeader.TLabel").pack(anchor=tk.W, pady=(4, 2))
        self.engine_var = tk.StringVar(value="auto")
        self.r_eng_auto = ttk.Radiobutton(self.trans_tab, text="Auto (OCR + Free Google Translate)", variable=self.engine_var, value="auto")
        self.r_eng_auto.pack(anchor=tk.W)
        self.r_eng_ollama = ttk.Radiobutton(self.trans_tab, text="Ollama Local Vision AI (llama3.2-vision)", variable=self.engine_var, value="ollama")
        self.r_eng_ollama.pack(anchor=tk.W)

        self.trans_status_lbl = ttk.Label(
            self.trans_tab,
            text="Tip: When translating PDF files, the PDF pages are extracted at chosen DPI, speech bubbles are in-place typeset, and saved as a high-quality translated PDF.",
            font=("Segoe UI", 8, "italic"),
            foreground="#555555",
            wraplength=280
        )
        self.trans_status_lbl.pack(anchor=tk.W, pady=(8, 0))

        self._toggle_translation_controls()

        # ==========================================
        # 3. DEDICATED PROGRESS DASHBOARD
        # ==========================================
        progress_dashboard = ttk.LabelFrame(main_frame, text=" Progress & Status ", padding="10")
        progress_dashboard.pack(fill=tk.X, pady=(0, 8))

        # --- Sub-bar 1: Current Book / PDF Page Progress ---
        cur_header_frame = ttk.Frame(progress_dashboard)
        cur_header_frame.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(cur_header_frame, text="Current Item:", style="ProgressTitle.TLabel").pack(side=tk.LEFT)
        self.current_book_lbl = ttk.Label(cur_header_frame, text="Idle", style="ProgressText.TLabel")
        self.current_book_lbl.pack(side=tk.LEFT, padx=(5, 0))
        self.current_percent_lbl = ttk.Label(cur_header_frame, text="0%", style="ProgressPercent.TLabel")
        self.current_percent_lbl.pack(side=tk.RIGHT)

        self.current_progress_bar = ttk.Progressbar(progress_dashboard, orient=tk.HORIZONTAL, mode='determinate')
        self.current_progress_bar.pack(fill=tk.X, pady=(0, 8))

        # --- Sub-bar 2: Overall Batch Progress ---
        ovr_header_frame = ttk.Frame(progress_dashboard)
        ovr_header_frame.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(ovr_header_frame, text="Overall Batch:", style="ProgressTitle.TLabel").pack(side=tk.LEFT)
        self.overall_book_lbl = ttk.Label(ovr_header_frame, text="0 / 0 completed", style="ProgressText.TLabel")
        self.overall_book_lbl.pack(side=tk.LEFT, padx=(5, 0))
        self.overall_percent_lbl = ttk.Label(ovr_header_frame, text="0%", style="ProgressPercent.TLabel")
        self.overall_percent_lbl.pack(side=tk.RIGHT)

        self.overall_progress_bar = ttk.Progressbar(progress_dashboard, orient=tk.HORIZONTAL, mode='determinate')
        self.overall_progress_bar.pack(fill=tk.X, pady=(0, 2))

        # ==========================================
        # 4. ACTION BAR BUTTONS
        # ==========================================
        action_bar = ttk.Frame(main_frame)
        action_bar.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(
            action_bar,
            text="🚀 Convert Selected Folders to PDF",
            style="Primary.TButton",
            command=self.start_processing
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        open_folder_btn = ttk.Button(action_bar, text="📂 Open Output Folder", style="Action.TButton", command=self.open_output_folder)
        open_folder_btn.pack(side=tk.LEFT, padx=4)

        # ==========================================
        # 5. BOTTOM LOG WINDOW
        # ==========================================
        log_frame = ttk.LabelFrame(main_frame, text=" Activity Log ", padding="6")
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 0))

        self.log_text = tk.Text(log_frame, height=7, wrap=tk.WORD, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log("Ready. Select books or PDFs and click the action button to begin.")

    def _on_notebook_tab_changed(self, event):
        tab_idx = self.left_notebook.index(self.left_notebook.select())
        if tab_idx == 0:
            self.start_btn.configure(text="🚀 Convert Selected Folders to PDF")
            self._toggle_translation_controls()
        else:
            self.start_btn.configure(text="🌐 Translate Selected PDF Files")
            # When on PDF tab, enable translation controls
            self.r_replace.configure(state=tk.NORMAL)
            self.r_guide.configure(state=tk.NORMAL)
            self.r_both.configure(state=tk.NORMAL)
            self.src_lang_cb.configure(state=tk.NORMAL)
            self.dest_lang_cb.configure(state=tk.NORMAL)
            self.r_eng_auto.configure(state=tk.NORMAL)
            self.r_eng_ollama.configure(state=tk.NORMAL)

    def _toggle_output_entry(self):
        is_custom = not self.output_same_var.get()
        state = tk.NORMAL if is_custom else tk.DISABLED
        self.custom_output_entry.configure(state=state)
        self.custom_output_btn.configure(state=state)

    def _toggle_translation_controls(self):
        tab_idx = 0
        try:
            tab_idx = self.left_notebook.index(self.left_notebook.select())
        except Exception:
            pass

        # If on PDF tab, translation controls are always enabled
        if tab_idx == 1:
            state = tk.NORMAL
        else:
            enabled = self.enable_trans_var.get()
            state = tk.NORMAL if enabled else tk.DISABLED

        self.r_replace.configure(state=state)
        self.r_guide.configure(state=state)
        self.r_both.configure(state=state)
        self.src_lang_cb.configure(state=state)
        self.dest_lang_cb.configure(state=state)
        self.r_eng_auto.configure(state=state)
        self.r_eng_ollama.configure(state=state)

    def log(self, message: str):
        """Append message to log queue and activity log file."""
        timestamp = time.strftime("[%H:%M:%S] ")
        formatted = timestamp + message
        self.log_queue.put(formatted)
        try:
            with open(ACTIVITY_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass

    def _start_log_consumer(self):
        """Periodically pulls logs from the queue and inserts into log_text."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self._start_log_consumer)

    def update_current_progress(self, current: int, total: int, status_text: str = ""):
        """Thread-safe update for the Current Book/PDF progress bar."""
        def _update():
            self.current_progress_bar.configure(maximum=max(1, total), value=current)
            percent = (current / total * 100.0) if total > 0 else 0.0
            self.current_percent_lbl.configure(text=f"{percent:.1f}%")
            if status_text:
                self.current_book_lbl.configure(text=status_text)
        self.root.after(0, _update)

    def update_overall_progress(self, current: int, total: int, status_text: str = ""):
        """Thread-safe update for the Overall Batch progress bar."""
        def _update():
            self.overall_progress_bar.configure(maximum=max(1, total), value=current)
            percent = (current / total * 100.0) if total > 0 else 0.0
            self.overall_percent_lbl.configure(text=f"{percent:.1f}%")
            if status_text:
                self.overall_book_lbl.configure(text=status_text)
        self.root.after(0, _update)

    def browse_directory(self):
        selected = filedialog.askdirectory(initialdir=self.current_dir, title="Select Books Directory")
        if selected:
            self.current_dir = Path(selected)
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, str(self.current_dir))
            self.scan_books()

    def browse_output_directory(self):
        selected = filedialog.askdirectory(initialdir=self.current_dir, title="Select Output Directory")
        if selected:
            self.custom_output_entry.delete(0, tk.END)
            self.custom_output_entry.insert(0, selected)

    def add_custom_pdfs(self):
        """Allows user to select PDF files from anywhere on disk to add to the PDF list."""
        files = filedialog.askopenfilenames(
            initialdir=self.current_dir,
            title="Select PDF Files to Translate",
            filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")]
        )
        if files:
            added_count = 0
            for f_str in files:
                p = Path(f_str)
                if str(p) not in [self.pdf_tree.item(iid)['values'][0] for iid in self.pdf_tree.get_children()]:
                    page_cnt = translator.get_pdf_page_count(p)
                    self.pdf_tree.insert("", tk.END, iid=str(p), values=(p.name, page_cnt, "Ready"))
                    self.pdf_tree.selection_add(str(p))
                    added_count += 1
            if added_count:
                total_pdfs = len(self.pdf_tree.get_children())
                self.pdf_count_lbl.config(text=f"{total_pdfs} PDF(s) listed")
                self.log(f"Added {added_count} external PDF file(s) to list.")

    def scan_books(self):
        """Scans the workspace directory recursively for folders and PDF files."""
        p_str = self.dir_entry.get().strip()
        root_path = Path(p_str)
        if not root_path.exists() or not root_path.is_dir():
            messagebox.showerror("Invalid Directory", f"The directory does not exist:\n{root_path}")
            return

        self.current_dir = root_path
        self.folder_tree.delete(*self.folder_tree.get_children())
        self.pdf_tree.delete(*self.pdf_tree.get_children())
        self.log(f"Scanning '{root_path.name}' for image book folders & PDF files...")

        # 1. Scan image folders
        folders = folder_to_pdf.find_image_folders(root_path, recursive=True)
        self.discovered_folders = folders

        for f in folders:
            images = folder_to_pdf.get_image_files_in_folder(f)
            pdf_path = f.parent / f"{f.name}.pdf"
            status = "Already Converted" if pdf_path.exists() else "Ready"
            self.folder_tree.insert("", tk.END, iid=str(f), values=(f.name, len(images), status))

        self.folder_count_lbl.config(text=f"{len(folders)} folder(s) found")

        # 2. Scan existing PDF files
        pdfs = folder_to_pdf.find_pdf_files(root_path, recursive=True)
        self.discovered_pdfs = pdfs

        for p in pdfs:
            # Check if translation already exists
            t_pdf = p.parent / f"{p.stem} [English Translated].pdf"
            status = "Already Translated" if t_pdf.exists() else "Ready"
            pages = translator.get_pdf_page_count(p)
            self.pdf_tree.insert("", tk.END, iid=str(p), values=(p.name, pages, status))

        self.pdf_count_lbl.config(text=f"{len(pdfs)} PDF(s) found")
        self.log(f"Scan complete: Found {len(folders)} image folder(s) and {len(pdfs)} PDF file(s).")

        # Select all in active tab
        tab_idx = self.left_notebook.index(self.left_notebook.select())
        if tab_idx == 0:
            self.folder_tree.selection_set(self.folder_tree.get_children())
        else:
            self.pdf_tree.selection_set(self.pdf_tree.get_children())

    def start_processing(self):
        if self.is_processing:
            return

        tab_idx = self.left_notebook.index(self.left_notebook.select())
        if tab_idx == 0:
            self._start_folder_conversion()
        else:
            self._start_pdf_translation()

    def _start_folder_conversion(self):
        selected_ids = self.folder_tree.selection()
        if not selected_ids:
            messagebox.showwarning("No Folders Selected", "Please select one or more book folders from the list to convert.")
            return

        folders_to_convert = [Path(iid) for iid in selected_ids]

        # Read settings
        quality = self.quality_var.get()
        overwrite = self.overwrite_var.get()
        custom_out = None if self.output_same_var.get() else Path(self.custom_output_entry.get().strip())
        enable_trans = self.enable_trans_var.get()
        trans_mode = self.trans_mode_var.get()
        src_code = self.src_lang_cb.get().split("(")[-1].replace(")", "").strip()
        dest_code = self.dest_lang_cb.get().split("(")[-1].replace(")", "").strip()
        engine = self.engine_var.get()

        self.is_processing = True
        self.start_btn.configure(state=tk.DISABLED, text="⏳ Processing Folders...")

        self.update_current_progress(0, 1, "Initializing...")
        self.update_overall_progress(0, len(folders_to_convert), f"0 / {len(folders_to_convert)} folders completed")

        thread = threading.Thread(
            target=self._folder_worker_process,
            args=(folders_to_convert, custom_out, overwrite, quality, enable_trans, trans_mode, src_code, dest_code, engine),
            daemon=True
        )
        thread.start()

    def _folder_worker_process(self, folders, custom_out, overwrite, quality, enable_trans, trans_mode, src_code, dest_code, engine):
        total = len(folders)
        success_count = 0
        self.log(f"Starting conversion for {total} selected book folder(s)...")

        for idx, folder in enumerate(folders, 1):
            folder_name = folder.name
            self.log(f"[{idx}/{total}] Processing '{folder_name}'...")
            self.update_overall_progress(idx - 1, total, f"Folder {idx} of {total}: '{folder_name}'")

            def on_page_progress(cur, tot, msg):
                disp_msg = f"'{folder_name}' - {msg}"
                self.update_current_progress(cur, tot, disp_msg)

            # 1. Convert to PDF
            pdf_path = folder_to_pdf.convert_folder_to_pdf(
                folder,
                output_dir=custom_out,
                overwrite=overwrite,
                quality=quality,
                page_callback=on_page_progress
            )

            if pdf_path:
                success_count += 1
                self.root.after(0, lambda f=folder: self.folder_tree.set(str(f), "status", "Converted ✓"))

                # 2. Optional Translation step
                if enable_trans:
                    self.log(f"    🌐 Running translation for '{folder_name}' ({src_code} -> {dest_code}, mode: {trans_mode})...")

                    if trans_mode in ("replace", "both"):
                        self.log(f"       Inpainting & typesetting translated pages for '{folder_name}'...")
                        t_pdf, page_data = folder_to_pdf.create_translated_pdf(
                            folder,
                            output_dir=custom_out,
                            overwrite=overwrite,
                            quality=quality,
                            src_lang=src_code,
                            dest_lang=dest_code,
                            engine=engine,
                            page_callback=on_page_progress
                        )
                        if t_pdf:
                            self.log(f"    ✓ Translated PDF created: {t_pdf.name}")

                        if trans_mode == "both" and page_data:
                            guide_dir = custom_out if custom_out else folder.parent
                            md_path, txt_path = translator.save_translation_guide(folder_name, page_data, guide_dir)
                            self.log(f"    ✓ Translation companion guide saved: {md_path.name}")

                    elif trans_mode == "guide":
                        image_files = folder_to_pdf.get_image_files_in_folder(folder)
                        total_pages = len(image_files)
                        page_translations = []

                        for p_idx, img_path in enumerate(image_files, 1):
                            self.update_current_progress(
                                p_idx,
                                total_pages,
                                f"Translating Page {p_idx}/{total_pages}: {img_path.name}"
                            )
                            trans_data = translator.translate_page(
                                img_path,
                                src_lang=src_code,
                                dest_lang=dest_code,
                                engine=engine
                            )
                            page_translations.append(trans_data)

                        guide_dir = custom_out if custom_out else folder.parent
                        md_path, txt_path = translator.save_translation_guide(folder_name, page_translations, guide_dir)
                        self.log(f"    ✓ Translation companion guide saved: {md_path.name}")

            else:
                self.root.after(0, lambda f=folder: self.folder_tree.set(str(f), "status", "Skipped / Error"))

            self.update_overall_progress(idx, total, f"{idx} / {total} folders completed")

        self.update_current_progress(100, 100, "All operations finished.")
        self.update_overall_progress(total, total, f"Finished! {success_count}/{total} books created.")
        self.log(f"Done! Successfully processed {success_count}/{total} book folder(s).")
        self.root.after(0, self._on_processing_complete)

    def _start_pdf_translation(self):
        selected_ids = self.pdf_tree.selection()
        if not selected_ids:
            messagebox.showwarning("No PDFs Selected", "Please select one or more PDF files from the list to translate.")
            return

        pdfs_to_translate = [Path(iid) for iid in selected_ids]

        # Read settings
        quality = self.quality_var.get()
        dpi = self.dpi_var.get()
        overwrite = self.overwrite_var.get()
        custom_out = None if self.output_same_var.get() else Path(self.custom_output_entry.get().strip())
        trans_mode = self.trans_mode_var.get()
        src_code = self.src_lang_cb.get().split("(")[-1].replace(")", "").strip()
        dest_code = self.dest_lang_cb.get().split("(")[-1].replace(")", "").strip()
        engine = self.engine_var.get()

        self.is_processing = True
        self.start_btn.configure(state=tk.DISABLED, text="⏳ Translating PDFs...")

        self.update_current_progress(0, 1, "Initializing PDF translation...")
        self.update_overall_progress(0, len(pdfs_to_translate), f"0 / {len(pdfs_to_translate)} PDFs completed")

        thread = threading.Thread(
            target=self._pdf_worker_process,
            args=(pdfs_to_translate, custom_out, overwrite, quality, dpi, trans_mode, src_code, dest_code, engine),
            daemon=True
        )
        thread.start()

    def _pdf_worker_process(self, pdfs, custom_out, overwrite, quality, dpi, trans_mode, src_code, dest_code, engine):
        total = len(pdfs)
        success_count = 0
        self.log(f"Starting direct translation for {total} selected PDF file(s)...")

        for idx, pdf_p in enumerate(pdfs, 1):
            pdf_name = pdf_p.name
            self.log(f"[{idx}/{total}] Translating PDF: '{pdf_name}' (mode: {trans_mode}, {dpi} DPI)...")
            self.update_overall_progress(idx - 1, total, f"PDF {idx} of {total}: '{pdf_name}'")

            def on_page_progress(cur, tot, msg):
                disp_msg = f"'{pdf_name}' - {msg}"
                self.update_current_progress(cur, tot, disp_msg)

            try:
                out_pdf, guide_data = translator.translate_pdf_file(
                    pdf_p,
                    output_dir=custom_out,
                    overwrite=overwrite,
                    quality=quality,
                    mode=trans_mode,
                    src_lang=src_code,
                    dest_lang=dest_code,
                    engine=engine,
                    dpi=dpi,
                    page_callback=on_page_progress
                )

                if out_pdf or (trans_mode == "guide" and guide_data):
                    success_count += 1
                    self.root.after(0, lambda p=pdf_p: self.pdf_tree.set(str(p), "status", "Translated ✓"))
                    if out_pdf:
                        size_str = folder_to_pdf.format_size(out_pdf.stat().st_size)
                        self.log(f"    ✓ Translated PDF saved: '{out_pdf.name}' ({size_str})")
                    if trans_mode in ("guide", "both"):
                        self.log(f"    ✓ Translation companion guide saved for '{pdf_name}'")
                else:
                    self.root.after(0, lambda p=pdf_p: self.pdf_tree.set(str(p), "status", "Skipped"))
                    self.log(f"    [-] Skipped '{pdf_name}' (already exists or no pages)")

            except Exception as e:
                self.log(f"    [!] Error translating '{pdf_name}': {e}")
                self.root.after(0, lambda p=pdf_p: self.pdf_tree.set(str(p), "status", "Error"))

            self.update_overall_progress(idx, total, f"{idx} / {total} PDFs completed")

        self.update_current_progress(100, 100, "All PDF operations finished.")
        self.update_overall_progress(total, total, f"Finished! {success_count}/{total} PDF(s) translated.")
        self.log(f"Done! Successfully processed {success_count}/{total} PDF file(s).")
        self.root.after(0, self._on_processing_complete)

    def _on_processing_complete(self):
        self.is_processing = False
        tab_idx = self.left_notebook.index(self.left_notebook.select())
        if tab_idx == 0:
            self.start_btn.configure(state=tk.NORMAL, text="🚀 Convert Selected Folders to PDF")
        else:
            self.start_btn.configure(state=tk.NORMAL, text="🌐 Translate Selected PDF Files")
        messagebox.showinfo("Complete", "Processing has finished successfully!")

    def open_output_folder(self):
        target = self.current_dir
        if not self.output_same_var.get():
            custom = self.custom_output_entry.get().strip()
            if custom and Path(custom).exists():
                target = Path(custom)
        os.startfile(str(target))


def main():
    root = tk.Tk()
    app = PDFConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
