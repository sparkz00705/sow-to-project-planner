
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests

AI_ENGINE_VERSION = "groq-qwen38-compact-v4"


@dataclass(frozen=True)
class GroqConfig:
    api_key: str
    model: str = "qwen/qwen3.8-27b"
    base_url: str = "https://api.groq.com/openai/v1"
    timeout_seconds: int = 90


def get_groq_config(api_key: str, model: str, base_url: str) -> GroqConfig:
    return GroqConfig(
        api_key=api_key,
        model=model or "qwen/qwen3.8-27b",
        base_url=(base_url or "https://api.groq.com/openai/v1").rstrip("/"),
    )


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        value = json.loads(match.group(0))
        if isinstance(value, dict):
            return value
    raise ValueError("Groq response was not valid JSON.")


def _compact_sow(sow_items: list[dict[str, Any]], max_items: int = 20) -> str:
    rows = []
    count = 0
    for row in sow_items:
        if not row.get("executable") and row.get("type") not in {"Milestone", "Clarification / Gap", "Risk / Constraint"}:
            continue
        count += 1
        rows.append(f"{count}. {row.get('statement','')[:220]}")
        if len(rows) >= max_items:
            break
    return "\n".join(rows)


def generate_ai_advice(sow_items: list[dict[str, Any]], project_name: str, config: GroqConfig) -> dict[str, Any]:
    if not config.api_key:
        raise RuntimeError("Groq API key is missing.")

    prompt = f"""
Project: {project_name}

You are advising a project manager. Return ONLY a compact JSON object with:
project_type (string),
summary (string <= 250 chars),
confidence ("High"|"Medium"|"Low"),
gaps (array of <= 3 short strings),
risks (array of <= 3 short strings),
assumptions (array of <= 3 short strings).

Do NOT generate a WBS, task list, traceability table, dates, durations, budgets, resources or long prose.
Use only the information in the SOW excerpts below. Treat ambiguity as a gap.

SOW EXCERPTS:
{_compact_sow(sow_items)}
""".strip()

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "You are a senior project/program planning advisor. Be concise."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 450,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "X-Title": "SOW Project Planner",
    }
    response = requests.post(
        f"{config.base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=config.timeout_seconds,
    )
    if not response.ok:
        raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text[:2000]}")

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("Groq returned no choices.")
    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    result = _extract_json(content)

    result.setdefault("gaps", [])
    result.setdefault("risks", [])
    result.setdefault("assumptions", [])
    return result
