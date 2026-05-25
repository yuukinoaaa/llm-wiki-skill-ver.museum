from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .web_enrichment import ALLOWED_WEB_SOURCE_TYPES, WEB_SOURCE_REQUIRED_FIELDS, web_source_identity


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
    _validate_outgoing_link_targets(pages, content_dir)
    _append_index_page(pages, normalized)
    pages_by_path = {page["path"]: page for page in pages}
    title_by_target = {_target(page["path"]): page["title"] for page in pages}

    _append_web_enrichments(pages)
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

    manifest = _merge_manifest(existing_manifest, {**normalized, "pages": pages})
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
        page["web_enrichments"] = _normalize_web_enrichments(page.get("web_enrichments", []), page["path"])
        pages.append(page)
    web_enrichment = plan.get("web_enrichment", {})
    if web_enrichment and not isinstance(web_enrichment, Mapping):
        raise ValueError("Plan field web_enrichment must be an object")
    return {
        "source_id": str(plan["source_id"]),
        "source_hash": str(plan["source_hash"]),
        "topic": str(plan["topic"]),
        "web_enrichment": dict(web_enrichment),
        "pages": pages,
    }


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
            if field not in raw_enrichment:
                raise ValueError(f"Missing web enrichment field in {page_path}: {field}")
        anchor_text = str(raw_enrichment["anchor_text"]).strip()
        content_md = str(raw_enrichment["content_md"]).strip()
        if not anchor_text:
            raise ValueError(f"web_enrichments[{index}] anchor_text cannot be empty in {page_path}")
        if not content_md:
            raise ValueError(f"web_enrichments[{index}] content_md cannot be empty in {page_path}")
        sources = _normalize_web_sources(raw_enrichment["sources"], page_path)
        enrichments.append(
            {
                "anchor_text": anchor_text,
                "content_md": content_md,
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
        sources.append(
            {
                "title": str(raw_source["title"]).strip(),
                "url": str(raw_source["url"]).strip(),
                "source_type": source_type,
                "accessed_at": str(raw_source["accessed_at"]).strip(),
            }
        )
    return _dedupe_web_sources(sources)


def _validate_outgoing_link_targets(pages: list[dict[str, Any]], content_dir: Path) -> None:
    known_paths = {page["path"] for page in pages}
    existing_paths = {
        path.relative_to(content_dir).as_posix()
        for path in content_dir.rglob("*.md")
    } if content_dir.exists() else set()
    missing: list[str] = []

    for source in pages:
        for raw_link in source.get("outgoing_links", []):
            path = _normalize_page_path(raw_link)
            if path in known_paths or path in existing_paths:
                continue
            missing.append(f"{source['path']} -> {path}")

    if missing:
        details = "\n".join(f"- {item}" for item in sorted(missing))
        raise ValueError(f"Missing outgoing link targets:\n{details}")


def _append_index_page(pages: list[dict[str, Any]], plan: Mapping[str, Any]) -> None:
    if any(page["path"] == "index.md" for page in pages):
        return

    grouped: dict[str, list[dict[str, Any]]] = {
        "stop": [],
        "exhibit": [],
        "work": [],
        "person": [],
        "concept": [],
        "place": [],
    }
    for page in pages:
        if page["type"] in grouped:
            grouped[page["type"]].append(page)

    labels = {
        "stop": "讲解路线",
        "exhibit": "展品",
        "work": "典籍与作品",
        "person": "人物",
        "concept": "概念",
        "place": "地点",
    }
    sections = [f"# {plan['topic']}", "", "此首页由 `materialize` 自动生成，用于进入本地 Wiki。"]
    for page_type, title in labels.items():
        items = sorted(grouped[page_type], key=lambda item: item["path"])
        if not items:
            continue
        sections.extend(["", f"## {title}"])
        sections.extend(f"- {_link(item)}" for item in items)

    pages.insert(
        0,
        {
            "type": "index",
            "path": "index.md",
            "title": str(plan["topic"]),
            "body_md": "\n".join(sections),
            "source_block_ids": [],
            "outgoing_links": [],
        },
    )


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


def _append_web_enrichments(pages: list[dict[str, Any]]) -> None:
    for page in pages:
        for enrichment in page.get("web_enrichments", []):
            page["body_md"] = _insert_web_enrichment(page["body_md"], enrichment, page["path"])


def _insert_web_enrichment(body_md: str, enrichment: Mapping[str, Any], page_path: str) -> str:
    paragraphs = body_md.rstrip().split("\n\n")
    anchor_text = str(enrichment["anchor_text"])
    callout = _render_web_enrichment_callout(enrichment)
    for index, paragraph in enumerate(paragraphs):
        if anchor_text in paragraph:
            paragraphs.insert(index + 1, callout)
            return "\n\n".join(paragraphs)
    raise ValueError(f"Web enrichment anchor not found in {page_path}: {anchor_text}")


def _render_web_enrichment_callout(enrichment: Mapping[str, Any]) -> str:
    lines = ["> [!info] 联网补充"]
    for line in str(enrichment["content_md"]).splitlines():
        lines.append("> " + line if line else ">")
    lines.append(">")
    source_links = "；".join(_web_source_link(source) for source in enrichment["sources"])
    lines.append(f"> 来源：{source_links}")
    return "\n".join(lines)


def _web_source_link(source: Mapping[str, str]) -> str:
    return (
        f"[{source['title']}]({source['url']})"
        f"（{source['source_type']}，访问：{source['accessed_at']}）"
    )


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
    if plan.get("web_enrichment"):
        manifest["web_enrichment"] = dict(plan["web_enrichment"])
    source_id = plan["source_id"]
    current_paths = {page["path"] for page in plan["pages"]}
    for page_path, record in list(manifest["pages"].items()):
        source_ids = record.get("source_ids", [])
        if source_id in source_ids and page_path not in current_paths:
            record["source_ids"] = [item for item in source_ids if item != source_id]
            if not record["source_ids"]:
                del manifest["pages"][page_path]

    manifest["sources"][source_id] = {"hash": plan["source_hash"], "topic": plan["topic"]}
    for page in plan["pages"]:
        record = manifest["pages"].setdefault(page["path"], {"source_ids": []})
        record["title"] = page["title"]
        record["type"] = page["type"]
        record.setdefault("source_ids", [])
        if source_id not in record["source_ids"]:
            record["source_ids"].append(source_id)
        web_sources = _web_sources_for_page(page)
        if web_sources:
            record["web_sources"] = web_sources
        else:
            record.pop("web_sources", None)
    return manifest


def _web_sources_for_page(page: Mapping[str, Any]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for enrichment in page.get("web_enrichments", []):
        sources.extend(enrichment.get("sources", []))
    return _dedupe_web_sources(sources)


def _dedupe_web_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for source in sources:
        identity = web_source_identity(source)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(dict(source))
    return deduped


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
