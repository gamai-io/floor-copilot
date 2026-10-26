# GAMA Floor Copilot

**Industrial floor copilot built on Meta Model API (Muse + SAM 3.1) — every answer carries evidence.**

Meta Global AI Developer Hackathon 2026 · Track: **Startup** · Team: GAMA TRADE d.o.o. (product: gamAI)

## Problem

Small industrial distributors and service shops still run on paper and spreadsheets:

- supplier invoices are typed in by hand (hours per week, errors in quantities/prices),
- incoming parts are inspected by eye, with no photo record or measurement,
- operators ask "what is the price / do we have it in stock / what does this document say" and get no reliable answer.

Generic chatbots are not usable here: a wrong number in an invoice or a stock answer costs real money, so **an answer without evidence is worse than no answer**.

## What we built

A local-first copilot with three flows, each gated by an evidence check:

1. **Invoice intake (vision)** — photo/PDF of a supplier invoice → Muse vision → structured JSON (supplier, line items, quantity, unit price) → arithmetic re-check + 17% VAT → **evidence**: image hash, page, bounding box per field.
2. **Part inspection (SAM 3.1)** — photo of a part/equipment → segmentation masks → damaged areas highlighted → report with masks, area in pixels/cm² and confidence.
3. **Operator Q&A (Muse, bs/en/de)** — "price and stock of X", "what does this document say" — answers cite the source row/document; confidential data never leaves the local network.

## Evidence gate

Every automated result is accepted only if it can be verified:

| Flow | Check | Fail behaviour |
|---|---|---|
| Invoice | sum(items) == total, VAT == 17%, fields non-empty | mark `unverified`, list missing fields |
| Inspection | mask area > 0, image hash stored | return original photo + "no damage detected" |
| Q&A | answer cites a source row/document id | answer "no evidence found" instead of guessing |

This is the part hackathon demos usually skip: the copilot **fails closed**.

## Architecture

```
            ┌─────────────────────────────┐
  photo/PDF │  web UI (single page)       │
  ─────────►│  upload → result → evidence │
            └──────────────┬──────────────┘
                           │
                 ┌─────────▼──────────┐
                 │  agent loop        │  plan → tool → verify → answer
                 │  (tool calling)    │
                 └─────────┬──────────┘
        ┌──────────────────┼───────────────────┐
        │                  │                   │
┌───────▼──────┐  ┌────────▼───────┐  ┌────────▼───────┐
│ meta_adapter │  │ invoice_extract│  │ inspect_part    │
│ Muse / SAM   │  │ schema + VAT   │  │ SAM 3.1 masks   │
└───────┬──────┘  └────────┬───────┘  └────────┬────────┘
        │                  │                   │
        └──────────────────┼───────────────────┘
                           │
                 ┌─────────▼──────────┐
                 │ evidence store     │  hash + bbox + source
                 └────────────────────┘
```

Fallback: if the Meta API key is unavailable, the same adapter interface talks to local models (Ollama / vLLM), so the demo works offline too.

## Stack

- **Meta Model API** — Muse (vision + chat, multilingual bs/en/de), SAM 3.1 (segmentation)
- Python 3.11+, FastAPI (or plain HTTP), minimal HTML/JS UI
- SQLite for the evidence store (demo), pluggable to Postgres
- Partner credits used: Baseten, Modal, Fireworks (as applicable)

## Run (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add META_API_KEY
uvicorn app:app --reload      # http://127.0.0.1:8000
```

## Repo layout

```
app.py               # HTTP API + upload endpoints
meta_adapter.py      # Meta Model API client (vision, chat, segmentation) + local fallback
invoice_extract.py   # invoice → JSON, arithmetic + VAT validation, evidence
inspect_part.py      # SAM 3.1 masks, damage report
evidence.py          # evidence store (hash, bbox, source, verdict)
web/index.html       # single-page UI: upload → result → evidence
samples/             # anonymised sample documents/images
```

## Results (to be filled during the hackathon)

| Metric | Before | GAMA Floor Copilot |
|---|---|---|
| invoice entry time | ~6 min / invoice | target < 30 s |
| field accuracy | — | target ≥ 95% on samples |
| stock/price answer | manual lookup | < 2 s with cited source |

## Privacy / sanitisation

The public repo and demo contain **no** customer names, internal hosts, credentials or proprietary data. All samples are anonymised or synthetic.

## License

MIT — see `LICENSE`.
