"""normalize.py — two-layer canonical + one-way markdown.

DEFERRED until documents are harvested. Routes each file by type:
  born-digital PDF (~90%) -> fitz (fast path)
  scanned PDF (~10%)      -> docling / OCR (install tesseract or rapidocr first)
  HTML                    -> trafilatura
  XLSX/CSV/JSON           -> KEEP structured; markdown is a one-way *view* only
Reuses CivicAtlasMA/src/ocr_pdf.py (pypdf->docling->OCR auto-escalation).
"""
