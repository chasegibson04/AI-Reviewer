from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

try:
    from PIL import Image, ImageColor, ImageDraw
except Exception:
    Image = None
    ImageColor = None
    ImageDraw = None

try:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:
    HexColor = None
    letter = None
    canvas = None

SCHEMA_VERSION = "color_palette_v1"
VIRIDIS_SAMPLES = [
    (68, 1, 84),
    (71, 24, 106),
    (65, 68, 135),
    (53, 95, 141),
    (42, 120, 142),
    (34, 144, 140),
    (45, 171, 126),
    (82, 197, 105),
    (124, 209, 79),
    (189, 223, 38),
    (253, 231, 37),
]
PLASMA_SAMPLES = [
    (13, 8, 135),
    (47, 5, 150),
    (84, 3, 160),
    (118, 1, 168),
    (150, 19, 161),
    (179, 42, 144),
    (203, 71, 119),
    (223, 101, 92),
    (239, 135, 64),
    (248, 175, 35),
    (240, 249, 33),
]
DEFAULT_CONFIG = {
    "dpi": 120,
    "max_page_pixels": 350_000,
    "quantized_colors_per_page": 48,
    "merge_distance": 16.0,
    "family_match_distance": 30.0,
    "min_pixel_fraction": 0.0005,
    "min_pixel_count": 48,
    "suppress_near_white": True,
    "suppress_near_black": True,
    "suppress_neutral_gray": True,
    "white_threshold": 242,
    "black_threshold": 18,
    "gray_chroma_threshold": 12,
    "create_debug_montage": True,
}


@dataclass
class RepresentativeColor:
    rgb: tuple[int, int, int]
    pixel_count: int
    page_counts: dict[int, int]
    source_count: int = 1


class ColorPaletteError(RuntimeError):
    pass


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(v))) for v in rgb)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    if ImageColor is None:
        raise ColorPaletteError("Pillow is required for color parsing")
    return tuple(ImageColor.getrgb(value))


def rgb_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return math.sqrt(sum((int(x) - int(y)) ** 2 for x, y in zip(a, b)))


def is_near_white(rgb: tuple[int, int, int], threshold: int) -> bool:
    return min(rgb) >= threshold


def is_near_black(rgb: tuple[int, int, int], threshold: int) -> bool:
    return max(rgb) <= threshold


def is_neutral_gray(rgb: tuple[int, int, int], chroma_threshold: int) -> bool:
    return (max(rgb) - min(rgb)) <= chroma_threshold


def nearest_palette_family(
    rgb: tuple[int, int, int],
    threshold: float,
) -> dict[str, Any]:
    families = {
        "viridis_like": VIRIDIS_SAMPLES,
        "plasma_like": PLASMA_SAMPLES,
    }
    best_family = "unmatched"
    best_distance = float("inf")
    for family, samples in families.items():
        distance = min(rgb_distance(rgb, sample) for sample in samples)
        if distance < best_distance:
            best_distance = distance
            best_family = family
    if best_distance > threshold:
        best_family = "unmatched"
    confidence = 0.0
    if best_family != "unmatched":
        confidence = round(max(0.0, 1.0 - (best_distance / max(threshold * 1.5, 1.0))), 4)
    return {
        "classification": best_family,
        "distance": round(best_distance, 4),
        "confidence": confidence,
    }


def merge_nearby_colors(
    page_color_counts: dict[tuple[int, int, int], dict[int, int]],
    merge_distance: float,
) -> list[RepresentativeColor]:
    ordered = sorted(
        page_color_counts.items(),
        key=lambda item: (-sum(item[1].values()), rgb_to_hex(item[0])),
    )
    reps: list[RepresentativeColor] = []
    for rgb, page_counts in ordered:
        pixel_count = sum(page_counts.values())
        match: RepresentativeColor | None = None
        for rep in reps:
            if rgb_distance(rep.rgb, rgb) <= merge_distance:
                match = rep
                break
        if match is None:
            reps.append(RepresentativeColor(rgb=rgb, pixel_count=pixel_count, page_counts=dict(page_counts)))
            continue
        combined = match.pixel_count + pixel_count
        weighted = tuple(
            int(round(((match.rgb[idx] * match.pixel_count) + (rgb[idx] * pixel_count)) / combined))
            for idx in range(3)
        )
        match.rgb = weighted
        match.pixel_count = combined
        match.source_count += 1
        for page_no, count in page_counts.items():
            match.page_counts[page_no] = match.page_counts.get(page_no, 0) + count
    return reps


