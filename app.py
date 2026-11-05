"""gamAI Floor Copilot — minimal HTTP API + single page UI."""
from __future__ import annotations

from pathlib import Path
import hmac
import logging
import os

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

import inspect_part
import invoice_extract
import evidence
import meta_adapter

app = FastAPI(title="gamAI Floor Copilot")
WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 10 * 1024 * 1024
API_KEY = os.getenv("FLOOR_API_KEY", "").strip()
DEBUG = os.getenv("FLOOR_DEBUG", "") == "1"
log = logging.getLogger("floor-copilot")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional bearer gate: enforced only when FLOOR_API_KEY is set."""
    if API_KEY and not hmac.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="unauthorized")


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
    """Read in chunks and stop at the limit, so an oversized upload never lands in RAM whole."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD:
            raise ValueError("file too large (max 10 MB)")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise ValueError("empty file")
    return data


@app.post("/api/invoice", dependencies=[Depends(require_api_key)])
async def api_invoice(file: UploadFile = File(...)) -> JSONResponse:
    try:
        data = await _read(file)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    try:
        return JSONResponse(invoice_extract.extract(data))
    except Exception as exc:  # model/network errors must fail closed
        log.exception("invoice extraction failed")
        body = {"ok": False, "error": type(exc).__name__}
        if DEBUG:
            body["detail"] = str(exc)[:300]
        return JSONResponse(body, status_code=502)


@app.post("/api/inspect", dependencies=[Depends(require_api_key)])
async def api_inspect(file: UploadFile = File(...)) -> JSONResponse:
    try:
        data = await _read(file)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    try:
        return JSONResponse(inspect_part.inspect(data))
    except Exception as exc:
        log.exception("part inspection failed")
        body = {"ok": False, "error": type(exc).__name__}
        if DEBUG:
            body["detail"] = str(exc)[:300]
        return JSONResponse(body, status_code=502)
