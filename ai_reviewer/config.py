from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ai_reviewer.paths import REPO_ROOT


@dataclass
class Timeouts:
    connect_seconds: int = 10
    chat_seconds: int = 240
    embed_seconds: int = 120
    health_seconds: int = 5


@dataclass
class RetryPolicy:
    chat_attempts: int = 3
    embed_attempts: int = 2
    base_backoff_seconds: float = 1.0


@dataclass
class ChunkingConfig:
    max_chars: int = 2600
    overlap_chars: int = 260


@dataclass
class RetrievalConfig:
    enabled: bool = True
    top_k: int = 6
    max_chunk_embed_chars: int = 3000


@dataclass
class CompareConfig:
    max_old_chars: int = 20000
    max_new_chars: int = 20000


@dataclass
class BenchmarkDefaults:
    short_fixture: str = "tests/fixtures/sample_short.md"
    long_fixture: str = "tests/fixtures/sample_long.md"
    malformed_fixture: str = "tests/fixtures/malformed_response.txt"
    max_models: int = 4


@dataclass
class TrainingConfig:
    enabled: bool = True
    source_root: str = "training_materials"
    cache_root: str = "data/training_cache"
    auto_sync_on_start: bool = True
    inject_by_default: bool = True
    max_injection_chars: int = 2200


@dataclass
class OrchestratorConfig:
    enabled: bool = False
    model: str = "phi4-reasoning:latest"
    max_stage_retries: int = 1
    max_total_retries: int = 3
    temperature: float = 0.0
    require_json: bool = True
    allow_stage_rerank: bool = True
    enable_final_synthesis_review: bool = True
    enable_writing_qa: bool = True
    enable_deeprun_qa: bool = True
    log_decisions: bool = True
    fail_open: bool = True


@dataclass
class ConcurrencyConfig:
    enable_project_locks: bool = True
    allow_same_project_concurrency: bool = False
    lock_ttl_seconds: int = 4 * 3600


@dataclass
class FigureReviewConfig:
    enabled: bool = False
    model: str = "qwen2.5-vl:7b"
    max_figures: int = 6
    include_captions: bool = True
    include_nearby_text: bool = True
    fail_open: bool = True
    min_confidence: float = 0.3
    style_checks_enabled: bool = True


@dataclass
class CitationFetchConfig:
    enabled: bool = False
    email: str = ""
    max_papers: int = 500
    max_refs_per_doc: int = 500
    request_timeout_seconds: int = 20
    methods: list[str] = field(default_factory=lambda: ["doi_open_access_apis", "crossref_lookup_then_oa"])


@dataclass
class Defaults:
    balanced_review_model: str = "mistral-small3.2:latest"
    deep_review_model: str = "phi4-reasoning:latest"
    embedding_model: str = "bge-m3:latest"
    embedding_fallback_model: str = "nomic-embed-text-v2-moe:latest"
    repair_models: list[str] = field(default_factory=lambda: ["qwen2.5:7b-instruct", "mistral-small3.2:latest"])
    default_profile: str = "balanced"
    output_root: str = "outputs"
    strict_offline: bool = True
    keep_raw_outputs: bool = True
    strict_schema: bool = True
    logging_level: str = "INFO"
    ollama_base_url: str = "http://127.0.0.1:11434"


