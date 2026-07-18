from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


METADATA_SCHEMA_VERSION = "1.1.0"
DEFAULT_EXIFTOOL_VERSION = "13.59"


class MetadataManifestError(ValueError):
    """Raised when the scan manifest cannot be used safely."""


class ExifToolError(RuntimeError):
    """Raised when ExifTool is missing or cannot return usable JSON."""


def default_exiftool_path() -> Path | None:
    """Locate an explicit, bundled, or PATH-installed ExifTool executable."""
    configured = os.environ.get("HOTELCUT_EXIFTOOL")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))

    project_root = Path(__file__).resolve().parents[2]
    executable_name = "exiftool.exe" if os.name == "nt" else "exiftool"
    candidates.append(
        project_root / "vendor" / "exiftool" / DEFAULT_EXIFTOOL_VERSION / executable_name
    )

    from_path = shutil.which("exiftool")
    if from_path:
        candidates.append(Path(from_path))

    for candidate in candidates:
        expanded = candidate.expanduser()
        if expanded.is_file():
            return expanded.resolve()
    return None


def resolve_exiftool_path(exiftool_path: Path | None = None) -> Path:
    candidate = exiftool_path.expanduser() if exiftool_path else default_exiftool_path()
    if candidate is None:
        raise ExifToolError(
            "ExifTool was not found. Pass --exiftool or set HOTELCUT_EXIFTOOL."
        )
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ExifToolError(f"ExifTool executable does not exist: {resolved}")
    return resolved


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def exiftool_version(executable: Path, *, timeout_seconds: int = 30) -> str:
    try:
        completed = subprocess.run(
            [str(executable), "-ver"],
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
            creationflags=_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExifToolError(f"Unable to start ExifTool: {exc}") from exc
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ExifToolError(f"ExifTool version check failed: {error or completed.returncode}")
    version = completed.stdout.decode("ascii", errors="replace").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)+", version):
        raise ExifToolError(f"Unexpected ExifTool version output: {version!r}")
    return version


def _write_exiftool_argfile(path: Path, media_paths: Iterable[Path]) -> None:
    arguments = [
        "-j",
        "-G1",
        "-n",
        "-charset",
        "filename=UTF8",
        "-api",
        "LargeFileSupport=1",
        "--",
    ]
    for media_path in media_paths:
        value = str(media_path)
        if "\n" in value or "\r" in value:
            raise MetadataManifestError(f"Newline is not allowed in a media path: {value!r}")
        arguments.append(value)
    path.write_text("\n".join(arguments) + "\n", encoding="utf-8", newline="\n")


