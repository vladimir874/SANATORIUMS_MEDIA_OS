from __future__ import annotations

import json
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hotelcut.scanner import _fingerprint  # noqa: E402


SCAN_REPORT = PROJECT_ROOT / "outputs" / "olymp-iv-scan.json"
METADATA_REPORT = PROJECT_ROOT / "outputs" / "olymp-iv-metadata.json"


class OlympMetadataIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not SCAN_REPORT.is_file() or not METADATA_REPORT.is_file():
            raise unittest.SkipTest("Olymp IV reports are not available in this checkout")
        cls.scan = json.loads(SCAN_REPORT.read_text(encoding="utf-8"))
        cls.report = json.loads(METADATA_REPORT.read_text(encoding="utf-8"))
        cls.media = cls.report["inventory"]["media"]

    def test_scan_identity_fields_are_preserved(self) -> None:
        scanned_by_id = {item["media_id"]: item for item in self.scan["inventory"]["media"]}
        metadata_by_id = {item["media_id"]: item for item in self.media}

        self.assertEqual(len(scanned_by_id), 134)
        self.assertEqual(set(metadata_by_id), set(scanned_by_id))
        for media_id, scanned in scanned_by_id.items():
            enriched = metadata_by_id[media_id]
            for field in ("fingerprint", "relative_path", "size_bytes", "category"):
                self.assertEqual(enriched[field], scanned[field], f"{media_id}: {field}")

    def test_every_source_still_matches_scanned_size_and_fingerprint(self) -> None:
        for item in self.media:
            path = Path(item["absolute_path"])
            self.assertTrue(path.is_file(), item["relative_path"])
            size = path.stat().st_size
            self.assertEqual(size, item["size_bytes"], item["relative_path"])
            self.assertEqual(
                _fingerprint(path, size),
                item["fingerprint"],
                item["relative_path"],
            )

    def test_required_metadata_and_real_profiles(self) -> None:
        profiles: Counter[tuple[str, int, int, int, int]] = Counter()
        for item in self.media:
            metadata = item["technical_metadata"]
            video = metadata["video"]
            rate = video["frame_rate"]
            self.assertNotEqual(metadata["status"], "error", item["relative_path"])
            self.assertGreater(metadata["duration_seconds"], 0, item["relative_path"])
            self.assertGreater(video["width"], 0, item["relative_path"])
            self.assertGreater(video["height"], 0, item["relative_path"])
            self.assertTrue(video["codec"], item["relative_path"])
            self.assertTrue(metadata["capture_time"]["value"], item["relative_path"])
            self.assertAlmostEqual(
                rate["fps"],
                rate["numerator"] / rate["denominator"],
                places=5,
                msg=item["relative_path"],
            )
            profiles[
                (
                    video["codec"],
                    video["width"],
                    video["height"],
                    rate["numerator"],
                    rate["denominator"],
                )
            ] += 1

        self.assertEqual(
            profiles,
            Counter(
                {
                    ("H.264/AVC", 1920, 1080, 50, 1): 127,
                    ("H.265/HEVC", 3840, 2160, 60000, 1001): 7,
                }
            ),
        )

    def test_capture_order_is_contiguous_and_edit_order_is_absent(self) -> None:
        categories: dict[str, list[int]] = defaultdict(list)
        for item in self.media:
            self.assertNotIn("edit_order", item)
            categories[item["category"]].append(item["capture_order"])
        for category, orders in categories.items():
            self.assertEqual(
                sorted(orders),
                list(range(1, len(orders) + 1)),
                category,
            )

    def test_audit_summary_is_recomputed_from_media(self) -> None:
        summary = self.report["metadata_audit"]["summary"]
        durations = sum(item["technical_metadata"]["duration_seconds"] for item in self.media)
        warning_counts: Counter[str] = Counter()
        for item in self.media:
            warning_counts.update(item["technical_metadata"]["warnings"])

        self.assertEqual(summary["files_requested"], 134)
        self.assertEqual(summary["files_read"], 134)
        self.assertEqual(summary["files_failed"], 0)
        self.assertAlmostEqual(summary["total_duration_seconds"], durations, places=5)
        self.assertEqual(summary["audio_track_present"], 127)
        self.assertEqual(summary["audio_track_missing"], 7)
        self.assertEqual(summary["timecode_track_present"], 127)
        self.assertEqual(summary["warning_counts"], dict(sorted(warning_counts.items())))


if __name__ == "__main__":
    unittest.main()
