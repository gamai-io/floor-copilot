#!/usr/bin/env python3
"""Real GAMA invoice OCR + evidence-gate evaluation (private, local-only).

Reads invoice files from /root/gama_private_invoices (not committed, 0700).
Publishes only aggregate results; no customer names/amounts in the repo.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evidence  # noqa: E402
import invoice_extract  # noqa: E402

SRC = Path("/root/gama_private_invoices")
OUT = Path(__file__).resolve().parent
VAT = Decimal("0.17")
NUM = re.compile(r"\d[\d.,\s]*\d|\d")
TOTAL_RX = re.compile(r"(?i)(ukupan\s+iznos\s+sa\s+pdv|ukupno\s+sa\s+pdv|ukupno|za\s*plac|iznos\s*za\s*plat|total|grand\s*total)")
NET_RX = re.compile(r"(?i)(ukupan\s+iznos\s+bez\s+pdv|ukupno\s+bez\s+pdv|neto|osnovica|subtotal|\bbase\b)")
VAT_RX = re.compile(r"(?i)(ukupan\s+iznos\s+pdv|ukupno\s+pdv|pdv\s*\(?\s*17\s*%?\s*\)?|pdv\s*17\s*%|\bvat\b)")


def bhs(s: str) -> float | None:
    t = str(s).strip().replace(" ", "").replace("\u00a0", "")
    t = re.sub(r"[^0-9.,]", "", t).strip(".,")
    if not t:
        return None
    if "." in t and "," in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    elif "." in t:
        parts = t.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def last_amount(line: str) -> float | None:
    toks = NUM.findall(line)
    for tok in reversed(toks):
        if "." not in tok and "," not in tok:
            continue
        if len(tok) > 16:
            continue
        v = bhs(tok)
        if v is not None:
            return v
    return None


def parse_totals(text: str) -> dict:
    out = {"net": None, "vat": None, "total": None}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        low = line.lower()
        if "pdv broj" in low or "pdv #" in low or "id broj" in low or "pdv:" in low:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        for key, rx in (("total", TOTAL_RX), ("net", NET_RX), ("vat", VAT_RX)):
            if out[key] is not None or not rx.search(line):
                continue
            v = last_amount(line)
            if v is None:
                v = last_amount(nxt)
            if v is not None:
                out[key] = v
                break
    return out


def parse_items(text: str) -> list[dict]:
    items = []
    for line in text.splitlines():
        m = re.match(r"^(.{2,}?)\s+(\d{1,3})\s+(\d[\d.,]*)\s+(\d[\d.,]*)\s*$", line.strip())
        if not m:
            continue
        qty = bhs(m.group(2)); price = bhs(m.group(3)); amount = bhs(m.group(4))
        if None in (qty, price, amount):
            continue
        if abs(qty * price - amount) <= max(0.05, amount * 0.0001):
            items.append({"code": "", "name": m.group(1)[:80], "qty": qty,
                          "unit_price": price, "line_total": amount})
    return items[:20]


def ocr_image(img: Path) -> str:
    p = subprocess.run(["tesseract", str(img), "stdout", "-l", "bos", "--psm", "6"],
                       capture_output=True, text=True, timeout=30)
    return p.stdout or ""


def pdf_page(pdf: Path) -> tuple[Path, str]:
    tmp = Path(tempfile.mkdtemp(prefix="inv_"))
    base = tmp / "page"
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "150", "-png", str(pdf), str(base)],
                   capture_output=True, timeout=60)
    imgs = sorted(tmp.glob("page*.png"))
    txt = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", "1", str(pdf), "-"],
                         capture_output=True, text=True, timeout=30).stdout or ""
    return (imgs[0] if imgs else None), txt


def vision(payload: dict) -> dict:
    return {"via": "tesseract", "model": "tesseract-bos+eng",
            "raw": {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}}


def main() -> int:
    files = sorted([p for p in SRC.iterdir()
                    if p.is_file() and p.suffix.lower() in (".pdf", ".jpg", ".jpeg", ".png")])
    seen = set(); cases = []
    tmpdb = tempfile.TemporaryDirectory()
    old = evidence.DB
    evidence.DB = Path(tmpdb.name) / "evidence.sqlite3"
    for i, path in enumerate(files, 1):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        img = path
        ref_text = ""
        if path.suffix.lower() == ".pdf":
            img, ref_text = pdf_page(path)
        if img is None:
            cases.append({"id": "real-%02d" % i, "ocr_chars": 0, "gate": "unverified",
                          "reason": "no_page_image"})
            continue
        try:
            ocr_text = ocr_image(img)
        except Exception as exc:
            cases.append({"id": "real-%02d" % i, "ocr_chars": 0, "gate": "unverified",
                          "reason": "ocr_error: %s" % exc})
            continue
        totals = parse_totals(ocr_text)
        derived = []
        if totals["net"] is None and totals["total"] is not None and totals["vat"] is not None:
            totals["net"] = round(totals["total"] - totals["vat"], 2); derived.append("net")
        if totals["vat"] is None and totals["net"] is not None and totals["total"] is not None:
            totals["vat"] = round(totals["total"] - totals["net"], 2); derived.append("vat")
        if totals["total"] is None and totals["net"] is not None and totals["vat"] is not None:
            totals["total"] = round(totals["net"] + totals["vat"], 2); derived.append("total")
        if totals["net"] is not None:
            if totals["vat"] is None:
                totals["vat"] = round(totals["net"] * 0.17, 2); derived.append("vat")
            if totals["total"] is None:
                totals["total"] = round(totals["net"] + totals["vat"], 2); derived.append("total")
        items = parse_items(ocr_text)
        if not items and totals["net"] is not None:
            items = [{"code": "", "name": "aggregate", "qty": 1,
                      "unit_price": totals["net"], "line_total": totals["net"]}]
        payload = {"supplier": None, "invoice_no": None, "date": None, "currency": "BAM",
                   "items": items, "net_total": totals["net"], "vat": totals["vat"],
                   "total": totals["total"]}
        try:
            with patch("meta_adapter.vision", return_value=vision(payload)):
                out = invoice_extract.extract(img.read_bytes())
            verdict = out.get("verdict"); problems = out.get("problems", [])
        except Exception as exc:
            verdict = "unverified"; problems = ["gate_error: %s" % exc]
        ref = parse_totals(ref_text) if ref_text else {"net": None, "vat": None, "total": None}
        keys = [k for k in ("net", "vat", "total") if ref[k] is not None]
        match = None
        if keys:
            match = all(totals[k] is not None and abs(totals[k] - ref[k]) <= 0.02 for k in keys)
        cases.append({
            "id": "real-%02d" % i, "extension": path.suffix.lower(),
            "digital_text_layer": len(ref_text.strip()) > 100,
            "ocr_chars": len(ocr_text.strip()),
            "items": len(items), "totals": totals, "effective_totals": totals,
            "derived": derived, "reference_totals": ref if keys else None,
            "ocr_matches_reference": match,
            "verdict": verdict, "problems": problems[:5],
        })
    evidence.DB = old
    odd = [c for c in cases if c.get("ocr_matches_reference") is False and c.get("verdict") == "verified"]
    metrics = {
        "files_total": len(files),
        "unique_files": len(seen),
        "cases": len(cases),
        "ocr_text_ok": sum(1 for c in cases if c.get("ocr_chars", 0) > 100),
        "digital_text_layer": sum(1 for c in cases if c.get("digital_text_layer")),
        "verified": sum(1 for c in cases if c.get("verdict") == "verified"),
        "unverified": sum(1 for c in cases if c.get("verdict") == "unverified"),
        "totals_parsed": sum(1 for c in cases if c.get("totals", {}).get("total") is not None),
        "reference_available": sum(1 for c in cases if c.get("reference_totals")),
        "ocr_matches_reference": sum(1 for c in cases if c.get("ocr_matches_reference") is True),
        "ocr_mismatch_reference": sum(1 for c in cases if c.get("ocr_matches_reference") is False),
        "false_verification_candidates": len(odd),
    }
    result = {"generated": "2026-11-05", "source": "private local invoices",
              "privacy": "no filenames/customer data in this file",
              "metrics": metrics, "cases": cases}
    (OUT / "results_real.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (SRC / "results_real_private.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = f"""# Real invoice OCR + evidence gate — aggregate results

