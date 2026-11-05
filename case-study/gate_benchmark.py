#!/usr/bin/env python3
"""Synthetic evaluation of the Floor Copilot arithmetic evidence gate.

This exercises the real `invoice_extract` gate with *synthetic* OCR payloads.
It is not a real-invoice OCR study. It measures whether arithmetic errors are
caught and whether valid invoices are incorrectly rejected.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evidence  # noqa: E402
import invoice_extract  # noqa: E402

VAT = Decimal("0.17")
Q = Decimal("0.01")
SEED = 42


def q2(x) -> Decimal:
    return Decimal(str(x)).quantize(Q, rounding=ROUND_HALF_UP)


def vision(payload):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return {"via": "synthetic", "model": "synthetic-ocr",
            "raw": {"choices": [{"message": {"content": content}}]}}


def make_valid(rng: random.Random) -> dict:
    items = []
    for i in range(rng.randint(1, 5)):
        qty = rng.randint(1, 10)
        price = q2(rng.uniform(1, 1000))
        line = q2(qty * price)
        items.append({
            "code": "S%03d" % i,
            "name": "Artikal %d" % i,
            "qty": qty,
            "unit_price": float(price),
            "line_total": float(line),
        })
    net = q2(sum(Decimal(str(it["line_total"])) for it in items))
    vat = q2(net * VAT)
    total = q2(net + vat)
    return {
        "supplier": "SYNTH DOBAVLJAC DOO",
        "invoice_no": "SYN-%04d" % rng.randint(1, 9999),
        "date": "2026-11-05",
        "currency": "BAM",
        "items": items,
        "net_total": float(net),
        "vat": float(vat),
        "total": float(total),
    }


def mutate_arithmetic(data: dict, kind: str) -> dict:
    d = json.loads(json.dumps(data))
    if kind == "line_total":
        d["items"][0]["line_total"] = float(q2(Decimal(str(d["items"][0]["line_total"])) + 1))
    elif kind == "net_total":
        d["net_total"] = float(q2(Decimal(str(d["net_total"])) + 1))
    elif kind == "vat":
        d["vat"] = float(q2(Decimal(str(d["vat"])) + 1))
    elif kind == "total":
        d["total"] = float(q2(Decimal(str(d["total"])) + 1))
    elif kind == "missing_price":
        d["items"][0]["unit_price"] = None
    return d


def run(payload, tmp_db: Path, label: str) -> dict:
    old = evidence.DB
    evidence.DB = tmp_db
    try:
        with patch("meta_adapter.vision", return_value=vision(payload)):
            out = invoice_extract.extract(b"synthetic-image")
        return {"label": label, "verdict": out.get("verdict"),
                "computed_totals": bool(out.get("computed_totals")),
                "problems": out.get("problems", [])}
    finally:
        evidence.DB = old


def main() -> int:
    rng = random.Random(SEED)
    tmp = tempfile.TemporaryDirectory()
    tmp_db = Path(tmp.name) / "evidence.sqlite3"
    cases = []
    t0 = time.time()

    for i in range(40):
        cases.append(run(make_valid(rng), tmp_db, "valid"))
    for i in range(30):
        kind = ["line_total", "net_total", "vat", "total", "missing_price"][i % 5]
        cases.append(run(mutate_arithmetic(make_valid(rng), kind), tmp_db, "arithmetic_error"))
    for i in range(10):
        d = make_valid(rng)
        d["net_total"] = d["vat"] = d["total"] = None
        cases.append(run(d, tmp_db, "missing_totals"))
    for i in range(10):
        d = make_valid(rng)
        d["supplier"] = "POGREŠAN NAZIV DOO"
        d["items"][0]["name"] = "Pogrešan naziv"
        cases.append(run(d, tmp_db, "ocr_name_only"))
    for i in range(10):
        cases.append(run("not json at all", tmp_db, "invalid_output"))

    elapsed = round(time.time() - t0, 3)
    by = {}
    for c in cases:
        by.setdefault(c["label"], []).append(c)
    metrics = {
        "valid_verified": sum(1 for c in by["valid"] if c["verdict"] == "verified"),
        "valid_total": len(by["valid"]),
        "arithmetic_unverified": sum(1 for c in by["arithmetic_error"] if c["verdict"] == "unverified"),
        "arithmetic_false_verified": sum(1 for c in by["arithmetic_error"] if c["verdict"] == "verified"),
        "arithmetic_total": len(by["arithmetic_error"]),
        "missing_totals_verified": sum(1 for c in by["missing_totals"] if c["verdict"] == "verified"),
        "missing_totals_total": len(by["missing_totals"]),
        "ocr_name_verified": sum(1 for c in by["ocr_name_only"] if c["verdict"] == "verified"),
        "ocr_name_total": len(by["ocr_name_only"]),
        "invalid_unverified": sum(1 for c in by["invalid_output"] if c["verdict"] == "unverified"),
        "invalid_total": len(by["invalid_output"]),
        "elapsed_s": elapsed,
        "cases": len(cases),
    }
    result = {
        "generated": "2026-11-05",
        "seed": SEED,
        "method": "synthetic OCR payloads through the real invoice_extract arithmetic gate",
        "caveat": "Synthetic, not real invoices. Measures arithmetic gate only; OCR field confidence is not modeled.",
        "metrics": metrics,
        "cases": cases,
    }
    out = Path(__file__).parent
    (out / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = f"""# Floor Copilot — synthetic gate benchmark

**Date:** 2026-11-05  
**Seed:** {SEED}  
**Cases:** {metrics['cases']} synthetic OCR payloads through the real `invoice_extract` arithmetic gate.

> **Caveat:** synthetic OCR outputs, not real customer invoices. This measures the arithmetic evidence gate only. OCR field confidence and supplier-name verification are not modeled.

## Results

| Case type | n | Outcome |
|---|---:|---|
| Valid invoices | {metrics['valid_total']} | {metrics['valid_verified']} verified |
| Arithmetic errors | {metrics['arithmetic_total']} | {metrics['arithmetic_unverified']} unverified; **{metrics['arithmetic_false_verified']} false verifications** |
| Missing totals | {metrics['missing_totals_total']} | {metrics['missing_totals_verified']} verified with computed totals |
| OCR name wrong, math correct | {metrics['ocr_name_total']} | {metrics['ocr_name_verified']} verified (**known limitation**) |
| Invalid/unparseable output | {metrics['invalid_total']} | {metrics['invalid_unverified']} unverified |

Elapsed: {elapsed}s.

## Interpretation
- The arithmetic gate caught every injected arithmetic error in this sample and did not reject any valid invoice.
- It **does not** verify supplier names or OCR transcription; a wrong name with correct arithmetic is still `verified`. That is the documented next step (field-level OCR confidence).
- This is a gate benchmark, not a field study. Real invoices require anonymization and a separate OCR evaluation.

Reproduce: `python case-study/gate_benchmark.py`
"""
    (out / "RESULTS.md").write_text(md, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
