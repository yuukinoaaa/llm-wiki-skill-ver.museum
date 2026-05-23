from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


VALID_PAGE_TYPES = {"source", "stop", "exhibit", "work", "person", "concept", "place", "index"}
PAGE_TYPE_ALIASES = {
    "sources": "source",
    "stops": "stop",
    "exhibits": "exhibit",
    "works": "work",
    "people": "person",
    "persons": "person",
    "concepts": "concept",
    "places": "place",
    "indexes": "index",
    "indices": "index",
}


def materialize_plan(plan: Mapping[str, Any], wiki_dir: str | Path, apply: bool = False) -> dict[str, int]:
    normalized = _normalize_plan(plan)
    wiki = Path(wiki_dir)
    content_dir = wiki / "content"
    manifest_path = wiki / "llm-wiki-manifest.json"
    existing_manifest = _read_manifest(manifest_path)

    pages = deepcopy(normalized["pages"])
    pages_by_path = {page["path"]: page for page in pages}
    title_by_target = {_target(page["path"]): page["title"] for page in pages}

    _append_route_links(pages)
    _append_outgoing_sections(pages, title_by_target)
    _append_backlinks(pages, pages_by_path)

    created = 0
    updated = 0
    for page in pages:
        destination = content_dir / page["path"]
        if destination.exists():
            updated += 1
        else:
            created += 1
        if apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(_render_page(page, normalized), encoding="utf-8")

    manifest = _merge_manifest(existing_manifest, normalized)
    if apply:
        wiki.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"created": created, "updated": updated}
    return {"would_create": created, "would_update": updated}


def _normalize_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    required = ["source_id", "source_hash", "topic", "pages"]
    for key in required:
        if key not in plan:
            raise ValueError(f"Missing plan field: {key}")
    pages = []
    for raw_page in plan["pages"]:
        page = dict(raw_page)
        for key in ["type", "path", "title", "body_md"]:
            if key not in page:
                raise ValueError(f"Missing page field: {key}")
        page["type"] = _normalize_page_type(page["type"])
        page["path"] = _normalize_page_path(page["path"])
        page["source_block_ids"] = list(page.get("source_block_ids", []))
        page["outgoing_links"] = [_normalize_page_path(link) for link in page.get("outgoing_links", [])]
        pages.append(page)
    return {
        "source_id": str(plan["source_id"]),
        "source_hash": str(plan["source_hash"]),
        "topic": str(plan["topic"]),
        "pages": pages,
    }


def _normalize_page_type(value: object) -> str:
    page_type = str(value).strip().lower()
    page_type = PAGE_TYPE_ALIASES.get(page_type, page_type)
    if page_type not in VALID_PAGE_TYPES:
        valid = ", ".join(sorted(VALID_PAGE_TYPES | set(PAGE_TYPE_ALIASES)))
        raise ValueError(f"Unsupported page type: {value}. Supported values: {valid}")
    return page_type


def _normalize_page_path(value: str) -> str:
    path = value.replace("\\", "/").strip().lstrip("/")
    if path.startswith("content/"):
        path = path.removeprefix("content/")
    if not path.endswith(".md"):
        path += ".md"
    parts = Path(path).parts
    if ".." in parts:
        raise ValueError(f"Page path cannot contain '..': {value}")
    return path


def _append_route_links(pages: list[dict[str, Any]]) -> None:
    stops = sorted((page for page in pages if page["type"] == "stop"), key=lambda page: page["path"])
    for index, page in enumerate(stops):
        lines = ["## 导航"]
        if index > 0:
            previous = stops[index - 1]
            lines.append(f"- 上一页：{_link(previous)}")
        if index < len(stops) - 1:
            next_page = stops[index + 1]
            lines.append(f"- 下一页：{_link(next_page)}")
        if len(lines) > 1:
            _append_section(page, "\n".join(lines))


def _append_outgoing_sections(pages: list[dict[str, Any]], title_by_target: dict[str, str]) -> None:
    for page in pages:
        links = []
        for raw_link in page["outgoing_links"]:
            target = _target(raw_link)
            if target == _target(page["path"]) or _contains_target(page["body_md"], target):
                continue
            title = title_by_target.get(target, target.rsplit("/", 1)[-1])
            links.append(f"- [[{target}|{title}]]")
        if links:
            _append_section(page, "## 相关页面\n" + "\n".join(links))


def _append_backlinks(pages: list[dict[str, Any]], pages_by_path: dict[str, dict[str, Any]]) -> None:
    pages_by_target = {_target(path): page for path, page in pages_by_path.items()}
    backlinks: dict[str, list[dict[str, Any]]] = {}
    for source in pages:
        for link in source["outgoing_links"]:
            target = _target(link)
            if target in pages_by_target and target != _target(source["path"]):
                backlinks.setdefault(target, []).append(source)

    for target, sources in backlinks.items():
        page = pages_by_target[target]
        lines = []
        for source in sources:
            if not _contains_target(page["body_md"], _target(source["path"])):
                lines.append(f"- {_link(source)}")
        if lines:
            _append_section(page, "## 关联页面\n" + "\n".join(lines))


def _append_section(page: dict[str, Any], section: str) -> None:
    body = page["body_md"].rstrip()
    if section in body:
        return
    page["body_md"] = body + "\n\n" + section + "\n"


def _render_page(page: Mapping[str, Any], plan: Mapping[str, Any]) -> str:
    source_blocks = page.get("source_block_ids", [])
    frontmatter = [
        "---",
        f'title: "{_escape_yaml(page["title"])}"',
        f'type: "{_escape_yaml(page["type"])}"',
        f'source_id: "{_escape_yaml(plan["source_id"])}"',
        "source_blocks:",
    ]
    if source_blocks:
        frontmatter.extend(f"  - {block_id}" for block_id in source_blocks)
    else:
        frontmatter.append("  []")
    frontmatter.append("---")
    return "\n".join(frontmatter) + "\n\n" + page["body_md"].rstrip() + "\n"


def _merge_manifest(existing: dict[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    manifest = existing or {"schema_version": "llm-wiki-manifest.v1", "sources": {}, "pages": {}}
    manifest.setdefault("schema_version", "llm-wiki-manifest.v1")
    manifest.setdefault("sources", {})
    manifest.setdefault("pages", {})
    manifest["sources"][plan["source_id"]] = {"hash": plan["source_hash"], "topic": plan["topic"]}
    for page in plan["pages"]:
        record = manifest["pages"].setdefault(page["path"], {"source_ids": []})
        record["title"] = page["title"]
        record["type"] = page["type"]
        record.setdefault("source_ids", [])
        if plan["source_id"] not in record["source_ids"]:
            record["source_ids"].append(plan["source_id"])
    return manifest


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _target(path: str) -> str:
    normalized = _normalize_page_path(path)
    return normalized[:-3]


def _link(page: Mapping[str, Any]) -> str:
    return f"[[{_target(page['path'])}|{page['title']}]]"


def _contains_target(markdown: str, target: str) -> bool:
    return bool(re.search(r"\[\[" + re.escape(target) + r"(?:[|#\]])", markdown))


def _escape_yaml(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
