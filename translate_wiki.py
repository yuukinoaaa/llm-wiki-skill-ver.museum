#!/usr/bin/env python3
"""
Optional translation helper for LLM Wiki pages.

Translation is disabled by default. Enable it explicitly with
LLM_WIKI_TRANSLATION_ENGINE=zhipu and ZHIPU_API_KEY, or pass matching CLI flags.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_ZHIPU_ENDPOINT = "https://open.bigmodel.cn/api/anthropic/v1/messages"
DEFAULT_ZHIPU_MODEL = "GLM-4-Flash"

SKIP_PATTERNS = [
    r"^---",
    r"^#",
    r"^\s*$",
    r"^\s*[-*]\s+\[\[",
    r"^\s*[-*]\s+$",
    r"^```",
    r"^!\[",
    r"^<div",
]


@dataclass(frozen=True)
class TranslationConfig:
    engine: str = "none"
    api_key: str | None = None
    api_url: str = DEFAULT_ZHIPU_ENDPOINT
    model: str = DEFAULT_ZHIPU_MODEL

    @property
    def enabled(self) -> bool:
        return self.engine != "none" and bool(self.api_key)


def load_config(
    env: Mapping[str, str] | None = None,
    *,
    engine: str | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
    model: str | None = None,
) -> TranslationConfig:
    values = env if env is not None else os.environ
    selected_engine = (engine or values.get("LLM_WIKI_TRANSLATION_ENGINE") or "none").lower()
    selected_key = api_key or values.get("ZHIPU_API_KEY") or values.get("LLM_WIKI_TRANSLATION_API_KEY")
    return TranslationConfig(
        engine=selected_engine,
        api_key=selected_key,
        api_url=api_url or values.get("ZHIPU_API_ENDPOINT") or DEFAULT_ZHIPU_ENDPOINT,
        model=model or values.get("ZHIPU_MODEL") or DEFAULT_ZHIPU_MODEL,
    )


def should_skip(line: str) -> bool:
    return any(re.match(pattern, line) for pattern in SKIP_PATTERNS)


def translate_paragraph(text: str, config: TranslationConfig) -> str | None:
    if not config.enabled:
        return None
    if config.engine != "zhipu":
        raise ValueError(f"Unsupported translation engine: {config.engine}")

    payload = json.dumps(
        {
            "model": config.model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "请将以下英文技术文本翻译成中文。保留专有名词、代码标识、URL 和 wikilink，"
                        "只输出译文，不要解释。\n\n"
                        + text
                    ),
                }
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        config.api_url,
        data=payload,
        headers={
            "x-api-key": config.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read())
                return data["content"][0]["text"].strip()
        except urllib.error.HTTPError as error:
            if error.code == 429:
                time.sleep(2**attempt)
                continue
            print(f"HTTP {error.code}: {error.read()[:200]}")
            return None
        except Exception as error:
            print(f"Translation failed: {error}")
            return None
    return None


def process_file(path: Path, config: TranslationConfig) -> int:
    if not config.enabled:
        return 0

    text = path.read_text(encoding="utf-8")
    if '<div class="zh-trans">' in text:
        print(f"SKIP already translated: {path}")
        return 0

    lines = text.split("\n")
    new_lines: list[str] = []
    in_frontmatter = False
    in_code_block = False
    translations_added = 0
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            new_lines.append(line)
            index += 1
            continue
        if in_frontmatter:
            new_lines.append(line)
            index += 1
            continue

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            new_lines.append(line)
            index += 1
            continue
        if in_code_block:
            new_lines.append(line)
            index += 1
            continue

        if line.strip() and not should_skip(line):
            paragraph_lines = [line]
            cursor = index + 1
            while cursor < len(lines) and lines[cursor].strip() and not should_skip(lines[cursor]):
                paragraph_lines.append(lines[cursor])
                cursor += 1

            paragraph = " ".join(paragraph_lines)
            if len(paragraph) > 20 and re.search(r"[a-zA-Z]{3,}", paragraph):
                translated = translate_paragraph(paragraph, config)
                new_lines.extend(paragraph_lines)
                if translated:
                    new_lines.append(f'<div class="zh-trans">{translated}</div>')
                    new_lines.append("")
                    translations_added += 1
                index = cursor
                continue

        new_lines.append(line)
        index += 1

    if translations_added:
        path.write_text("\n".join(new_lines), encoding="utf-8")
    return translations_added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optionally add Chinese translation blocks to existing wiki pages.")
    parser.add_argument("--content-dir", type=Path, help="Wiki content directory containing Markdown pages.")
    parser.add_argument("--engine", choices=["none", "zhipu"], help="Translation engine. Default: none.")
    parser.add_argument("--api-key", help="Translation API key. Prefer environment variables for local use.")
    parser.add_argument("--api-url", help="Translation API endpoint.")
    parser.add_argument("--model", help="Translation model name.")
    args = parser.parse_args(argv)

    config = load_config(engine=args.engine, api_key=args.api_key, api_url=args.api_url, model=args.model)
    if not config.enabled:
        print("Translation is disabled. Set --engine zhipu and provide an API key to enable it.")
        return 0
    if args.content_dir is None:
        parser.error("--content-dir is required when translation is enabled")
    if not args.content_dir.exists():
        parser.error(f"content directory does not exist: {args.content_dir}")

    total = 0
    for markdown in sorted(args.content_dir.rglob("*.md")):
        count = process_file(markdown, config)
        if count:
            print(f"{markdown}: added {count} translations")
        total += count
        time.sleep(0.3)
    print(f"Done. Total translations added: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
