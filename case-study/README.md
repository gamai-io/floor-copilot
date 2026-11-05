# Floor Copilot — synthetic gate benchmark

**Status:** synthetic, reproducible gate benchmark. **Not** a real-invoice OCR study.

## What it measures
The real `invoice_extract` arithmetic evidence gate, driven by synthetic OCR payloads:

- valid invoices are not falsely rejected,
- arithmetic errors are caught,
- missing totals are recomputed,
- OCR-name errors are **not** caught (known limitation),
- unparseable output fails closed.

## Run
```bash
python case-study/gate_benchmark.py
```

Outputs:
- `results.json` — full results + per-case verdicts
- `RESULTS.md` — summary table

## Results (seed 42, 100 cases)

| Case type | n | Outcome |
|---|---:|---|
| Valid invoices | 40 | 40 verified |
| Arithmetic errors | 30 | 30 unverified; **0 false verifications** |
| Missing totals | 10 | 10 verified with computed totals |
| OCR name wrong, math correct | 10 | 10 verified (**known limitation**) |
| Invalid/unparseable output | 10 | 10 unverified |

Elapsed: ~0.3 s.

## What this does NOT prove
- No real customer invoices, no real OCR model, no field error distribution.
- Supplier-name and transcription correctness are outside the gate.
- The sample is small and synthetic; it is a regression test, not a field study.

## Next step
Run the same gate on 100+ **anonymized real invoices** with ground truth and measure:
- arithmetic error detection,
- OCR field error rate,
- supplier-name mismatch rate,
- time saved vs manual entry.

No customer data leaves the local environment; only aggregated, anonymized results are published.
