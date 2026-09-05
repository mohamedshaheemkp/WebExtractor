from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console

from webextractor.cli.commands.extract import execute_extract
from webextractor.cli.commands.inspect import execute_inspect
from webextractor.cli.commands.rip import execute_rip

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

console = Console(legacy_windows=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="webextractor",
        description="WebExtractor — Deep Website Reverse Engineering, Code Generation & Asset Extraction.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: rip (Complete reverse engineering pipeline)
    rip_parser = subparsers.add_parser(
        "rip",
        help="Deep capture, reverse-engineer and generate a Next.js project from a URL or HAR file.",
    )
    rip_parser.add_argument(
        "target",
        type=str,
        help="Target URL (e.g. https://example.com) or path to HAR file.",
    )
    rip_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Destination directory for generated project.",
    )

    # Command: extract (Asset extraction only)
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract and download raw website assets into output folder.",
    )
    extract_parser.add_argument(
        "har_file",
        type=Path,
        help="Path to HAR archive file.",
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Destination folder (default: ./output).",
    )
    extract_parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=None,
        help="Concurrent download workers count.",
    )

    # Command: inspect (Website inspection)
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect website framework, resources, domains, and API endpoints.",
    )
    inspect_parser.add_argument(
        "har_file",
        type=Path,
        help="Path to HAR archive file.",
    )

    return parser


def main() -> None:
    parser = build_parser()

    # Fallback support: if user types `webextractor samples/ms.har` or `webextractor https://example.com`
    if len(sys.argv) > 1 and sys.argv[1] not in (
        "rip",
        "extract",
        "inspect",
        "reconstruct",
        "-h",
        "--help",
    ):
        target = sys.argv[1]
        if target.startswith("http://") or target.startswith("https://"):
            sys.argv.insert(1, "rip")
        else:
            sys.argv.insert(1, "extract")

    args = parser.parse_args()

    if args.command == "rip":
        asyncio.run(execute_rip(args.target, args.output))
    elif args.command == "extract":
        asyncio.run(execute_extract(args.har_file, args.output, args.workers))
    elif args.command == "inspect":
        execute_inspect(args.har_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
