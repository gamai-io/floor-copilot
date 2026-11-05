# Floor Copilot — GAMA-style synthetic invoices (real OCR)

15 synthetic invoices rendered in a GAMA TRADE-style layout, processed by **Tesseract 5** OCR, then checked by the **real `invoice_extract` arithmetic gate**.

**This is not a real customer-invoice study.** The documents are synthetic; the layout is modeled on GAMA offers/invoices (header, item table, 17% VAT, BAM totals).

## Results

| Metric | Result |
|---|---|
| Cases | 15 |
| OCR parsed | 15/15 |
| Valid invoices verified | 8/8 |
| Arithmetic errors caught | 4/4 |
| **False verifications (arithmetic)** | **0** |
| Missing totals verified/computed | 1/1 |
| Supplier typo still verified | 1/1 |
| Low-quality image verdict | verified |
| Supplier exact / cases | 14/15 |
| Invoice no exact / cases | 15/15 |
| Item lines exact | 26/26 |
| Elapsed | 10.14 s |

## Cases
- 8 valid invoices
- 4 arithmetic errors (line total, net, VAT, total)
- 1 invoice without printed totals
- 1 supplier-name typo (math correct)
- 1 low-quality (rotated/downscaled) image

## Interpretation
- OCR is real (Tesseract, `bos`, psm 6) but the documents are synthetic and the layout is controlled.
- The gate caught all 4 arithmetic errors and did not reject any valid invoice.
- The supplier typo is still `verified`: the gate checks arithmetic, not supplier transcription. This is the documented field-level gap.
- The low-quality image still parsed and verified; that is acceptable because the arithmetic was correct, not because the gate ignored quality.

## Reproduce
```bash
python case-study/realistic/generate_invoices.py       # writes images/ + ground_truth.json
python case-study/realistic/run_tesseract_case_study.py
```

Requires `tesseract` with the `bos` language pack and Pillow.

## Files
- `generate_invoices.py` — deterministic synthetic GAMA-style invoices (seed-based)
- `images/` — 15 PNGs
- `ground_truth.json` — expected data/verdict per case
- `run_tesseract_case_study.py` — OCR + real gate
- `results_tesseract.json` — per-case results
- `RESULTS_TESSERACT.md` — summary

## Next step
Replace synthetic images with **100+ anonymized real invoices** and ground truth. No customer data leaves the local environment; publish only aggregates.
