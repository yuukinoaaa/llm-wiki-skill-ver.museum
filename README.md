# llm-wiki-skill

A Claude Code skill and Python helper toolkit for turning local documents into an interconnected Quartz wiki.

Chinese is the primary documentation language. See [README.zh.md](./README.zh.md) for the full workflow, configuration, business logic, and maintenance notes.

## Workflow

1. Put local `DOCX`, `PDF`, `MD`, or `TXT` files in `input/`.
2. Batch-extract them into normalized text blocks and `source-manifest.json`.
3. Ask Claude Code to create per-document plans under `ingest-output/plans/`.
4. Merge those local plans into one unified `ingest-plan.json`.
5. Materialize the plan into Quartz Markdown pages with route links, entity backlinks, `source_refs`, `aliases`, and marked web enrichments.
6. Validate wikilinks, metadata, source refs, and structured web source records.
7. Build HTML with Quartz.

The materializer does not create placeholder pages. Every `outgoing_links` target must be a real page in the plan or existing wiki content.

Translation is disabled by default. Use `translate_wiki.py` only when explicitly configured with a local API key.

Web enrichment is enabled in the default workflow, but helper scripts do not search the web. Claude Code performs research using entity/book/concept names only. Allowed source types are `museum`, `library`, `university`, `government`, `encyclopedia`, `publisher`, `journal`, `database`, and `archive`.

## Commands

```bash
python ingest_wiki.py extract-dir --input input --out ingest-output
python ingest_wiki.py extract path/to/your-real-source.docx --out source.blocks.json
python ingest_wiki.py merge-plans ingest-output/plans --out ingest-plan.json
python ingest_wiki.py materialize ingest-plan.json --wiki wiki --dry-run
python ingest_wiki.py materialize ingest-plan.json --wiki wiki --apply
python ingest_wiki.py clean-stubs --wiki wiki --dry-run
python ingest_wiki.py validate --wiki wiki
python ingest_wiki.py build --wiki wiki
python ingest_wiki.py serve --wiki wiki --port 8888
```

Run commands from the repository root. If your shell is already inside `wiki/`, use `python ..\ingest_wiki.py serve --wiki . --port 8888`.

Local `input/`, `ingest-output/`, `wiki/`, `.claude/`, and `tests/` are ignored and are not pushed to GitHub.

## License

MIT
