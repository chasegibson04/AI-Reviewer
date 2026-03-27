from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def strip_reference_noise(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().lower().startswith("copyright"):
            continue
        lines.append(line)
    return "\n".join(lines)
