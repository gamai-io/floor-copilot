"""Single adapter for Meta Model API (Muse vision/chat, SAM 3.1) with local fallback."""
from __future__ import annotations

import base64
import os
from typing import Any

import httpx

META_KEY = os.getenv("META_API_KEY", "")
META_BASE = os.getenv("META_BASE_URL", "https://api.meta.ai")
META_MUSE = os.getenv("META_MODEL_MUSE", "")
META_SAM = os.getenv("META_MODEL_SAM", "")

LOCAL_URL = os.getenv("LOCAL_VISION_URL", "http://127.0.0.1:8100/v1")
LOCAL_MODEL = os.getenv("LOCAL_CHAT_MODEL", "Qwen/Qwen2.5-7B-Instruct-AWQ")


def available() -> bool:
    return bool(META_KEY and META_MUSE)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def vision(image: bytes, prompt: str, *, json_mode: bool = False) -> dict[str, Any]:
    """Send an image + prompt to Muse vision (or local vision fallback)."""
    if available():
        body = {
            "model": META_MUSE,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(image)}"}},
                ],
            }],
            "temperature": 0,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(f"{META_BASE}/v1/chat/completions",
                       headers={"Authorization": f"Bearer {META_KEY}"},
                       json=body, timeout=120)
        r.raise_for_status()
        return {"via": "meta", "model": META_MUSE, "raw": r.json()}

    # local fallback (same contract)
    body = {
        "model": LOCAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    r = httpx.post(f"{LOCAL_URL}/chat/completions", json=body, timeout=120)
    r.raise_for_status()
    return {"via": "local", "model": LOCAL_MODEL, "raw": r.json()}


def segment(image: bytes, prompt: str = "part") -> dict[str, Any]:
    """SAM 3.1 segmentation → masks/metadata (or local CV fallback)."""
    if available() and META_SAM:
        r = httpx.post(
            f"{META_BASE}/v1/segment",
            headers={"Authorization": f"Bearer {META_KEY}"},
            json={"model": META_SAM, "image": _b64(image), "prompt": prompt},
            timeout=120,
        )
        r.raise_for_status()
        return {"via": "meta", "model": META_SAM, "raw": r.json()}
    return {"via": "local", "model": "cv-fallback", "raw": {"masks": [], "note": "SAM unavailable"}}


def chat(messages: list[dict[str, str]], *, json_mode: bool = False) -> dict[str, Any]:
    if available():
        body = {"model": META_MUSE, "messages": messages, "temperature": 0}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = httpx.post(f"{META_BASE}/v1/chat/completions",
                       headers={"Authorization": f"Bearer {META_KEY}"},
                       json=body, timeout=120)
        r.raise_for_status()
        return {"via": "meta", "model": META_MUSE, "raw": r.json()}
    r = httpx.post(f"{LOCAL_URL}/chat/completions",
                   json={"model": LOCAL_MODEL, "messages": messages, "temperature": 0},
                   timeout=120)
    r.raise_for_status()
    return {"via": "local", "model": LOCAL_MODEL, "raw": r.json()}
