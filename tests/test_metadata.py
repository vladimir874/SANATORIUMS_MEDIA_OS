from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hotelcut.metadata import (  # noqa: E402
    MetadataManifestError,
    _write_exiftool_argfile,
    enrich_scan_report,
    normalize_metadata,
)


class MetadataTests(unittest.TestCase):
    def test_normalizes_canon_video_audio_timecode_and_capture_timezone(self) -> None:
        raw = {
            "SourceFile": "C:/hotel/1_подводки/clip.mp4",
            "Composite:SubSecDateTimeOriginal": "2026:06:09 14:28:15.44+01:00",
            "QuickTime:Duration": 126.32,
            "Composite:AvgBitrate": 58_851_185,
            "Composite:Rotation": 0,
            "Track1:HandlerType": "vide",
            "Track1:ImageWidth": 1920,
            "Track1:ImageHeight": 1080,
            "Track1:VideoFrameRate": 50,
            "Track1:CompressorID": "avc1",
            "Track1:BitDepth": 24,
            "Track1:ColorPrimaries": 1,
            "Track1:TransferCharacteristics": 1,
            "Track1:MatrixCoefficients": 1,
            "Track1:VideoFullRangeFlag": 1,
            "Track2:HandlerType": "soun",
            "Track2:AudioFormat": "twos",
            "Track2:AudioSampleRate": 48000,
            "Track2:AudioChannels": 2,
            "Track2:AudioBitsPerSample": 16,
            "Track3:HandlerType": "tmcd",
            "Track3:OtherFormat": "tmcd",
            "Track3:PlaybackFrameRate": 50,
            "IFD0:Make": "Canon",
            "IFD0:Model": "Canon EOS R6m2",
            "ExifIFD:LensModel": "RF14-35mm F4 L IS USM",
        }

        metadata = normalize_metadata(raw)

        self.assertEqual(metadata["capture_time"]["value"], "2026-06-09T14:28:15.440000+01:00")
        self.assertEqual(metadata["capture_time"]["utc"], "2026-06-09T13:28:15.440000+00:00")
        self.assertEqual(metadata["video"]["codec"], "H.264/AVC")
        self.assertEqual(metadata["video"]["frame_rate"]["numerator"], 50)
        self.assertEqual(metadata["video"]["color"]["primaries"]["label"], "BT.709")
        self.assertEqual(metadata["audio"]["sample_rate_hz"], 48000)
        self.assertTrue(metadata["timecode"]["track_present"])
        self.assertIn("timecode_track_without_readable_start", metadata["warnings"])

    def test_normalizes_dji_hevc_and_preserves_unspecified_timezone(self) -> None:
        raw = {
            "SourceFile": "C:/hotel/2_экстерьер/drone.mp4",
            "QuickTime:CreateDate": "2026:06:08 08:24:36",
            "QuickTime:Duration": 49.9832666666667,
            "Composite:AvgBitrate": 74_291_609,
            "Track1:HandlerType": "vide",
            "Track1:ImageWidth": 3840,
            "Track1:ImageHeight": 2160,
            "Track1:VideoFrameRate": 59.9400599400599,
            "Track1:CompressorID": "hvc1",
            "Track1:ColorPrimaries": 1,
            "Track1:TransferCharacteristics": 1,
            "Track1:MatrixCoefficients": 1,
            "Track1:VideoFullRangeFlag": 0,
        }

        metadata = normalize_metadata(raw)

        self.assertEqual(metadata["capture_time"]["value"], "2026-06-08T08:24:36")
        self.assertIsNone(metadata["capture_time"]["utc"])
        self.assertEqual(metadata["capture_time"]["timezone_status"], "unspecified")
        self.assertEqual(metadata["video"]["codec"], "H.265/HEVC")
        self.assertEqual(metadata["video"]["frame_rate"]["numerator"], 60000)
        self.assertEqual(metadata["video"]["frame_rate"]["denominator"], 1001)
        self.assertIsNone(metadata["audio"])
        self.assertIn("audio_track_missing", metadata["warnings"])

    def test_utf8_argfile_keeps_cyrillic_path_unquoted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            argument_file = Path(temporary_directory) / "args.txt"
            media_path = Path("C:/Видео/Санаторий/кадр 01.mp4")
            _write_exiftool_argfile(argument_file, [media_path])
            text = argument_file.read_text(encoding="utf-8")
            self.assertIn("filename=UTF8", text)
            self.assertIn("C:\\Видео\\Санаторий\\кадр 01.mp4", text)
            self.assertNotIn('"C:\\Видео', text)

    def test_enrichment_rejects_path_outside_hotel_root_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "hotel"
            root.mkdir()
            outside = Path(temporary_directory) / "outside.mp4"
            outside.write_bytes(b"video")
            report = {
                "schema_version": "1.0.0",
                "project": {"hotel_root": str(root), "hotel_id": "TEST"},
                "pipeline": {"stage": "scan", "status": "success"},
                "inventory": {
                    "media_files_count": 1,
                    "media": [
                        {
                            "media_id": "media_1",
                            "absolute_path": str(outside),
                            "relative_path": "outside.mp4",
                            "category": "exterior",
                            "size_bytes": outside.stat().st_size,
                        }
                    ],
                },
                "warnings": [],
            }

            with (
                patch("hotelcut.metadata.resolve_exiftool_path", return_value=Path("exiftool")),
                patch("hotelcut.metadata.exiftool_version", return_value="13.59"),
                patch("hotelcut.metadata.read_exiftool_json", return_value=([], [])) as reader,
            ):
                enriched = enrich_scan_report(report)

            reader.assert_called_once_with(Path("exiftool"), [], timeout_seconds=600)
            self.assertEqual(enriched["metadata_audit"]["summary"]["files_failed"], 1)
            self.assertEqual(
                enriched["metadata_audit"]["failures"][0]["error"],
                "path_outside_hotel_root",
            )

    def test_manifest_with_duplicate_paths_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "hotel"
            root.mkdir()
            clip = root / "clip.mp4"
            clip.write_bytes(b"video")
            item = {
                "media_id": "media_1",
                "absolute_path": str(clip),
                "relative_path": "clip.mp4",
                "category": "exterior",
                "size_bytes": clip.stat().st_size,
            }
            report = {
                "project": {"hotel_root": str(root)},
                "inventory": {"media": [item, {**item, "media_id": "media_2"}]},
            }
            with (
                patch("hotelcut.metadata.resolve_exiftool_path", return_value=Path("exiftool")),
                patch("hotelcut.metadata.exiftool_version", return_value="13.59"),
                self.assertRaises(MetadataManifestError),
            ):
                enrich_scan_report(report)


if __name__ == "__main__":
    unittest.main()
