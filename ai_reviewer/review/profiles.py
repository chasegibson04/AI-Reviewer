from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewProfile:
    key: str
    display_name: str
    system_prompt: str
    rubric_focus: str
    chunk_size: int
    chunk_overlap: int
    ensemble_count: int
    reflection_count: int
    strict_schema: bool
    force_repair_pass: bool
    use_retrieval: bool
    include_section_comments: bool
    temperature: float
    max_review_words: int


PROFILES: dict[str, ReviewProfile] = {
    "quick": ReviewProfile(
        key="quick",
        display_name="Quick Screen",
        system_prompt="You are a strict screening reviewer. Identify acceptance blockers fast.",
        rubric_focus="Find fatal flaws and top risks quickly with concise bullets.",
        chunk_size=1800,
        chunk_overlap=120,
        ensemble_count=1,
        reflection_count=1,
        strict_schema=True,
        force_repair_pass=False,
        use_retrieval=False,
        include_section_comments=False,
        temperature=0.1,
        max_review_words=650,
    ),
    "balanced": ReviewProfile(
        key="balanced",
        display_name="Balanced Reviewer",
        system_prompt="You are a balanced, evidence-driven ML reviewer.",
        rubric_focus="Balance novelty, rigor, and writing quality with actionable recommendations.",
        chunk_size=2600,
        chunk_overlap=260,
        ensemble_count=1,
        reflection_count=2,
        strict_schema=True,
        force_repair_pass=False,
        use_retrieval=True,
        include_section_comments=True,
        temperature=0.2,
        max_review_words=1300,
    ),
    "deep": ReviewProfile(
        key="deep",
        display_name="Deep Reviewer",
        system_prompt="You are a highly critical senior reviewer focused on methodological rigor.",
        rubric_focus="Deeply inspect claims, assumptions, controls, and reproducibility.",
        chunk_size=3400,
        chunk_overlap=340,
        ensemble_count=1,
        reflection_count=3,
        strict_schema=True,
        force_repair_pass=True,
        use_retrieval=True,
        include_section_comments=True,
        temperature=0.15,
        max_review_words=1900,
    ),
    "adversarial": ReviewProfile(
        key="adversarial",
        display_name="Reviewer #2",
        system_prompt="You are Reviewer #2: adversarial, precise, and evidence-focused.",
        rubric_focus="Stress-test overclaiming, weak baselines, and unsupported conclusions.",
        chunk_size=2400,
        chunk_overlap=220,
        ensemble_count=1,
        reflection_count=2,
        strict_schema=True,
        force_repair_pass=True,
        use_retrieval=True,
        include_section_comments=True,
        temperature=0.2,
        max_review_words=1500,
    ),
    "writing": ReviewProfile(
        key="writing",
        display_name="Writing & Clarity",
        system_prompt="You are an editorial reviewer focusing on clarity, structure, and readability.",
        rubric_focus="Prioritize writing flow, structure, readability, and ambiguity reduction.",
        chunk_size=3000,
        chunk_overlap=200,
        ensemble_count=1,
        reflection_count=1,
        strict_schema=True,
        force_repair_pass=False,
        use_retrieval=False,
        include_section_comments=True,
        temperature=0.25,
        max_review_words=1000,
    ),
    "methods": ReviewProfile(
        key="methods",
        display_name="Methods & Rigor",
        system_prompt="You are a methods/statistics reviewer auditing validity and inferential rigor.",
        rubric_focus="Assess controls, ablations, significance, uncertainty, and reproducibility.",
        chunk_size=2500,
        chunk_overlap=250,
        ensemble_count=1,
        reflection_count=2,
        strict_schema=True,
        force_repair_pass=True,
        use_retrieval=True,
        include_section_comments=True,
        temperature=0.12,
        max_review_words=1400,
    ),
    "revision": ReviewProfile(
        key="revision",
        display_name="Revision Comparison",
        system_prompt="You are reviewing a revised manuscript against prior weaknesses.",
        rubric_focus="What changed, what remains unresolved, and what regressed.",
        chunk_size=2400,
        chunk_overlap=220,
        ensemble_count=1,
        reflection_count=1,
        strict_schema=True,
        force_repair_pass=True,
        use_retrieval=True,
        include_section_comments=True,
        temperature=0.15,
        max_review_words=1100,
    ),
    "editor": ReviewProfile(
        key="editor",
        display_name="Short Editor Summary",
        system_prompt="You are an editor writing a concise decision memo.",
        rubric_focus="High-signal summary for editorial decision support.",
        chunk_size=3200,
        chunk_overlap=120,
        ensemble_count=1,
        reflection_count=1,
        strict_schema=True,
        force_repair_pass=False,
        use_retrieval=False,
        include_section_comments=False,
        temperature=0.1,
        max_review_words=500,
    ),
    "citation": ReviewProfile(
        key="citation",
        display_name="Citation Sanity",
        system_prompt="You are evaluating citation relevance, coverage, and reference integrity.",
        rubric_focus="Detect missing key citations, weak prior-work framing, and citation misuse.",
        chunk_size=2600,
        chunk_overlap=180,
        ensemble_count=1,
        reflection_count=1,
        strict_schema=True,
        force_repair_pass=True,
        use_retrieval=True,
        include_section_comments=False,
        temperature=0.15,
        max_review_words=900,
    ),
    "repro": ReviewProfile(
        key="repro",
        display_name="Reproducibility & Transparency",
        system_prompt="You focus on reproducibility, transparency, and implementation readiness.",
        rubric_focus="Assess reproducibility artifacts, experiment traceability, and reporting completeness.",
        chunk_size=2600,
        chunk_overlap=260,
        ensemble_count=1,
        reflection_count=2,
        strict_schema=True,
        force_repair_pass=True,
        use_retrieval=True,
        include_section_comments=True,
        temperature=0.15,
        max_review_words=1200,
    ),
}


def get_profile(profile_key: str) -> ReviewProfile:
    key = profile_key.lower().strip()
    if key not in PROFILES:
        valid = ", ".join(sorted(PROFILES))
        raise KeyError(f"Unknown profile '{profile_key}'. Valid profiles: {valid}")
    return PROFILES[key]
