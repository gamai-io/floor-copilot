"""Evidence-gate tests. No model or network required."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evidence  # noqa: E402
import inspect_part  # noqa: E402
import invoice_extract  # noqa: E402


def _vision(payload: dict | str):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return {"via": "mock", "model": "mock", "raw": {"choices": [{"message": {"content": content}}]}}


VALID = {
    "supplier": "MOCK DOBAVLJAC DOO",
    "invoice_no": "MOCK-001",
    "date": "2026-10-20",
    "currency": "BAM",
    "items": [{"code": "R600", "name": "Rukavice 600mm", "qty": 4,
               "unit_price": 12.50, "line_total": 50.00}],
    "net_total": 50.00, "vat": 8.50, "total": 58.50,
}


class FlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old = evidence.DB
        evidence.DB = Path(self.tmp.name) / "evidence.sqlite3"

    def tearDown(self) -> None:
        evidence.DB = self.old
        self.tmp.cleanup()

    def test_invoice_verified_and_hashed(self) -> None:
        with patch("meta_adapter.vision", return_value=_vision(VALID)):
            out = invoice_extract.extract(b"image-bytes")
        self.assertEqual(out["verdict"], "verified", out)
        self.assertEqual(out["problems"], [])
        row = evidence.get(out["evidence_id"], out["evidence_key"])
        self.assertEqual(row["kind"], "invoice")
        self.assertEqual(row["verdict"], "verified")
        self.assertEqual(row["sha256"], evidence.sha256_bytes(b"image-bytes"))
        self.assertIsNone(evidence.get(out["evidence_id"], "wrong-token"))

    def test_line_total_mismatch_fails_closed(self) -> None:
        bad = json.loads(json.dumps(VALID))
        bad["items"][0]["line_total"] = 49.00
        with patch("meta_adapter.vision", return_value=_vision(bad)):
            out = invoice_extract.extract(b"img")
        self.assertEqual(out["verdict"], "unverified")
        self.assertTrue(any("line_total" in p for p in out["problems"]))

    def test_missing_totals_are_computed(self) -> None:
        data = json.loads(json.dumps(VALID))
        data["net_total"] = data["vat"] = data["total"] = None
        with patch("meta_adapter.vision", return_value=_vision(data)):
            out = invoice_extract.extract(b"img")
        self.assertEqual(out["verdict"], "verified")
        self.assertTrue(out.get("computed_totals"))
        self.assertAlmostEqual(out["total"], 58.50)

    def test_fenced_json_is_parsed(self) -> None:
        text = "```json\n" + json.dumps(VALID) + "\n```"
        with patch("meta_adapter.vision", return_value=_vision(text)):
            out = invoice_extract.extract(b"img")
        self.assertEqual(out["verdict"], "verified")

    def test_unparseable_output_fails_closed(self) -> None:
        with patch("meta_adapter.vision", return_value=_vision("not json at all")):
            out = invoice_extract.extract(b"img")
        self.assertEqual(out["verdict"], "unverified")
        self.assertIn("no items", out["problems"])

    def test_inspection_without_masks_is_unverified(self) -> None:
        seg = {"via": "local", "model": "none", "raw": {"masks": []}}
        with patch("meta_adapter.segment", return_value=seg), \
             patch("meta_adapter.chat", return_value=_vision("no damage detected")):
            out = inspect_part.inspect(b"part")
        self.assertEqual(out["verdict"], "unverified")
        self.assertEqual(out["masks"], 0)

    def test_inspection_with_mask_is_verified(self) -> None:
        seg = {"via": "meta", "model": "sam", "raw": {"masks": [{"bbox": [1, 2, 3, 4]}]}}
        with patch("meta_adapter.segment", return_value=seg), \
             patch("meta_adapter.chat", return_value=_vision("crack visible")):
            out = inspect_part.inspect(b"part")
        self.assertEqual(out["verdict"], "verified")
        self.assertEqual(out["masks"], 1)


if __name__ == "__main__":
    unittest.main()
