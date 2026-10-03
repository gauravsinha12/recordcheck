"""Verification: does each cited sentence's facts appear on the pages it cites?

Statuses, in the order a reviewer should look at them:
  MISSING_PAGE  a cited Bates page is not in the production
  CONTRADICTED  a stated value is not on the cited page(s) (and usually not anywhere)
  WRONG_PAGE    every fact exists in the record, but on a different page than cited
  UNCITED       the sentence states clinical values but cites nothing
  SUPPORTED     every extracted fact appears on a cited page
  NOT_CHECKED   cited, but no machine-checkable facts (left to the reviewer / LLM check)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .facts import Fact, extract, present
from .records import Production
from .report import Sentence

ORDER = ["MISSING_PAGE", "CONTRADICTED", "WRONG_PAGE", "UNCITED", "SUPPORTED", "NOT_CHECKED"]


@dataclass
class Check:
    sentence: Sentence
    status: str
    facts: list[Fact] = field(default_factory=list)
    missing: list[Fact] = field(default_factory=list)
    found_elsewhere: dict[str, list[str]] = field(default_factory=dict)   # fact text -> pages
    missing_pages: list[str] = field(default_factory=list)
    note: str = ""
    llm: dict | None = None


def check_sentence(s: Sentence, prod: Production) -> Check:
    facts = extract(s.text)
    if not s.cites:
        if facts:
            elsewhere = {f.text: [b for b in prod.pages if present(f, prod.norm(b))] for f in facts}
            pages = sorted({p for v in elsewhere.values() for p in v})
            note = f"States {len(facts)} clinical value(s) with no citation." + (f" Candidates: {', '.join(pages[:4])}." if pages else " Not found anywhere in the production.")
            return Check(s, "UNCITED", facts, facts, elsewhere, note=note)
        return Check(s, "NOT_CHECKED", facts, note="No citation and no clinical values (analysis or narrative).")

    missing_pages = [b for b in s.cites if prod.norm(b) is None]
    if missing_pages:
        return Check(s, "MISSING_PAGE", facts, missing_pages=missing_pages,
                     note=f"Cited page(s) {', '.join(missing_pages)} are not in the production.")
    if not facts:
        return Check(s, "NOT_CHECKED", facts, note="Cited, but nothing machine-checkable; reviewer to confirm the characterization.")

    cited_text = " ".join(prod.norm(b) for b in s.cites)
    missing = [f for f in facts if not present(f, cited_text)]
    if not missing:
        return Check(s, "SUPPORTED", facts, note=f"All {len(facts)} value(s) found on the cited page(s).")

    elsewhere = {f.text: [b for b in prod.pages if b not in s.cites and present(f, prod.norm(b))] for f in missing}
    if all(elsewhere[f.text] for f in missing):
        pages = sorted({p for v in elsewhere.values() for p in v})
        return Check(s, "WRONG_PAGE", facts, missing, elsewhere,
                     note=f"{', '.join(f.text for f in missing)} not on {', '.join(s.cites)}; found on {', '.join(pages)}.")
    not_anywhere = [f.text for f in missing if not elsewhere[f.text]]
    return Check(s, "CONTRADICTED", facts, missing, elsewhere,
                 note=f"Not found on the cited page or anywhere in the production: {', '.join(not_anywhere)}.")


def check_all(sentences: list[Sentence], prod: Production) -> list[Check]:
    return [check_sentence(s, prod) for s in sentences]
