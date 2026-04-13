from src.bridge.python import review_mcp_server as bridge


def test_extract_reference_entries_from_parenthetical_blocks() -> None:
    content = (
        "Main text sentence about prior work (1).\n"
        "Another sentence (2).\n\n"
        "(1) Smith, J. Example one. Journal 2021, 10, 20-25. doi:10.1000/one.\n"
        "(2) Doe, A. Example two. Journal 2020, 9, 12-18. doi:10.1000/two.\n"
    )
    refs = bridge._extract_reference_entries(content)
    assert len(refs) == 2
    assert refs[0]["index"] == 1
    assert refs[1]["index"] == 2
    assert refs[0]["doi"] == "10.1000/one"
    assert refs[1]["doi"] == "10.1000/two"


def test_citation_mentions_capture_single_parenthetical_numeric() -> None:
    content = (
        "This claim is supported by prior experiments (7).\n"
        "References\n"
        "[7] Example reference line."
    )
    mentions = bridge._citation_mentions_by_sentence(content)
    numeric_markers = [row for row in mentions if row.get("marker_type") == "numeric"]
    assert numeric_markers
    assert any(row.get("marker_raw") == "(7)" for row in numeric_markers)


def test_references_split_prefers_decorated_heading_over_inline_mentions() -> None:
    content = (
        "Main text says the citation references did not match the article titles.\n"
        "More body text here.\n"
        "■ REFERENCES\n"
        "(1) Smith, J. Example one. Journal 2021, 10, 20-25.\n"
        "(2) Doe, A. Example two. Journal 2020, 9, 12-18.\n"
    )
    body, refs = bridge._references_split(content)
    assert "citation references did not match" in body
    assert refs.startswith("(1) Smith")
    entries = bridge._extract_reference_entries(content)
    assert [row["index"] for row in entries] == [1, 2]


def test_extract_reference_entries_handles_same_line_parenthetical_blocks() -> None:
    content = (
        "Body sentence with citation (21).\n"
        "■ REFERENCES\n"
        "(21) Zhao, X.-Y. Example twenty-one. RSC Adv. 2016, 6, 24484-24490. "
        "(22) King, A. K. Example twenty-two. Catal. Sci. Technol. 2023, 13, 301-304.\n"
    )
    refs = bridge._extract_reference_entries(content)
    assert [row["index"] for row in refs] == [21, 22]
    assert "Example twenty-one" in refs[0]["raw"]
    assert "Example twenty-two" in refs[1]["raw"]