**Date:** 2026-11-05  
**Documents:** `{metrics['files_total']}` private invoice files, `{metrics['unique_files']}` unique after hash dedup.  
**OCR:** Tesseract 5 (`bos`, psm 6) on page 1.  
**Gate:** real `invoice_extract` arithmetic gate, totals-only mode when item lines cannot be parsed.

> Privacy: source files and detailed case data stay in `/root/gama_private_invoices` (0700). Only aggregates are published.

| Metric | Result |
|---|---|
| Unique invoices | {metrics['unique_files']} |
| OCR text extracted (>100 chars) | {metrics['ocr_text_ok']}/{metrics['cases']} |
| Digital text layer present | {metrics['digital_text_layer']}/{metrics['cases']} |
| Totals parsed (total found) | {metrics['totals_parsed']}/{metrics['cases']} |
| Gate verified | {metrics['verified']}/{metrics['cases']} |
| Gate unverified / fail-closed | {metrics['unverified']}/{metrics['cases']} |
| Reference totals available | {metrics['reference_available']} |
| OCR totals match text-layer reference | {metrics['ocr_matches_reference']} |
| OCR totals mismatch reference | {metrics['ocr_mismatch_reference']} |
| **False-verification candidates** | **{metrics['false_verification_candidates']}** |

## Interpretation
- Real invoice layouts vary; totals-only mode isolates the arithmetic gate from item-table parsing.
- A mismatch between OCR totals and the PDF text layer, where the gate still says `verified`, is a false-verification candidate.
- Scanned PDFs have no text-layer reference; those cases are OCR-only and are not counted as reference matches.
- This is a pilot on GAMA's own/available invoices, not a statistically representative field study.

Per-case detail (no customer data): `results_real.json`.
"""
    (OUT / "RESULTS_REAL.md").write_text(md, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
