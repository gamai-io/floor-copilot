# Floor Copilot — GAMA-style synthetic invoices (Tesseract OCR)

**Date:** 2026-11-05  
**Documents:** 15 synthetic GAMA-style invoices (PNG)  
**OCR:** Tesseract 5, `bos`, psm 6  
**Gate:** real `invoice_extract` arithmetic gate

> **Caveat:** synthetic documents, not real customer invoices. The gate checks arithmetic, not supplier transcription.

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
| Elapsed | 10.14s |

## Interpretation
- OCR is real (Tesseract), but the documents are synthetic and the layout is controlled.
- The number that matters: **false verifications on arithmetic errors** (must be 0).
- Supplier-name errors can still pass because the gate does not check the supplier; this is the documented field-level gap.
- A low-quality image may be refused (`unverified`); that is acceptable. Fabricating `verified` is not.

Per-case results: `results_tesseract.json`.
