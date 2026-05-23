# llm-wiki-skill

A Claude Code skill and Python helper toolkit for turning local documents into an interconnected Quartz wiki.

The current workflow is document-ingestion first:

1. Extract local `DOCX`, `PDF`, `MD`, or `TXT` files into normalized text blocks.
2. Ask Claude Code to turn those blocks into an ingestion plan.
3. Materialize the plan into Quartz Markdown pages with route links and entity backlinks.
4. Validate wikilinks and metadata.
5. Build HTML with Quartz.

Chinese is the primary documentation language for this project. See [README.zh.md](./README.zh.md) for installation, usage, configuration, business logic, and maintenance notes.

Translation is disabled by default. Use `translate_wiki.py` only when explicitly configured with a local API key.

## Commands

```bash
python ingest_wiki.py extract path/to/your-real-source.docx --out source.blocks.json
python ingest_wiki.py materialize ingest-plan.json --wiki wiki --dry-run
python ingest_wiki.py materialize ingest-plan.json --wiki wiki --apply
python ingest_wiki.py validate --wiki wiki
python ingest_wiki.py serve --wiki wiki --port 8888
```

`source.docx` in examples is a placeholder. Replace it with an existing local file path.
Use `serve` for local preview after `npx quartz build`; plain `python -m http.server` does not resolve Quartz clean URLs to `.html` files.

## License

MIT
