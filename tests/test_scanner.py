from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hotelcut.scanner import load_folder_config, scan_hotel, write_json_atomic  # noqa: E402


class ScannerTests(unittest.TestCase):
    def test_editable_and_packaged_folder_maps_match(self) -> None:
        editable = load_folder_config(PROJECT_ROOT / "config" / "folder_map.json")
        packaged = load_folder_config(PROJECT_ROOT / "src" / "hotelcut" / "data" / "folder_map.json")
        self.assertEqual(editable["category_order"], packaged["category_order"])
        self.assertEqual(editable["alias_lookup"], packaged["alias_lookup"])
        self.assertEqual(editable["excluded_lookup"], packaged["excluded_lookup"])

    def test_scans_unicode_tree_and_excludes_generated_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "Отель Тест"
            (root / "2_экстерьер").mkdir(parents=True)
            (root / "3_двухместный_номер" / "ванная").mkdir(parents=True)
            (root / "2_экстерьер_дрон").mkdir(parents=True)
            (root / "неизвестная папка").mkdir(parents=True)
            (root / "proxies").mkdir(parents=True)
            (root / "outbox").mkdir(parents=True)

            (root / "2_экстерьер" / "ФАСАД.MP4").write_bytes(b"video-a")
            (root / "3_двухместный_номер" / "ванная" / "кадр.mov").write_bytes(b"video-b")
            (root / "неизвестная папка" / "звук.WAV").write_bytes(b"audio")
            (root / "proxies" / "ignored.mp4").write_bytes(b"proxy")
            (root / "outbox" / "ignored.jpg").write_bytes(b"output")
            (root / "notes.txt").write_text("skip", encoding="utf-8")

            report = scan_hotel(root, hotel_id="HOTEL-001")

            self.assertEqual(report["project"]["hotel_id"], "HOTEL-001")
            self.assertEqual(report["inventory"]["media_files_count"], 3)
            self.assertEqual(report["inventory"]["counts_by_type"], {"audio": 1, "video": 2})
            self.assertEqual(report["inventory"]["counts_by_category"]["exterior"], 1)
            self.assertEqual(report["inventory"]["counts_by_category"]["rooms"], 1)
            self.assertEqual(report["inventory"]["counts_by_category"]["unclassified"], 1)
            self.assertEqual(report["source_structure"]["unknown_folders"], ["неизвестная папка"])
            self.assertIn("2_экстерьер_дрон", report["source_structure"]["empty_media_folders"])
            self.assertNotIn("proxies/ignored.mp4", json.dumps(report, ensure_ascii=False))
            self.assertNotIn("outbox/ignored.jpg", json.dumps(report, ensure_ascii=False))

    def test_asset_id_is_deterministic_but_fingerprint_detects_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "hotel"
            folder = root / "2_интерьер"
            folder.mkdir(parents=True)
            media_path = folder / "clip.mp4"
            media_path.write_bytes(b"first")

            first = scan_hotel(root)["inventory"]["media"][0]
            original_mtime_ns = media_path.stat().st_mtime_ns
            media_path.write_bytes(b"other")
            os.utime(media_path, ns=(original_mtime_ns, original_mtime_ns))
            second = scan_hotel(root)["inventory"]["media"][0]

            self.assertEqual(first["media_id"], second["media_id"])
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_nested_standard_dining_folders_are_classified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "hotel"
            for meal in ("завтрак", "обед", "ужин"):
                folder = root / "Питание" / meal
                folder.mkdir(parents=True)
                (folder / f"{meal}.mp4").write_bytes(meal.encode("utf-8"))

            report = scan_hotel(root)

            self.assertEqual(report["inventory"]["counts_by_category"]["dining_breakfast"], 1)
            self.assertEqual(report["inventory"]["counts_by_category"]["dining_lunch"], 1)
            self.assertEqual(report["inventory"]["counts_by_category"]["dining_dinner"], 1)
            self.assertEqual(report["source_structure"]["recognized_folders"][0]["category"], "grouped")

    def test_atomic_writer_produces_valid_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "outbox" / "project.json"
            write_json_atomic({"hotel": "Олимп"}, output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"hotel": "Олимп"})
            self.assertEqual(list(output.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
