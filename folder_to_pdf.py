#!/usr/bin/env python3
"""
Folder to High-Quality PDF Converter
Converts folders of images into high-quality PDFs named after the folder.
Supports Drag-and-Drop, CLI arguments, Interactive mode, and Real-time Progress Tracking.
"""

import os
import sys
import re
import time
import argparse
from pathlib import Path
from PIL import Image, ImageOps

# Supported image extensions
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.jp2'
}

# Optional lossless embedding via img2pdf if installed
try:
    import img2pdf
    HAS_IMG2PDF = True
except ImportError:
    HAS_IMG2PDF = False


def print_cli_progress_bar(current: int, total: int, prefix: str = '', suffix: str = '', bar_length: int = 30):
    """
    Renders an ASCII/Unicode progress bar in the terminal:
    e.g. [████████████████░░░░░░░░] 60.0% (18/30) - Scan_018.jpg
    """
    if total <= 0:
        return
    fraction = min(1.0, max(0.0, current / total))
    percent = fraction * 100.0
    filled = int(round(bar_length * fraction))
    bar = '█' * filled + '░' * (bar_length - filled)
    
    # Print with carriage return \r to overwrite line
    sys.stdout.write(f"\r  {prefix}[{bar}] {percent:5.1f}% ({current}/{total}) {suffix}")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()


