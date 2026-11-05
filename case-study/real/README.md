# Real invoice OCR pilot (private data, aggregate results only)

**Status:** pilot on GAMA's own/available invoices. **This is not a representative field study.**

## Data and privacy
- Source: `/root/gama_private_invoices` (mode 0700), collected from GAMA's dispatcher/server file system with the owner's authorization.
- The source files and the per-case `results_real.json` are **not** committed to git.
- Only aggregate numbers are published in `RESULTS_REAL.md`.
- No customer names, no invoice numbers, no per-invoice amounts appear in this repository.

## Method
- 36 invoice files, 34 unique after SHA-256 dedup.
- PDFs: page 1 rendered at 150 dpi; text layer extracted with `pdftotext -layout` as the reference where available.
- OCR: Tesseract 5, `bos`, psm 6.
- Gate: the real `invoice_extract` arithmetic gate.
- When item lines cannot be parsed, a totals-only aggregate item is used so the arithmetic gate can still check `net`, `VAT 17%`, and `total`.
- Missing values are derived only when mathematically possible and are marked as `derived` in the private results.

## Results

| Metric | Result |
|---|---|
| Unique invoices | 34 |
| OCR text extracted (>100 chars) | 34/34 |
| Digital text layer present | 29/34 |
| Total found by OCR parser | 23/34 |
| Gate verified | 19/34 |
| Gate unverified / fail-closed | 15/34 |
| Reference totals available | 23 |
| OCR totals match text-layer reference | 21/23 |
| OCR totals mismatch reference | 2/23 |
| **False verifications (effective totals)** | **0** |

## What this shows
- The gate is **fail-closed** on this real-layout pilot: 15/34 could not be verified and were marked `unverified`, not `verified`.
- Where a text layer existed, OCR totals matched the reference in 21/23 cases.
- Two mismatches were OCR/format issues (e.g. decimal separator ambiguity); both ended `unverified`, so they were not false successes.
- Real layouts differ; totals-only mode is a parser-assisted measurement, not a claim that arbitrary invoices are fully extracted.

## Known gaps
- Item-table parsing is layout-dependent; many invoices fall back to totals-only.
- Scanned PDFs have no text-layer reference; those are OCR-only.
- Different VAT rates (non-17%) and multi-rate invoices are rejected by the gate, correctly but not usefully classified.
- 34 invoices is a pilot, not a statistical sample.

## Reproduce
```bash
python case-study/real/run_real_invoices.py
```
Requires `pdftoppm`, `pdftotext`, and `tesseract` with the `bos` language pack, plus the private invoice folder. The script writes aggregate results to this folder and detailed private results to `/root/gama_private_invoices/results_real_private.json`.

## Next step
- 100+ anonymized real invoices with ground truth, stratified by supplier/layout.
- Compare Tesseract vs NVIDIA/Qwen VL on the same pages.
- Add field-level accuracy (supplier, invoice no, line items), not just totals.
