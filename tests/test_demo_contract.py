from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DemoContractTests(unittest.TestCase):
    def test_required_demo_documents_exist(self) -> None:
        required = (
            "README.md",
            "CHANGELOG.md",
            "docs/ARCHITECTURE.md",
            "docs/DEMO_RUNBOOK.md",
            "docs/PROJECT_MEMORY.md",
            "docs/REPOSITORY_MAP.md",
            "hotelcut.cmd",
            "hotelcut.ps1",
            "project_status.json",
            "tools/install_ffmpeg.ps1",
            "vendor/ffmpeg/README.md",
        )
        for relative in required:
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)

    def test_public_reports_do_not_expose_local_root_or_serial_values(self) -> None:
        for name in ("olymp-iv-scan.json", "olymp-iv-metadata.json"):
            text = (PROJECT_ROOT / "outputs" / name).read_text(encoding="utf-8")
            self.assertNotIn("C:\\\\Users\\\\SAN-VK", text)

        report = json.loads(
            (PROJECT_ROOT / "outputs" / "olymp-iv-metadata.json").read_text(
                encoding="utf-8"
            )
        )
        for item in report["inventory"]["media"]:
            camera = item["technical_metadata"]["camera"]
            self.assertIsNone(camera["serial_number"])
            self.assertIsNone(camera["lens_serial_number"])

    def test_project_status_is_valid_demo_state(self) -> None:
        status = json.loads(
            (PROJECT_ROOT / "project_status.json").read_text(encoding="utf-8")
        )
        self.assertEqual(status["project"], "SANATORIUMS MEDIA OS / HOTELCUT")
        self.assertEqual(status["current_stage"], 1)
        self.assertEqual(status["approved_steps"], ["1.1", "1.2"])


if __name__ == "__main__":
    unittest.main()
