"""
Book & Artbook Translator Module
Provides optional Japanese translation features:
1. Companion Translation Guides (.md & .txt sidecar files)
2. In-Place Scanlation & Typesetting (Erases Japanese text & renders English into speech bubbles)
3. Generates high-quality translated companion PDFs: '<Name> [English Translated].pdf'

Translation Engines Supported:
- Free Online Translation (zero-config, no API key needed)
- Local Ollama Vision AI (private offline translation with Llama3.2-Vision / MiniCPM-V)
- EasyOCR & Tesseract OCR for text & bounding box detection
"""

import os
import re
import json
import base64
import textwrap
import urllib.request
import urllib.parse
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont

# Check available local OCR engines
HAS_EASYOCR = False
_easyocr_reader = None
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    pass

HAS_PYTESSERACT = False
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    pass


def get_available_font(size: int = 14, bold: bool = True) -> ImageFont.ImageFont:
    """
    Finds a suitable comic / readable font for scanlation typesetting.
    Checks Windows font directory for Comic Sans MS, Segoe UI, or Arial.
    """
    font_candidates = [
        r"C:\Windows\Fonts\comicbd.ttf" if bold else r"C:\Windows\Fonts\comic.ttf",
        r"C:\Windows\Fonts\comic.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\arial.ttf"
    ]
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def free_translate_text(text: str, src: str = 'ja', dest: str = 'en') -> str:
    """
    Translates text using Google's public translation endpoint without requiring an API key.
    """
    clean_text = text.strip()
    if not clean_text:
        return ""

    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': src,
            'tl': dest,
            'dt': 't',
            'q': clean_text
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            full_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            translated_pieces = [chunk[0] for chunk in data[0] if chunk and chunk[0]]
            return "".join(translated_pieces).strip()
    except Exception as e:
        return f"[Translation Error: {e}]"


def ollama_translate_image(image_path: Path, prompt: str = None, model: str = "llama3.2-vision") -> str:
    """
    Sends an image page to a local Ollama instance with a Vision model to extract and translate text.
    """
    if prompt is None:
        prompt = (
            "You are an expert translator specializing in Japanese artbooks, manga, and video game developer commentary. "
            "Examine this page carefully. Transcribe any Japanese text (titles, lore, character bios, captions, dialogue) "
            "and provide an accurate, natural English translation. "
            "Format your response cleanly with headings for each section or text block."
        )

    try:
        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [encoded_image],
            "stream": False
        }
        
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "").strip()
    except Exception as e:
        return f"[Ollama Error: Could not reach Ollama at localhost:11434. Make sure Ollama is running with {model}. Error: {e}]"


def ocr_detect_boxes(image_path: Path, src_lang: str = 'ja') -> list[dict]:
    """
    Detects text and bounding boxes in an image.
    Returns list of dicts: [{'box': (x0, y0, x1, y1), 'text': str, 'confidence': float}]
    """
    image_path = Path(image_path)
    boxes = []

    # 1. Try EasyOCR if available
    global _easyocr_reader
    if HAS_EASYOCR:
        try:
            if _easyocr_reader is None:
                _easyocr_reader = easyocr.Reader(['ja', 'en'], gpu=False)
            results = _easyocr_reader.readtext(str(image_path))
            for bbox, text, conf in results:
                if not text.strip() or conf < 0.2:
                    continue
                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
                boxes.append({
                    'box': (x0, y0, x1, y1),
                    'text': text.strip(),
                    'confidence': float(conf)
                })
            if boxes:
                return boxes
        except Exception:
            pass

    # 2. Try Pytesseract if available
    if HAS_PYTESSERACT:
        try:
            img = Image.open(image_path)
            tess_lang = 'jpn' if src_lang == 'ja' else 'eng'
            data = pytesseract.image_to_data(img, lang=tess_lang, output_type=pytesseract.Output.DICT)
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = int(data['conf'][i])
                if not text or conf < 30:
                    continue
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                if w < 10 or h < 10:
                    continue
                boxes.append({
                    'box': (x, y, x + w, y + h),
                    'text': text,
                    'confidence': conf / 100.0
                })
            if boxes:
                return boxes
        except Exception:
            pass

    return boxes


