from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from planner import build_fallback_plan, merge_ai_seed_into_plan


@dataclass(frozen=True)
class GroqConfig:
    api_key: str
    model: str = "qwen/qwen3.8-27b"
    base_url: str = "https://api.groq.com/openai/v1"
    timeout_seconds: int = 180


def get_groq_config(api_key: str, model: str, base_url: str) -> GroqConfig:
    return GroqConfig(
        api_key=api_key,
        model=model or "qwen/qwen3.8-27b",
        base_url=(base_url or "https://api.groq.com/openai/v1").rstrip("/"),
        timeout_seconds=180,
    )


# Deliberately small schema. Groq's current organization limit reported by the
# user's account is 1,000 output tokens/minute. Asking Qwen to produce the full
# plan in one response causes schema truncation. The AI therefore returns only
# a compact planning seed; deterministic local code expands it into the full plan.
AI_SEED_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "project_type": {"type": "string"},
        "description": {"type": "string"},
        "confidence": {"type": "string"},
        "phases": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "phase": {"type": "string"},
                    "purpose": {"type": "string"},
                },
                "required": ["phase", "purpose"],
            },
        },
        "key_activities": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "phase": {"type": "string"},
                    "duration_days": {"type": "integer"},
                    "owner_role": {"type": "string"},
                    "source_indexes": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {"type": "integer"},
                    },
                },
                "required": ["name", "phase", "duration_days", "owner_role", "source_indexes"],
            },
        },
        "milestones": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "target": {"type": "string"},
                },
                "required": ["name", "target"],
            },
        },
        "gaps": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
        },
        "risks": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
        },
        "assumptions": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
        },
    },
    "required": [
        "project_type",
        "description",
        "confidence",
        "phases",
        "key_activities",
        "milestones",
        "gaps",
        "risks",
        "assumptions",
    ],
}


SYSTEM_PROMPT = """
You are a senior project/program management planning architect.
Analyze the supplied Statement of Work and produce a compact planning seed.

Important rules:
1. Use only facts supported by the SOW; clearly separate planning proposals.
2. Project type should be specific when evidence exists; otherwise use a cautious label.
3. Identify the most useful phases and 6 or fewer high-value activities.
4. Keep every field short. Do not write paragraphs inside arrays.
5. For each AI activity, source_indexes refer to the numbered SOW statements supplied in the prompt.
6. Do not invent contractual commitments, dates, budgets, resources, acceptance criteria, or scope.
7. Surface ambiguity as a gap instead of silently resolving it.
""".strip()


def _parse_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _number_sow_statements(sow_text: str, limit: int = 24) -> list[str]:
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", sow_text) if s.strip()]
    result = []
    for sentence in sentences:
        if len(sentence) < 20:
            continue
        result.append(sentence)
        if len(result) >= limit:
            break
    return result


def generate_plan_with_groq(sow_text: str, project_name: str, config: GroqConfig) -> dict[str, Any]:
    if not config.api_key:
        raise RuntimeError("Groq API key is missing.")

    numbered = _number_sow_statements(sow_text)
    numbered_text = "\n".join(f"{i}. {text}" for i, text in enumerate(numbered, 1))

    user_prompt = f"""
Project name: {project_name}

NUMBERED SOW STATEMENTS:
{numbered_text}

Return ONLY the compact JSON object required by the schema.
Prioritize the project type, 4-5 phases, up to 6 key activities, key milestones, and the most material gaps/risks.
Use very short phrases. The response must stay compact.
""".strip()

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "reasoning_effort": "none",
        "reasoning_format": "hidden",
        "max_completion_tokens": 650,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sow_planning_seed",
                "strict": True,
                "schema": AI_SEED_SCHEMA,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "X-Title": "SOW Project Planner",
    }

    url = f"{config.base_url}/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=config.timeout_seconds)
    if not response.ok:
        raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text[:2000]}")

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"Groq returned no choices: {json.dumps(body)[:2000]}")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError("Groq returned an empty model response.")

    seed = _parse_content(content)
    base_plan = build_fallback_plan(sow_text, project_name)
    plan = merge_ai_seed_into_plan(base_plan, seed)
    plan.setdefault("metadata", {})
    plan["metadata"].update(
        {
            "engine": "groq_ai_seed_plus_local_planner",
            "source_characters": len(sow_text),
            "model": config.model,
        }
    )
    return plan
