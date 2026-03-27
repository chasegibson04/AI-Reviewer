from pathlib import Path

from ai_reviewer.ingest.loaders import parse_path
from ai_reviewer.review.compare import align_sections, section_add_remove


def test_compare_section_add_remove_reordered():
    old = parse_path(Path("tests/fixtures/draft_old.md"))[0]
    new = parse_path(Path("tests/fixtures/draft_new.md"))[0]
    aligned = align_sections(old, new)
    added, removed = section_add_remove(old, new)
    assert aligned
    assert isinstance(added, list)
    assert isinstance(removed, list)
