# recordcheck: every fact in the report ties to a page

For expert reports and claims reviews written from Bates-stamped productions. It checks every
cited sentence in a draft `.docx` against the OCR text of the pages it cites. It also harvests the
reviewers' tracked changes and comments into one Excel log, so nothing is lost when they are
worked back in.

```bash
pip install python-docx openpyxl
python samples/make_samples.py        # synthetic production + draft (fictional patient, no PHI)
python -m recordcheck --records samples/production --report samples/draft_claims_review.docx --out out
```

```
10 record pages · 19 sentences · 10 cited
  MISSING_PAGE 1 · CONTRADICTED 1 · WRONG_PAGE 1 · UNCITED 1 · SUPPORTED 6 · NOT_CHECKED 9
  4 reviewer edits/comments harvested

[CONTRADICTED] Repeat lactate on 03/04/2026 was 1.8 mmol/L (MRX000104).
    Not found on the cited page or anywhere in the production: 1.8 mmol/L.
[WRONG_PAGE] Urine culture grew >100,000 CFU/mL of E. coli ... (MRX000106).
    >100000 CFU/mL not on MRX000106; found on MRX000107.
[MISSING_PAGE] The claim was billed as MS-DRG 872 (MRX000111).
    Cited page(s) MRX000111 are not in the production.
[UNCITED] Platelets were 98 K/uL, indicating thrombocytopenia.
    States 1 clinical value(s) with no citation. Not found anywhere in the production.
```

Outputs:
- `*.provenance.xlsx`: Summary; Citation check (one row per sentence: status, values checked,
  which value is missing, where it actually is); Reviewer edits (every tracked insertion and
  deletion and every comment, with author, date, section and context, plus a "Done?" column).
- `*.checked.docx`: a copy of the draft with a Word comment from "Provenance Check" on every
  flagged sentence, so reviewers see the issues where they already work.

## How it decides
1. Extracts checkable facts from each sentence: values with units, vitals, dates, ICD-10 codes, DRGs.
   Characterizations ("improved", "indicating sepsis") are not string-matched.
2. Looks for each fact on the cited pages with number-boundary matching (1.3 never matches 11.3 or 1.35).
3. If a fact is missing, it searches the whole production. If found elsewhere, the cite is wrong;
   if found nowhere, the statement is contradicted.
4. `--llm` adds a Claude pass for the judgments matching can't make. Claude returns a verdict plus
   an exact quote, and the quote must appear verbatim on the cited page, otherwise the verdict is
   downgraded. The model can't invent provenance.

Verification runs first, before anyone reads the draft, so reviewers spend their time on the
flagged sentences instead of re-checking every cite.