def filter_representatives(
    reps: list[RepresentativeColor],
    total_pixels: int,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    full_entries: list[dict[str, Any]] = []
    filtered_entries: list[dict[str, Any]] = []
    min_pixel_count = max(int(config["min_pixel_count"]), int(total_pixels * float(config["min_pixel_fraction"])))

    for rep in sorted(reps, key=lambda item: (-item.pixel_count, rgb_to_hex(item.rgb))):
        if rep.pixel_count < min_pixel_count:
            continue
        page_numbers = sorted(rep.page_counts.keys())
        family = nearest_palette_family(rep.rgb, float(config["family_match_distance"]))
        base_filters: list[str] = []
        if config.get("suppress_near_white") and is_near_white(rep.rgb, int(config["white_threshold"])):
            base_filters.append("near_white")
        if config.get("suppress_near_black") and is_near_black(rep.rgb, int(config["black_threshold"])):
            base_filters.append("near_black")
        if config.get("suppress_neutral_gray") and is_neutral_gray(rep.rgb, int(config["gray_chroma_threshold"])):
            base_filters.append("neutral_gray")
        entry = {
            "hex": rgb_to_hex(rep.rgb),
            "rgb": list(rep.rgb),
            "pixel_count": rep.pixel_count,
            "pixel_fraction": round(rep.pixel_count / max(total_pixels, 1), 6),
            "page_count": len(page_numbers),
            "pages": page_numbers,
            "classification": family["classification"],
            "match_distance": family["distance"],
            "match_confidence": family["confidence"],
            "merge_sources": rep.source_count,
            "base_filter_reasons": base_filters,
            "filtered_out": bool(base_filters) or family["classification"] in {"viridis_like", "plasma_like"},
        }
        full_entries.append(entry)
        if not entry["filtered_out"]:
            filtered_entries.append(entry)
    return full_entries, filtered_entries


def render_pdf_pages(pdf_path: Path, dpi: int) -> list[Image.Image]:
    if convert_from_path is None or Image is None:
        raise ColorPaletteError("Missing PDF palette dependencies: pdf2image and Pillow are required")
    poppler_bin = shutil.which("pdftoppm") or shutil.which("pdftocairo")
    poppler_path = str(Path(poppler_bin).parent) if poppler_bin else None
    pages: list[Image.Image] = []
    errors: list[str] = []
    render_attempts = [
        {"fmt": "ppm", "use_pdftocairo": False},
        {"fmt": "png", "use_pdftocairo": bool(shutil.which("pdftocairo"))},
    ]
    for attempt in render_attempts:
        try:
            pages = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                fmt=attempt["fmt"],
                thread_count=1,
                use_pdftocairo=attempt["use_pdftocairo"],
                poppler_path=poppler_path,
            )
            if pages:
                break
        except Exception as exc:
            errors.append(f"{attempt['fmt']}/pdftocairo={attempt['use_pdftocairo']}: {exc}")
    if not pages:
        detail = "; ".join(errors) if errors else "no render backend returned pages"
        raise ColorPaletteError(f"PDF render produced no pages: {detail}")
    return [page.convert("RGB") for page in pages]


def downsample_page(image: Image.Image, max_pixels: int) -> Image.Image:
    if Image is None:
        raise ColorPaletteError("Pillow is required for image resizing")
    page = image.copy()
    if page.width * page.height <= max_pixels:
        return page
    scale = math.sqrt(max_pixels / float(page.width * page.height))
    new_size = (max(1, int(page.width * scale)), max(1, int(page.height * scale)))
    return page.resize(new_size, Image.Resampling.LANCZOS)


