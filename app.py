"""gamAI Floor Copilot — minimal HTTP API + single page UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

import inspect_part
import invoice_extract
import evidence
import meta_adapter

app = FastAPI(title="gamAI Floor Copilot")
WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 10 * 1024 * 1024


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (WEB / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "meta_configured": meta_adapter.available(),
        "local_vision_model": meta_adapter.LOCAL_VISION_MODEL,
        "local_chat_model": meta_adapter.LOCAL_CHAT_MODEL,
    }


@app.get("/api/evidence/{item_id}")
def api_evidence(item_id: int, k: str = "") -> JSONResponse:
    row = evidence.get(item_id, k)
    if not row:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    return JSONResponse(row)


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise ValueError("file too large (max 10 MB)")
    if not data:
        raise ValueError("empty file")
    return data


@app.post("/api/invoice")
async def api_invoice(file: UploadFile = File(...)) -> JSONResponse:
    try:
        data = await _read(file)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    try:
        return JSONResponse(invoice_extract.extract(data))
    except Exception as exc:  # model/network errors must fail closed
        return JSONResponse({"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]},
                            status_code=502)


@app.post("/api/inspect")
async def api_inspect(file: UploadFile = File(...)) -> JSONResponse:
    try:
        data = await _read(file)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    try:
        return JSONResponse(inspect_part.inspect(data))
    except Exception as exc:
        return JSONResponse({"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]},
                            status_code=502)