def read_exiftool_json(
    executable: Path,
    media_paths: list[Path],
    *,
    timeout_seconds: int = 600,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Read every file in one ExifTool process through a UTF-8 argument file."""
    if not media_paths:
        return [], []

    with tempfile.TemporaryDirectory(prefix="hotelcut-exiftool-") as temporary_directory:
        argument_path = Path(temporary_directory) / "arguments.txt"
        _write_exiftool_argfile(argument_path, media_paths)
        try:
            completed = subprocess.run(
                [str(executable), "-@", str(argument_path)],
                check=False,
                capture_output=True,
                timeout=timeout_seconds,
                creationflags=_creation_flags(),
            )
        except subprocess.TimeoutExpired as exc:
            raise ExifToolError(
                f"ExifTool exceeded the {timeout_seconds}-second timeout"
            ) from exc
        except OSError as exc:
            raise ExifToolError(f"Unable to start ExifTool: {exc}") from exc

    stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
    messages = [line.strip() for line in stderr_text.splitlines() if line.strip()]
    stdout_text = completed.stdout.decode("utf-8-sig", errors="strict")
    if completed.returncode != 0:
        detail = "; ".join(messages[-5:]) or f"exit code {completed.returncode}"
        raise ExifToolError(f"ExifTool metadata extraction failed: {detail}")

    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        raise ExifToolError(f"ExifTool returned invalid JSON: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ExifToolError("ExifTool JSON root must be a list of objects")
    return payload, messages


def _canonical_path(value: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(Path(value).resolve(strict=False))))


def _first(raw: dict[str, Any], *keys: str) -> tuple[Any | None, str | None]:
    for key in keys:
        value = raw.get(key)
        if value is not None and value != "":
            return value, key
    return None, None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _integer(value: Any) -> int | None:
    parsed = _number(value)
    return int(round(parsed)) if parsed is not None else None


def _track_number(group: str) -> int:
    match = re.fullmatch(r"Track(\d+)", group)
    return int(match.group(1)) if match else 1_000_000


def _track_groups(raw: dict[str, Any], kind: str) -> list[str]:
    groups = {key.split(":", 1)[0] for key in raw if ":" in key}
    matched: list[str] = []
    for group in groups:
        handler = str(raw.get(f"{group}:HandlerType", "")).casefold()
        if kind == "video" and (
            handler in {"vide", "video", "video track"}
            or f"{group}:VideoFrameRate" in raw
        ):
            matched.append(group)
        elif kind == "audio" and (
            handler in {"soun", "sound", "audio", "audio track"}
            or f"{group}:AudioFormat" in raw
        ):
            matched.append(group)
        elif kind == "timecode" and (
            handler in {"tmcd", "time code", "timecode"}
            or str(raw.get(f"{group}:OtherFormat", "")).casefold() == "tmcd"
        ):
            matched.append(group)
    return sorted(set(matched), key=lambda group: (_track_number(group), group))


_EXIF_DATE_PATTERN = re.compile(
    r"^(?P<year>\d{4}):(?P<month>\d{2}):(?P<day>\d{2})[ T]"
    r"(?P<time>\d{2}:\d{2}:\d{2}(?:\.\d+)?)"
    r"(?P<offset>Z|[+-]\d{2}:?\d{2})?$"
)


def _date_to_iso(value: Any, offset: Any | None = None) -> tuple[str, bool] | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = _EXIF_DATE_PATTERN.match(text)
    if not match:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.isoformat(), parsed.tzinfo is not None

    date_offset = match.group("offset")
    if not date_offset and isinstance(offset, str) and re.fullmatch(r"[+-]\d{2}:?\d{2}", offset):
        date_offset = offset
    if date_offset and date_offset != "Z" and ":" not in date_offset:
        date_offset = f"{date_offset[:3]}:{date_offset[3:]}"
    suffix = "+00:00" if date_offset == "Z" else (date_offset or "")
    iso_value = (
        f"{match.group('year')}-{match.group('month')}-{match.group('day')}T"
        f"{match.group('time')}{suffix}"
    )
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError:
        return None
    if parsed.year < 1971:
        return None
    return parsed.isoformat(), parsed.tzinfo is not None


def _capture_time(raw: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        ("Composite:SubSecDateTimeOriginal", "ExifIFD:OffsetTimeOriginal", "high"),
        ("ExifIFD:DateTimeOriginal", "ExifIFD:OffsetTimeOriginal", "high"),
        ("Keys:CreationDate", None, "high"),
        ("UserData:DateTimeOriginal", None, "medium"),
        ("QuickTime:CreateDate", None, "medium"),
        ("Track1:MediaCreateDate", None, "medium"),
        ("System:FileModifyDate", None, "low"),
    ]
    for tag, offset_tag, confidence in candidates:
        value = raw.get(tag)
        parsed = _date_to_iso(value, raw.get(offset_tag) if offset_tag else None)
        if parsed is None:
            continue
        iso_value, has_timezone = parsed
        parsed_datetime = datetime.fromisoformat(iso_value)
        utc_value = (
            parsed_datetime.astimezone(timezone.utc).isoformat()
            if parsed_datetime.tzinfo is not None
            else None
        )
        return {
            "value": iso_value,
            "utc": utc_value,
            "source_tag": tag,
            "raw_value": value,
            "timezone_status": "explicit" if has_timezone else "unspecified",
            "confidence": confidence if has_timezone or confidence == "low" else "medium",
        }
    return None


def _rate(value: Any) -> dict[str, Any] | None:
    fps = _number(value)
    if fps is None or fps <= 0:
        return None
    fraction = Fraction(str(fps)).limit_denominator(1001)
    return {
        "fps": round(fps, 6),
        "numerator": fraction.numerator,
        "denominator": fraction.denominator,
        "ntsc": fraction.denominator == 1001,
    }


def _codec_label(identifier: Any) -> str | None:
    if identifier is None:
        return None
    code = str(identifier).strip()
    labels = {
        "avc1": "H.264/AVC",
        "avc3": "H.264/AVC",
        "hvc1": "H.265/HEVC",
        "hev1": "H.265/HEVC",
        "apch": "Apple ProRes 422 HQ",
        "apcn": "Apple ProRes 422",
        "apcs": "Apple ProRes 422 LT",
        "apco": "Apple ProRes 422 Proxy",
        "ap4h": "Apple ProRes 4444",
    }
    return labels.get(code.casefold(), code)


def _audio_codec_label(identifier: Any) -> str | None:
    if identifier is None:
        return None
    code = str(identifier).strip()
    labels = {
        "twos": "PCM signed 16-bit big-endian",
        "sowt": "PCM signed 16-bit little-endian",
        "lpcm": "Linear PCM",
        "mp4a": "AAC",
        "ac-3": "Dolby Digital AC-3",
    }
    return labels.get(code.casefold(), code)


def _coded_value(value: Any, labels: dict[int, str]) -> dict[str, Any] | None:
    numeric = _integer(value)
    if numeric is None:
        return None
    return {"code": numeric, "label": labels.get(numeric, "unspecified")}


def normalize_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    video_groups = _track_groups(raw, "video")
    audio_groups = _track_groups(raw, "audio")
    timecode_groups = _track_groups(raw, "timecode")
    video_group = video_groups[0] if video_groups else None
    audio_group = audio_groups[0] if audio_groups else None
    timecode_group = timecode_groups[0] if timecode_groups else None

    duration_value, duration_tag = _first(
        raw,
        "QuickTime:Duration",
        *(f"{group}:MediaDuration" for group in video_groups),
        "Composite:Duration",
    )
    duration_seconds = _number(duration_value)

    width_value, width_tag = _first(
        raw,
        *(f"{group}:ImageWidth" for group in video_groups),
        "QuickTime:ImageWidth",
        "File:ImageWidth",
    )
    height_value, height_tag = _first(
        raw,
        *(f"{group}:ImageHeight" for group in video_groups),
        "QuickTime:ImageHeight",
        "File:ImageHeight",
    )
    width = _integer(width_value)
    height = _integer(height_value)
    rotation_value, rotation_tag = _first(
        raw,
        "Composite:Rotation",
        *(f"{group}:Rotation" for group in video_groups),
    )
    rotation = _integer(rotation_value) or 0
    display_width, display_height = width, height
    if rotation % 180 and width is not None and height is not None:
        display_width, display_height = height, width

    frame_rate_value, frame_rate_tag = _first(
        raw,
        *(f"{group}:VideoFrameRate" for group in video_groups),
        "QuickTime:VideoFrameRate",
    )
    frame_rate = _rate(frame_rate_value)
    compressor_value, compressor_tag = _first(
        raw,
        *(f"{group}:CompressorID" for group in video_groups),
        "QuickTime:CompressorID",
    )
    bitrate_value, bitrate_tag = _first(raw, "Composite:AvgBitrate", "QuickTime:AvgBitrate")

    audio: dict[str, Any] | None = None
    if audio_group:
        audio_format, audio_format_tag = _first(raw, f"{audio_group}:AudioFormat")
        audio = {
            "track_group": audio_group,
            "codec_id": audio_format,
            "codec": _audio_codec_label(audio_format),
            "sample_rate_hz": _integer(raw.get(f"{audio_group}:AudioSampleRate")),
            "channels": _integer(raw.get(f"{audio_group}:AudioChannels")),
            "bits_per_sample": _integer(raw.get(f"{audio_group}:AudioBitsPerSample")),
            "source_tags": {
                "codec": audio_format_tag,
                "sample_rate": f"{audio_group}:AudioSampleRate",
                "channels": f"{audio_group}:AudioChannels",
            },
        }

    timecode_value, timecode_tag = _first(
        raw,
        *(f"{group}:StartTimecode" for group in timecode_groups),
        *(f"{group}:TimeCode" for group in timecode_groups),
        "QuickTime:StartTimecode",
        "QuickTime:TimeCode",
    )
    timecode_rate = None
    if timecode_group:
        timecode_rate = _rate(
            raw.get(f"{timecode_group}:PlaybackFrameRate")
            or raw.get(f"{timecode_group}:VideoFrameRate")
        )

    camera_make, camera_make_tag = _first(raw, "IFD0:Make", "UserData:Make")
    camera_model, camera_model_tag = _first(raw, "IFD0:Model", "UserData:Model")
    serial, serial_tag = _first(raw, "ExifIFD:SerialNumber", "Canon:InternalSerialNumber")
    lens_model, lens_model_tag = _first(raw, "ExifIFD:LensModel", "Canon:LensModel")
    lens_serial, lens_serial_tag = _first(
        raw, "ExifIFD:LensSerialNumber", "Canon:LensSerialNumber"
    )

    warnings: list[str] = []
    capture_time = _capture_time(raw)
    if capture_time is None:
        warnings.append("capture_time_missing")
    elif capture_time["timezone_status"] == "unspecified":
        warnings.append("capture_timezone_unspecified")
    if duration_seconds is None or duration_seconds <= 0:
        warnings.append("duration_missing_or_invalid")
    if width is None or height is None or width <= 0 or height <= 0:
        warnings.append("video_dimensions_missing_or_invalid")
    if frame_rate is None:
        warnings.append("frame_rate_missing_or_invalid")
    if compressor_value is None:
        warnings.append("video_codec_missing")
    if audio is None:
        warnings.append("audio_track_missing")
    if timecode_group and timecode_value is None:
        warnings.append("timecode_track_without_readable_start")

    required_errors = {
        "duration_missing_or_invalid",
        "video_dimensions_missing_or_invalid",
        "frame_rate_missing_or_invalid",
        "video_codec_missing",
    }
    status = "error" if required_errors.intersection(warnings) else ("warning" if warnings else "success")

    return {
        "status": status,
        "capture_time": capture_time,
        "duration_seconds": round(duration_seconds, 6) if duration_seconds is not None else None,
        "video": {
            "track_group": video_group,
            "track_count": len(video_groups),
            "width": width,
            "height": height,
            "display_width": display_width,
            "display_height": display_height,
            "rotation_degrees": rotation,
            "frame_rate": frame_rate,
            "codec_id": compressor_value,
            "codec": _codec_label(compressor_value),
            "average_bitrate_bps": _integer(bitrate_value),
            "bit_depth": _integer(raw.get(f"{video_group}:BitDepth")) if video_group else None,
            "color": {
                "profile": raw.get(f"{video_group}:ColorProfiles") if video_group else None,
                "primaries": _coded_value(
                    raw.get(f"{video_group}:ColorPrimaries") if video_group else None,
                    {1: "BT.709", 9: "BT.2020"},
                ),
                "transfer": _coded_value(
                    raw.get(f"{video_group}:TransferCharacteristics") if video_group else None,
                    {1: "BT.709", 16: "PQ (ST 2084)", 18: "HLG"},
                ),
                "matrix": _coded_value(
                    raw.get(f"{video_group}:MatrixCoefficients") if video_group else None,
                    {1: "BT.709", 9: "BT.2020 non-constant"},
                ),
                "full_range": (
                    bool(_integer(raw.get(f"{video_group}:VideoFullRangeFlag")))
                    if video_group
                    and _integer(raw.get(f"{video_group}:VideoFullRangeFlag")) is not None
                    else None
                ),
            },
            "source_tags": {
                "duration": duration_tag,
                "width": width_tag,
                "height": height_tag,
                "rotation": rotation_tag,
                "frame_rate": frame_rate_tag,
                "codec": compressor_tag,
                "bitrate": bitrate_tag,
            },
        },
        "audio": audio,
        "timecode": {
            "track_present": bool(timecode_groups),
            "track_group": timecode_group,
            "start": timecode_value,
            "frame_rate": timecode_rate,
            "source_tag": timecode_tag,
        },
        "camera": {
            "make": camera_make,
            "model": camera_model,
            "serial_number": serial,
            "lens_model": lens_model,
            "lens_serial_number": lens_serial,
            "source_tags": {
                "make": camera_make_tag,
                "model": camera_model_tag,
                "serial_number": serial_tag,
                "lens_model": lens_model_tag,
                "lens_serial_number": lens_serial_tag,
            },
        },
        "container": {
            "file_type": raw.get("File:FileType"),
            "mime_type": raw.get("File:MIMEType"),
            "major_brand": raw.get("QuickTime:MajorBrand"),
            "compatible_brands": raw.get("QuickTime:CompatibleBrands"),
        },
        "warnings": warnings,
    }


def _validate_scan_report(report: dict[str, Any]) -> tuple[Path, list[dict[str, Any]]]:
    if not isinstance(report, dict):
        raise MetadataManifestError("Manifest root must be a JSON object")
    project = report.get("project")
    inventory = report.get("inventory")
    if not isinstance(project, dict) or not isinstance(inventory, dict):
        raise MetadataManifestError("Manifest must contain project and inventory objects")
    root_value = project.get("hotel_root")
    media = inventory.get("media")
    if not isinstance(root_value, str) or not isinstance(media, list):
        raise MetadataManifestError("Manifest must contain hotel_root and inventory.media")
    root = Path(root_value).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise MetadataManifestError(f"Hotel root is not a directory: {root}")
    if not all(isinstance(item, dict) for item in media):
        raise MetadataManifestError("Every inventory.media entry must be an object")
    return root, media


def _capture_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    metadata = item.get("technical_metadata") or {}
    capture_time = metadata.get("capture_time") or {}
    value = capture_time.get("value") or item.get("modified_time_utc") or "9999-12-31T23:59:59"
    wall_clock = re.sub(r"(?:Z|[+-]\d{2}:\d{2})$", "", str(value))
    return wall_clock, str(item.get("relative_path", "")).casefold()


def _assign_capture_order(media: list[dict[str, Any]]) -> None:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in media:
        by_category[str(item.get("category", "unclassified"))].append(item)
    for items in by_category.values():
        for index, item in enumerate(sorted(items, key=_capture_sort_key), start=1):
            item["capture_order"] = index


def _count_key(value: Any, fallback: str = "unknown") -> str:
    return str(value) if value not in (None, "") else fallback


def _summarize(media: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    processed = [item for item in media if isinstance(item.get("technical_metadata"), dict)]
    frame_rates: Counter[str] = Counter()
    resolutions: Counter[str] = Counter()
    codecs: Counter[str] = Counter()
    camera_models: Counter[str] = Counter()
    capture_sources: Counter[str] = Counter()
    warning_codes: Counter[str] = Counter()
    total_duration = 0.0
    audio_tracks = 0
    timecode_tracks = 0

    for item in processed:
        metadata = item["technical_metadata"]
        duration = _number(metadata.get("duration_seconds"))
        total_duration += duration or 0.0
        video = metadata.get("video") or {}
        rate = video.get("frame_rate") or {}
        fps = rate.get("fps")
        if fps is not None:
            frame_rates[f"{float(fps):g}"] += 1
        width, height = video.get("width"), video.get("height")
        if width and height:
            resolutions[f"{width}x{height}"] += 1
        codecs[_count_key(video.get("codec"))] += 1
        camera = metadata.get("camera") or {}
        camera_models[_count_key(camera.get("model"))] += 1
        capture = metadata.get("capture_time") or {}
        capture_sources[_count_key(capture.get("source_tag"), "missing")] += 1
        if metadata.get("audio"):
            audio_tracks += 1
        if (metadata.get("timecode") or {}).get("track_present"):
            timecode_tracks += 1
        warning_codes.update(metadata.get("warnings") or [])

    return {
        "files_requested": len(media),
        "files_read": len(processed),
        "files_failed": len(failures),
        "total_duration_seconds": round(total_duration, 6),
        "frame_rate_counts": dict(sorted(frame_rates.items())),
        "resolution_counts": dict(sorted(resolutions.items())),
        "video_codec_counts": dict(sorted(codecs.items())),
        "camera_model_counts": dict(sorted(camera_models.items())),
        "capture_time_source_counts": dict(sorted(capture_sources.items())),
        "audio_track_present": audio_tracks,
        "audio_track_missing": len(processed) - audio_tracks,
        "timecode_track_present": timecode_tracks,
        "warning_counts": dict(sorted(warning_codes.items())),
    }


def enrich_scan_report(
    scan_report: dict[str, Any],
    *,
    exiftool_path: Path | None = None,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Return a metadata-enriched copy of a Stage 1.1 scan report."""
    root, source_media = _validate_scan_report(scan_report)
    report = copy.deepcopy(scan_report)
    media: list[dict[str, Any]] = report["inventory"]["media"]
    executable = resolve_exiftool_path(exiftool_path)
    version = exiftool_version(executable)

    valid_paths: list[Path] = []
    failures: list[dict[str, Any]] = []
    media_by_path: dict[str, dict[str, Any]] = {}
    for source_item, item in zip(source_media, media, strict=True):
        absolute_path = source_item.get("absolute_path")
        if not isinstance(absolute_path, str):
            failures.append({"media_id": item.get("media_id"), "error": "absolute_path_missing"})
            continue
        path = Path(absolute_path).expanduser().resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError:
            failures.append(
                {
                    "media_id": item.get("media_id"),
                    "relative_path": item.get("relative_path"),
                    "error": "path_outside_hotel_root",
                }
            )
            continue
        if not path.is_file():
            failures.append(
                {
                    "media_id": item.get("media_id"),
                    "relative_path": item.get("relative_path"),
                    "error": "source_file_missing",
                }
            )
            continue
        expected_size = source_item.get("size_bytes")
        if isinstance(expected_size, int) and path.stat().st_size != expected_size:
            failures.append(
                {
                    "media_id": item.get("media_id"),
                    "relative_path": item.get("relative_path"),
                    "error": "source_size_changed_since_scan",
                }
            )
            continue
        canonical = _canonical_path(path)
        if canonical in media_by_path:
            raise MetadataManifestError(f"Duplicate absolute_path in manifest: {path}")
        valid_paths.append(path)
        media_by_path[canonical] = item

    raw_items, tool_messages = read_exiftool_json(
        executable, valid_paths, timeout_seconds=timeout_seconds
    )
    returned_paths: set[str] = set()
    for raw in raw_items:
        source_file = raw.get("SourceFile")
        if not isinstance(source_file, str):
            continue
        canonical = _canonical_path(source_file)
        item = media_by_path.get(canonical)
        if item is None:
            failures.append({"source_file": source_file, "error": "unexpected_exiftool_result"})
            continue
        returned_paths.add(canonical)
        error_value, _ = _first(raw, "ExifTool:Error", "System:Error", "Error")
        if error_value is not None:
            failures.append(
                {
                    "media_id": item.get("media_id"),
                    "relative_path": item.get("relative_path"),
                    "error": str(error_value),
                }
            )
            continue
        item["technical_metadata"] = normalize_metadata(raw)

    for canonical, item in media_by_path.items():
        if canonical not in returned_paths:
            failures.append(
                {
                    "media_id": item.get("media_id"),
                    "relative_path": item.get("relative_path"),
                    "error": "no_exiftool_result",
                }
            )

    _assign_capture_order(media)
    summary = _summarize(media, failures)
    warning_counts = summary["warning_counts"]
    report["schema_version"] = METADATA_SCHEMA_VERSION
    report["pipeline"] = {
        "stage": "metadata",
        "status": "error"
        if failures
        else ("warning" if warning_counts or tool_messages else "success"),
    }
    report["metadata_audit"] = {
        "tool": {
            "name": "ExifTool",
            "version": version,
            "executable": str(executable),
            "invocation": "single_process_utf8_argfile",
        },
        "summary": summary,
        "failures": failures,
        "tool_messages": tool_messages,
        "ordering_policy": {
            "field": "capture_order",
            "scope": "within_category",
            "basis": "capture wall-clock timestamp, then relative_path",
            "creative_edit_order_assigned": False,
        },
    }
    previous_warnings = [
        warning
        for warning in report.get("warnings", [])
        if isinstance(warning, dict) and warning.get("code") != "metadata_warnings"
    ]
    if warning_counts:
        previous_warnings.append({"code": "metadata_warnings", "counts": warning_counts})
    if failures:
        previous_warnings.append({"code": "metadata_failures", "count": len(failures)})
    report["warnings"] = previous_warnings
    return report


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MetadataManifestError(f"Manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MetadataManifestError(f"Manifest is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise MetadataManifestError("Manifest root must be a JSON object")
    return payload
