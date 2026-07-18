from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hotelcut.metadata import (
    ExifToolError,
    MetadataManifestError,
    enrich_scan_report,
    load_manifest,
)
from hotelcut.scanner import ScanConfigurationError, scan_hotel, write_json_atomic


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hotelcut")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="Scan a hotel folder without changing source media")
    scan.add_argument("--hotel-root", type=Path, required=True)
    scan.add_argument("--hotel-id")
    scan.add_argument("--config", type=Path)
    scan.add_argument("--output", type=Path, required=True)

    metadata = commands.add_parser(
        "metadata", help="Read local media metadata with ExifTool"
    )
    metadata.add_argument("--manifest", type=Path, required=True)
    metadata.add_argument("--output", type=Path, required=True)
    metadata.add_argument("--exiftool", type=Path)
    metadata.add_argument("--timeout", type=int, default=600)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "scan":
        try:
            report = scan_hotel(
                args.hotel_root,
                hotel_id=args.hotel_id,
                config_path=args.config,
            )
            write_json_atomic(report, args.output)
        except (OSError, ScanConfigurationError, ValueError) as exc:
            print(f"HOTELCUT scan failed: {exc}", file=sys.stderr)
            return 1

        summary = {
            "status": report["pipeline"]["status"],
            "hotel_id": report["project"]["hotel_id"],
            "media_files_count": report["inventory"]["media_files_count"],
            "counts_by_type": report["inventory"]["counts_by_type"],
            "warnings": report["warnings"],
            "output": str(args.output.resolve()),
        }
    elif args.command == "metadata":
        if args.timeout <= 0:
            print("HOTELCUT metadata failed: --timeout must be positive", file=sys.stderr)
            return 1
        try:
            report = enrich_scan_report(
                load_manifest(args.manifest),
                exiftool_path=args.exiftool,
                timeout_seconds=args.timeout,
            )
            write_json_atomic(report, args.output)
        except (OSError, ExifToolError, MetadataManifestError, ValueError) as exc:
            print(f"HOTELCUT metadata failed: {exc}", file=sys.stderr)
            return 1
        audit_summary = report["metadata_audit"]["summary"]
        summary = {
            "status": report["pipeline"]["status"],
            "hotel_id": report["project"]["hotel_id"],
            "files_read": audit_summary["files_read"],
            "files_failed": audit_summary["files_failed"],
            "frame_rate_counts": audit_summary["frame_rate_counts"],
            "resolution_counts": audit_summary["resolution_counts"],
            "video_codec_counts": audit_summary["video_codec_counts"],
            "warning_counts": audit_summary["warning_counts"],
            "output": str(args.output.resolve()),
        }
    else:
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