def natural_sort_key(s: str):
    """
    Sort strings containing numbers naturally:
    e.g. ['page1.jpg', 'page2.jpg', 'page10.jpg'] instead of ['page1', 'page10', 'page2'].
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


def is_valid_image_file(path: Path) -> bool:
    """Check if the file is a supported image and not system/hidden junk."""
    name = path.name
    # Filter out macOS resource forks, hidden files, and Thumbs.db
    if name.startswith('.') or name.startswith('._') or name.lower() == 'thumbs.db':
        return False
    if '__MACOSX' in path.parts:
        return False
    return path.suffix.lower() in IMAGE_EXTENSIONS


def get_image_files_in_folder(folder: Path) -> list[Path]:
    """Return all valid image files directly inside the given folder, naturally sorted."""
    if not folder.is_dir():
        return []
    
    images = []
    try:
        for entry in folder.iterdir():
            if entry.is_file() and is_valid_image_file(entry):
                images.append(entry)
    except Exception as e:
        print(f"  [!] Error reading directory '{folder.name}': {e}")
        return []

    images.sort(key=lambda p: natural_sort_key(p.name))
    return images


def find_image_folders(root: Path, recursive: bool = True) -> list[Path]:
    """
    Find directories that directly contain valid image files.
    If recursive=False, only checks immediate subdirectories of root.
    """
    image_folders = []
    
    # Check if root itself has images
    if get_image_files_in_folder(root):
        image_folders.append(root)

    if recursive:
        for dirpath, dirnames, _ in os.walk(root):
            # Skip hidden / macOS dirs
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__MACOSX']
            p = Path(dirpath)
            if p != root and get_image_files_in_folder(p):
                image_folders.append(p)
    else:
        for item in root.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != '__MACOSX':
                if get_image_files_in_folder(item):
                    image_folders.append(item)

    image_folders.sort(key=lambda p: natural_sort_key(p.name))
    return image_folders


def find_pdf_files(root: Path, recursive: bool = True) -> list[Path]:
    """
    Finds PDF files in directory, ignoring already translated companion PDFs.
    """
    pdfs = []
    if not root.is_dir():
        if root.is_file() and root.suffix.lower() == '.pdf':
            return [root]
        return []

    try:
        if recursive:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__MACOSX']
                for fn in filenames:
                    if fn.lower().endswith('.pdf'):
                        fl = fn.lower()
                        if "[english translated]" in fl or "[translated]" in fl:
                            continue
                        pdfs.append(Path(dirpath) / fn)
        else:
            for entry in root.iterdir():
                if entry.is_file() and entry.suffix.lower() == '.pdf':
                    fl = entry.name.lower()
                    if "[english translated]" in fl or "[translated]" in fl:
                        continue
                    pdfs.append(entry)
    except Exception:
        pass

    pdfs.sort(key=lambda p: natural_sort_key(p.name))
    return pdfs


def format_size(num_bytes: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} TB"


def prepare_pillow_image(image_path: Path) -> Image.Image:
    """
    Opens an image, corrects EXIF orientation, and ensures compatibility with PDF.
    Transparent images (RGBA / P) are composited onto a pure white background.
    """
    img = Image.open(image_path)
    
    # Auto-orient based on EXIF tag (e.g. scanned books or phone photos)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Handle color channels
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        rgba = img.convert('RGBA')
        # Create pure white background
        bg = Image.new('RGB', rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        return bg
    elif img.mode != 'RGB':
        return img.convert('RGB')
    
    return img


def convert_folder_to_pdf(
    folder: Path,
    output_dir: Path | None = None,
    overwrite: bool = False,
    quality: int = 100,
    page_callback=None
) -> Path | None:
    """
    Convert all images in `folder` to a PDF named `<folder.name>.pdf`.
    Saves in `output_dir` if provided, otherwise alongside `folder` (in folder.parent).
    `page_callback(current, total, message)` is called as each page is processed.
    """
    folder = folder.resolve()
    image_paths = get_image_files_in_folder(folder)
    total_images = len(image_paths)

    if total_images == 0:
        print(f"[-] Skipped '{folder.name}': No supported images found.")
        return None

    # Destination PDF named exactly as the folder
    target_dir = output_dir.resolve() if output_dir else folder.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = target_dir / f"{folder.name}.pdf"

    if pdf_path.exists() and not overwrite:
        print(f"[-] Skipped '{folder.name}': PDF already exists ('{pdf_path.name}'). Use --overwrite to replace.")
        return pdf_path

    print(f"\n[+] Processing '{folder.name}' ({total_images} images)...")
    start_time = time.time()

    # Initial progress notify
    if page_callback:
        page_callback(0, total_images, f"Starting '{folder.name}'...")
    else:
        print_cli_progress_bar(0, total_images, prefix="Preparing: ")

    # Strategy 1: Try img2pdf if installed (100% byte-for-byte lossless embedding)
    if HAS_IMG2PDF:
        try:
            if page_callback:
                page_callback(int(total_images * 0.5), total_images, "Embedding images losslessly via img2pdf...")
            with open(pdf_path, 'wb') as f:
                f.write(img2pdf.convert([str(p) for p in image_paths]))
            
            elapsed = time.time() - start_time
            size_str = format_size(pdf_path.stat().st_size)
            if page_callback:
                page_callback(total_images, total_images, f"Completed: {pdf_path.name}")
            else:
                print_cli_progress_bar(total_images, total_images, prefix="Completed: ")
            print(f"    ✓ Lossless PDF created via img2pdf in {elapsed:.1f}s: {pdf_path.name} ({size_str})")
            return pdf_path
        except Exception:
            # Fall back to Pillow if img2pdf fails on an exotic/alpha format
            pass

    # Strategy 2: High-Quality Pillow conversion with per-page progress tracking
    try:
        # Load first image
        if page_callback:
            page_callback(1, total_images, f"Page 1/{total_images}: {image_paths[0].name}")
        else:
            print_cli_progress_bar(1, total_images, prefix="Converting: ", suffix=image_paths[0].name[:20])

        first_img = prepare_pillow_image(image_paths[0])
        
        # Load subsequent images, updating progress for each
        remaining_imgs = []
        for idx, p in enumerate(image_paths[1:], 2):
            if page_callback:
                page_callback(idx, total_images, f"Page {idx}/{total_images}: {p.name}")
            else:
                print_cli_progress_bar(idx, total_images, prefix="Converting: ", suffix=p.name[:20])
            remaining_imgs.append(prepare_pillow_image(p))

        if page_callback:
            page_callback(total_images, total_images, "Writing and compiling PDF...")

        # Save as PDF with maximum quality (subsampling=0 preserves crisp text/lines)
        first_img.save(
            pdf_path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=remaining_imgs,
            quality=quality,
            subsampling=0
        )

        # Close all opened images to free RAM immediately
        first_img.close()
        for im in remaining_imgs:
            im.close()

        elapsed = time.time() - start_time
        size_str = format_size(pdf_path.stat().st_size)
        
        if page_callback:
            page_callback(total_images, total_images, f"Saved ({size_str})")
        else:
            print_cli_progress_bar(total_images, total_images, prefix="Completed:  ", suffix=f"Done in {elapsed:.1f}s")

        print(f"    ✓ High-Quality PDF created in {elapsed:.1f}s: {pdf_path.name} ({size_str})")
        return pdf_path

    except Exception as e:
        print(f"\n    [!] Error converting '{folder.name}': {e}")
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
        return None


def create_translated_pdf(
    folder: Path,
    output_dir: Path | None = None,
    overwrite: bool = False,
    quality: int = 100,
    src_lang: str = 'ja',
    dest_lang: str = 'en',
    engine: str = 'auto',
    page_callback: callable = None
) -> tuple[Path | None, list[dict]]:
    """
    Optional Scanlation Mode:
    Detects text on each page, translates it, replaces/inpaints the original text in-place,
    and compiles into '<Folder_Name> [English Translated].pdf'.
    Returns (translated_pdf_path, page_translations_list).
    """
    import translator

    folder = Path(folder)
    if not folder.is_dir():
        return None, []

    image_paths = get_image_files_in_folder(folder)
    if not image_paths:
        return None, []

    total_images = len(image_paths)
    target_dir = Path(output_dir) if output_dir else folder.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out_pdf_path = target_dir / f"{folder.name} [English Translated].pdf"

    if out_pdf_path.exists() and not overwrite:
        if page_callback:
            page_callback(total_images, total_images, "Already exists (Skipped)")
        return out_pdf_path, []

    start_time = time.time()
    translated_imgs = []
    page_data = []

    try:
        for idx, img_path in enumerate(image_paths, 1):
            if page_callback:
                page_callback(idx, total_images, f"Translating page {idx}/{total_images}: {img_path.name}")
            else:
                print_cli_progress_bar(idx, total_images, prefix="Translating: ", suffix=img_path.name[:20])

            # Typeset image and collect metadata
            scanned_img, data = translator.translate_and_typeset_image(
                img_path,
                src_lang=src_lang,
                dest_lang=dest_lang,
                engine=engine
            )
            translated_imgs.append(scanned_img)
            page_data.append(data)

        if not translated_imgs:
            return None, []

        if page_callback:
            page_callback(total_images, total_images, "Compiling Translated PDF...")

        first_img = translated_imgs[0]
        remaining = translated_imgs[1:] if len(translated_imgs) > 1 else []

        first_img.save(
            out_pdf_path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=remaining,
            quality=quality,
            subsampling=0
        )

        # Free image memory
        first_img.close()
        for im in remaining:
            im.close()

        elapsed = time.time() - start_time
        size_str = format_size(out_pdf_path.stat().st_size)
        if page_callback:
            page_callback(total_images, total_images, f"Translated PDF Saved ({size_str})")
        else:
            print_cli_progress_bar(total_images, total_images, prefix="Completed:  ", suffix=f"Done in {elapsed:.1f}s")

        return out_pdf_path, page_data

    except Exception as e:
        print(f"\n    [!] Error creating translated PDF for '{folder.name}': {e}")
        return None, page_data


def run_interactive():
    """Interactive console menu when running without arguments."""
    print("=" * 65)
    print("        Folder to High-Quality PDF Converter")
    print("=" * 65)
    print(f"Engine: {'img2pdf (Lossless) + ' if HAS_IMG2PDF else ''}Pillow (High Quality 100%)")
    print(f"Current Working Directory: {Path.cwd()}")
    print("-" * 65)
    print("1. Convert all image folders in current directory (Direct subfolders)")
    print("2. Convert all image folders recursively (Includes deep subfolders)")
    print("3. Enter a custom folder path to convert")
    print("4. Translate existing PDF file(s)")
    print("5. Exit")
    print("-" * 65)

    choice = input("Enter your choice (1-5) [default: 1]: ").strip()
    if choice == '' or choice == '1':
        folders = find_image_folders(Path.cwd(), recursive=False)
        process_batch(folders)
    elif choice == '2':
        folders = find_image_folders(Path.cwd(), recursive=True)
        process_batch(folders)
    elif choice == '3':
        custom_path = input("Enter folder path: ").strip().strip('"').strip("'")
        p = Path(custom_path)
        if not p.exists() or not p.is_dir():
            print(f"[!] Invalid folder path: {custom_path}")
            return
        folders = find_image_folders(p, recursive=True)
        if not folders:
            print("[-] No folders containing supported images were found.")
            return
        process_batch(folders)
    elif choice == '4':
        pdf_path_str = input("Enter PDF file path to translate: ").strip().strip('"').strip("'")
        p = Path(pdf_path_str)
        if not p.exists() or not p.is_file():
            print(f"[!] Invalid PDF file path: {pdf_path_str}")
            return
        import translator
        print(f"\nTranslating '{p.name}'...")
        out_p, _ = translator.translate_pdf_file(p, mode="replace", overwrite=False)
        if out_p:
            print(f"[✓] Translated PDF saved to: {out_p}")
    elif choice == '5':
        print("Goodbye!")
        return
    else:
        print("[!] Invalid option selected.")


def process_batch(folders: list[Path], output_dir: Path | None = None, overwrite: bool = False):
    """Processes a list of folders, showing progress bars and a summary."""
    if not folders:
        print("[-] No image folders found to process.")
        return

    print(f"\nFound {len(folders)} folder(s) to convert:")
    for idx, f in enumerate(folders, 1):
        print(f"  {idx}. {f.name}")
    
    confirm = input("\nProceed with conversion? [Y/n]: ").strip().lower()
    if confirm not in ('', 'y', 'yes'):
        print("Cancelled.")
        return

    total_start = time.time()
    converted_count = 0

    for idx, folder in enumerate(folders, 1):
        print(f"\n--- Book [{idx}/{len(folders)}]: {folder.name} ---")
        result = convert_folder_to_pdf(folder, output_dir=output_dir, overwrite=overwrite)
        if result:
            converted_count += 1

    total_elapsed = time.time() - total_start
    print("\n" + "=" * 65)
    print(f"Conversion Complete! Successfully created {converted_count}/{len(folders)} PDF(s) in {total_elapsed:.1f}s.")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="Convert folders of images into high-quality PDFs named after the folder."
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="One or more folders to convert (supports drag & drop)."
    )
    parser.add_argument(
        "-o", "--output",
        help="Custom output directory to save PDFs (default: saved alongside each folder)."
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan subdirectories recursively for folders containing images."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Convert all image folders in the current directory."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing PDF files if they already exist."
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=100,
        help="Image quality (1-100, default: 100 for maximum clarity)."
    )
    parser.add_argument(
        "--translate",
        action="store_true",
        help="Enable optional Japanese translation."
    )
    parser.add_argument(
        "--translate-mode",
        choices=["replace", "guide", "both"],
        default="replace",
        help="Translation mode: 'replace' (scanlation), 'guide' (companion guide), or 'both'."
    )
    parser.add_argument(
        "--src-lang",
        default="ja",
        help="Source language code (default: ja)."
    )
    parser.add_argument(
        "--dest-lang",
        default="en",
        help="Target language code (default: en)."
    )
    parser.add_argument(
        "--engine",
        default="auto",
        help="Translation engine: 'auto' or 'ollama'."
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Rendering resolution (DPI) for PDF translation (default: 200)."
    )

    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None

    # Case 1: Drag & drop or CLI arguments provided (Folders or PDF Files)
    if args.inputs:
        folder_targets = []
        pdf_targets = []

        for item_str in args.inputs:
            p = Path(item_str.strip('"').strip("'"))
            if not p.exists():
                print(f"[!] Path does not exist: {p}")
                continue
            if p.is_file() and p.suffix.lower() == '.pdf':
                pdf_targets.append(p)
            elif p.is_dir():
                if get_image_files_in_folder(p):
                    folder_targets.append(p)
                else:
                    sub_folders = find_image_folders(p, recursive=True)
                    folder_targets.extend(sub_folders)
                    # Also look for PDFs in subfolders if requested
                    sub_pdfs = find_pdf_files(p, recursive=True)
                    if sub_pdfs and args.translate:
                        pdf_targets.extend(sub_pdfs)

        # Process any PDF targets
        if pdf_targets:
            import translator
            print(f"\nProcessing {len(pdf_targets)} PDF file(s) for translation...")
            for idx, pdf_p in enumerate(pdf_targets, 1):
                print(f"\n--- PDF [{idx}/{len(pdf_targets)}]: {pdf_p.name} ---")
                def on_pdf_prog(cur, tot, msg):
                    print_cli_progress_bar(cur, tot, prefix="Page: ", suffix=msg[:30])
                try:
                    out_pdf, guide_data = translator.translate_pdf_file(
                        pdf_p,
                        output_dir=output_dir,
                        overwrite=args.overwrite,
                        quality=args.quality,
                        mode=args.translate_mode,
                        src_lang=args.src_lang,
                        dest_lang=args.dest_lang,
                        engine=args.engine,
                        dpi=args.dpi,
                        page_callback=on_pdf_prog
                    )
                    if out_pdf:
                        print(f"  [✓] Translated PDF saved: {out_pdf.name}")
                except Exception as e:
                    print(f"  [!] Error translating '{pdf_p.name}': {e}")

        # Process any Folder targets
        if folder_targets:
            for idx, f in enumerate(folder_targets, 1):
                print(f"\n--- Book [{idx}/{len(folder_targets)}]: {f.name} ---")
                convert_folder_to_pdf(f, output_dir=output_dir, overwrite=args.overwrite, quality=args.quality)
                if args.translate:
                    create_translated_pdf(
                        f,
                        output_dir=output_dir,
                        overwrite=args.overwrite,
                        quality=args.quality,
                        src_lang=args.src_lang,
                        dest_lang=args.dest_lang,
                        engine=args.engine
                    )

        if not folder_targets and not pdf_targets:
            print("[-] No image folders or PDF files found in provided arguments.")

    # Case 2: --all or --recursive flag specified without inputs
    elif args.all or args.recursive:
        folders = find_image_folders(Path.cwd(), recursive=args.recursive)
        process_batch(folders, output_dir=output_dir, overwrite=args.overwrite)

    # Case 3: No arguments -> Run interactive menu
    else:
        run_interactive()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user.")
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}")
