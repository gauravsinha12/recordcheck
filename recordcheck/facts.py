"""Pull checkable facts out of a sentence: measurements with units, vitals, dates, codes.

Deliberately conservative. A fact is something that must appear on the cited page more or less
verbatim (a value, a date, a code). Characterizations ("improved", "indicating sepsis") are left
to the reviewer or the LLM check, because string matching can't judge them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .records import normalize

UNITS = r"(?:k/ul|x10\^?3/ul|mmol/l|mg/dl|g/dl|meq/l|cfu/ml|ml/kg|mmhg|bpm|%|mg|g|ml|c|f|units?)"
LABS = r"(?:wbc|white blood cell count|lactate|creatinine|platelets?|bilirubin|hemoglobin|sodium|potassium|map|temperature|heart rate|respiratory rate|blood pressure|spo2|oxygen saturation)"


@dataclass(frozen=True)
class Fact:
    kind: str       # value | vital | date | code | bp
    text: str       # as written in the sentence
    needle: str     # normalized form to look for in the record


def extract(sentence: str) -> list[Fact]:
    s = normalize(sentence)
    facts: list[Fact] = []
    seen: set[str] = set()

    def add(kind: str, text: str, needle: str):
        if needle not in seen:
            seen.add(needle)
            facts.append(Fact(kind, display(text.strip()), needle))

    for m in re.finditer(r"\b(\d{2,3}/\d{2,3})\b(?!/)", s):                       # blood pressure 96/58
        if not re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", s[m.start():m.start() + 10]):
            add("bp", m.group(1), m.group(1))
    for m in re.finditer(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", s):                      # dates 03/04/2026
        add("date", m.group(1), m.group(1))
    for m in re.finditer(r"\b([a-z]\d{2}(?:\.\d{1,4})?)\b", s):                   # ICD-10 codes A41.51
        if re.match(r"[a-tv-z]\d{2}\.\d", m.group(1)):
            add("code", m.group(1).upper(), m.group(1))
    for m in re.finditer(r"\b(?:ms-)?drg\s*(\d{3})\b", s):                         # MS-DRG 872
        add("code", f"DRG {m.group(1)}", m.group(1))
    for m in re.finditer(rf"(?:[<>]\s*)?(\d+(?:\.\d+)?)\s*{UNITS}\b", s):          # 2.4 mmol/l, 38.9 c, 1 g
        value = m.group(1)
        if not re.fullmatch(r"\d{1,2}", value) or re.search(r"[a-z/%]", m.group(0)):
            add("value", m.group(0), value)
    for m in re.finditer(rf"\b{LABS}\b(?:\s+(?:of|was|is|at))?\s+(\d+(?:\.\d+)?)", s):  # heart rate 118, lactate of 1.8
        add("vital", m.group(0), m.group(1))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:k/ul)", s):
        add("value", m.group(0), m.group(1))
    return facts


_UNIT_CASE = {"mmol/l": "mmol/L", "k/ul": "K/uL", "cfu/ml": "CFU/mL", "mg/dl": "mg/dL", "g/dl": "g/dL",
              "meq/l": "mEq/L", "ml/kg": "mL/kg", "mmhg": "mmHg", "wbc": "WBC", "spo2": "SpO2", "map": "MAP"}


def display(text: str) -> str:
    """Normalized text back to clinical casing for reports: '1.8 mmol/l' -> '1.8 mmol/L'."""
    return re.sub(r"[a-z0-9/]+", lambda m: _UNIT_CASE.get(m.group(0), m.group(0)), text)


def present(fact: Fact, page_norm: str) -> bool:
    """Exact token match on the page: '1.3' must not match inside '11.3' or '1.35'."""
    return re.search(rf"(?<![\d.]){re.escape(fact.needle)}(?![\d])", page_norm) is not None
