from __future__ import annotations

from dataclasses import dataclass

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.platform import detect_platform


@dataclass
class ModelSelection:
    balanced_model: str
    deep_model: str
    embedding_model: str | None
    embedding_fallback: str | None
    repair_candidates: list[str]


@dataclass
class ModelCapability:
    name: str
    kind: str
    size_hint: str
    recommended_role: str


def infer_model_roles(installed: list[str], config: ReviewerConfig) -> ModelSelection:
    platform_info = detect_platform()
    wanted_balanced = config.defaults.balanced_review_model
    wanted_deep = config.defaults.deep_review_model
    wanted_embed = config.defaults.embedding_model
    wanted_fallback = config.defaults.embedding_fallback_model

    balanced_priority = [
        wanted_balanced,
        "mistral-small3.2:latest",
        "gemma3:27b",
        "qwen3:14b",
        "gemma3:12b",
        "phi4-reasoning:latest",
        "phi4-mini:latest",
    ]
    deep_priority = [
        wanted_deep,
        "qwen3:32b",
        "phi4-reasoning:latest",
        "llama3.3:70b-instruct-q4_K_M",
        "mistral-small3.2:latest",
        "gemma3:27b",
        "qwen3:14b",
    ]
    if platform_info.is_mac_arm:
        balanced_priority = [
            wanted_balanced,
            "qwen3:14b",
            "gemma3:27b",
            "mistral-small3.2:latest",
            "gemma3:12b",
            "phi4-reasoning:latest",
            "phi4-mini:latest",
        ]
        deep_priority = [
            wanted_deep,
            "qwen3:32b",
            "qwen3:14b",
            "llama3.3:70b-instruct-q4_K_M",
            "mistral-small3.2:latest",
            "gemma3:27b",
        ]

    def pick(candidates: list[str], fallback: str) -> str:
        for c in candidates:
            if c and c in installed:
                return c
        return fallback

    balanced = pick(balanced_priority, installed[0] if installed else wanted_balanced)
    deep = pick(deep_priority, balanced)

    embedding_model = wanted_embed if wanted_embed in installed else None
    embedding_fallback = wanted_fallback if wanted_fallback in installed else None
    if embedding_model is None:
        embedding_model = embedding_fallback

    repairs = [m for m in config.defaults.repair_models if m in installed]
    if not repairs:
        repairs = [m for m in installed if "qwen2.5:7b" in m.lower() or "mistral-small3.2" in m.lower() or "mistral" in m.lower() or "qwen" in m.lower()]

    return ModelSelection(
        balanced_model=balanced,
        deep_model=deep,
        embedding_model=embedding_model,
        embedding_fallback=embedding_fallback,
        repair_candidates=repairs,
    )


def is_embedding_model(model_name: str) -> bool:
    lowered = model_name.lower()
    embedding_markers = ["embed", "embedding", "bge-m3", "mxbai", "nomic-embed"]
    return any(marker in lowered for marker in embedding_markers)


def is_multimodal_model(model_name: str) -> bool:
    lowered = model_name.lower()
    return "vl" in lowered or "vision" in lowered


def split_chat_and_embedding_models(installed: list[str]) -> tuple[list[str], list[str]]:
    embedding = [m for m in installed if is_embedding_model(m)]
    chat = [m for m in installed if m not in embedding]
    return sorted(chat), sorted(embedding)


def model_capability(model_name: str) -> ModelCapability:
    lowered = model_name.lower()
    if is_embedding_model(model_name):
        kind = "embedding"
    elif is_multimodal_model(model_name):
        kind = "multimodal"
    else:
        kind = "chat"

    if "70b" in lowered:
        size = "large"
    elif "32b" in lowered:
        size = "large"
    elif "27b" in lowered or "24b" in lowered or "14b" in lowered or "small3.2" in lowered or "phi4-reasoning" in lowered:
        size = "medium"
    elif "12b" in lowered or "8b" in lowered or "7b" in lowered or "4b" in lowered or "mini" in lowered:
        size = "small"
    else:
        size = "unknown"

    role = "general"
    if is_embedding_model(model_name) or "qwen3-embedding" in lowered:
        role = "embedding"
    elif is_multimodal_model(model_name):
        role = "vision"
    elif "qwen2.5:7b" in lowered or "mistral-small3.1" in lowered or "mistral-small3.2" in lowered:
        role = "repair_candidate"
    elif "phi4-reasoning" in lowered:
        role = "reasoning_verifier"
    elif "phi4-mini" in lowered or "qwen3:4b" in lowered:
        role = "triage"
    elif "70b" in lowered:
        role = "deep_review"
    elif "gemma3:27b" in lowered or "mistral-small3.2" in lowered:
        role = "balanced_review"

    return ModelCapability(name=model_name, kind=kind, size_hint=size, recommended_role=role)


def weak_model_warning(model_name: str, task: str) -> str | None:
    lowered = model_name.lower()
    if task == "deep" and ("4b" in lowered or "7b" in lowered or "8b" in lowered):
        return f"{model_name} may be too small for deep review quality."
    if task == "repair" and not ("mistral" in lowered or "qwen" in lowered):
        return f"{model_name} is not a typical repair model; format recovery may be weaker."
    return None