def sample_background_color(img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    """
    Samples background color along the border of the bounding box.
    Returns RGB tuple.
    """
    x0, y0, x1, y1 = box
    w, h = img.size
    margin = 3
    bx0, by0 = max(0, x0 - margin), max(0, y0 - margin)
    bx1, by1 = min(w - 1, x1 + margin), min(h - 1, y1 + margin)

    pixels = []
    # Sample top and bottom perimeter
    for x in range(bx0, bx1, max(1, (bx1 - bx0) // 10)):
        pixels.append(img.getpixel((x, by0))[:3])
        pixels.append(img.getpixel((x, by1))[:3])
    # Sample left and right perimeter
    for y in range(by0, by1, max(1, (by1 - by0) // 10)):
        pixels.append(img.getpixel((bx0, y))[:3])
        pixels.append(img.getpixel((bx1, y))[:3])

    if not pixels:
        return (255, 255, 255)

    avg_r = sum(p[0] for p in pixels) // len(pixels)
    avg_g = sum(p[1] for p in pixels) // len(pixels)
    avg_b = sum(p[2] for p in pixels) // len(pixels)

    # Standard speech bubbles in manga / artbooks are almost pure white or dark
    lum = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b
    if lum > 200:
        return (255, 255, 255)
    if lum < 50:
        return (0, 0, 0)
    return (avg_r, avg_g, avg_b)


def fit_and_draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    bg_color: tuple[int, int, int]
):
    """
    Fits and renders English translated text inside the bounding box.
    Automatically handles text wrapping, font size scaling, and contrasting colors.
    """
    x0, y0, x1, y1 = box
    bw = max(10, x1 - x0)
    bh = max(10, y1 - y0)
    pad = 3
    avail_w = max(5, bw - pad * 2)
    avail_h = max(5, bh - pad * 2)

    # Determine text color for contrast
    lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
    text_color = (0, 0, 0) if lum > 128 else (255, 255, 255)

    # Try descending font sizes
    best_font = None
    best_lines = []
    best_line_height = 0

    max_font_size = min(36, max(9, bh - 4))
    for fsize in range(max_font_size, 7, -2):
        font = get_available_font(size=fsize, bold=True)
        # Estimate characters per line
        sample_w = font.getbbox("M")[2] - font.getbbox("M")[0]
        c_per_line = max(1, int(avail_w / max(1, sample_w * 0.9)))
        
        words = text.split()
        lines = []
        cur_line = []
        for word in words:
            test_line = " ".join(cur_line + [word])
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
            if w <= avail_w:
                cur_line.append(word)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                    cur_line = [word]
                else:
                    lines.append(word)
                    cur_line = []
        if cur_line:
            lines.append(" ".join(cur_line))

        # Check total height
        line_bbox = font.getbbox("Ay")
        line_h = (line_bbox[3] - line_bbox[1]) + 2
        total_h = len(lines) * line_h

        if total_h <= avail_h and len(lines) > 0:
            best_font = font
            best_lines = lines
            best_line_height = line_h
            break

    if not best_font or not best_lines:
        best_font = get_available_font(size=8, bold=True)
        best_lines = [text[:25]]
        best_line_height = 10

    # Draw centered text
    total_text_h = len(best_lines) * best_line_height
    start_y = y0 + pad + max(0, (avail_h - total_text_h) // 2)

    for i, line in enumerate(best_lines):
        line_bbox = best_font.getbbox(line)
        lw = line_bbox[2] - line_bbox[0]
        start_x = x0 + pad + max(0, (avail_w - lw) // 2)
        draw.text((start_x, start_y + i * best_line_height), line, fill=text_color, font=best_font)


def replace_text_in_image(
    image: Image.Image,
    translated_blocks: list[dict]
) -> Image.Image:
    """
    Erases Japanese text in bounding boxes and typesets English translations in-place.
    """
    img_out = image.convert("RGB")
    draw = ImageDraw.Draw(img_out)

    for block in translated_blocks:
        box = block.get('box')
        eng_text = block.get('translated_text', '').strip()
        if not box or not eng_text:
            continue

        # Inpaint / clean the box
        bg = sample_background_color(img_out, box)
        draw.rectangle(box, fill=bg)

        # Typeset English text
        fit_and_draw_text(draw, eng_text, box, bg)

    return img_out


def translate_page(
    image_path: Path,
    src_lang: str = 'ja',
    dest_lang: str = 'en',
    engine: str = 'auto',
    ollama_model: str = 'llama3.2-vision'
) -> dict:
    """
    Translates a single image page for companion guides or inspection.
    """
    image_path = Path(image_path)
    result = {
        'page_name': image_path.name,
        'original_text': '',
        'translated_text': '',
        'engine_used': engine,
        'blocks': []
    }

    # 1. Ollama Vision Mode
    if engine == 'ollama':
        res = ollama_translate_image(image_path, model=ollama_model)
        result['translated_text'] = res
        return result

    # 2. Extract bounding boxes and text via OCR
    boxes = ocr_detect_boxes(image_path, src_lang=src_lang)
    if boxes:
        translated_blocks = []
        orig_pieces = []
        trans_pieces = []
        for b in boxes:
            txt = b['text']
            trans = free_translate_text(txt, src=src_lang, dest=dest_lang)
            orig_pieces.append(txt)
            trans_pieces.append(trans)
            translated_blocks.append({
                'box': b['box'],
                'original_text': txt,
                'translated_text': trans
            })
        result['original_text'] = "\n".join(orig_pieces)
        result['translated_text'] = "\n".join(trans_pieces)
        result['blocks'] = translated_blocks
        result['engine_used'] = 'OCR + GoogleTranslate'
        return result

    # 3. Fallback: Check Ollama
    ollama_res = ollama_translate_image(image_path, model=ollama_model)
    if not ollama_res.startswith("[Ollama Error"):
        result['translated_text'] = ollama_res
        result['engine_used'] = f"Ollama ({ollama_model})"
        return result

    result['translated_text'] = (
        "No OCR engine active. For automatic translation:\n"
        "1. Install EasyOCR: 'pip install easyocr', OR\n"
        "2. Start Ollama Vision: 'ollama run llama3.2-vision'"
    )
    result['engine_used'] = 'None'
    return result


def translate_and_typeset_image(
    image_path: Path,
    src_lang: str = 'ja',
    dest_lang: str = 'en',
    engine: str = 'auto'
) -> tuple[Image.Image, dict]:
    """
    Loads an image, translates detected text boxes, and returns the modified scanlated Image.
    """
    image_path = Path(image_path)
    img = Image.open(image_path)
    trans_data = translate_page(image_path, src_lang=src_lang, dest_lang=dest_lang, engine=engine)

    blocks = trans_data.get('blocks', [])
    if blocks:
        scanlated_img = replace_text_in_image(img, blocks)
        return scanlated_img, trans_data

    # If no bounding boxes detected, return original image unchanged
    return img.convert("RGB"), trans_data


def save_translation_guide(
    folder_name: str,
    page_results: list[dict],
    output_dir: Path
) -> tuple[Path, Path]:
    """
    Saves a formatted Markdown (.md) and plain text (.txt) translation guide companion book.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{folder_name} (English Translation Guide).md"
    txt_path = output_dir / f"{folder_name} (English Translation Guide).txt"

    # Markdown format
    md_lines = [
        f"# {folder_name}",
        "## English Translation Companion Guide",
        f"*Total Pages Processed: {len(page_results)}*",
        "\n---\n"
    ]

    # Plain text format
    txt_lines = [
        "=" * 60,
        f"  {folder_name} - English Translation Guide",
        "=" * 60,
        "\n"
    ]

    for idx, item in enumerate(page_results, 1):
        pname = item.get('page_name', f"Page {idx}")
        trans = item.get('translated_text', '').strip()
        orig = item.get('original_text', '').strip()

        # Markdown
        md_lines.append(f"### Page {idx} (`{pname}`)")
        if orig:
            md_lines.append(f"> **Original Japanese:**\n> {orig.replace(chr(10), chr(10) + '> ')}\n")
        md_lines.append(f"**English Translation:**\n\n{trans}\n")
        md_lines.append("\n---\n")

        # TXT
        txt_lines.append(f"--- [Page {idx}: {pname}] ---")
        if orig:
            txt_lines.append(f"[Japanese]:\n{orig}\n")
        txt_lines.append(f"[English Translation]:\n{trans}\n\n")

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_lines))

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(txt_lines))

    return md_path, txt_path
