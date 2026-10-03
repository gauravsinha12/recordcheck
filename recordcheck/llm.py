"""Optional second pass with Claude for the judgments string matching can't make.

Claude reads the sentence and the cited pages and returns a verdict plus an exact supporting
quote. The quote is then checked to appear verbatim on the cited page. A quote that isn't there
is downgraded, so the model can't invent provenance. Runs only when credentials are configured.
"""
from __future__ import annotations

import json
import os

from .records import Production, normalize

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["supported", "partially_supported", "not_supported"]},
        "quote": {"type": "string", "description": "Exact text copied from the cited page that supports the sentence; empty if none."},
        "issue": {"type": "string", "description": "What is unsupported or overstated, in one sentence; empty if supported."},
    },
    "required": ["verdict", "quote", "issue"],
    "additionalProperties": False,
}


def available() -> bool:
    return any(os.environ.get(v) for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"))


def verify(sentence: str, cites: list[str], prod: Production, model: str = "claude-opus-5-5") -> dict | None:
    import anthropic

    pages = "\n\n".join(f"[{b}]\n{prod.text(b)}" for b in cites if prod.text(b))
    prompt = (
        "You are checking an expert report against the produced medical record. Decide whether the cited pages "
        "support the sentence exactly as written, including every number, date and characterization. "
        "Quote the supporting text exactly as it appears on the page.\n\n"
        f"SENTENCE:\n{sentence}\n\nCITED PAGES:\n{pages}"
    )
    client = anthropic.Anthropic()
    try:
        res = client.messages.create(
            model=model, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        return {"verdict": "error", "quote": "", "issue": str(exc)[:200]}
    if res.stop_reason == "refusal":
        return None
    data = json.loads(next(b.text for b in res.content if b.type == "text"))
    if data["quote"] and not any(normalize(data["quote"]) in (prod.norm(b) or "") for b in cites):
        data["issue"] = ("Quoted text does not appear verbatim on the cited page. " + data["issue"]).strip()
        data["verdict"] = "not_supported" if data["verdict"] == "supported" else data["verdict"]
    return data
