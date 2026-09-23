from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from planner import build_fallback_plan, merge_ai_seed_into_plan, parse_sow_items

AI_ENGINE_VERSION = "groq-qwen38-guided-structured-v4"


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
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise RuntimeError("Groq returned JSON, but it was not an object.")
    return obj


def _select_ai_items(items: list[dict[str, Any]], limit: int = 16) -> list[tuple[int, dict[str, Any]]]:
    """Select useful SOW source items while preserving their original 1-based indexes."""
    preferred = {"Scope / Workstream", "Deliverable", "Acceptance", "Milestone", "Dependency", "Risk / Constraint", "Assumption"}
    selected: list[tuple[int, dict[str, Any]]] = []

    # Prioritize actual workstreams and obligations first.
    for idx, item in enumerate(items, 1):
        if item.get("type") in preferred:
            selected.append((idx, item))
        if len(selected) >= limit:
            break

    # Ensure earlier context is represented for SOWs without enough typed items.
    if len(selected) < limit:
        used = {i for i, _ in selected}
        for idx, item in enumerate(items, 1):
            if idx not in used:
                selected.append((idx, item))
            if len(selected) >= limit:
                break
    return selected


SEED_SYSTEM_PROMPT = """
You are a senior project/program manager. Analyze the SOW and return a compact JSON planning seed.
The deterministic planning engine will create the full WBS and detailed schedule, so you must NOT
write the entire project plan.

Return ONLY JSON with these keys:
project_type: short string
summary: short string
phases: array of up to 4 objects {phase: short string}
activities: array of up to 4 objects {name: short string, phase: short string, source_index: integer}
milestones: array of up to 3 objects {name: short string, target: short string}
gaps: array of up to 3 short strings
risks: array of up to 3 short strings

Rules:
- source_index MUST refer to the exact numbered SOW item shown in the prompt.
- Use only information supported by the SOW.
- Keep every string short.
- Prioritize workstreams, major deliverables, acceptance conditions and explicit milestones.
- Do not convert exclusions, assumptions, responsibilities or risks into activities.
- Do not invent dates, budgets, resources or contractual commitments.
- Surface ambiguous or undefined requirements as gaps.
""".strip()


def generate_plan_with_groq(sow_text: str, project_name: str, config: GroqConfig) -> dict[str, Any]:
    if not config.api_key:
        raise RuntimeError("Groq API key is missing.")

    source_items = parse_sow_items(sow_text)
    selected = _select_ai_items(source_items, limit=16)
    numbered_text = "\n".join(
        f"{original_index}. [{item.get('type','Context')}] {item.get('section','')}: {item.get('statement','')}"
        for original_index, item in selected
    )

    user_prompt = f"""
Project name: {project_name}

NUMBERED SOW ITEMS:
{numbered_text}

Return the compact JSON seed now. Keep the whole answer comfortably below the model output limit.
""".strip()

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SEED_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "reasoning_effort": "none",
        "reasoning_format": "hidden",
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

    normalized = {
        "project_type": str(seed.get("project_type", "")).strip(),
        "description": str(seed.get("summary", "")).strip(),
        "confidence": "High" if seed.get("project_type") else "Medium",
        "phases": [x for x in (seed.get("phases") or []) if isinstance(x, dict)][:4],
        "key_activities": [],
        "milestones": [x for x in (seed.get("milestones") or []) if isinstance(x, dict)][:3],
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
        ref = row.get("source_index")
        try:
            source_index = int(ref)
        except Exception:
            source_index = None
        normalized["key_activities"].append(
            {
                "name": name,
                "phase": str(row.get("phase", "General Delivery")).strip() or "General Delivery",
                "duration_days": 5,
                "owner_role": "Project Team",
                "source_indexes": [source_index] if source_index is not None else [],
            }
        )

    base_plan = build_fallback_plan(sow_text, project_name)
    plan = merge_ai_seed_into_plan(base_plan, normalized)
    plan.setdefault("metadata", {})
    plan["metadata"].update(
        {
            "engine": "groq_qwen38_guided_structured_planner",
            "engine_version": AI_ENGINE_VERSION,
            "source_characters": len(sow_text),
            "model": config.model,
            "ai_output_cap": 600,
        }
    )
    return plan
