from __future__ import annotations

from io import BytesIO

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader


def _clean(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\x00", " ").splitlines()]
    out = []
    blank = False
    for line in lines:
        if line.strip():
            out.append(line.strip())
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def extract_document(data: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        reader = PdfReader(BytesIO(data))
        return _clean("\n\n".join(page.extract_text() or "" for page in reader.pages))
    if ext == "docx":
        doc = Document(BytesIO(data))
        chunks = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                chunks.append(" | ".join(cell.text.strip() for cell in row.cells))
        return _clean("\n".join(chunks))
    if ext in {"xlsx", "xlsm"}:
        wb = load_workbook(BytesIO(data), data_only=True, read_only=True)
        chunks = []
        for ws in wb.worksheets:
            chunks.append(f"[SHEET: {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                values = ["" if v is None else str(v) for v in row]
                line = " | ".join(values).strip()
                if line:
                    chunks.append(line)
        return _clean("\n".join(chunks))
    if ext in {"txt", "md"}:
        return _clean(data.decode("utf-8", errors="replace"))
    raise ValueError(f"Unsupported file type: .{ext}")
