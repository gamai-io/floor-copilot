"""GAMA Floor Copilot — minimal HTTP API + single page UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

import inspect_part
import invoice_extract

app = FastAPI(title="GAMA Floor Copilot")
WEB = Path(__file__).parent / "web"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (WEB / "index.html").read_text(encoding="utf-8")


@app.post("/api/invoice")
async def api_invoice(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    return JSONResponse(invoice_extract.extract(data))


@app.post("/api/inspect")
async def api_inspect(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    return JSONResponse(inspect_part.inspect(data))


@app.get("/health")
def health() -> dict:
    return {"ok": True}
