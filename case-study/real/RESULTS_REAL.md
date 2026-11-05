# Real invoice OCR + evidence gate — aggregate results

**Date:** 2026-11-05  
**Documents:** `36` private invoice files, `34` unique after hash dedup.  
**OCR:** Tesseract 5 (`bos`, psm 6) on page 1.  
**Gate:** real `invoice_extract` arithmetic gate, totals-only mode when item lines cannot be parsed.

> Privacy: source files and detailed case data stay in `/root/gama_private_invoices` (0700). Only aggregates are published.

| Metric | Result |
|---|---|
| Unique invoices | 34 |
| OCR text extracted (>100 chars) | 34/34 |
| Digital text layer present | 29/34 |
| Totals parsed (total found) | 23/34 |
| Gate verified | 19/34 |
| Gate unverified / fail-closed | 15/34 |
| Reference totals available | 23 |
| OCR totals match text-layer reference | 21 |
| OCR totals mismatch reference | 2 |
| **False-verification candidates** | **0** |

## Interpretation
- Real invoice layouts vary; totals-only mode isolates the arithmetic gate from item-table parsing.
- A mismatch between OCR totals and the PDF text layer, where the gate still says `verified`, is a false-verification candidate.
- Scanned PDFs have no text-layer reference; those cases are OCR-only and are not counted as reference matches.
- This is a pilot on GAMA's own/available invoices, not a statistically representative field study.

Per-case detail (no customer data): `results_real.json`.
