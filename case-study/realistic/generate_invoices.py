#!/usr/bin/env python3
"""Generate realistic synthetic GAMA-style invoices (PNG) + ground truth.

Images are synthetic. No customer data. Layout is modeled on GAMA TRADE
offers/invoices (header, item table, 17% VAT, BAM totals).
"""
from __future__ import annotations

import json
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)
VAT = Decimal("0.17")
Q = Decimal("0.01")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def q2(x) -> Decimal:
    return Decimal(str(x)).quantize(Q, rounding=ROUND_HALF_UP)


def fmt(x) -> str:
    s = f"{Decimal(str(x)):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_qty(x) -> str:
    d = Decimal(str(x))
    return str(int(d)) if d == d.to_integral() else str(d).replace(".", ",")


def make_invoice(seed: int, scenario: str) -> dict:
    rng = random.Random(seed)
    names = [
        ("17E669", "Graco Mark X Standard airless"),
        ("C-5520", "Vijčani kompresor Comprag 5.5kW"),
        ("HDA531", "Mlaznica HDA 531 za glet"),
        ("BM15", "Crijevo BlueMax 15m 1/2\""),
        ("PG-200", "Pjeskarenje BlastPack 200"),
    ]
    items = []
    for i in range(rng.randint(1, 3)):
        code, name = names[(seed + i) % len(names)]
        qty = rng.randint(1, 5)
        price = q2(rng.uniform(40, 1800))
        line = q2(qty * price)
        items.append({"code": code, "name": name, "qty": qty,
                      "unit_price": float(price), "line_total": float(line)})
    net = q2(sum(Decimal(str(it["line_total"])) for it in items))
    vat = q2(net * VAT)
    total = q2(net + vat)
    data = {"supplier": "GAMA TRADE d.o.o.", "invoice_no": "GAMA-2026-%03d" % (seed + 1),
            "date": "05.11.2026", "currency": "BAM", "items": items,
            "net_total": float(net), "vat": float(vat), "total": float(total)}
    expected = "verified"
    note = scenario
    if scenario == "line_total":
        data["items"][0]["line_total"] = float(q2(Decimal(str(data["items"][0]["line_total"])) + 1))
        expected = "unverified"
    elif scenario == "net_total":
        data["net_total"] = float(q2(Decimal(str(net)) + 1))
        expected = "unverified"
    elif scenario == "vat":
        data["vat"] = float(q2(Decimal(str(vat)) + 1))
        expected = "unverified"
    elif scenario == "total":
        data["total"] = float(q2(Decimal(str(total)) + 1))
        expected = "unverified"
    elif scenario == "missing_totals":
        data["net_total"] = data["vat"] = data["total"] = None
        expected = "verified"
    elif scenario == "supplier_typo":
        data["supplier"] = "GAMA TRDE d.o.o."
        expected = "verified"
    return {"scenario": scenario, "expected": expected, "data": data}


def draw(inv: dict, path: Path, low_quality: bool = False) -> None:
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 22)
    fb = ImageFont.truetype(FONT_B, 30)
    fs = ImageFont.truetype(FONT, 20)
    fm = ImageFont.truetype(FONT_B, 22)
    x0, y = 80, 70
    d.text((x0, y), "GAMA TRADE d.o.o.", font=fb, fill="#1a3a6b")
    d.text((x0, y + 42), "Usora, Bosna i Hercegovina  ·  gamatrade.ba", font=f, fill="#333")
    d.text((W - 360, y), "FAKTURA / RAČUN", font=fb, fill="#1a3a6b")
    d.text((W - 360, y + 42), "Broj: " + inv["data"]["invoice_no"], font=f, fill="#333")
    d.text((W - 360, y + 72), "Datum: " + inv["data"]["date"], font=f, fill="#333")
    y += 125
    d.line((x0, y, W - 80, y), fill="#aaa", width=2)
    y += 18
    d.text((x0, y), "Kupac: KUPAC %02d d.o.o." % (inv["data"]["invoice_no"][-3:] and int(inv["data"]["invoice_no"][-3:]) % 20 + 1), font=f, fill="#111")
    d.text((x0, y + 30), "Adresa: Ulica %d, Bosna i Hercegovina" % (int(inv["data"]["invoice_no"][-3:]) + 1), font=fs, fill="#333")
    d.text((x0, y + 58), "ID/PDV: 0000000000000  ·  Valuta: BAM", font=fs, fill="#333")
    y += 110
    # table header
    cols = [80, 210, 690, 790, 930, 1090]
    headers = ["Šifra", "Naziv", "Kol.", "Cijena", "Iznos"]
    d.rectangle((x0, y, W - 80, y + 40), fill="#eef1f7", outline="#999")
    for i, h in enumerate(headers):
        d.text((cols[i], y + 8), h, font=fm, fill="#1a3a6b")
    y += 40
    for it in inv["data"]["items"]:
        d.line((x0, y + 38, W - 80, y + 38), fill="#ccc", width=1)
        d.text((cols[0], y + 8), it["code"], font=fs, fill="#111")
        d.text((cols[1], y + 8), it["name"][:42], font=fs, fill="#111")
        d.text((cols[2], y + 8), fmt_qty(it["qty"]), font=fs, fill="#111")
        d.text((cols[3], y + 8), fmt(it["unit_price"]), font=fs, fill="#111")
        d.text((cols[4], y + 8), fmt(it["line_total"]), font=fs, fill="#111")
        y += 40
    d.line((x0, y, W - 80, y), fill="#aaa", width=2)
    y += 20
    # totals (omitted for missing_totals)
    if inv["scenario"] != "missing_totals":
        rows = [("Neto:", inv["data"]["net_total"]), ("PDV 17%:", inv["data"]["vat"]),
                ("UKUPNO:", inv["data"]["total"])]
        for label, val in rows:
            d.text((W - 420, y), label, font=fm, fill="#111")
            d.text((W - 260, y), fmt(val) + " BAM", font=fm, fill="#111")
            y += 36
    else:
        d.text((W - 420, y), "Neto / PDV / UKUPNO: nije ispisano", font=f, fill="#555")
    d.text((x0, H - 110), "Hvala na povjerenju.  Plaćanje: 30 dana.  Rok isporuke: 10 radnih dana.", font=fs, fill="#555")
    d.text((x0, H - 80), "GAMA TRADE d.o.o. · Usora · ovo je sintetički dokument za evaluaciju.", font=fs, fill="#888")
    if low_quality:
        img = img.rotate(2.5, expand=True, fillcolor="white")
        img = img.resize((900, int(900 * img.height / img.width)))
    img.save(path)


def main() -> int:
    scenarios = [("valid", i) for i in range(1, 9)] + [
        ("line_total", 9), ("net_total", 10), ("vat", 11), ("total", 12),
        ("missing_totals", 13), ("supplier_typo", 14), ("low_quality", 15),
    ]
    truth = []
    for scenario, seed in scenarios:
        inv = make_invoice(seed, scenario)
        path = IMG / ("faktura-%02d-%s.png" % (seed, scenario))
        draw(inv, path, low_quality=(scenario == "low_quality"))
        inv["image"] = path.name
        truth.append(inv)
    (ROOT / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print("generated", len(truth), "invoices in", IMG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
