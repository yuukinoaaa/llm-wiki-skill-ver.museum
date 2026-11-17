from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .materialize import _normalize_aliases, _normalize_page_path, _normalize_page_type
from .web_enrichment import ALLOWED_WEB_SOURCE_TYPES, WEB_SOURCE_REQUIRED_FIELDS


DEFAULT_WEB_ENRICHMENT = {
    "enabled": True,
    "source_policy": "authoritative",
    "density": "medium",
    "query_policy": "entity_names_only",
}


def merge_plans_from_dir(plan_dir: str | Path, out_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(plan_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Plan directory not found: {root}")

    plans = [_read_plan(path) for path in sorted(root.glob("*.json")) if _is_plan_file(path)]
    if not plans:
        raise ValueError(f"No plan JSON files found in {root}")

    merged_pages: dict[str, dict[str, Any]] = {}
    source_records: list[dict[str, str]] = []
    hash_parts: list[str] = []

    for plan in plans:
        source_id = str(plan["source_id"])
        source_hash = str(plan["source_hash"])
        topic = str(plan["topic"])
        source_records.append({"source_id": source_id, "source_hash": source_hash, "topic": topic})
        hash_parts.append(f"{source_id}:{source_hash}")
        for raw_page in plan.get("pages", []):
            page = _normalize_page(raw_page, source_id)
            existing = merged_pages.get(page["path"])
            if existing is None:
                merged_pages[page["path"]] = page
            else:
                _merge_page(existing, page, source_id)

    pages = [merged_pages[path] for path in sorted(merged_pages)]
    _validate_link_targets(pages)
    merged = {
        "source_id": "input-batch",
        "source_hash": hashlib.sha256("\n".join(sorted(hash_parts)).encode("utf-8")).hexdigest(),
        "topic": "统一 LLM Wiki",
        "web_enrichment": dict(DEFAULT_WEB_ENRICHMENT),
        "sources": source_records,
        "pages": pages,
    }
    if out_path:
        Path(out_path).write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged


def _is_plan_file(path: Path) -> bool:
    return path.name not in {"source-manifest.json", "input-manifest.json"}


def _read_plan(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Plan must be an object: {path}")
    for field in ["source_id", "source_hash", "topic", "pages"]:
        if field not in data:
            raise ValueError(f"Missing plan field in {path}: {field}")
    if not isinstance(data["pages"], list):
        raise ValueError(f"Plan field pages must be a list: {path}")
    return data


def _normalize_page(raw_page: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    page = dict(raw_page)
    for field in ["type", "path", "title", "body_md"]:
        if field not in page:
            raise ValueError(f"Missing page field: {field}")
    page["type"] = _normalize_page_type(page["type"])
    page["path"] = _normalize_page_path(str(page["path"]))
    page["title"] = str(page["title"])
    page["body_md"] = str(page["body_md"]).strip()
    page["source_block_ids"] = _unique_strings(page.get("source_block_ids", []))
    page["source_refs"] = _normalize_source_refs(page.get("source_refs"), source_id, page["source_block_ids"], page["path"])
    page["outgoing_links"] = _unique_strings(_normalize_page_path(str(link)) for link in page.get("outgoing_links", []))
    page["aliases"] = _normalize_aliases(page.get("aliases", []), page["path"])
    page["web_enrichments"] = _normalize_web_enrichments(page.get("web_enrichments", []), page["path"])
    return page


def _normalize_source_refs(value: object, source_id: str, block_ids: list[str], page_path: str) -> list[dict[str, Any]]:
    if value in (None, []):
        if not block_ids:
            return []
        return [{"source_id": source_id, "block_ids": block_ids, "quote_purpose": "source"}]
    if not isinstance(value, list):
        raise ValueError(f"source_refs must be a list in {page_path}")
    refs: list[dict[str, Any]] = []
    for index, raw_ref in enumerate(value):
        if not isinstance(raw_ref, Mapping):
            raise ValueError(f"source_refs[{index}] must be an object in {page_path}")
        if "source_id" not in raw_ref or not str(raw_ref["source_id"]).strip():
            raise ValueError(f"source_refs[{index}] missing source_id in {page_path}")
        block_value = raw_ref.get("block_ids", [])
        if not isinstance(block_value, list) or not block_value:
            raise ValueError(f"source_refs[{index}] block_ids must be a non-empty list in {page_path}")
        refs.append(
            {
                "source_id": str(raw_ref["source_id"]).strip(),
                "block_ids": _unique_strings(block_value),
                "quote_purpose": str(raw_ref.get("quote_purpose", "source")).strip() or "source",
            }
        )
    return _dedupe_source_refs(refs)


def _normalize_web_enrichments(value: object, page_path: str) -> list[dict[str, Any]]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise ValueError(f"web_enrichments must be a list in {page_path}")
    enrichments: list[dict[str, Any]] = []
    for index, raw_enrichment in enumerate(value):
        if not isinstance(raw_enrichment, Mapping):
            raise ValueError(f"web_enrichments[{index}] must be an object in {page_path}")
        for field in ["anchor_text", "content_md", "sources"]:
            if field not in raw_enrichment or not raw_enrichment[field]:
                raise ValueError(f"Missing web enrichment field in {page_path}: {field}")
        sources = _normalize_web_sources(raw_enrichment["sources"], page_path)
        enrichments.append(
            {
                "anchor_text": str(raw_enrichment["anchor_text"]).strip(),
                "content_md": str(raw_enrichment["content_md"]).strip(),
                "sources": sources,
            }
        )
    return enrichments


def _normalize_web_sources(value: object, page_path: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"web enrichment sources must be a non-empty list in {page_path}")
    sources: list[dict[str, str]] = []
    for index, raw_source in enumerate(value):
        if not isinstance(raw_source, Mapping):
            raise ValueError(f"web enrichment sources[{index}] must be an object in {page_path}")
        for field in WEB_SOURCE_REQUIRED_FIELDS:
            if field not in raw_source or not str(raw_source[field]).strip():
                raise ValueError(f"Missing web source field in {page_path}: {field}")
        source_type = str(raw_source["source_type"]).strip().lower()
        if source_type not in ALLOWED_WEB_SOURCE_TYPES:
            raise ValueError(f"Unsupported web source_type in {page_path}: {source_type}")
        sources.append({field: str(raw_source[field]).strip() for field in WEB_SOURCE_REQUIRED_FIELDS})
        sources[-1]["source_type"] = source_type
    return sources


def _merge_page(existing: dict[str, Any], incoming: dict[str, Any], source_id: str) -> None:
    if existing["type"] != incoming["type"] or existing["title"] != incoming["title"]:
        raise ValueError(f"Conflicting page definition for {existing['path']}")
    if incoming["body_md"] and incoming["body_md"] not in existing["body_md"]:
        existing["body_md"] = existing["body_md"].rstrip() + f"\n\n## From {source_id}\n\n" + incoming["body_md"].strip()
    existing["source_block_ids"] = _unique_strings([*existing.get("source_block_ids", []), *incoming.get("source_block_ids", [])])
    existing["source_refs"] = _dedupe_source_refs([*existing.get("source_refs", []), *incoming.get("source_refs", [])])
    existing["outgoing_links"] = _unique_strings([*existing.get("outgoing_links", []), *incoming.get("outgoing_links", [])])
    existing["aliases"] = _unique_strings([*existing.get("aliases", []), *incoming.get("aliases", [])])
    existing["web_enrichments"] = [*existing.get("web_enrichments", []), *deepcopy(incoming.get("web_enrichments", []))]


def _validate_link_targets(pages: list[dict[str, Any]]) -> None:
    known = {page["path"] for page in pages}
    missing: list[str] = []
    for page in pages:
        for link in page.get("outgoing_links", []):
            if link not in known:
                missing.append(f"{page['path']} -> {link}")
    if missing:
        details = "\n".join(f"- {item}" for item in sorted(missing))
        raise ValueError(f"Missing outgoing link targets:\n{details}")


def _dedupe_source_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for ref in refs:
        identity = (str(ref["source_id"]), tuple(ref["block_ids"]), str(ref.get("quote_purpose", "")))
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(dict(ref))
    return deduped


def _unique_strings(values: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    if values is None:
        return result
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
