from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .extractors import extract_document, write_extracted_json
from .materialize import materialize_plan
from .validate import validate_wiki


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest_wiki", description="Extract documents and materialize LLM Wiki pages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract DOCX/PDF/MD/TXT into normalized JSON blocks.")
    extract_parser.add_argument("source", help="Input document path.")
    extract_parser.add_argument("--out", help="Output JSON path. Prints to stdout when omitted.")

    materialize_parser = subparsers.add_parser("materialize", help="Create or update Quartz Markdown pages from a plan.")
    materialize_parser.add_argument("plan", help="Ingestion plan JSON path.")
    materialize_parser.add_argument("--wiki", required=True, help="Quartz wiki directory.")
    materialize_parser.add_argument("--apply", action="store_true", help="Write files. Without this flag, runs dry-run.")
    materialize_parser.add_argument("--dry-run", action="store_true", help="Dry-run alias for readability.")

    validate_parser = subparsers.add_parser("validate", help="Validate generated wiki links and metadata.")
    validate_parser.add_argument("--wiki", required=True, help="Quartz wiki directory.")

    args = parser.parse_args(argv)
    if args.command == "extract":
        document = extract_document(args.source)
        if args.out:
            write_extracted_json(document, args.out)
        else:
            print(json.dumps(document.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "materialize":
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        summary = materialize_plan(plan, args.wiki, apply=args.apply)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        issues = validate_wiki(args.wiki)
        if issues:
            for issue in issues:
                print(issue, file=sys.stderr)
            return 1
        print("Validation passed")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
