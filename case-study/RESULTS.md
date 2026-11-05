# Floor Copilot — synthetic gate benchmark

**Date:** 2026-11-05  
**Seed:** 42  
**Cases:** 100 synthetic OCR payloads through the real `invoice_extract` arithmetic gate.

> **Caveat:** synthetic OCR outputs, not real customer invoices. This measures the arithmetic evidence gate only. OCR field confidence and supplier-name verification are not modeled.

## Results

| Case type | n | Outcome |
|---|---:|---|
| Valid invoices | 40 | 40 verified |
| Arithmetic errors | 30 | 30 unverified; **0 false verifications** |
| Missing totals | 10 | 10 verified with computed totals |
| OCR name wrong, math correct | 10 | 10 verified (**known limitation**) |
| Invalid/unparseable output | 10 | 10 unverified |

Elapsed: 0.291s.

## Interpretation
- The arithmetic gate caught every injected arithmetic error in this sample and did not reject any valid invoice.
- It **does not** verify supplier names or OCR transcription; a wrong name with correct arithmetic is still `verified`. That is the documented next step (field-level OCR confidence).
- This is a gate benchmark, not a field study. Real invoices require anonymization and a separate OCR evaluation.

Reproduce: `python case-study/gate_benchmark.py`
