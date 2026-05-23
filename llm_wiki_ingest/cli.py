from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from json import JSONDecodeError

from .extractors import extract_document, write_extracted_json
from .materialize import materialize_plan
from .serve import serve_wiki
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

    serve_parser = subparsers.add_parser("serve", help="Serve Quartz public output with clean URL support.")
    serve_parser.add_argument("--wiki", required=True, help="Quartz wiki directory.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1.")
    serve_parser.add_argument("--port", type=int, default=8888, help="Bind port. Default: 8888.")

    args = parser.parse_args(argv)
    if args.command == "extract":
        try:
            document = extract_document(args.source)
        except FileNotFoundError as error:
            _print_missing_source_error(Path(error.filename or args.source))
            return 1
        except ValueError as error:
            print(f"Input error: {error}", file=sys.stderr)
            return 1
        if args.out:
            write_extracted_json(document, args.out)
        else:
            print(json.dumps(document.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "materialize":
        try:
            plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
            summary = materialize_plan(plan, args.wiki, apply=args.apply)
        except FileNotFoundError:
            print(f"Plan file not found: {args.plan}", file=sys.stderr)
            return 1
        except JSONDecodeError as error:
            print(f"Plan JSON error in {args.plan}: {error}", file=sys.stderr)
            return 1
        except ValueError as error:
            print(f"Plan error: {error}", file=sys.stderr)
            return 1
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

    if args.command == "serve":
        try:
            serve_wiki(args.wiki, host=args.host, port=args.port)
        except FileNotFoundError as error:
            print(error, file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nServer stopped")
            return 0
        return 0

    return 2


def _print_missing_source_error(path: Path) -> None:
    candidates = _find_candidate_sources(path.parent if path.parent != Path("") else Path.cwd())
    print(f"Input file not found: {path}", file=sys.stderr)
    print(f"Current directory: {Path.cwd()}", file=sys.stderr)
    print("Use the real document path instead of the README placeholder `source.docx`.", file=sys.stderr)
    if candidates:
        print("Candidate source files in the same directory:", file=sys.stderr)
        for candidate in candidates[:10]:
            print(f"  - {candidate.name}", file=sys.stderr)
    else:
        print("No DOCX/PDF/MD/TXT candidates found in the same directory.", file=sys.stderr)


def _find_candidate_sources(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        directory = Path.cwd()
    extensions = {".docx", ".pdf", ".md", ".txt"}
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in extensions)


if __name__ == "__main__":
    raise SystemExit(main())
