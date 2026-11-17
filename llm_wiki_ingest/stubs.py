from __future__ import annotations

from pathlib import Path


STUB_MARKER = "此页面由 `materialize` 根据摄入计划中的链接自动创建，用于避免 Wiki 出现断链。"


def find_stub_pages(wiki_dir: str | Path) -> list[Path]:
    wiki = Path(wiki_dir)
    content = wiki / "content"
    if not content.exists():
        return []
    return sorted(
        page
        for page in content.rglob("*.md")
        if STUB_MARKER in page.read_text(encoding="utf-8")
    )


def clean_stub_pages(wiki_dir: str | Path, apply: bool = False) -> dict[str, object]:
    wiki = Path(wiki_dir)
    content = wiki / "content"
    stubs = find_stub_pages(wiki)
    relative_paths = [page.relative_to(content).as_posix() for page in stubs]

    if not apply:
        return {"would_delete": len(relative_paths), "deleted": [], "candidates": relative_paths}

    for page in stubs:
        page.unlink()
    return {"would_delete": 0, "deleted": relative_paths, "candidates": []}
