"""The produced record: OCR text per Bates-stamped page, and Bates citation parsing."""
from __future__ import annotations

import json
import re
from pathlib import Path

# A Bates number: letter prefix + 6-8 digits, e.g. MRX000123. Ranges: "MRX000101-MRX000103",
# "MRX000101–103" (short form) or "MRX000101 through MRX000103".
BATES = r"[A-Z]{2,6}\d{6,8}"
CITE_RE = re.compile(rf"({BATES})(?:\s*(?:-|–|—|through|to)\s*({BATES}|\d{{1,8}}))?")


def expand(start: str, end: str | None) -> list[str]:
    if not end:
        return [start]
    prefix = re.match(r"[A-Z]+", start).group(0)
    width = len(start) - len(prefix)
    first = int(start[len(prefix):])
    last_digits = end[len(prefix):] if end.startswith(prefix) else end
    # Short form "MRX000101–103": the end replaces the trailing digits of the start.
    last = int(str(first)[: max(0, len(str(first)) - len(last_digits))] + last_digits) if len(last_digits) < width else int(last_digits)
    if last < first or last - first > 500:
        return [start]
    return [f"{prefix}{n:0{width}d}" for n in range(first, last + 1)]


def find_cites(text: str) -> list[str]:
    pages: list[str] = []
    for m in CITE_RE.finditer(text):
        for page in expand(m.group(1), m.group(2)):
            if page not in pages:
                pages.append(page)
    return pages


class Production:
    """OCR text by Bates number. Loads a folder of <BATES>.txt files or a JSONL of {"bates", "text"}."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self._norm = {k: normalize(v) for k, v in pages.items()}

    @classmethod
    def load(cls, path: str | Path) -> "Production":
        path = Path(path)
        pages: dict[str, str] = {}
        if path.is_dir():
            for f in sorted(path.glob("*.txt")):
                pages[f.stem.upper()] = f.read_text(encoding="utf-8", errors="replace")
        else:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    pages[str(rec["bates"]).upper()] = rec["text"]
        return cls(pages)

    def text(self, bates: str) -> str | None:
        return self.pages.get(bates)

    def norm(self, bates: str) -> str | None:
        return self._norm.get(bates)

    def search(self, needle_norm: str) -> list[str]:
        return [b for b, t in self._norm.items() if needle_norm in t]


def normalize(text: str) -> str:
    """Lowercase, unify dashes/degree signs/whitespace so '38.9 °C' and '38.9 C' compare equal."""
    text = text.lower().replace("–", "-").replace("—", "-").replace("µ", "u").replace("°", " ")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)           # 100,000 -> 100000
    text = re.sub(r"\s+", " ", text)
    return text
