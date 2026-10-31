"""Bounded PDF, DOCX and image extraction using the shared OCR pipeline."""
import io
import os
import zipfile
from pathlib import Path
from xml.etree import ElementTree
import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError
import config
import parsing


def parse(content, filename, domain, workflow):
    ext = Path(filename).suffix.lower()
    reader=None
    if domain=='medical' and os.getenv('MEDICAL_IMAGE_READER','ocr')=='vision':
        from medical_vision import read_page
        reader=read_page
    def read_pdf(data):
        result=parsing.parse_pdf_detailed(data,page_reader=reader)
        if reader and result[3].get('ocr_pages'):
            result[3]['reader']='groq-vision'
            result[3]['warnings'].append('Page images were transcribed by Groq vision. Uncertain words, medicine names and doses must be checked against the original.')
        return result
    if ext == '.pdf':
        return read_pdf(content)
    if ext == '.docx' and domain == 'hr':
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if sum(i.file_size for i in z.infolist()) > 20_000_000 or len(z.infolist()) > 2000:
                    raise ValueError('This DOCX expands beyond the supported size.')
                raw = z.read('word/document.xml')
                if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                    raise ValueError('Unsupported XML in DOCX.')
                root = ElementTree.fromstring(raw)
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            paragraphs = [''.join(t.text or '' for t in p.iter(ns+'t')) for p in root.iter(ns+'p')]
            return from_text('\n'.join(paragraphs), 'DOCX')
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ValueError('This DOCX is damaged or does not contain readable document text.') from exc
    if ext in ('.png','.jpg','.jpeg','.webp') and domain == 'medical':
        try:
            with Image.open(io.BytesIO(content)) as original:
                if original.width * original.height > 25_000_000:
                    raise ValueError('Choose an image with fewer than 25 million pixels.')
                image = ImageOps.exif_transpose(original).convert('RGB')
                image.thumbnail((3000,3000))
                buffer = io.BytesIO(); image.save(buffer, format='PNG')
            with pymupdf.open() as pdf:
                page = pdf.new_page(width=image.width, height=image.height)
                page.insert_image(page.rect, stream=buffer.getvalue())
                return read_pdf(pdf.tobytes())
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
            raise ValueError('This image could not be read. Upload a clear JPG, PNG or WEBP.') from exc
    raise ValueError('Use PDF for all workspaces, DOCX for HR, or JPG/PNG/WEBP for Medical.')


def from_text(text, kind='text'):
    text = parsing.clean_text(text)
    if len(text) < 20 or len(text) > config.MAX_TEXT_CHARS:
        raise ValueError('Use a readable document with 20â€“120,000 characters.')
    # DOCX does not have stable PDF-style page boundaries. Page 1 means extracted body.
    chunks = []
    for start in range(0, len(text), 1600):
        chunks.append({'clause_index':len(chunks), 'page':1, 'heading':'Extracted body', 'text':text[start:start+1600]})
    return text, chunks, 1, {'language':'Unknown','ocr_pages':[], 'warnings':[f'{kind} uses extracted-body references; page layout is not preserved.'], 'version':3}
