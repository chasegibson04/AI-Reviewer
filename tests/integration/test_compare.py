from pathlib import Path

from ai_reviewer.ingest.loaders import parse_path
from ai_reviewer.review.compare import align_sections, detect_claim_changes


def test_compare_workflow_helpers():
    old = parse_path(Path("tests/fixtures/draft_old.md"))[0]
    new = parse_path(Path("tests/fixtures/draft_new.md"))[0]

    aligned = align_sections(old, new)
    added, removed, changed = detect_claim_changes(old, new)

    assert aligned
    assert isinstance(added, list)
    assert isinstance(removed, list)
    assert isinstance(changed, list)
