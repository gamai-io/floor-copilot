[![CI](https://github.com/gamai-io/floor-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/gamai-io/floor-copilot/actions/workflows/ci.yml)

# Floor Copilot

**An evidence-gated intake copilot for small industrial distributors.**

Meta Global AI Developer Hackathon 2026 · Track: **Startup** · Theme: **Build for Your World**
Team: gamAI

## The problem

A small distributor types supplier invoices by hand: 5–7 minutes each, and a wrong
quantity or price propagates into stock and margin. A generic chatbot makes this worse,
because a confident wrong number is indistinguishable from a right one.

Floor Copilot takes a photo of the invoice, extracts line items, recomputes the
arithmetic with 17% VAT, and **refuses to mark the result verified when the numbers do
not reconcile**. Every result carries a SHA-256 of the image and a stored evidence record.

## What works today (measured, not projected)

**Live demo:** https://gamai.io

Invoice photo → structured JSON → arithmetic gate → evidence record.

Real run on the included synthetic sample (`samples/faktura-mock.png`), local vision
model `qwen3-vl:8b` on an RTX 8000, **21.1 s** end to end:

```json
{
  "supplier": "MOC K DOBAVLJAC DOO",
  "invoice_no": "MOCK-001",
  "date": "2026-10-20",
  "items": [{"name": "Rukavice 600mm", "qty": 4, "unit_price": 12.5, "line_total": 50.0}],
  "net_total": 50.0, "vat": 8.5, "total": 58.5,
  "computed_totals": true,
  "evidence_id": 2,
  "verdict": "verified",
  "problems": []
}
```

Honest note: the supplier name was transcribed as `MOC K DOBAVLJAC DOO` (the print is
`MOCK DOBAVLJAC DOO`). The gate verifies arithmetic, not name transcription. Field-level
OCR confidence is the next step, not a claim we make now.

The seven unit tests run without a model or network:

```bash
python3 -m unittest discover -s tests -v   # 7/7
```

They cover: verified invoice, line-total mismatch → `unverified`, missing totals →
computed, fenced JSON, unparseable output → fail closed, inspection with/without masks.

## Evidence gate

| Flow | Check | On failure |
|---|---|---|
| Invoice | each `qty × unit_price == line_total`; `net == Σ lines`; `vat == 17%`; `total == net + vat` | `unverified` + exact problem list |
| Missing totals | recompute from lines | fill fields, set `computed_totals: true` |
| Part inspection | segmentation masks present | `unverified`; never invent damage |

`/api/evidence/{id}?k=...` returns the stored record: image SHA-256, source (`meta`/`local`),
extracted payload, problems and verdict. The `k` token is returned by the extraction call;
without it the endpoint returns 404, so evidence IDs cannot be enumerated.

## Part inspection — partial

`/api/inspect` calls the Meta segmentation adapter when `META_API_KEY` and
`META_MODEL_SAM` are set. Without SAM it returns **`unverified` with 0 masks** rather
than a fabricated result. The local fallback does not pretend to segment. This is
deliberate: inspection is the flow where a false positive is expensive.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # point LOCAL_VISION_URL at Ollama/vLLM
uvicorn app:app --host 127.0.0.1 --port 8017
```

Open `http://127.0.0.1:8017`, upload a photo, read the verdict and the evidence link.

Local vision (OpenAI-compatible endpoint):

```bash
LOCAL_VISION_URL=http://127.0.0.1:11434/v1
LOCAL_VISION_MODEL=qwen3-vl:8b     # or qwen2.5vl:7b
LOCAL_CHAT_MODEL=qwen2.5:3b
```

Meta adapter (ids and base URL are supplied at kickoff; defaults below are placeholders
until confirmed):

```bash
META_API_KEY=...
META_BASE_URL=https://api.meta.ai
META_MODEL_MUSE=...
META_MODEL_SAM=...
```

## Architecture

```
photo ─► FastAPI ─► meta_adapter.vision ─► invoice_extract
                         │                      │
                         │                      ├─ Decimal arithmetic + 17% VAT
                         │                      └─ evidence.add(hash, payload, verdict)
                         └─ Meta Muse / local qwen-vl
                                               │
                        GET /api/evidence/{id} ┘
```

## API

| endpoint | purpose |
|---|---|
| `GET /` | single-page UI |
| `GET /health` | adapter configuration (no secrets) |
| `POST /api/invoice` | multipart image → extraction + verdict |
| `POST /api/inspect` | multipart image → masks (SAM) or fail closed |
| `GET /api/evidence/{id}` | stored evidence record |

Upload cap is 10 MB. Model/network errors return 502, never a fake `verified`.

## Not implemented (so we do not claim it)

- Operator Q&A over stock/prices — designed, not built.
- PDF input — photos only.
- Field-level bounding boxes / OCR confidence.
- Auth, multi-tenant storage, production rate limits.

## Repo layout

```
app.py               FastAPI + upload endpoints
meta_adapter.py      Meta Muse/SAM client + local vision fallback
invoice_extract.py   schema, Decimal math, VAT, evidence
inspect_part.py      SAM masks → report (fail closed)
evidence.py          SQLite evidence store
web/index.html       single page UI
samples/             synthetic invoice and part images
tests/               evidence-gate tests (no model)
```

## Privacy

The public repo and samples contain no customer names, internal hosts, credentials or
proprietary data. Samples are synthetic. The app runs on your own network; when a local
vision endpoint is configured, invoice images do not leave it.

## License

MIT — see `LICENSE`.
