from src.bridge.python import review_mcp_server as bridge


def test_visible_comment_limits_citation_noise() -> None:
    details = []
    for idx in range(12):
        details.append(
            {
                "stage": "citation_verification",
                "severity": "medium",
                "issue": f"This sentence may need a citation: claim snippet {idx}",
                "fix": "Add a source.",
            }
        )
    comments = bridge._compose_visible_comments(details)
    assert len(comments) <= 4


def test_suggested_changes_deduplicates_repeated_rows() -> None:
    details = [
        {
            "stage": "citation_verification",
            "severity": "medium",
            "issue": "This sentence may need a citation.",
            "fix": "Add a citation with direct support.",
        },
        {
            "stage": "citation_verification",
            "severity": "medium",
            "issue": "This sentence may need a citation.",
            "fix": "Add a citation with direct support.",
        },
    ]
    out = bridge._build_suggested_changes(details, [])
    assert len(out) == 1
