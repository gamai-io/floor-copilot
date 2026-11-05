#!/usr/bin/env python3
"""Tesseract OCR + Floor Copilot gate on 15 synthetic GAMA-style invoices."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evidence  # noqa: E402
import invoice_extract  # noqa: E402

HERE = Path(__file__).resolve().parent
IMAGES = HERE / "images"
TRUTH = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
ITEM_RE = re.compile(r"^([A-Z0-9-]+)\s+(.+?)\s+(\d+)\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s*$")


def bhs(s: str) -> float:
    return float(str(s).replace(".", "").replace(",", "."))


def ocr(path: Path) -> str:
    p = subprocess.run(["tesseract", str(path), "stdout", "-l", "bos", "--psm", "6"],
                       capture_output=True, text=True, timeout=45)
    return p.stdout or ""


def parse(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    supplier = None
    for line in lines:
        if "GAMA TRADE" in line or "GAMA TRDE" in line:
            supplier = line.split("FAKTURA")[0].strip()
            break
    inv = re.search(r"Broj:\s*(\S+)", text)
    date = re.search(r"Datum:\s*(\S+)", text)
    items = []
    for line in lines:
        m = ITEM_RE.match(line)
        if m:
            items.append({"code": m.group(1), "name": m.group(2).strip(),
                          "qty": int(m.group(3)), "unit_price": bhs(m.group(4)),
                          "line_total": bhs(m.group(5))})
    def total(label):
        m = re.search(label + r"\s*:?\s*([\d.]+,\d{2})\s*BAM", text)
        return bhs(m.group(1)) if m else None
    return {
        "supplier": supplier,
        "invoice_no": inv.group(1) if inv else None,
        "date": date.group(1) if date else None,
        "currency": "BAM",
        "items": items,
        "net_total": total("Neto"),
        "vat": total("PDV 17%"),
        "total": total("UKUPNO"),
    }


def vision(payload: dict) -> dict:
    content = json.dumps(payload, ensure_ascii=False)
    return {"via": "tesseract", "model": "tesseract-bos",
            "raw": {"choices": [{"message": {"content": content}}]}}


def norm(s) -> str:
    return " ".join(str(s or "").lower().replace(".", "").split())


def close(a, b, tol=0.02) -> bool:
    try:
        return abs(Decimal(str(a)) - Decimal(str(b))) <= Decimal(str(tol))
    except Exception:
        return False


def compare(truth: dict, out: dict) -> dict:
    data = truth["data"]
    items = out.get("items") or []
    line_ok = sum(1 for got, want in zip(items, data["items"])
                  if close(got.get("qty"), want["qty"]) and close(got.get("unit_price"), want["unit_price"])
                  and close(got.get("line_total"), want["line_total"]))
    totals = {}
    for k in ("net_total", "vat", "total"):
        if data[k] is None:
            totals[k] = out.get(k) is None
        else:
            totals[k] = close(out.get(k), data[k])
    return {"supplier_exact": norm(out.get("supplier")) == norm(data["supplier"]),
            "invoice_no_exact": str(out.get("invoice_no")) == str(data["invoice_no"]),
            "item_count_exact": len(items) == len(data["items"]),
            "items_exact": line_ok, "items_total": len(data["items"]),
            "totals": totals}


def main() -> int:
    tmp = tempfile.TemporaryDirectory()
    old = evidence.DB
    evidence.DB = Path(tmp.name) / "evidence.sqlite3"
    cases = []
    t0 = time.time()
    for truth in TRUTH:
        image = IMAGES / truth["image"]
        started = time.time()
        try:
            text = ocr(image)
            payload = parse(text)
            with patch("meta_adapter.vision", return_value=vision(payload)):
                out = invoice_extract.extract(image.read_bytes())
            err = None
        except Exception as exc:
            text = ""
            payload = {}
            out = {"verdict": "unverified", "problems": ["ocr_error: %s" % exc]}
            err = "%s: %s" % (type(exc).__name__, exc)
        cases.append({
            "image": truth["image"], "scenario": truth["scenario"],
            "expected": truth["expected"], "verdict": out.get("verdict"),
            "computed_totals": bool(out.get("computed_totals")),
            "problems": out.get("problems", []),
            "parsed": payload, "ocr_chars": len(text),
            "compare": compare(truth, payload) if payload else {},
            "seconds": round(time.time() - started, 2), "ocr_error": err,
        })
    evidence.DB = old
    elapsed = round(time.time() - t0, 2)
    by = {}
    for c in cases:
        by.setdefault(c["scenario"], []).append(c)
    arithmetic = [c for c in cases if c["scenario"] in ("line_total", "net_total", "vat", "total")]
    valid = by.get("valid", [])
    metrics = {
        "cases": len(cases), "elapsed_s": elapsed,
        "ocr_parsed": sum(1 for c in cases if not c["ocr_error"]),
        "valid_verified": sum(1 for c in valid if c["verdict"] == "verified"),
        "valid_total": len(valid),
        "arithmetic_caught": sum(1 for c in arithmetic if c["verdict"] == "unverified"),
        "arithmetic_false_verified": sum(1 for c in arithmetic if c["verdict"] == "verified"),
        "arithmetic_total": len(arithmetic),
        "missing_totals_verified": sum(1 for c in by.get("missing_totals", []) if c["verdict"] == "verified"),
        "missing_totals_total": len(by.get("missing_totals", [])),
        "supplier_typo_verified": sum(1 for c in by.get("supplier_typo", []) if c["verdict"] == "verified"),
        "supplier_typo_total": len(by.get("supplier_typo", [])),
        "low_quality_verdict": (by.get("low_quality", [{}])[0].get("verdict")),
        "supplier_exact": sum(1 for c in cases if c["compare"].get("supplier_exact")),
        "invoice_no_exact": sum(1 for c in cases if c["compare"].get("invoice_no_exact")),
        "items_exact": sum(c["compare"].get("items_exact", 0) for c in cases),
        "items_total": sum(c["compare"].get("items_total", 0) for c in cases),
    }
    result = {"generated": "2026-11-05", "ocr": "tesseract 5 (-l bos, psm 6)",
              "method": "15 synthetic GAMA-style invoices -> tesseract OCR -> real invoice_extract arithmetic gate",
              "caveat": "Synthetic documents, not real customer invoices. Supplier-name correctness is not enforced by the gate.",
              "metrics": metrics, "cases": cases}
    (HERE / "results_tesseract.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = f"""# Floor Copilot — GAMA-style synthetic invoices (Tesseract OCR)

