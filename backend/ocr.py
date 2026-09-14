"""Local Hindi/English OCR. PDF content is never sent to an OCR service."""
import os
import shutil
import time
from pathlib import Path
from threading import BoundedSemaphore
import csv
import io
import subprocess
import tempfile
from PIL import Image, ImageOps
import config
os.environ.setdefault('OMP_THREAD_LIMIT', '2')

GATE = BoundedSemaphore(1)
MAX_OCR_PAGES = 12
MAX_OCR_SECONDS = 90


def executable():
    configured = os.getenv('TESSERACT_CMD', '')
    candidates = [configured, shutil.which('tesseract'),
        str(config.ROOT / '.runtime' / 'tesseract' / 'tesseract.exe'),
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        str(Path(os.getenv('LOCALAPPDATA', '')) / 'Programs' / 'Tesseract-OCR' / 'tesseract.exe')]
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def available_languages():
    binary = executable()
    if not binary:
        return []
    try:
        result = run([binary, '--list-langs'], timeout=10)
        return [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
    except Exception:
        return []


def run(args, timeout):
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def read_page(page, deadline):
    languages = available_languages()
    requested = os.getenv('OCR_LANGUAGES', 'hin+eng').split('+')
    if any(language not in languages for language in requested):
        raise ValueError('This PDF needs OCR. Install Tesseract with Hindi and English language data; see docs/OCR.md.')
    seconds = deadline - time.monotonic()
    if seconds < 1:
        raise ValueError('OCR took too long. Split this scan into a smaller PDF and retry.')
    # Bound even unusually large pages to ~9 million pixels.
    scale = min(3.5, 3000 / max(page.rect.width, page.rect.height))
    import pymupdf
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY, alpha=False)
    image = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    image = ImageOps.autocontrast(image, cutoff=1)
    try:
        with tempfile.TemporaryDirectory(prefix='simplydoc-ocr-') as folder:
            image_path = Path(folder) / 'page.png'
            image.save(image_path)
            result = run([executable(), str(image_path), 'stdout', '-l', '+'.join(requested),
                          '--oem', '1', '--psm', '6', 'tsv'], max(1, min(40, seconds)))
        data = list(csv.DictReader(io.StringIO(result.stdout), delimiter='\t', quoting=csv.QUOTE_NONE))
    except subprocess.TimeoutExpired:
        raise ValueError('OCR timed out. Split the scan into a smaller PDF and retry.') from None
    except (subprocess.CalledProcessError, OSError):
        raise ValueError('OCR could not read this page. Try a clearer scan.') from None
    lines, current, words, scores = [], None, [], []
    for row in data:
        word = (row.get('text') or '').strip()
        if not word:
            continue
        key = (row['block_num'], row['par_num'], row['line_num'])
        if key != current:
            if words:
                lines.append(' '.join(words))
            if current is not None and key[:2] != current[:2]:
                lines.append('')
            current, words = key, []
        words.append(word)
        confidence = float(row['conf'])
        if confidence >= 0 and len(word) > 1:
            scores.append(confidence)
    if words:
        lines.append(' '.join(words))
    return '\n'.join(lines), round(sum(scores)/len(scores), 1) if scores else 0
