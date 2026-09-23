from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


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


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "project_name": {"type": "string"},
                "project_type": {"type": "string"},
                "description": {"type": "string"},
                "confidence": {"type": "string"},
            },
            "required": ["project_name", "project_type", "description", "confidence"],
        },
        "scope": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "in_scope": {"type": "array", "items": {"type": "string"}},
                "out_of_scope": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["in_scope", "out_of_scope"],
        },
        "sow_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sow_id": {"type": "string"},
                    "statement": {"type": "string"},
                    "type": {"type": "string"},
                    "explicit": {"type": "boolean"},
                    "priority": {"type": "string"},
                },
                "required": ["sow_id", "statement", "type", "explicit", "priority"],
            },
        },
        "wbs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "wbs_id": {"type": "string"},
                    "phase": {"type": "string"},
                    "parent_wbs_id": {"type": "string"},
                },
                "required": ["wbs_id", "phase", "parent_wbs_id"],
            },
        },
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "wbs_id": {"type": "string"},
                    "activity_id": {"type": "string"},
                    "activity_name": {"type": "string"},
                    "phase": {"type": "string"},
                    "duration_days": {"type": "integer"},
                    "dependency_ids": {"type": "array", "items": {"type": "string"}},
                    "owner_role": {"type": "string"},
                    "deliverable": {"type": "string"},
                    "milestone": {"type": "boolean"},
                    "source_sow_ids": {"type": "array", "items": {"type": "string"}},
                    "planning_note": {"type": "string"},
                },
                "required": [
                    "wbs_id", "activity_id", "activity_name", "phase", "duration_days",
                    "dependency_ids", "owner_role", "deliverable", "milestone", "source_sow_ids", "planning_note"
                ],
            },
        },
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "milestone_id": {"type": "string"},
                    "name": {"type": "string"},
                    "target": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["milestone_id", "name", "target", "source"],
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "gap_id": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["gap_id", "category", "description", "severity", "recommendation"],
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "risk_id": {"type": "string"},
                    "risk": {"type": "string"},
                    "impact": {"type": "string"},
                    "probability": {"type": "string"},
                    "mitigation": {"type": "string"},
                },
                "required": ["risk_id", "risk", "impact", "probability", "mitigation"],
            },
        },
        "traceability": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sow_id": {"type": "string"},
                    "activity_ids": {"type": "array", "items": {"type": "string"}},
                    "status": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["sow_id", "activity_ids", "status", "reason"],
            },
        },
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "engine": {"type": "string"},
                "source_characters": {"type": "integer"},
                "model": {"type": "string"},
            },
            "required": ["engine", "source_characters", "model"],
        },
    },
    "required": [
        "summary", "scope", "sow_items", "wbs", "activities", "milestones",
        "assumptions", "constraints", "gaps", "risks", "traceability", "metadata"
    ],
}


SYSTEM_PROMPT = """
You are a senior project/program management planning architect.
Transform a Statement of Work (SOW) into a domain-agnostic project plan.

Rules:
1. Separate what the SOW explicitly states from what you infer or propose.
2. Never invent a customer commitment, date, budget, resource, or contractual requirement.
3. When the SOW is silent, create a planning proposal and clearly mark it in planning_note or assumptions.
4. Extract every meaningful SOW scope/deliverable statement and give it a stable SOW ID.
5. Build a logical WBS and activities suitable for PM review.
6. Create reasonable predecessor relationships only when supported by normal project sequencing; explain inferred sequencing in planning_note.
7. Map each SOW item to one or more activities. If it cannot be mapped confidently, mark the traceability status as Unmapped or Review.
8. Identify gaps that would prevent a PM from confidently baselining the plan.
9. Identify planning risks arising from ambiguity, dependencies, missing ownership, missing acceptance criteria, or schedule constraints.
10. Keep the output usable across any industry/domain.
11. Preserve dates, quantities, locations, deliverables and acceptance wording from the SOW where present.
12. Do not produce a generic methodology dump; derive the plan from the actual SOW content.
""".strip()


def _parse_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


def generate_plan_with_groq(sow_text: str, project_name: str, config: GroqConfig) -> dict[str, Any]:
    if not config.api_key:
        raise RuntimeError("Groq API key is missing.")

    user_prompt = f"""
Project name: {project_name}

SOW TEXT:
---
{sow_text}
---

Generate the complete project-planning JSON according to the required schema.
""".strip()

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 7000,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sow_project_plan",
                "strict": True,
                "schema": PLAN_SCHEMA,
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
        detail = response.text[:2000]
        raise RuntimeError(f"Groq HTTP {response.status_code}: {detail}")

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"Groq returned no choices: {json.dumps(body)[:2000]}")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("Groq returned an empty model response.")

    plan = _parse_content(content)
    plan.setdefault("metadata", {})
    plan["metadata"]["engine"] = "groq"
    plan["metadata"]["source_characters"] = len(sow_text)
    plan["metadata"]["model"] = config.model
    return plan
