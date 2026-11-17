---
name: llm-wiki
version: 1.1.0
description: |
  Ingest input/ documents into a unified Quartz-based LLM Wiki. The skill uses
  helper scripts to batch-extract DOCX/PDF/MD/TXT files, asks Claude Code to
  create per-document ingestion plans, merges plans, materializes interconnected
  Markdown pages, validates links and source records, and builds Quartz HTML.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# /llm-wiki - Batch Document Ingestion Wiki Manager

Use this skill to turn local `input/` documents into a connected Quartz Wiki.

The default workflow is batch document ingestion plus clearly marked web enrichment. Claude Code performs page planning, entity/concept splitting, writing, and web research; helper scripts do not search or fetch web sources.

## Core Rules

- Use Chinese for user-facing communication unless the user asks otherwise.
- Treat source documents as read-only.
- Use `input/` as the default source directory for new ingestion work.
- Build one unified Wiki: each document gets a `source` page, scripts create route `stop` pages, research documents create source/topic pages, and entity/concept pages are reused across documents.
- Default content ratio: about 75% local input material and 25% marked web enrichment.
- Local input should use relatively rich excerpts: about 30-40% key source passages per page, connected by concise explanatory writing.
- Translation is disabled by default.
- Do not commit or upload `input/`, extracted blocks, `ingest-output/`, private `ingest-plan.json`, private `wiki/`, generated HTML, `.claude/`, or `tests/`.
- Use full Quartz wikilinks from the content root, for example `[[works/shi-ji|史记]]`.
- Do not create placeholder pages. Short pages must still contain a summary, a source excerpt, and source references.

## Phase 1: Extract Input Directory

Supported formats:

- `.docx`
- `.pdf` with extractable text
- `.md`
- `.txt`

Run from the repository root:

```bash
python ingest_wiki.py extract-dir --input "input" --out "ingest-output"
```

This writes:

- `ingest-output/blocks/*.blocks.json`
- `ingest-output/source-manifest.json`
- `ingest-output/plans/` as the recommended location for local per-document plans

`extract-dir` reuses unchanged block files by SHA256. Unsupported files are skipped and listed in `source-manifest.json`.

Optional `input/input-manifest.json` can override automatic classification:

```json
{
  "documents": {
    "展览讲解词.docx": {
      "document_type": "script",
      "priority": 1
    },
    "某篇论文.docx": {
      "document_type": "research"
    }
  }
}
```

Use `document_type: "script"` for explanation scripts and `document_type: "research"` for papers or research materials.

## Phase 2: Create Per-Document Plans

For each extracted block file, read the matching source manifest entry and create one local plan JSON under `ingest-output/plans/`.

Required page model:

- Every input document gets a `source` page under `sources/`.
- Script documents preserve route order with `stop` pages.
- Research documents create source/topic pages and link to shared entities and concepts.
- Entities use page types `exhibit`, `work`, `person`, `place`.
- Concepts use page type `concept`, medium-fine granularity, and `aliases` for synonyms.

Entity and concept rules:

- Entity pages are created when a named entity appears. Avoid empty pages by adding a short summary, source excerpt, and source refs.
- Concept pages are created when the term has reuse value or explanation value.
- Do not create duplicate concept pages for synonyms. Pick one pinyin slug and put other names in `aliases`.

Plan schema excerpt:

```json
{
  "source_id": "stable-source-id",
  "source_hash": "sha256-from-blocks",
  "topic": "document topic",
  "pages": [
    {
      "type": "source",
      "path": "sources/stable-source-id.md",
      "title": "文档标题",
      "aliases": [],
      "body_md": "页面正文，包含关键原文摘录和整理说明。",
      "source_refs": [
        {
          "source_id": "stable-source-id",
          "block_ids": ["b0001"],
          "quote_purpose": "excerpt"
        }
      ],
      "outgoing_links": ["concepts/banben.md"],
      "web_enrichments": []
    }
  ]
}
```

Compatibility:

- Old `source_block_ids` is still accepted.
- New multi-document plans should prefer `source_refs`.

## Phase 3: Web Enrichment

Web enrichment is enabled by default, but it must be clearly marked.

Rules:

- Query using entity names, book/work names, concept names, or place names only. Do not search private source text snippets.
- Chinese authoritative sources are preferred; foreign authoritative sources are allowed when Chinese sources are insufficient.
- Default density: 0-2 enrichments per useful page. Do not force enrichment on simple pages.
- Each enrichment needs `anchor_text`, `content_md`, and at least one source.
- `anchor_text` must appear in `body_md`.
- Allowed `source_type`: `museum`, `library`, `university`, `government`, `encyclopedia`, `publisher`, `journal`, `database`, `archive`.
- Encyclopedia sources are fallback only.

Rendered callout:

```md
> [!info] 联网补充
> 补充内容……
>
> 来源：[来源标题](https://example.com)（library，访问：2026-05-31）
```

## Phase 4: Merge Plans

After per-document plans are ready:

```bash
python ingest_wiki.py merge-plans "ingest-output/plans" --out "ingest-plan.json"
```

Merge behavior:

- Duplicate page paths are merged only when `type` and `title` match.
- `aliases`, `source_refs`, `source_block_ids`, `outgoing_links`, and `web_enrichments` are combined.
- Different bodies for the same page are appended under a source-specific section.
- Missing `outgoing_links` targets fail the merge.

## Phase 5: Materialize, Validate, Build, Serve

Dry-run first:

```bash
python ingest_wiki.py materialize "ingest-plan.json" --wiki "wiki" --dry-run
```

Apply after review:

```bash
python ingest_wiki.py materialize "ingest-plan.json" --wiki "wiki" --apply
```

Validate:

```bash
python ingest_wiki.py validate --wiki "wiki"
```

Build:

```bash
python ingest_wiki.py build --wiki "wiki"
```

Preview:

```bash
python ingest_wiki.py serve --wiki "wiki" --port 8888
```

If the shell is already inside the Quartz wiki directory, use:

```bash
python ../ingest_wiki.py serve --wiki "." --port 8888
```

Do not recommend plain `python -m http.server` for Quartz `public/` output because Quartz clean URLs often omit `.html`.

## Optional Single-File Extraction

For debugging one document:

```bash
python ingest_wiki.py extract "{source_file}" --out "{source_file}.blocks.json"
```

## Optional Translation

Only run translation when explicitly requested and configured with a local API key:

```bash
LLM_WIKI_TRANSLATION_ENGINE=zhipu ZHIPU_API_KEY=... python translate_wiki.py --content-dir "wiki/content" --engine zhipu
```

Do not infer that translation is desired from the existence of `translate_wiki.py`.

## Git Hygiene

Do not stage or commit:

- `input/`
- `ingest-output/`
- `.claude/`
- `tests/`
- source `.docx` / `.pdf`
- extracted `*.blocks.json`
- private `ingest-plan.json`
- private local `wiki/`
- Quartz `public/`
- local `config.md`

Before commit or push, run:

```bash
git status --short
```

Confirm private source files and generated wiki content are not staged.
