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
                "project_type": {"type": "string"},
                "description": {"type": "string"},
                "confidence": {"type": "string"},
            },
            "required": ["project_type", "description", "confidence"],
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
        "phases": {"type": "array", "items": {"type": "string"}},
        "key_activities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "phase": {"type": "string"},
                    "duration_days": {"type": "integer"},
                },
                "required": ["name", "phase", "duration_days"],
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary", "scope", "phases", "key_activities",
        "assumptions", "constraints", "gaps", "risks"
    ],
}


SYSTEM_PROMPT = """
You are a senior project/program management planning architect. Analyze the SOW and return ONLY the compact JSON requested.
Rules: distinguish explicit SOW facts from planning proposals; never invent contractual commitments; derive the project type and phases from the SOW; identify key activities, gaps and risks; keep each text item short. Return at most 5 phases, 8 key activities, 5 in-scope items, 5 out-of-scope items, 4 assumptions, 4 constraints, 5 gaps and 5 risks.
""".strip()


def _parse_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


def _expand_seed_to_plan(seed: dict[str, Any], sow_text: str, project_name: str, model: str) -> dict[str, Any]:
    from planner import build_fallback_plan

    base = build_fallback_plan(sow_text, project_name)
    summary = seed.get("summary", {}) if isinstance(seed.get("summary"), dict) else {}
    base["summary"] = {
        "project_name": project_name,
        "project_type": summary.get("project_type", "Other / To be confirmed"),
        "description": summary.get("description", "AI-assisted project plan generated from SOW text."),
        "confidence": summary.get("confidence", "Medium"),
    }
    base["scope"] = {
        "in_scope": seed.get("scope", {}).get("in_scope", []),
        "out_of_scope": seed.get("scope", {}).get("out_of_scope", []),
    }

    phases = seed.get("phases") or []
    if phases:
        base["wbs"] = []
        for i, phase in enumerate(phases[:5], 1):
            base["wbs"].append({
                "wbs_id": str(i),
                "phase": str(phase),
                "parent_wbs_id": "",
            })
    else:
        base["wbs"] = [
            {"wbs_id": str(i), "phase": phase, "parent_wbs_id": ""}
            for i, phase in enumerate([
                "Initiation & Planning", "Requirements & Design",
                "Execution", "Testing & Acceptance", "Deployment & Closure"
            ], 1)
        ]

    ai_activities = seed.get("key_activities") or []
    if ai_activities:
        activities = []
        for i, item in enumerate(ai_activities[:8], 1):
            if not isinstance(item, dict):
                continue
            phase = str(item.get("phase") or (phases[min(i-1, len(phases)-1)] if phases else "Execution"))
            wbs_id = next(
                (w["wbs_id"] for w in base["wbs"] if str(w["phase"]).lower() == phase.lower()),
                str(min(i, len(base["wbs"]) or 1)),
            )
            aid = f"AI-ACT-{i:03d}"
            activities.append({
                "wbs_id": wbs_id,
                "activity_id": aid,
                "activity_name": str(item.get("name") or f"AI planning activity {i}"),
                "phase": phase,
                "duration_days": max(1, min(int(item.get("duration_days", 5)), 60)),
                "dependency_ids": [f"AI-ACT-{i-1:03d}"] if i > 1 else [],
                "owner_role": "Project Team",
                "deliverable": "Planning deliverable / PM review",
                "milestone": False,
                "source_sow_ids": [],
                "planning_note": "AI-proposed activity derived from the SOW; PM validation required.",
            })
        if activities:
            base["activities"] = activities
            base["traceability"] = []
            for item in base.get("sow_items", []):
                base["traceability"].append({
                    "sow_id": item["sow_id"],
                    "activity_ids": [a["activity_id"] for a in activities[:3]],
                    "status": "Review",
                    "reason": "Compact AI planning pass did not retain item-level source IDs; PM should validate mapping.",
                })

    base["assumptions"] = seed.get("assumptions") or base.get("assumptions", [])
    base["constraints"] = seed.get("constraints") or base.get("constraints", [])
    base["gaps"] = [
        {
            "gap_id": f"AI-GAP-{i:03d}",
            "category": "AI planning review",
            "description": text,
            "severity": "Medium",
            "recommendation": "PM to clarify before baselining.",
        }
        for i, text in enumerate((seed.get("gaps") or [])[:5], 1)
    ] or base.get("gaps", [])
    base["risks"] = [
        {
            "risk_id": f"AI-RISK-{i:03d}",
            "risk": text,
            "impact": "Project delivery impact",
            "probability": "Medium",
            "mitigation": "Assign an owner and monitor through RAID governance.",
        }
        for i, text in enumerate((seed.get("risks") or [])[:5], 1)
    ]
    base["metadata"] = {
        "engine": "groq_ai_assisted_compact",
        "source_characters": len(sow_text),
        "model": model,
    }
    return base


def generate_plan_with_groq(sow_text: str, project_name: str, config: GroqConfig) -> dict[str, Any]:
    if not config.api_key:
        raise RuntimeError("Groq API key is missing.")

    user_prompt = f"""Project: {project_name}
SOW:
{sow_text}

Return a compact planning seed. Do not generate the full project plan. Keep the JSON concise so the response remains below 700 output tokens.""".strip()

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "reasoning_effort": "none",
        "include_reasoning": False,
        "max_completion_tokens": 700,
        "response_format": {"type": "json_schema", "json_schema": {"name": "sow_planning_seed", "strict": True, "schema": PLAN_SCHEMA}},
    }

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    url = f"{config.base_url}/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=config.timeout_seconds)
    if not response.ok:
        raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text[:2000]}")

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"Groq returned no choices: {json.dumps(body)[:2000]}")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("Groq returned an empty model response.")

    seed = _parse_content(content)
    return _expand_seed_to_plan(seed, sow_text, project_name, config.model)

