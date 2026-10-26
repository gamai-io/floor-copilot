"""Supplier invoice → structured JSON with arithmetic + 17% VAT validation."""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import meta_adapter
import evidence

VAT = Decimal("0.17")
Q = Decimal("0.01")

SCHEMA_PROMPT = """Extract this supplier invoice into JSON only:
{"supplier": str, "invoice_no": str, "date": "YYYY-MM-DD", "currency": "BAM|EUR|USD",
 "items": [{"code": str, "name": str, "qty": number, "unit_price": number, "line_total": number}],
 "net_total": number, "vat": number, "total": number}
Rules: never invent values; if a field is unreadable use null. Numbers as decimals with a dot."""


def _d(v: Any) -> Decimal | None:
    try:
        if v is None or v == "":
            return None
        return Decimal(str(v)).quantize(Q, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def extract(image: bytes) -> dict[str, Any]:
    res = meta_adapter.vision(image, SCHEMA_PROMPT, json_mode=True)
    try:
        text = res["raw"]["choices"][0]["message"]["content"]
        data = json.loads(text)
    except Exception:
        data = {"error": "parse_failed", "raw": res.get("raw")}

    problems: list[str] = []
    items = data.get("items") or []
    if not items:
        problems.append("no items")
    calc_net = Decimal("0.00")
    for i, it in enumerate(items, 1):
        qty = _d(it.get("qty"))
        up = _d(it.get("unit_price"))
        lt = _d(it.get("line_total"))
        if qty is None or up is None:
            problems.append(f"item {i}: missing qty/unit_price")
            continue
        expect = (qty * up).quantize(Q, rounding=ROUND_HALF_UP)
        if lt is None:
            problems.append(f"item {i}: missing line_total")
        elif lt != expect:
            problems.append(f"item {i}: line_total {lt} != {expect}")
        calc_net += lt if lt is not None else expect

    net = _d(data.get("net_total"))
    if net is not None and net != calc_net:
        problems.append(f"net_total {net} != sum(lines) {calc_net}")
    base = net if net is not None else calc_net
    vat_expect = (base * VAT).quantize(Q, rounding=ROUND_HALF_UP)
    vat = _d(data.get("vat"))
    if vat is not None and vat != vat_expect:
        problems.append(f"vat {vat} != 17% of {base} ({vat_expect})")
    total = _d(data.get("total"))
    total_expect = (base + vat_expect).quantize(Q, rounding=ROUND_HALF_UP)
    if total is not None and total != total_expect:
        problems.append(f"total {total} != {total_expect}")

    verdict = "verified" if not problems else "unverified"
    eid = evidence.add("invoice", image, {"extracted": data, "problems": problems,
                                         "computed": {"net": str(base), "vat": str(vat_expect),
                                                      "total": str(total_expect)}},
                       verdict, source=res["via"])
    data["evidence_id"] = eid
    data["verdict"] = verdict
    data["problems"] = problems
    return data
