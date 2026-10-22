import os
import re
from typing import List, Dict, Tuple
from pypdf import PdfReader
from pypdf.errors import PdfReadError, FileNotDecryptedError

def clean_text(text: str) -> str:
    """
    Cleans and normalizes extracted document text.
    - Replaces null bytes and non-printable control characters.
    - Standardizes CRLF / CR to standard LF newlines.
    - Condenses multiple consecutive spaces/tabs into a single space.
    - Condenses more than two consecutive newlines into double newlines (paragraphs).
    """
    if not text:
        return ""

    # Remove null bytes and non-printable characters (except standard newlines/tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Standardize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Replace weird unicode spaces with standard space
    text = re.sub(r'[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]', ' ', text)

    # Condense inline whitespaces (spaces, tabs)
    text = re.sub(r'[ \t]+', ' ', text)

    # Condense 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def extract_from_pdf(file_path: str) -> Tuple[List[Dict[str, any]], int]:
    """
    Extracts text page-by-page from a PDF file using pypdf.
    Streams page-by-page to minimize memory usage for files up to 50MB.
    Handles corrupted, encrypted, and unscannable files with clear errors.
    Returns:
        (pages, total_pages) where pages is a list of dicts:
        [{'page_number': int, 'text': str}]
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise ValueError("The uploaded PDF file is empty (0 bytes).")

    try:
        reader = PdfReader(file_path)
    except (PdfReadError, Exception) as e:
        raise ValueError(f"The uploaded PDF file is corrupted or not a valid PDF: {str(e)}")

    if getattr(reader, 'is_encrypted', False):
        try:
            # Try decrypting with empty password
            decrypted = reader.decrypt('')
            if not decrypted:
                raise ValueError("The uploaded PDF is password-protected or encrypted. Please remove password protection before uploading.")
        except Exception:
            raise ValueError("The uploaded PDF is password-protected or encrypted. Please remove password protection before uploading.")

    try:
        total_pages = len(reader.pages)
    except Exception as e:
        raise ValueError(f"Failed to read PDF page structure (file may be damaged): {str(e)}")

    if total_pages == 0:
        raise ValueError("The uploaded PDF contains 0 pages.")

    pages_data = []

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""

        cleaned = clean_text(raw_text)
        if cleaned:
            pages_data.append({
                'page_number': page_num,
                'text': cleaned
            })

    if not pages_data:
        raise ValueError("Could not extract any readable text from this PDF. It may be scanned or image-only without an OCR text layer.")

    return pages_data, total_pages


def extract_from_txt(file_path: str) -> Tuple[List[Dict[str, any]], int]:
    """
    Extracts text from a plain TXT file with multi-encoding fallback.
    Returns:
        (pages, 1) where pages is a single-element list with page_number=1.
    """
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    raw_content = None

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                raw_content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if raw_content is None:
        raise ValueError("Failed to decode the TXT file with standard UTF-8/Latin-1 encodings.")

    cleaned = clean_text(raw_content)
    if not cleaned:
        raise ValueError("The uploaded TXT file is empty or contains only whitespace.")

    return [{'page_number': 1, 'text': cleaned}], 1


def extract_and_clean_document(file_path: str, file_type: str) -> Tuple[List[Dict[str, any]], int]:
    """
    High-level entry point to extract and clean text based on file type.
    Supported types: 'pdf', 'txt'.
    """
    ext = file_type.lower().lstrip('.')
    if ext == 'pdf':
        return extract_from_pdf(file_path)
    elif ext == 'txt':
        return extract_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported document format: {file_type}")
