from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from planner import build_fallback_plan, merge_ai_seed_into_plan

AI_ENGINE_VERSION = "groq-qwen38-seed-v3"


@dataclass(frozen=True)
class GroqConfig:
    api_key: str
    model: str = "qwen/qwen3.8-27b"
    base_url: str = "https://api.groq.com/openai/v1"
    timeout_seconds: int = 120


def get_groq_config(api_key: str, model: str, base_url: str) -> GroqConfig:
    return GroqConfig(
        api_key=api_key,
        model=model or "qwen/qwen3.8-27b",
        base_url=(base_url or "https://api.groq.com/openai/v1").rstrip("/"),
        timeout_seconds=120,
    )


def _parse_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _number_sow_statements(sow_text: str, limit: int = 18) -> list[str]:
    import re

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", sow_text)
        if s.strip() and len(s.strip()) >= 20
    ]
    return sentences[:limit]


# Intentionally tiny JSON object. Groq's documented API exposes max_completion_tokens,
# but this user's organization has reported a 1,000-output-token/minute limit. Keeping
# the requested completion at 600 and avoiding a large strict JSON schema prevents the
# planner call from being rejected for expected output size.
SEED_SYSTEM_PROMPT = """
You are a senior project/program manager. Analyze the supplied SOW and return a VERY COMPACT
JSON planning seed for a deterministic planning engine.

Return ONLY JSON with these keys:
project_type: short string
summary: short string
phases: array of up to 4 short strings
activities: array of up to 4 objects with name, phase, source_index
milestones: array of up to 3 short strings
gaps: array of up to 3 short strings
risks: array of up to 3 short strings

Rules:
- Use only information supported by the SOW.
- source_index refers to the numbered SOW statements in the prompt.
- Keep strings very short.
- Do not generate a full WBS, traceability matrix, or long explanations.
- Do not invent dates, budgets, resources, or contractual commitments.
- Surface ambiguity as a gap.
""".strip()


def generate_plan_with_groq(sow_text: str, project_name: str, config: GroqConfig) -> dict[str, Any]:
    if not config.api_key:
        raise RuntimeError("Groq API key is missing.")

    numbered = _number_sow_statements(sow_text)
    numbered_text = "\n".join(f"{i}. {text}" for i, text in enumerate(numbered, 1))

    user_prompt = f"""
Project name: {project_name}

NUMBERED SOW STATEMENTS:
{numbered_text}

Return the compact JSON seed now. Keep the entire answer brief enough for a 600-token maximum response.
""".strip()

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SEED_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "reasoning_effort": "none",
        "reasoning_format": "hidden",
        # Use the current parameter name documented by Groq.
        "max_completion_tokens": 600,
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
        raise RuntimeError(f"Groq returned no choices: {json.dumps(body)[:2000]}")

    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise RuntimeError("Groq returned an empty model response.")

    seed = _parse_content(content)
    if not isinstance(seed, dict):
        raise RuntimeError("Groq returned JSON, but it was not an object.")

    # Normalize the smaller seed into the existing merge contract.
    normalized = {
        "project_type": seed.get("project_type", "").strip() if isinstance(seed.get("project_type"), str) else "",
        "description": seed.get("summary", "").strip() if isinstance(seed.get("summary"), str) else "",
        "confidence": "High" if seed.get("project_type") else "Medium",
        "phases": [
            {"phase": str(x).strip(), "purpose": "AI-suggested phase; PM review required."}
            for x in (seed.get("phases") or []) if str(x).strip()
        ][:4],
        "key_activities": [],
        "milestones": [],
        "gaps": [str(x).strip() for x in (seed.get("gaps") or []) if str(x).strip()][:3],
        "risks": [str(x).strip() for x in (seed.get("risks") or []) if str(x).strip()][:3],
        "assumptions": [],
    }

    for row in (seed.get("activities") or [])[:4]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        normalized["key_activities"].append(
            {
                "name": name,
                "phase": str(row.get("phase", "")).strip() or "Execution",
                "duration_days": 5,
                "owner_role": "Project Team",
                "source_indexes": [int(row["source_index"]) ] if str(row.get("source_index", "")).isdigit() else [],
            }
        )

    for item in (seed.get("milestones") or [])[:3]:
        if isinstance(item, str) and item.strip():
            normalized["milestones"].append({"name": item.strip(), "target": "TBD"})

    base_plan = build_fallback_plan(sow_text, project_name)
    plan = merge_ai_seed_into_plan(base_plan, normalized)
    plan.setdefault("metadata", {})
    plan["metadata"].update(
        {
            "engine": "groq_qwen38_compact_seed",
            "engine_version": AI_ENGINE_VERSION,
            "source_characters": len(sow_text),
            "model": config.model,
            "ai_output_cap": 600,
        }
    )
    return plan
