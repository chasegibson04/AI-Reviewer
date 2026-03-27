from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.review.repair import parse_and_repair


@dataclass
class BenchmarkResult:
    model: str
    success: bool
    latency_seconds: float
    structured_pass: bool
    repair_needed: bool
    completeness_score: float
    output_length: int
    quality_note: str
    recommendation_tag: str


def _recommendation_tag(model: str, latency: float, structured: bool, repair_needed: bool, completeness: float) -> str:
    lowered = model.lower()
    if not structured:
        return "avoid for primary review"
    if "mistral" in lowered or "qwen" in lowered:
        return "use only for repair" if repair_needed or completeness < 0.55 else "best speed"
    if latency < 7 and completeness >= 0.65:
        return "best speed"
    if completeness >= 0.8 and not repair_needed:
        return "best quality"
    return "best default"


def benchmark_models(
    provider: Provider,
    models: list[str],
    short_fixture: Path,
    long_fixture: Path,
    malformed_fixture: Path,
    repair_models: list[str],
    timeout_seconds: int,
    logger,
) -> list[BenchmarkResult]:
    short_text = short_fixture.read_text(encoding="utf-8", errors="replace")
    long_text = long_fixture.read_text(encoding="utf-8", errors="replace")
    malformed_text = malformed_fixture.read_text(encoding="utf-8", errors="replace")
    results: list[BenchmarkResult] = []

    for model in models:
        prompt = (
            "Produce a strict review JSON that includes summary, major strengths, major weaknesses, recommendation, confidence, and action items. "
            "Return JSON only.\n\n"
            f"SHORT_DOC:\n{short_text[:4500]}\n\nLONG_DOC:\n{long_text[:13000]}\n"
        )
        start = time.time()
        try:
            resp = provider.chat(
                ChatRequest(
                    model=model,
                    system_prompt="You are a benchmarked review model.",
                    user_prompt=prompt,
                    temperature=0.1,
                    max_tokens=1700,
                    timeout_seconds=timeout_seconds,
                )
            )
            elapsed = time.time() - start

            parsed = parse_and_repair(
                resp.content,
                provider=provider,
                primary_model=model,
                repair_models=repair_models,
                timeout_seconds=timeout_seconds,
                logger=logger,
                allow_self_repair=False,
            )
            malformed_repair = parse_and_repair(
                malformed_text,
                provider=provider,
                primary_model=model,
                repair_models=repair_models,
                timeout_seconds=timeout_seconds,
                logger=logger,
                allow_self_repair=False,
            )

            structured_pass = parsed.parsed is not None and parsed.parse_failures <= 1
            repair_needed = parsed.repair_stage != "initial"
            completeness = 0.0
            if parsed.parsed is not None:
                rv = parsed.parsed
                filled_sections = sum(
                    1
                    for section in [
                        rv.summary,
                        rv.major_strengths,
                        rv.major_weaknesses,
                        rv.methodological_concerns,
                        rv.statistical_concerns,
                        rv.detailed_reviewer_comments,
                        rv.extracted_action_items,
                    ]
                    if section
                )
                completeness = round(filled_sections / 7.0, 3)

            if malformed_repair.parsed is None:
                completeness = max(0.0, completeness - 0.2)

            quality_note = "robust" if structured_pass and completeness >= 0.7 else "formatting or completeness weak"
            tag = _recommendation_tag(model, elapsed, structured_pass, repair_needed, completeness)

            results.append(
                BenchmarkResult(
                    model=model,
                    success=True,
                    latency_seconds=elapsed,
                    structured_pass=structured_pass,
                    repair_needed=repair_needed,
                    completeness_score=completeness,
                    output_length=len(resp.content),
                    quality_note=quality_note,
                    recommendation_tag=tag,
                )
            )
        except Exception as exc:
            elapsed = time.time() - start
            results.append(
                BenchmarkResult(
                    model=model,
                    success=False,
                    latency_seconds=elapsed,
                    structured_pass=False,
                    repair_needed=False,
                    completeness_score=0.0,
                    output_length=0,
                    quality_note=f"failed: {exc}",
                    recommendation_tag="avoid for primary review",
                )
            )

    if results:
        best_idx = max(range(len(results)), key=lambda i: (results[i].completeness_score, -results[i].latency_seconds))
        if results[best_idx].success and results[best_idx].structured_pass:
            results[best_idx].recommendation_tag = "best default"

    return results


def write_benchmark_report(path: Path, results: list[BenchmarkResult]) -> None:
    serialized = [r.__dict__ for r in results]
    path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
