from pathlib import Path

from src.bridge.python import review_mcp_server as bridge


def test_extract_title_line_skips_boilerplate() -> None:
    text = (
        "Downloaded via UNIVERSITY LIBRARY on April 7, 2026.\n"
        "This article is licensed under a Creative Commons Attribution License.\n"
        "Autonomous platforms for data-driven organic synthesis\n"
        "A. Example, B. Example\n"
        "Abstract We studied a catalytic workflow...\n"
    )
    title = bridge._extract_title_line(text, "fallback title")
    assert title == "Autonomous platforms for data-driven organic synthesis"


def test_map_support_to_reference_uses_matching_hints() -> None:
    support_doc = {
        "source_provenance": {"path": str(Path("/tmp/support-paper.pdf"))},
        "identity": {
            "title": "Autonomous platforms for data-driven organic synthesis",
            "doi": "10.1038/s41467-022-28736-4",
            "year": "2022",
            "authors": ["Gao", "Raghavan"],
        },
        "matching_hints": {
            "normalized_title": "autonomous platforms data driven organic synthesis",
            "title_tokens": ["autonomous", "platforms", "data", "driven", "organic", "synthesis"],
            "author_tokens": ["gao", "raghavan"],
            "year": "2022",
            "doi_variants": ["10.1038/s41467-022-28736-4"],
            "source_name_tokens": ["autonomous", "platforms", "organic", "synthesis"],
        },
        "citation_anchors": ["10.1038/s41467-022-28736-4", "2022", "gao"],
    }
    reference = {
        "raw": "Gao, W.; Raghavan, P.; Coley, C. W. Autonomous platforms for data-driven organic synthesis. Nat. Commun. 2022. doi:10.1038/s41467-022-28736-4",
        "doi": "10.1038/s41467-022-28736-4",
        "year": "2022",
        "author_hint": "Gao",
        "title_hint": "Autonomous platforms for data-driven organic synthesis",
    }

    matched, meta = bridge._map_support_to_reference(reference, [support_doc])

    assert matched == support_doc
    assert meta["score"] >= 6.0
    assert "doi" in meta["basis"]


def test_manuscript_variant_detection_excludes_managed_copy() -> None:
    manuscript = Path("/tmp/project/materials/manuscript/designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf")
    managed = Path("/tmp/project/materials/managed/20260329_174704_137524/project1_clean_native.docx")
    assert bridge._is_manuscript_variant(manuscript, managed) is True


def test_manuscript_variant_detection_keeps_distinct_support_paper() -> None:
    manuscript = Path("/tmp/project/materials/manuscript/designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf")
    support = Path("/tmp/project/materials/other/Autonomous_platforms_for_data-driven_organic_synthesis.pdf")
    assert bridge._is_manuscript_variant(manuscript, support) is False