**Date:** 2026-11-05  
**Documents:** 15 synthetic GAMA-style invoices (PNG)  
**OCR:** Tesseract 5, `bos`, psm 6  
**Gate:** real `invoice_extract` arithmetic gate

> **Caveat:** synthetic documents, not real customer invoices. The gate checks arithmetic, not supplier transcription.

## Results

| Metric | Result |
|---|---|
| Cases | {metrics['cases']} |
| OCR parsed | {metrics['ocr_parsed']}/{metrics['cases']} |
| Valid invoices verified | {metrics['valid_verified']}/{metrics['valid_total']} |
| Arithmetic errors caught | {metrics['arithmetic_caught']}/{metrics['arithmetic_total']} |
| **False verifications (arithmetic)** | **{metrics['arithmetic_false_verified']}** |
| Missing totals verified/computed | {metrics['missing_totals_verified']}/{metrics['missing_totals_total']} |
| Supplier typo still verified | {metrics['supplier_typo_verified']}/{metrics['supplier_typo_total']} |
| Low-quality image verdict | {metrics['low_quality_verdict']} |
| Supplier exact / cases | {metrics['supplier_exact']}/{metrics['cases']} |
| Invoice no exact / cases | {metrics['invoice_no_exact']}/{metrics['cases']} |
| Item lines exact | {metrics['items_exact']}/{metrics['items_total']} |
| Elapsed | {elapsed}s |

## Interpretation
- OCR is real (Tesseract), but the documents are synthetic and the layout is controlled.
- The number that matters: **false verifications on arithmetic errors** (must be 0).
- Supplier-name errors can still pass because the gate does not check the supplier; this is the documented field-level gap.
- A low-quality image may be refused (`unverified`); that is acceptable. Fabricating `verified` is not.

Per-case results: `results_tesseract.json`.
"""
    (HERE / "RESULTS_TESSERACT.md").write_text(md, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
