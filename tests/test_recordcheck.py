import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from recordcheck.facts import extract, present
from recordcheck.records import Production, expand, find_cites, normalize
from recordcheck.report import read_report
from recordcheck.verify import check_all

SAMPLES = ROOT / "samples"


def setup_module():
    subprocess.run([sys.executable, str(SAMPLES / "make_samples.py")], check=True, capture_output=True)


def test_bates_ranges():
    assert expand("MRX000101", "MRX000103") == ["MRX000101", "MRX000102", "MRX000103"]
    assert expand("MRX000101", "103") == ["MRX000101", "MRX000102", "MRX000103"]
    assert find_cites("as shown (MRX000101–103; MRX000110)") == ["MRX000101", "MRX000102", "MRX000103", "MRX000110"]


def test_value_matching_respects_number_boundaries():
    [fact] = [f for f in extract("Repeat lactate was 1.3 mmol/L.") if f.kind == "value"]
    assert present(fact, normalize("Lactate 1.3 mmol/L"))
    assert not present(fact, normalize("Lactate 11.3 mmol/L"))
    assert not present(fact, normalize("Lactate 1.35 mmol/L"))


def test_planted_problems_are_caught():
    prod = Production.load(SAMPLES / "production")
    sentences, review, _ = read_report(SAMPLES / "draft_claims_review.docx")
    status = {c.sentence.text[:30]: c.status for c in check_all(sentences, prod)}
    assert status["Repeat lactate on 03/04/2026 w"] == "CONTRADICTED"
    assert status["Urine culture grew >100,000 CF"] == "WRONG_PAGE"
    assert status["The claim was billed as MS-DRG"] == "MISSING_PAGE"
    assert status["Platelets were 98 K/uL, indica"] == "UNCITED"
    assert status["Triage vital signs were temper"] == "SUPPORTED"
    assert status["Initial labs showed a white bl"] == "SUPPORTED"


def test_reviewer_edits_and_comments_are_harvested_with_sections():
    _, review, _ = read_report(SAMPLES / "draft_claims_review.docx")
    kinds = sorted((r.kind, r.section) for r in review)
    assert kinds == [("comment", "Summary of Records"), ("comment", "Summary of Records"),
                     ("deletion", "Analysis"), ("insertion", "Summary of Records")]
    comment = next(r for r in review if r.author == "S. Rao, CCS")
    assert "MS-DRG 872" in comment.anchor
