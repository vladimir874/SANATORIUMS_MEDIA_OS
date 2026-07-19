from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any


PUBLIC_ROOT = "${HOTELCUT_OLYMP_ROOT}"


def sanitize_report(report: dict[str, Any]) -> dict[str, Any]:
    project = report.get("project")
    if isinstance(project, dict):
        project["hotel_root"] = PUBLIC_ROOT

    source_structure = report.get("source_structure")
    if isinstance(source_structure, dict):
        source_structure["folder_map_path"] = "config/folder_map.json"

    media = report.get("inventory", {}).get("media", [])
    for item in media:
        relative = PurePosixPath(str(item["relative_path"]))
        item["absolute_path"] = f"{PUBLIC_ROOT}/{relative.as_posix()}"
        metadata = item.get("technical_metadata")
        if isinstance(metadata, dict):
            camera = metadata.get("camera")
            if isinstance(camera, dict):
                camera["serial_number"] = None
                camera["lens_serial_number"] = None

    metadata_audit = report.get("metadata_audit")
    if isinstance(metadata_audit, dict):
        tool = metadata_audit.get("tool")
        if isinstance(tool, dict):
            tool["executable"] = "vendor/exiftool/13.59/exiftool.exe"
    return report


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create shareable HOTELCUT reports without local paths or serials."
    )
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    names = ("olymp-iv-scan.json", "olymp-iv-metadata.json")
    for name in names:
        source = args.input_dir / name
        report = json.loads(source.read_text(encoding="utf-8"))
        write_json(args.output_dir / name, sanitize_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
