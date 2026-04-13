from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from src.bridge.python import review_mcp_server as bridge
from src.bridge.python.color_palette_audit import (
    RepresentativeColor,
    audit_pdf_color_palette,
    filter_representatives,
    merge_nearby_colors,
    nearest_palette_family,
    rgb_to_hex,
)


def _make_fixture_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(300, 300))
    c.setFillColor(Color(1, 1, 1))
    c.rect(0, 0, 300, 300, fill=1, stroke=0)

    c.setFillColor(Color(1, 0, 0))
    c.rect(20, 180, 80, 80, fill=1, stroke=0)

    c.setFillColor(Color(0.98, 0.02, 0.02))
    c.rect(105, 180, 80, 80, fill=1, stroke=0)

    c.setFillColor(Color(68 / 255, 1 / 255, 84 / 255))
    c.rect(190, 180, 80, 80, fill=1, stroke=0)

    c.setFillColor(Color(0.5, 0.5, 0.5))
    c.rect(20, 70, 80, 80, fill=1, stroke=0)

    c.setFillColor(Color(0, 0.45, 0.85))
    c.rect(105, 70, 80, 80, fill=1, stroke=0)

    c.showPage()
    c.setFillColor(Color(1, 1, 1))
    c.rect(0, 0, 300, 300, fill=1, stroke=0)
    c.setFillColor(Color(239 / 255, 135 / 255, 64 / 255))
    c.rect(20, 180, 120, 80, fill=1, stroke=0)
    c.setFillColor(Color(0, 0.45, 0.85))
    c.rect(150, 180, 120, 80, fill=1, stroke=0)
    c.save()


def test_merge_near_duplicates_and_hex() -> None:
    merged = merge_nearby_colors(
        {
            (255, 0, 0): {1: 100},
            (250, 4, 4): {1: 60},
            (0, 100, 200): {2: 50},
        },
        merge_distance=12.0,
    )
    assert len(merged) == 2
    assert rgb_to_hex(merged[0].rgb).startswith("#F")


def test_family_matching_and_filters() -> None:
    viridis = nearest_palette_family((68, 1, 84), threshold=26.0)
    plasma = nearest_palette_family((239, 135, 64), threshold=26.0)
    unmatched = nearest_palette_family((10, 120, 220), threshold=26.0)
    assert viridis["classification"] == "viridis_like"
    assert plasma["classification"] == "plasma_like"
    assert unmatched["classification"] == "unmatched"

    full, filtered = filter_representatives(
        [
            RepresentativeColor(rgb=(68, 1, 84), pixel_count=100, page_counts={1: 100}),
            RepresentativeColor(rgb=(245, 245, 245), pixel_count=120, page_counts={1: 120}),
            RepresentativeColor(rgb=(10, 120, 220), pixel_count=140, page_counts={1: 140}),
        ],
        total_pixels=360,
        config={
            "family_match_distance": 26.0,
            "min_pixel_count": 1,
            "min_pixel_fraction": 0.0,
            "suppress_near_white": True,
            "suppress_near_black": True,
            "suppress_neutral_gray": True,
            "white_threshold": 242,
            "black_threshold": 18,
            "gray_chroma_threshold": 12,
        },
    )
    assert len(full) == 3
    assert [entry["hex"] for entry in filtered] == ["#0A78DC"]


def test_palette_audit_generates_artifacts_and_filters(tmp_path: Path) -> None:
    pdf_path = tmp_path / "synthetic_palette_fixture.pdf"
    _make_fixture_pdf(pdf_path)
    output_root = tmp_path / "palette_outputs"
    result = audit_pdf_color_palette(
        pdf_path,
        output_root=output_root,
        config_overrides={
            "dpi": 144,
            "min_pixel_count": 20,
            "min_pixel_fraction": 0.0,
        },
    )
    artifact_paths = result["artifact_paths"]
    for key in [
        "color_palette_full_json",
        "color_palette_filtered_json",
        "color_palette_full_csv",
        "color_palette_filtered_csv",
        "color_palette_page_usage_json",
        "color_palette_report_pdf",
    ]:
        assert Path(artifact_paths[key]).exists(), key

    full_payload = json.loads(Path(artifact_paths["color_palette_full_json"]).read_text(encoding="utf-8"))
    filtered_payload = json.loads(Path(artifact_paths["color_palette_filtered_json"]).read_text(encoding="utf-8"))
    full_hexes = {entry["hex"] for entry in full_payload["colors"]}
    filtered_hexes = {entry["hex"] for entry in filtered_payload["colors"]}

    assert any(entry["classification"] == "viridis_like" for entry in full_payload["colors"])
    assert any(entry["classification"] == "plasma_like" for entry in full_payload["colors"])
    assert any(hex_code in full_hexes for hex_code in {"#FF0000", "#FE0101", "#FD0202"})
    assert "#0073D9" in filtered_hexes or "#0072D8" in filtered_hexes or "#0073DA" in filtered_hexes
    assert not any(entry["classification"] in {"viridis_like", "plasma_like"} for entry in filtered_payload["colors"])


def test_bridge_tool_blocks_forbidden_paths(tmp_path: Path) -> None:
    blocked_dir = tmp_path / "test-d2b"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    blocked_pdf = blocked_dir / "fixture.pdf"
    _make_fixture_pdf(blocked_pdf)
    payload = bridge._dispatch_tool("extract_color_palette", {"pdf_path": str(blocked_pdf)})
    assert "error" in payload
    assert "blocked by policy" in payload["error"].lower()