def collect_page_color_counts(
    pages: list[Image.Image],
    quantized_colors_per_page: int,
    max_page_pixels: int,
) -> tuple[dict[tuple[int, int, int], dict[int, int]], int, list[dict[str, Any]], list[Image.Image]]:
    color_pages: dict[tuple[int, int, int], dict[int, int]] = defaultdict(lambda: defaultdict(int))
    page_summaries: list[dict[str, Any]] = []
    thumbnails: list[Image.Image] = []
    total_pixels = 0
    for page_index, page in enumerate(pages, start=1):
        sampled = downsample_page(page, max_pixels=max_page_pixels)
        quantized = sampled.quantize(colors=quantized_colors_per_page, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts: dict[tuple[int, int, int], int] = defaultdict(int)
        for rgb in quantized.getdata():
            triplet = tuple(int(v) for v in rgb)
            counts[triplet] += 1
        for rgb, count in counts.items():
            color_pages[rgb][page_index] += count
        page_pixels = sampled.width * sampled.height
        total_pixels += page_pixels
        page_summaries.append(
            {
                "page": page_index,
                "sampled_size": [sampled.width, sampled.height],
                "sampled_pixels": page_pixels,
                "unique_quantized_colors": len(counts),
            }
        )
        thumbs = sampled.copy()
        thumbs.thumbnail((220, 220), Image.Resampling.LANCZOS)
        thumbnails.append(thumbs)
    return color_pages, total_pixels, page_summaries, thumbnails


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "hex",
        "rgb",
        "pixel_count",
        "pixel_fraction",
        "page_count",
        "pages",
        "classification",
        "match_distance",
        "match_confidence",
        "merge_sources",
        "base_filter_reasons",
        "filtered_out",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            row = dict(entry)
            row["rgb"] = ",".join(str(v) for v in entry["rgb"])
            row["pages"] = ",".join(str(v) for v in entry["pages"])
            row["base_filter_reasons"] = ",".join(entry["base_filter_reasons"])
            writer.writerow(row)


def write_debug_montage(path: Path, thumbnails: list[Image.Image]) -> None:
    if not thumbnails:
        return
    if Image is None or ImageDraw is None:
        raise ColorPaletteError("Pillow is required for debug montage generation")
    cols = min(3, len(thumbnails))
    rows = math.ceil(len(thumbnails) / cols)
    tile_w = max(img.width for img in thumbnails)
    tile_h = max(img.height for img in thumbnails)
    canvas_img = Image.new("RGB", (cols * tile_w, rows * tile_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(canvas_img)
    for idx, thumb in enumerate(thumbnails):
        x = (idx % cols) * tile_w
        y = (idx // cols) * tile_h
        canvas_img.paste(thumb, (x, y))
        draw.text((x + 6, y + 6), f"p{idx + 1}", fill=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas_img.save(path)


def write_report_pdf(
    path: Path,
    pdf_path: Path,
    full_entries: list[dict[str, Any]],
    filtered_entries: list[dict[str, Any]],
    page_summaries: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    if canvas is None or letter is None or HexColor is None:
        raise ColorPaletteError("reportlab is required for palette report PDF generation")
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter)
    _page_width, page_height = letter
    margin = 40

    def draw_header(title: str, subtitle: str, y: float) -> float:
        c.setFont("Helvetica-Bold", 15)
        c.drawString(margin, y, title)
        c.setFont("Helvetica", 9)
        c.drawString(margin, y - 14, subtitle)
        return y - 30

    def draw_entry(entry: dict[str, Any], y: float) -> float:
        if y < 80:
            c.showPage()
            return page_height - margin
        hex_code = entry["hex"]
        c.setFillColor(HexColor(hex_code))
        c.rect(margin, y - 14, 18, 18, fill=1, stroke=1)
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin + 26, y, hex_code)
        c.setFont("Helvetica", 9)
        pages_text = ", ".join(str(p) for p in entry["pages"][:8])
        if len(entry["pages"]) > 8:
            pages_text += ", ..."
        meta = (
            f"pixels={entry['pixel_count']}  share={entry['pixel_fraction']:.4f}  pages={pages_text or '-'}  "
            f"class={entry['classification']}  dist={entry['match_distance']}"
        )
        c.drawString(margin + 110, y, meta[:110])
        if entry["base_filter_reasons"]:
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(margin + 110, y - 11, f"suppressed by base filters: {', '.join(entry['base_filter_reasons'])}")
            return y - 26
        return y - 20

    y = page_height - margin
    y = draw_header(
        "Rendered PDF Color Palette Audit",
        f"Source: {pdf_path.name} | extracted from rendered pages, not raw PDF drawing commands",
        y,
    )
    c.setFont("Helvetica", 9)
    note = (
        f"dpi={config['dpi']} merge_distance={config['merge_distance']} family_threshold={config['family_match_distance']} "
        f"suppressed(neutral/black/white)={config['suppress_neutral_gray']}/{config['suppress_near_black']}/{config['suppress_near_white']}"
    )
    c.drawString(margin, y, note[:140])
    y -= 20
    page_meta = f"Rendered pages={len(page_summaries)} sampled_pages={len(page_summaries)}"
    c.drawString(margin, y, page_meta)
    y -= 28

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Full representative palette")
    y -= 18
    for entry in full_entries[:48]:
        y = draw_entry(entry, y)

    c.showPage()
    y = page_height - margin
    y = draw_header(
        "Filtered palette",
        "Viridis/plasma-like colors and configured neutral colors removed from this view.",
        y,
    )
    for entry in filtered_entries[:48]:
        y = draw_entry(entry, y)

    c.save()


def _stable_output_dir(root: Path, pdf_path: Path) -> Path:
    stem = pdf_path.stem[:60].replace(" ", "_")
    digest = hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:10]
    return root / f"{stem}-{digest}"


def audit_pdf_color_palette(
    pdf_path: str | Path,
    output_root: str | Path,
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pdf_file = Path(pdf_path).resolve()
    if not pdf_file.exists():
        raise ColorPaletteError(f"PDF not found: {pdf_file}")
    if pdf_file.suffix.lower() != ".pdf":
        raise ColorPaletteError("Only PDF inputs are supported")

    config = dict(DEFAULT_CONFIG)
    if config_overrides:
        config.update({k: v for k, v in config_overrides.items() if v is not None})

    output_dir = _stable_output_dir(Path(output_root).resolve(), pdf_file)
    output_dir.mkdir(parents=True, exist_ok=True)

    pages = render_pdf_pages(pdf_file, dpi=int(config["dpi"]))
    color_pages, total_pixels, page_summaries, thumbnails = collect_page_color_counts(
        pages,
        quantized_colors_per_page=int(config["quantized_colors_per_page"]),
        max_page_pixels=int(config["max_page_pixels"]),
    )
    reps = merge_nearby_colors(color_pages, merge_distance=float(config["merge_distance"]))
    full_entries, filtered_entries = filter_representatives(reps, total_pixels=total_pixels, config=config)

    full_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(pdf_file),
        "extraction_mode": "rendered_pages",
        "note": "Representative colors extracted from rendered PDF pages. This is not raw PDF object color parsing.",
        "config": config,
        "summary": {
            "page_count": len(pages),
            "sampled_pixels": total_pixels,
            "representative_colors": len(full_entries),
            "filtered_colors": len(filtered_entries),
            "viridis_like": sum(1 for entry in full_entries if entry["classification"] == "viridis_like"),
            "plasma_like": sum(1 for entry in full_entries if entry["classification"] == "plasma_like"),
        },
        "page_sampling": page_summaries,
        "colors": full_entries,
    }
    filtered_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(pdf_file),
        "extraction_mode": "rendered_pages",
        "config": config,
        "filter_basis": {
            "exclude_classifications": ["viridis_like", "plasma_like"],
            "suppress_near_white": bool(config["suppress_near_white"]),
            "suppress_near_black": bool(config["suppress_near_black"]),
            "suppress_neutral_gray": bool(config["suppress_neutral_gray"]),
        },
        "summary": {
            "retained_colors": len(filtered_entries),
            "removed_colors": len(full_entries) - len(filtered_entries),
        },
        "colors": filtered_entries,
    }
    page_usage_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(pdf_file),
        "pages": [
            {
                "page": page["page"],
                "sampled_size": page["sampled_size"],
                "sampled_pixels": page["sampled_pixels"],
                "unique_quantized_colors": page["unique_quantized_colors"],
            }
            for page in page_summaries
        ],
        "color_page_usage": [
            {"hex": entry["hex"], "pages": entry["pages"], "page_count": entry["page_count"]}
            for entry in full_entries
        ],
    }

    write_json(output_dir / "color_palette_full.json", full_payload)
    write_json(output_dir / "color_palette_filtered.json", filtered_payload)
    write_csv(output_dir / "color_palette_full.csv", full_entries)
    write_csv(output_dir / "color_palette_filtered.csv", filtered_entries)
    write_json(output_dir / "color_palette_page_usage.json", page_usage_payload)
    if config.get("create_debug_montage"):
        write_debug_montage(output_dir / "color_palette_debug_montage.png", thumbnails)
    write_report_pdf(
        output_dir / "color_palette_report.pdf",
        pdf_file,
        full_entries,
        filtered_entries,
        page_summaries,
        config,
    )

    return {
        "status": "success",
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(pdf_file),
        "output_dir": str(output_dir),
        "artifact_paths": {
            "color_palette_full_json": str(output_dir / "color_palette_full.json"),
            "color_palette_filtered_json": str(output_dir / "color_palette_filtered.json"),
            "color_palette_full_csv": str(output_dir / "color_palette_full.csv"),
            "color_palette_filtered_csv": str(output_dir / "color_palette_filtered.csv"),
            "color_palette_page_usage_json": str(output_dir / "color_palette_page_usage.json"),
            "color_palette_report_pdf": str(output_dir / "color_palette_report.pdf"),
            "color_palette_debug_montage_png": str(output_dir / "color_palette_debug_montage.png"),
        },
        "summary": full_payload["summary"],
        "top_colors": full_entries[:12],
        "top_filtered_colors": filtered_entries[:12],
    }
