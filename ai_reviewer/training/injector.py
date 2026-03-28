from __future__ import annotations

from dataclasses import dataclass

from ai_reviewer.training.schema import GlobalGuidance


PROFILE_CATEGORY_MAP: dict[str, list[str]] = {
    "quick": ["published_papers", "external_guides"],
    "balanced": ["published_papers", "external_guides"],
    "deep": ["published_papers", "external_guides", "other_groups_papers"],
    "adversarial": ["external_guides", "other_groups_papers", "published_papers"],
    "writing": ["formatting_color_guides", "published_papers", "external_guides"],
    "methods": ["published_papers", "other_groups_papers", "external_guides"],
    "revision": ["in_progress_examples", "published_papers", "external_guides"],
    "editor": ["external_guides", "published_papers", "formatting_color_guides"],
    "citation": ["external_guides", "published_papers", "other_groups_papers"],
    "repro": ["external_guides", "published_papers", "other_groups_papers"],
}


@dataclass
class GuidanceInjection:
    enabled: bool
    prompt_block: str
    categories_used: list[str]
    source_count: int
    warning_count: int


def build_guidance_injection(guidance: GlobalGuidance, profile_key: str, max_chars: int = 2200) -> GuidanceInjection:
    if guidance.active_file_count <= 0:
        return GuidanceInjection(enabled=False, prompt_block="", categories_used=[], source_count=0, warning_count=len(guidance.warnings))

    categories = PROFILE_CATEGORY_MAP.get(profile_key, list(guidance.category_guidance.keys()))
    lines = [
        "LAB TRAINING GUIDANCE (global, local cache):",
        f"Active files: {guidance.active_file_count}",
        f"Global summary: {guidance.global_summary}",
        "Apply as style/format constraints only; keep all critique grounded in manuscript context.",
    ]

    def _clean_bullets(items: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        raw_candidates: list[str] = []
        for raw in items:
            s = " ".join(str(raw).split()).strip()
            if not s:
                continue
            raw_candidates.append(s)
            low = s.lower()
            if low.startswith("use heading pattern similar to:"):
                continue
            if "intentionally omitted" in low:
                continue
            if len(s) < 20:
                continue
            if s in seen:
                continue
            seen.add(s)
            cleaned.append(s)
        if not cleaned:
            # Fallback for sparse fixtures or tiny guidance sets.
            for s in raw_candidates[:2]:
                if s not in seen:
                    cleaned.append(s)
                    seen.add(s)
        return cleaned

    used: list[str] = []
    for category in categories:
        bullets = _clean_bullets(guidance.category_guidance.get(category, []))[:3]
        if not bullets:
            continue
        used.append(category)
        lines.append(f"{category}:")
        lines.extend([f"- {b}" for b in bullets])
    if not used:
        fallback = sorted(guidance.category_guidance.keys())[:2]
        for category in fallback:
            bullets = _clean_bullets(guidance.category_guidance.get(category, []))[:3]
            if not bullets:
                continue
            used.append(category)
            lines.append(f"{category}:")
            lines.extend([f"- {b}" for b in bullets])
    if not used and guidance.active_file_count > 0:
        used.append("global_fallback")
        lines.append("global_fallback:")
        lines.append(f"- {guidance.global_summary}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 24].rstrip() + "\n- [truncated for budget]"
    return GuidanceInjection(
        enabled=bool(used),
        prompt_block=text if used else "",
        categories_used=used,
        source_count=guidance.active_file_count,
        warning_count=len(guidance.warnings),
    )
