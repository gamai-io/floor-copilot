"""Part inspection: SAM 3.1 masks + damage report (fail closed)."""
from __future__ import annotations

from typing import Any

import meta_adapter
import evidence

PROMPT = "Segment the part and any visible damage (cracks, rust, deformation). Return masks and labels."


def inspect(image: bytes) -> dict[str, Any]:
    seg = meta_adapter.segment(image, PROMPT)
    masks = (seg.get("raw") or {}).get("masks") or []
    summary = meta_adapter.chat([
        {"role": "system", "content": "You are an industrial inspection assistant. Report only what is visible. "
                                      "If nothing is damaged, say 'no damage detected'. Answer in Bosnian and English."},
        {"role": "user", "content": f"Segmentation returned {len(masks)} mask(s). Describe condition of the part."},
    ])
    try:
        text = summary["raw"]["choices"][0]["message"]["content"]
    except Exception:
        text = "no evidence"
    verdict = "verified" if masks else "unverified"
    ev = evidence.add("inspection", image, {"masks": masks, "report": text}, verdict, source=seg["via"])
    return {"evidence_id": ev["id"], "evidence_key": ev["token"], "verdict": verdict,
            "masks": len(masks), "report": text, "via": seg["via"]}
