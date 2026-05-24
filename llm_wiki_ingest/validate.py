from __future__ import annotations

import json
import re
from pathlib import Path

from .stubs import find_stub_pages


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def validate_wiki(wiki_dir: str | Path) -> list[str]:
    wiki = Path(wiki_dir)
    content = wiki / "content"
    issues: list[str] = []
    if not content.exists():
        return [f"Missing content directory: {content}"]

    pages = sorted(content.rglob("*.md"))
    existing_targets = {_target_for_path(path, content) for path in pages}
    for page in pages:
        rel = page.relative_to(content).as_posix()
        text = page.read_text(encoding="utf-8")
        fields = _frontmatter_fields(text)
        for required in ["title", "type"]:
            if required not in fields:
                issues.append(f"Missing frontmatter field in {rel}: {required}")
        for raw_link in WIKILINK_RE.findall(text):
            target = _normalize_link_target(raw_link)
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if target not in existing_targets:
                issues.append(f"Broken link in {rel}: [[{raw_link}]]")

    for stub in find_stub_pages(wiki):
        issues.append(f"Materialize stub page remains: {stub.relative_to(content).as_posix()}")

    issues.extend(_validate_manifest(wiki, existing_targets))
    return issues


def _frontmatter_fields(text: str) -> set[str]:
    if not text.startswith("---\n"):
        return set()
    end = text.find("\n---", 4)
    if end == -1:
        return set()
    fields = set()
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            fields.add(line.split(":", 1)[0].strip())
    return fields


def _normalize_link_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/").lstrip("/")
    if target.startswith("content/"):
        target = target.removeprefix("content/")
    if target.endswith(".md"):
        target = target[:-3]
    return target


def _target_for_path(path: Path, content: Path) -> str:
    rel = path.relative_to(content).as_posix()
    return rel[:-3]


def _validate_manifest(wiki: Path, existing_targets: set[str]) -> list[str]:
    manifest_path = wiki / "llm-wiki-manifest.json"
    if not manifest_path.exists():
        return []
    issues: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for page_path in manifest.get("pages", {}):
        target = page_path[:-3] if page_path.endswith(".md") else page_path
        if target not in existing_targets:
            issues.append(f"Manifest page missing from content: {page_path}")
    return issues
