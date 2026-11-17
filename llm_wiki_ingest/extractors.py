from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

from .models import ExtractedDocument, SourceInfo, TextBlock


SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".md", ".txt"}


def extract_document(path: str | Path) -> ExtractedDocument:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported file type {extension!r}. Supported: {supported}")

    if extension == ".docx":
        texts = _extract_docx(source_path)
    elif extension == ".pdf":
        texts = _extract_pdf(source_path)
    else:
        texts = _extract_text(source_path)

    blocks = [
        TextBlock(id=f"b{index:04d}", text=text)
        for index, text in enumerate(_clean_blocks(texts), start=1)
    ]
    return ExtractedDocument(
        schema_version="llm-wiki-ingest.blocks.v1",
        source=SourceInfo(
            path=str(source_path),
            name=source_path.name,
            type=extension.lstrip("."),
            sha256=_sha256(source_path),
        ),
        blocks=blocks,
    )


def write_extracted_json(document: ExtractedDocument, out_path: str | Path) -> None:
    Path(out_path).write_text(
        json.dumps(document.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def calculate_sha256(path: str | Path) -> str:
    return _sha256(Path(path))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_text(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    return re.split(r"\n\s*\n", text)


def _extract_docx(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag == "tab":
                parts.append("\t")
            elif tag in {"br", "cr"}:
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _extract_pdf(path: Path) -> list[str]:
    texts = _extract_pdf_with_pypdf(path)
    if texts:
        return texts
    return _extract_pdf_fallback(path)


def _extract_pdf_with_pypdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return []
    try:
        reader = PdfReader(str(path))
        return [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return []


def _extract_pdf_fallback(path: Path) -> list[str]:
    raw = path.read_bytes()
    chunks: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n?(.*?)\r?\n?endstream", raw, re.S):
        stream = match.group(1).strip(b"\r\n")
        before = raw[max(0, match.start() - 200) : match.start()]
        if b"FlateDecode" in before:
            try:
                stream = zlib.decompress(stream)
            except zlib.error:
                pass
        chunks.append(stream)
    if not chunks:
        chunks = [raw]

    strings: list[str] = []
    for chunk in chunks:
        content = chunk.decode("latin-1", errors="ignore")
        strings.extend(_pdf_literal_strings(content))
    return strings


def _pdf_literal_strings(content: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(r"\((?:\\.|[^\\)])*\)\s*Tj", content):
        values.append(_decode_pdf_string(match.group(0).rsplit(")", 1)[0][1:]))
    for array_match in re.finditer(r"\[(.*?)\]\s*TJ", content, re.S):
        for item in re.finditer(r"\((?:\\.|[^\\)])*\)", array_match.group(1)):
            values.append(_decode_pdf_string(item.group(0)[1:-1]))
    return values


def _decode_pdf_string(value: str) -> str:
    value = value.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    value = value.replace(r"\n", "\n").replace(r"\r", "\r").replace(r"\t", "\t")
    return html.unescape(value)


def _clean_blocks(texts: list[str]) -> list[str]:
    cleaned: list[str] = []
    for text in texts:
        normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        if normalized:
            cleaned.append(normalized)
    return cleaned
