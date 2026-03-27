from __future__ import annotations

from dataclasses import dataclass

from ai_reviewer.config import ReviewerConfig


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
    wanted_balanced = config.defaults.balanced_review_model
    wanted_deep = config.defaults.deep_review_model
    wanted_embed = config.defaults.embedding_model
    wanted_fallback = config.defaults.embedding_fallback_model

    balanced_priority = [
        wanted_balanced,
        "mistral-small3.2:latest",
        "gemma3:27b",
        "gemma3:12b",
        "phi4-reasoning:latest",
        "phi4-mini:latest",
    ]
    deep_priority = [
        wanted_deep,
        "phi4-reasoning:latest",
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


def split_chat_and_embedding_models(installed: list[str]) -> tuple[list[str], list[str]]:
    embedding_markers = ["embed", "embedding", "bge-m3"]
    embedding = [m for m in installed if any(marker in m.lower() for marker in embedding_markers)]
    chat = [m for m in installed if m not in embedding]
    return sorted(chat), sorted(embedding)


def model_capability(model_name: str) -> ModelCapability:
    lowered = model_name.lower()
    kind = "embedding" if "embed" in lowered or "embedding" in lowered or "bge-m3" in lowered else "chat"

    if "70b" in lowered:
        size = "large"
    elif "27b" in lowered or "24b" in lowered or "small3.2" in lowered or "phi4-reasoning" in lowered:
        size = "medium"
    elif "12b" in lowered or "8b" in lowered or "7b" in lowered or "4b" in lowered or "mini" in lowered:
        size = "small"
    else:
        size = "unknown"

    role = "general"
    if "bge-m3" in lowered or "mxbai" in lowered or "nomic-embed" in lowered or "qwen3-embedding" in lowered:
        role = "embedding"
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
