"""python -m recordcheck --records <folder|pages.jsonl> --report <draft.docx> [--out out/] [--llm]"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from . import llm
from .output import annotate, write_workbook
from .records import Production
from .report import read_report
from .verify import ORDER, check_all


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="recordcheck", description="Check every cited fact in a draft report against the produced record.")
    ap.add_argument("--records", required=True, help="folder of <BATES>.txt OCR pages, or a JSONL of {bates, text}")
    ap.add_argument("--report", required=True, help="draft report .docx (tracked changes and comments are read too)")
    ap.add_argument("--out", default="out", help="output folder")
    ap.add_argument("--llm", action="store_true", help="also ask Claude to verify cited sentences (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args(argv)

    prod = Production.load(args.records)
    sentences, review, doc = read_report(args.report)
    checks = check_all(sentences, prod)
    if args.llm:
        if not llm.available():
            print("--llm ignored: no Anthropic credentials configured", file=sys.stderr)
        else:
            for c in checks:
                if c.sentence.cites and c.status != "MISSING_PAGE":
                    c.llm = llm.verify(c.sentence.text, c.sentence.cites, prod)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.report).stem
    write_workbook(out / f"{stem}.provenance.xlsx", checks, review, Path(args.report).name)
    flagged = annotate(doc, checks, out / f"{stem}.checked.docx")

    counts = Counter(c.status for c in checks)
    print(f"{len(prod.pages)} record pages · {len(checks)} sentences · {sum(1 for c in checks if c.sentence.cites)} cited")
    print("  " + " · ".join(f"{s} {counts.get(s, 0)}" for s in ORDER))
    print(f"  {len(review)} reviewer edits/comments harvested")
    for c in checks:
        if c.status not in ("SUPPORTED", "NOT_CHECKED"):
            print(f"\n[{c.status}] {c.sentence.text}\n    {c.note}")
    print(f"\nwrote {out / (stem + '.provenance.xlsx')} and {out / (stem + '.checked.docx')} ({flagged} comments added)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
