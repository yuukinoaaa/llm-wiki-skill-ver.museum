---
name: llm-wiki
version: 1.0.0
description: |
  Ingest local documents into a Quartz-based LLM Wiki. The skill uses helper scripts
  to extract DOCX/PDF/MD/TXT files, asks Claude Code to create an ingestion plan,
  materializes interconnected Markdown pages, and validates wikilinks before build.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# /llm-wiki - Document Ingestion Wiki Manager

Use this skill to turn local documents into a connected Quartz Wiki.

The default workflow is document ingestion. Query, lint/heal, bilingual generation, web enrichment, and GitHub Pages deployment are not default v1 behavior.

## Core Rules

- Use Chinese for user-facing communication unless the user asks otherwise.
- Source documents are read-only. Never modify the user's source files.
- Translation is disabled by default.
- Chinese source documents should produce Chinese primary content by default.
- Do not create bilingual `<div class="zh-trans">` blocks unless the user explicitly asks for translation and provides configuration.
- Do not commit or upload private source documents, extracted block JSON, local wiki content, or generated HTML unless the user explicitly asks.
- Use full Quartz wikilinks from the content root, for example `[[works/shi-ji|史记]]`.

## Phase 0: Configuration Check

Read local configuration if available:

```bash
Read config.md
```

If `config.md` does not exist, use `config.example.md` as the template and ask the user for:

- source document directory
- Quartz wiki directory
- whether translation should remain disabled

Default translation settings:

```yaml
primary_engine: none
fallback_engine: none
bilingual_default: false
```

## Phase 1: Intent Routing

Classify the user request into one of these actions:

1. **Extract**: turn a document into normalized text blocks.
2. **Plan**: create or review an ingestion plan from extracted blocks.
3. **Materialize**: write plan pages into a Quartz wiki.
4. **Validate**: check generated pages and wikilinks.
5. **Build**: run Quartz build to create HTML.
6. **Translate**: optional, explicit-only translation of existing pages.

If intent is ambiguous, ask one concise question.

## Phase 2: Extract Documents

Supported v1 formats:

- `.docx`
- `.pdf` with extractable text
- `.md`
- `.txt`

Run:

```bash
python ingest_wiki.py extract "{source_file}" --out "{source_file}.blocks.json"
```

The output contains:

- `source`: path, name, type, sha256
- `blocks`: ordered text blocks with ids like `b0001`

If the source is a scanned PDF and text extraction is poor, report that OCR is out of v1 scope.

## Phase 3: Create an Ingestion Plan

Read the extracted block JSON and create a plan with this schema:

```json
{
  "source_id": "stable-source-id",
  "source_hash": "sha256-from-extract-output",
  "topic": "topic-name",
  "pages": [
    {
      "type": "stop",
      "path": "stops/01-welcome.md",
      "title": "欢迎词",
      "body_md": "页面正文。",
      "source_block_ids": ["b0001"],
      "outgoing_links": ["works/shi-ji.md"]
    }
  ]
}
```

Allowed page types:

- `source`: original document/source page
- `stop`: route node or explanation stop
- `exhibit`: exhibit object
- `work`: book, classic, article, or other textual work
- `person`: person
- `concept`: concept or technique
- `place`: place

For exhibition scripts, use the route-plus-knowledge-graph model:

- route pages preserve explanation order
- entity pages stay concise
- route pages link to entities
- entity pages link back to route pages

When asked to generate a plan, first produce a short plan summary before writing JSON:

- route/stop pages to create, in order
- entity pages to create or reuse
- key `outgoing_links`
- source block ranges used by each page
- ambiguous items needing user confirmation

After the user confirms, output valid JSON only. Keep these constraints:

- `source_hash` must equal `source.sha256` from the extracted blocks JSON.
- `source_block_ids` must use real block ids from the extracted JSON.
- `type` should use singular values: `source`, `stop`, `exhibit`, `work`, `person`, `concept`, `place`.
- `path` is relative to the Quartz `content` root and must not start with `content/`.
- `path` should use ASCII slugs, for example `stops/01-welcome.md` or `works/shi-ji.md`.
- Chinese titles belong in `title`, not in the file path.
- `outgoing_links` should use Markdown paths such as `works/shi-ji.md`.
- Do not duplicate the same person/work/concept page under different names.

## Phase 4: Review Before Writing

Before writing files, summarize:

- pages to create
- pages to update
- key entities
- important links
- source documents used

Ask for confirmation if the plan touches many pages or source ambiguity remains.

Dry-run:

```bash
python ingest_wiki.py materialize "{plan_json}" --wiki "{wiki_dir}" --dry-run
```

## Phase 5: Materialize Pages

After confirmation, write pages:

```bash
python ingest_wiki.py materialize "{plan_json}" --wiki "{wiki_dir}" --apply
```

This writes:

- Markdown pages under `{wiki_dir}/content`
- `{wiki_dir}/llm-wiki-manifest.json`

The materializer automatically adds:

- previous/next links between `stop` pages
- related-page links from `outgoing_links`
- backlinks from target pages to source pages

## Phase 6: Validate and Build

Validate:

```bash
python ingest_wiki.py validate --wiki "{wiki_dir}"
```

Fix all reported issues before building.

Build:

```bash
cd "{wiki_dir}"
npx quartz build
```

If a dev server is needed and the wiki has the usual Quartz scripts, use the project's existing preview command.

## Optional Translation Flow

Only run translation when the user explicitly asks and provides a local API key.

Example:

```bash
LLM_WIKI_TRANSLATION_ENGINE=zhipu ZHIPU_API_KEY=... python translate_wiki.py --content-dir "{wiki_dir}/content" --engine zhipu
```

Do not infer that translation is desired from the existence of `translate_wiki.py`.

## Git Hygiene

Do not stage or commit:

- source `.docx` / `.pdf`
- extracted `*.blocks.json`
- private local `wiki/`
- Quartz `public/`
- local `config.md`

Before commit or push, run:

```bash
git status --short
```

Confirm private source files and generated wiki content are not staged.
