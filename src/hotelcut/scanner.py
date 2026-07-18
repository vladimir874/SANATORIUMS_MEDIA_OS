from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = {
    ".avi",
    ".m2ts",
    ".mkv",
    ".mov",
    ".mp4",
    ".mts",
    ".mxf",
    ".webm",
}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".wav"}
IMAGE_EXTENSIONS = {
    ".dng",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
}
FINGERPRINT_SAMPLE_BYTES = 128 * 1024


class ScanConfigurationError(ValueError):
    """Raised when folder mapping configuration is unsafe or inconsistent."""


def _normalize_name(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


def _normalize_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    return "/".join(_normalize_name(part) for part in normalized.split("/") if part.strip())


def _default_config_path() -> Path:
    project_config = Path(__file__).resolve().parents[2] / "config" / "folder_map.json"
    if project_config.is_file():
        return project_config
    return Path(__file__).resolve().parent / "data" / "folder_map.json"


def load_folder_config(config_path: Path | None = None) -> dict[str, Any]:
    path = (config_path or _default_config_path()).resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ScanConfigurationError(f"Folder map does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ScanConfigurationError(f"Folder map is not valid JSON: {path}: {exc}") from exc

    aliases = raw.get("aliases")
    category_order = raw.get("category_order")
    excluded = raw.get("excluded_directories")
    if not isinstance(aliases, dict) or not isinstance(category_order, list):
        raise ScanConfigurationError("Folder map must contain aliases and category_order")
    if not isinstance(excluded, list):
        raise ScanConfigurationError("excluded_directories must be a list")

    alias_lookup: dict[str, str] = {}
    for category, names in aliases.items():
        if category not in category_order:
            raise ScanConfigurationError(f"Category missing from category_order: {category}")
        if not isinstance(names, list) or not names:
            raise ScanConfigurationError(f"Category must have at least one alias: {category}")
        for name in names:
            normalized = _normalize_relative_path(str(name))
            previous = alias_lookup.get(normalized)
            if previous and previous != category:
                raise ScanConfigurationError(
                    f"Folder alias {name!r} maps to both {previous!r} and {category!r}"
                )
            alias_lookup[normalized] = category

    return {
        "path": str(path),
        "schema_version": str(raw.get("schema_version", "1.0")),
        "category_order": list(category_order),
        "alias_lookup": alias_lookup,
        "excluded_lookup": {_normalize_name(str(item)) for item in excluded},
    }


def _media_type(extension: str) -> str | None:
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    return None


def _resolve_category(relative_path: Path, alias_lookup: dict[str, str]) -> str:
    directory_parts = relative_path.parts[:-1]
    normalized_parts = [_normalize_name(part) for part in directory_parts]
    for length in range(len(normalized_parts), 0, -1):
        candidate = "/".join(normalized_parts[:length])
        category = alias_lookup.get(candidate)
        if category:
            return category
    return "unclassified"


def _top_folder_category(folder_name: str, alias_lookup: dict[str, str]) -> str:
    normalized = _normalize_name(folder_name)
    exact = alias_lookup.get(normalized)
    if exact:
        return exact
    if any(alias.startswith(f"{normalized}/") for alias in alias_lookup):
        return "grouped"
    return "unclassified"


def _asset_id(relative_path: str) -> str:
    normalized_path = _normalize_name(relative_path.replace("\\", "/"))
    digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()[:20]
    return f"media_{digest}"


def _fingerprint(path: Path, size_bytes: int) -> str:
    """Return a fast content fingerprint using file size plus head/tail samples."""
    digest = hashlib.sha256()
    digest.update(b"hotelcut-fingerprint-v1\0")
    digest.update(str(size_bytes).encode("ascii"))
    digest.update(b"\0")

    with path.open("rb") as handle:
        digest.update(handle.read(FINGERPRINT_SAMPLE_BYTES))
        if size_bytes > FINGERPRINT_SAMPLE_BYTES:
            tail_offset = max(FINGERPRINT_SAMPLE_BYTES, size_bytes - FINGERPRINT_SAMPLE_BYTES)
            handle.seek(tail_offset)
            digest.update(handle.read(FINGERPRINT_SAMPLE_BYTES))
    return digest.hexdigest()


def _utc_iso_from_ns(timestamp_ns: int) -> str:
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc).isoformat()


def scan_hotel(
    hotel_root: Path,
    *,
    hotel_id: str | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    root = hotel_root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Hotel root is not a directory: {root}")

    config = load_folder_config(config_path)
    alias_lookup: dict[str, str] = config["alias_lookup"]
    excluded_lookup: set[str] = config["excluded_lookup"]
    category_order: list[str] = config["category_order"]

    run_id = str(uuid.uuid4())
    scanned_at = datetime.now(timezone.utc).isoformat()
    media: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    scan_errors: list[dict[str, str]] = []
    excluded_folders: list[str] = []
    skipped_link_folders: list[str] = []
    top_folder_media_counts: Counter[str] = Counter()
    top_folders: dict[str, dict[str, str]] = {}

    try:
        root_entries = sorted(root.iterdir(), key=lambda item: _normalize_name(item.name))
    except OSError as exc:
        raise OSError(f"Unable to list hotel root {root}: {exc}") from exc

    for entry in root_entries:
        if not entry.is_dir() or entry.is_symlink():
            continue
        normalized = _normalize_name(entry.name)
        if normalized in excluded_lookup:
            continue
        top_folders[entry.name] = {
            "name": entry.name,
            "category": _top_folder_category(entry.name, alias_lookup),
        }

    for current_root, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current_root)
        kept_directories: list[str] = []
        for directory_name in sorted(directory_names, key=_normalize_name):
            directory_path = current_path / directory_name
            relative_directory = directory_path.relative_to(root).as_posix()
            if _normalize_name(directory_name) in excluded_lookup:
                excluded_folders.append(relative_directory)
                continue
            if directory_path.is_symlink():
                skipped_link_folders.append(relative_directory)
                continue
            kept_directories.append(directory_name)
        directory_names[:] = kept_directories

        for file_name in sorted(file_names, key=_normalize_name):
            path = current_path / file_name
            relative = path.relative_to(root)
            relative_posix = unicodedata.normalize("NFC", relative.as_posix())
            if path.is_symlink():
                skipped.append({"relative_path": relative_posix, "reason": "symlink_file"})
                continue

            extension = path.suffix.casefold()
            kind = _media_type(extension)
            if kind is None:
                skipped.append({"relative_path": relative_posix, "reason": "unsupported_extension"})
                continue

            try:
                stat = path.stat()
                content_fingerprint = _fingerprint(path, stat.st_size)
            except OSError as exc:
                scan_errors.append({"relative_path": relative_posix, "error": str(exc)})
                continue

            top_folder = relative.parts[0] if len(relative.parts) > 1 else ""
            category = _resolve_category(relative, alias_lookup)
            if top_folder:
                top_folder_media_counts[top_folder] += 1
            media.append(
                {
                    "media_id": _asset_id(relative_posix),
                    "fingerprint": content_fingerprint,
                    "relative_path": relative_posix,
                    "absolute_path": str(path.resolve()),
                    "top_folder": top_folder,
                    "category": category,
                    "media_type": kind,
                    "extension": extension,
                    "size_bytes": stat.st_size,
                    "modified_time_utc": _utc_iso_from_ns(stat.st_mtime_ns),
                }
            )

    category_rank = {category: index for index, category in enumerate(category_order)}
    media.sort(
        key=lambda item: (
            category_rank.get(item["category"], len(category_rank)),
            _normalize_name(item["relative_path"]),
        )
    )
    skipped.sort(key=lambda item: _normalize_name(item["relative_path"]))
    excluded_folders.sort(key=_normalize_name)
    skipped_link_folders.sort(key=_normalize_name)

    counts_by_type = Counter(item["media_type"] for item in media)
    counted_categories = Counter(item["category"] for item in media)
    counts_by_category = {
        category: counted_categories.get(category, 0) for category in category_order
    }
    if counted_categories.get("unclassified", 0):
        counts_by_category["unclassified"] = counted_categories["unclassified"]

    recognized_folders = sorted(
        (folder for folder in top_folders.values() if folder["category"] != "unclassified"),
        key=lambda item: (_normalize_name(item["category"]), _normalize_name(item["name"])),
    )
    unknown_folders = sorted(
        (folder["name"] for folder in top_folders.values() if folder["category"] == "unclassified"),
        key=_normalize_name,
    )
    empty_media_folders = sorted(
        (name for name in top_folders if top_folder_media_counts.get(name, 0) == 0),
        key=_normalize_name,
    )

    warnings: list[dict[str, Any]] = []
    if unknown_folders:
        warnings.append({"code": "unknown_top_folders", "folders": unknown_folders})
    if empty_media_folders:
        warnings.append({"code": "empty_media_folders", "folders": empty_media_folders})
    if skipped_link_folders:
        warnings.append({"code": "linked_folders_skipped", "folders": skipped_link_folders})
    if scan_errors:
        warnings.append({"code": "scan_errors", "count": len(scan_errors)})

    return {
        "schema_version": "1.0.0",
        "project": {
            "hotel_id": hotel_id or root.name,
            "hotel_root": str(root),
            "run_id": run_id,
            "scanned_at_utc": scanned_at,
        },
        "pipeline": {
            "stage": "scan",
            "status": "warning" if warnings else "success",
        },
        "source_structure": {
            "folder_map_schema_version": config["schema_version"],
            "folder_map_path": config["path"],
            "recognized_folders": recognized_folders,
            "unknown_folders": unknown_folders,
            "empty_media_folders": empty_media_folders,
            "excluded_folders": excluded_folders,
        },
        "inventory": {
            "fingerprint_strategy": "sha256_size_head_tail_128k_v1",
            "media_files_count": len(media),
            "counts_by_type": dict(sorted(counts_by_type.items())),
            "counts_by_category": counts_by_category,
            "media": media,
            "skipped": skipped,
            "scan_errors": scan_errors,
        },
        "warnings": warnings,
    }


def write_json_atomic(report: dict[str, Any], output_path: Path) -> None:
    destination = output_path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
