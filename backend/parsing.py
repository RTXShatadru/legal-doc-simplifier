"""Extract native text or OCR scans; never mistake scanner watermarks for content."""
import re
import time
import unicodedata
import pymupdf as fitz
import config
import ocr

HEADING = re.compile(r'^(?:(?:article|section|clause)\s+[\w.]+|\d+(?:\.\d+)*[.)]?\s+|[०-९]+[.)।]?\s+|\([a-z0-9]+\)\s+)', re.I)
MAX_CHUNK = 1800
WATERMARK = re.compile(r'^\s*(?:scanned (?:by|with) camscanner|camscanner|scan(?:ned)? with adobe scan|adobe scan)\s*$', re.I)


def clean_text(text):
    text = re.sub(r'scanned\s+(?:by|with)\s+camscanner', '', text, flags=re.I)
    return '\n'.join(line.rstrip() for line in unicodedata.normalize('NFC', text).replace('\x00', '').splitlines()
                     if not WATERMARK.match(line)).strip()


def image_coverage(page):
    area = max(page.rect.get_area(), 1)
    return min(1, sum(rect.get_area() for image in page.get_images() for rect in page.get_image_rects(image[0]))/area)


def needs_ocr(page, text):
    letters = sum(c.isalpha() for c in text)
    # A full-page scan with a tiny hidden text layer (often a scanner footer).
    return image_coverage(page) > .35 and letters < 120


def parse_pdf(content: bytes):
    text, chunks, pages, _ = parse_pdf_detailed(content)
    return text, chunks, pages


def parse_pdf_detailed(content: bytes):
    if not content.startswith(b'%PDF-'):
        raise ValueError('This file is not a valid PDF.')
    try:
        pdf = fitz.open(stream=content, filetype='pdf')
    except Exception:
        raise ValueError('This PDF is damaged or unreadable.') from None
    gate = False
    try:
        if pdf.needs_pass:
            raise ValueError('Unlock this password-protected PDF before uploading.')
        if not 1 <= len(pdf) <= config.MAX_PAGES:
            raise ValueError(f'Please use a PDF with 1–{config.MAX_PAGES} pages.')
        texts = [clean_text(page.get_text('text', sort=True)) for page in pdf]
        scanned = [i for i, page in enumerate(pdf) if needs_ocr(page, texts[i])]
        if len(scanned) > ocr.MAX_OCR_PAGES:
            raise ValueError('Use at most 12 scanned pages per upload. Split this PDF and retry.')
        if scanned:
            gate = ocr.GATE.acquire(blocking=False)
            if not gate:
                raise ValueError('Another scan is being read. Please try again in a minute.')
        deadline = time.monotonic() + ocr.MAX_OCR_SECONDS
        details, unreadable = [], []
        for i in range(len(pdf)):
            confidence = None
            if i in scanned:
                value, confidence = ocr.read_page(pdf[i], deadline)
                texts[i] = clean_text(value)
            if sum(c.isalpha() for c in texts[i]) < 8:
                unreadable.append(i+1)
                texts[i] = ''
            details.append({'page':i+1, 'method':'ocr' if i in scanned else 'native',
                            'confidence':confidence, 'characters':len(texts[i])})
        full_text = '\n\n'.join(texts)
        if len(full_text) > config.MAX_TEXT_CHARS:
            raise ValueError('Too much text. Split this document into smaller PDFs.')
        if len(full_text.strip()) < 50:
            raise ValueError('No readable text found. Use a clearer scan.')
        chunks = []
        for page_number, page_text in enumerate(texts, 1):
            current, heading = [], None
            def flush():
                joined = '\n'.join(current).strip()
                while joined:
                    cut = len(joined)
                    if cut > MAX_CHUNK:
                        cut = max(joined.rfind('\n', 0, MAX_CHUNK), joined.rfind(' ', 0, MAX_CHUNK))
                        if cut < MAX_CHUNK // 2:
                            cut = MAX_CHUNK
                    piece, joined = joined[:cut].strip(), joined[cut:].strip()
                    if piece:
                        chunks.append({'clause_index':len(chunks), 'heading':heading, 'text':piece, 'page':page_number})
            for line in page_text.splitlines():
                if HEADING.match(line.strip()) or (not line.strip() and len('\n'.join(current)) > 300):
                    flush()
                    current = []
                    if HEADING.match(line.strip()):
                        heading = line.strip()[:120]
                current.append(line)
            flush()
        if len(chunks) > 256:
            raise ValueError('Too many sections. Split this PDF into smaller documents.')
        hindi = len(re.findall(r'[\u0900-\u097f]', full_text))
        english = len(re.findall(r'[a-zA-Z]', full_text))
        language = 'Hindi' if hindi > english else 'Hindi and English' if hindi > 30 else 'English / other'
        warnings = []
        if unreadable:
            warnings.append('Incomplete extraction: no readable text on pages ' + ', '.join(map(str, unreadable)) + '. Images, maps, signatures and handwriting require review in the original PDF.')
        if scanned:
            warnings.append('Text was read from page images. Names, dates, amounts, stamps and handwriting may be misread. Verify them against the original PDF.')
        low = [p['page'] for p in details if p['confidence'] is not None and p['confidence'] < 65]
        if low:
            warnings.append('Lower-confidence OCR on pages ' + ', '.join(map(str, low)) + '. Do not rely on these details without checking the scan.')
        return full_text, chunks, len(pdf), {'language':language, 'ocr_pages':[i+1 for i in scanned],
            'pages':details, 'unreadable_pages':unreadable, 'warnings':warnings, 'version':2}
    finally:
        pdf.close()
        if gate:
            ocr.GATE.release()
