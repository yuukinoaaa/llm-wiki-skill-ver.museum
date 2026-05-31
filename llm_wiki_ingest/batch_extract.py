from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .extractors import SUPPORTED_EXTENSIONS, calculate_sha256, extract_document, write_extracted_json
from .slug import slugify


MANIFEST_NAME = "source-manifest.json"
INPUT_MANIFEST_NAME = "input-manifest.json"


def extract_directory(input_dir: str | Path, out_dir: str | Path) -> dict[str, int]:
    source_root = Path(input_dir)
    output_root = Path(out_dir)
    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(f"Input directory not found: {source_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    blocks_dir = output_root / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)
    (output_root / "plans").mkdir(parents=True, exist_ok=True)

    input_manifest = _read_input_manifest(source_root / INPUT_MANIFEST_NAME)
    source_ids: dict[str, int] = {}
    sources: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    extracted = 0
    reused = 0

    for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        if source_path.name == INPUT_MANIFEST_NAME:
            continue
        rel_path = source_path.relative_to(source_root).as_posix()
        override = _document_override(input_manifest, rel_path, source_path.name)

        if source_path.name.startswith("."):
            skipped.append({"path": rel_path, "reason": "hidden"})
            continue
        if override.get("include") is False:
            skipped.append({"path": rel_path, "reason": "excluded_by_manifest"})
            continue
        if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped.append({"path": rel_path, "reason": "unsupported_type"})
            continue

        source_id = _source_id(source_path.stem, source_ids)
        blocks_path = blocks_dir / f"{source_id}.blocks.json"
        digest = calculate_sha256(source_path)
        if _existing_blocks_hash(blocks_path) == digest:
            reused += 1
        else:
            document = extract_document(source_path)
            write_extracted_json(document, blocks_path)
            extracted += 1

        sources.append(
            {
                "source_id": source_id,
                "path": rel_path,
                "name": source_path.name,
                "type": source_path.suffix.lower().lstrip("."),
                "sha256": digest,
                "blocks_path": blocks_path.relative_to(output_root).as_posix(),
                "document_type": str(override.get("document_type") or _infer_document_type(source_path)),
                "priority": override.get("priority"),
            }
        )

    manifest = {
        "schema_version": "llm-wiki-source-manifest.v1",
        "input_dir": str(source_root),
        "sources": sources,
        "skipped": skipped,
    }
    (output_root / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"extracted": extracted, "reused": reused, "skipped": len(skipped), "sources": len(sources)}


def _read_input_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{INPUT_MANIFEST_NAME} must be a JSON object")
    documents = data.get("documents", {})
    if documents and not isinstance(documents, dict):
        raise ValueError(f"{INPUT_MANIFEST_NAME} field documents must be an object")
    return data


def _document_override(manifest: dict[str, Any], rel_path: str, name: str) -> dict[str, Any]:
    documents = manifest.get("documents", {})
    if not isinstance(documents, dict):
        return {}
    value = documents.get(rel_path, documents.get(name, {}))
    return value if isinstance(value, dict) else {}


def _source_id(stem: str, seen: dict[str, int]) -> str:
    base = slugify(stem, fallback_prefix="source")
    count = seen.get(base, 0) + 1
    seen[base] = count
    return base if count == 1 else f"{base}-{count}"


def _existing_blocks_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    source = data.get("source", {})
    if not isinstance(source, dict):
        return None
    value = source.get("sha256")
    return str(value) if value else None


def _infer_document_type(path: Path) -> str:
    name = path.stem.lower()
    if "讲解词" in path.stem or "script" in name:
        return "script"
    return "research"