@dataclass
class ReviewerConfig:
    defaults: Defaults = field(default_factory=Defaults)
    benchmark: BenchmarkDefaults = field(default_factory=BenchmarkDefaults)
    timeouts: Timeouts = field(default_factory=Timeouts)
    retries: RetryPolicy = field(default_factory=RetryPolicy)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    compare: CompareConfig = field(default_factory=CompareConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    figure_review: FigureReviewConfig = field(default_factory=FigureReviewConfig)
    citation_fetch: CitationFetchConfig = field(default_factory=CitationFetchConfig)


DEFAULT_CONFIG = ReviewerConfig()


def _deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_update(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _as_dict(config: ReviewerConfig) -> dict[str, Any]:
    return asdict(config)


def _from_dict(raw: dict[str, Any]) -> ReviewerConfig:
    merged = _deep_update(_as_dict(DEFAULT_CONFIG), raw)
    return ReviewerConfig(
        defaults=Defaults(**merged.get("defaults", {})),
        benchmark=BenchmarkDefaults(**merged.get("benchmark", {})),
        timeouts=Timeouts(**merged.get("timeouts", {})),
        retries=RetryPolicy(**merged.get("retries", {})),
        chunking=ChunkingConfig(**merged.get("chunking", {})),
        retrieval=RetrievalConfig(**merged.get("retrieval", {})),
        compare=CompareConfig(**merged.get("compare", {})),
        training=TrainingConfig(**merged.get("training", {})),
        orchestrator=OrchestratorConfig(**merged.get("orchestrator", {})),
        concurrency=ConcurrencyConfig(**merged.get("concurrency", {})),
        figure_review=FigureReviewConfig(**merged.get("figure_review", {})),
        citation_fetch=CitationFetchConfig(**merged.get("citation_fetch", {})),
    )


def default_config_paths() -> list[Path]:
    return [
        REPO_ROOT / "config" / "defaults.yaml",
        REPO_ROOT / "config" / "local.yaml",
        REPO_ROOT / "config" / "local.override.yaml",
    ]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        patch = yaml.safe_load(handle) or {}
    if not isinstance(patch, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return patch


def _parse_bool(value: str) -> bool:
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean env value: {value}")


def _env_overrides() -> dict[str, Any]:
    mapping: list[tuple[str, tuple[str, ...], Any]] = [
        ("AI_REVIEWER_OUTPUT_ROOT", ("defaults", "output_root"), str),
        ("AI_REVIEWER_STRICT_OFFLINE", ("defaults", "strict_offline"), _parse_bool),
        ("AI_REVIEWER_BALANCED_MODEL", ("defaults", "balanced_review_model"), str),
        ("AI_REVIEWER_DEEP_MODEL", ("defaults", "deep_review_model"), str),
        ("AI_REVIEWER_EMBEDDING_MODEL", ("defaults", "embedding_model"), str),
        ("AI_REVIEWER_OLLAMA_URL", ("defaults", "ollama_base_url"), str),
        ("AI_REVIEWER_CHAT_TIMEOUT", ("timeouts", "chat_seconds"), int),
        ("AI_REVIEWER_EMBED_TIMEOUT", ("timeouts", "embed_seconds"), int),
        ("AI_REVIEWER_CHAT_ATTEMPTS", ("retries", "chat_attempts"), int),
        ("AI_REVIEWER_TRAINING_ENABLED", ("training", "enabled"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_ENABLED", ("orchestrator", "enabled"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_MODEL", ("orchestrator", "model"), str),
        ("AI_REVIEWER_ORCHESTRATOR_MAX_STAGE_RETRIES", ("orchestrator", "max_stage_retries"), int),
        ("AI_REVIEWER_ORCHESTRATOR_MAX_TOTAL_RETRIES", ("orchestrator", "max_total_retries"), int),
        ("AI_REVIEWER_ORCHESTRATOR_TEMPERATURE", ("orchestrator", "temperature"), float),
        ("AI_REVIEWER_ORCHESTRATOR_REQUIRE_JSON", ("orchestrator", "require_json"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_ALLOW_STAGE_RERANK", ("orchestrator", "allow_stage_rerank"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_ENABLE_FINAL_SYNTHESIS_REVIEW", ("orchestrator", "enable_final_synthesis_review"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_ENABLE_WRITING_QA", ("orchestrator", "enable_writing_qa"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_ENABLE_DEEPRUN_QA", ("orchestrator", "enable_deeprun_qa"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_LOG_DECISIONS", ("orchestrator", "log_decisions"), _parse_bool),
        ("AI_REVIEWER_ORCHESTRATOR_FAIL_OPEN", ("orchestrator", "fail_open"), _parse_bool),
        ("AI_REVIEWER_LOCKS_ENABLED", ("concurrency", "enable_project_locks"), _parse_bool),
        ("AI_REVIEWER_ALLOW_SAME_PROJECT_CONCURRENCY", ("concurrency", "allow_same_project_concurrency"), _parse_bool),
        ("AI_REVIEWER_LOCK_TTL_SECONDS", ("concurrency", "lock_ttl_seconds"), int),
        ("AI_REVIEWER_FIGURE_REVIEW_ENABLED", ("figure_review", "enabled"), _parse_bool),
        ("AI_REVIEWER_FIGURE_REVIEW_MODEL", ("figure_review", "model"), str),
        ("AI_REVIEWER_FIGURE_REVIEW_MAX_FIGURES", ("figure_review", "max_figures"), int),
        ("AI_REVIEWER_FIGURE_REVIEW_INCLUDE_CAPTIONS", ("figure_review", "include_captions"), _parse_bool),
        ("AI_REVIEWER_FIGURE_REVIEW_INCLUDE_NEARBY_TEXT", ("figure_review", "include_nearby_text"), _parse_bool),
        ("AI_REVIEWER_FIGURE_REVIEW_FAIL_OPEN", ("figure_review", "fail_open"), _parse_bool),
        ("AI_REVIEWER_FIGURE_REVIEW_MIN_CONFIDENCE", ("figure_review", "min_confidence"), float),
        ("AI_REVIEWER_FIGURE_STYLE_CHECKS_ENABLED", ("figure_review", "style_checks_enabled"), _parse_bool),
        ("AI_REVIEWER_CITATION_FETCH_ENABLED", ("citation_fetch", "enabled"), _parse_bool),
        ("AI_REVIEWER_CITATION_FETCH_EMAIL", ("citation_fetch", "email"), str),
        ("AI_REVIEWER_CITATION_FETCH_MAX_PAPERS", ("citation_fetch", "max_papers"), int),
        ("AI_REVIEWER_CITATION_FETCH_MAX_REFS", ("citation_fetch", "max_refs_per_doc"), int),
        ("AI_REVIEWER_CITATION_FETCH_TIMEOUT", ("citation_fetch", "request_timeout_seconds"), int),
        (
            "AI_REVIEWER_CITATION_FETCH_METHODS",
            ("citation_fetch", "methods"),
            lambda v: [x.strip() for x in v.split(",") if x.strip()],
        ),
    ]

    out: dict[str, Any] = {}
    for env_key, path, caster in mapping:
        raw = os.getenv(env_key)
        if raw is None:
            continue
        value = caster(raw)
        cursor = out
        for section in path[:-1]:
            cursor = cursor.setdefault(section, {})
        cursor[path[-1]] = value
    return out


def load_config(extra_path: str | None = None) -> ReviewerConfig:
    merged: dict[str, Any] = {}
    for path in default_config_paths():
        if path.exists():
            merged = _deep_update(merged, _load_yaml(path))
    if extra_path:
        cfg_path = Path(extra_path)
        if cfg_path.exists():
            merged = _deep_update(merged, _load_yaml(cfg_path))
        else:
            raise FileNotFoundError(f"Config path not found: {cfg_path}")
    merged = _deep_update(merged, _env_overrides())
    return _from_dict(merged)


def write_example_local_config(path: Path) -> None:
    sample = {
        "defaults": {
            "balanced_review_model": "mistral-small3.2:latest",
            "deep_review_model": "phi4-reasoning:latest",
            "embedding_model": "bge-m3:latest",
            "embedding_fallback_model": "nomic-embed-text-v2-moe:latest",
            "repair_models": ["qwen2.5:7b-instruct", "mistral-small3.2:latest"],
            "output_root": "outputs",
            "strict_offline": True,
            "keep_raw_outputs": True,
            "strict_schema": True,
            "logging_level": "INFO",
            "ollama_base_url": "http://127.0.0.1:11434",
        },
        "timeouts": {
            "connect_seconds": 10,
            "chat_seconds": 240,
            "embed_seconds": 120,
            "health_seconds": 5,
        },
        "retries": {
            "chat_attempts": 3,
            "embed_attempts": 2,
            "base_backoff_seconds": 1.0,
        },
        "chunking": {
            "max_chars": 2600,
            "overlap_chars": 260,
        },
        "retrieval": {
            "enabled": True,
            "top_k": 6,
            "max_chunk_embed_chars": 3000,
        },
        "compare": {
            "max_old_chars": 20000,
            "max_new_chars": 20000,
        },
        "benchmark": {
            "short_fixture": "tests/fixtures/sample_short.md",
            "long_fixture": "tests/fixtures/sample_long.md",
            "malformed_fixture": "tests/fixtures/malformed_response.txt",
            "max_models": 4,
        },
        "training": {
            "enabled": True,
            "source_root": "training_materials",
            "cache_root": "data/training_cache",
            "auto_sync_on_start": True,
            "inject_by_default": True,
            "max_injection_chars": 2200,
        },
        "orchestrator": {
            "enabled": False,
            "model": "phi4-reasoning:latest",
            "max_stage_retries": 1,
            "max_total_retries": 3,
            "temperature": 0.0,
            "require_json": True,
            "allow_stage_rerank": True,
            "enable_final_synthesis_review": True,
            "enable_writing_qa": True,
            "enable_deeprun_qa": True,
            "log_decisions": True,
            "fail_open": True,
        },
        "citation_fetch": {
            "enabled": False,
            "email": "",
            "max_papers": 500,
            "max_refs_per_doc": 500,
            "request_timeout_seconds": 20,
            "methods": ["doi_open_access_apis", "crossref_lookup_then_oa"],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(sample, handle, sort_keys=False)
