from __future__ import annotations

import hashlib
import re
from typing import Any


def _id(prefix: str, text: str, index: int) -> str:
    h = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
    return f"{prefix}-{index:03d}-{h}"


def build_fallback_plan(sow_text: str, project_name: str) -> dict[str, Any]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", sow_text) if s.strip()]
    deliverable_words = [
        "deliver", "provide", "implement", "configure", "develop", "build", "design", "migrate",
        "integrate", "test", "train", "deploy", "handover", "launch", "install", "complete",
    ]
    candidates = [s for s in sentences if any(w in s.lower() for w in deliverable_words)]
    if not candidates:
        candidates = sentences[:10]

    sow_items = []
    activities = []
    traceability = []

    phase_templates = [
        ("1", "Initiation & Planning", ["Kickoff", "Governance and stakeholder alignment"]),
        ("2", "Requirements & Design", ["Requirements confirmation", "Solution/design baseline"]),
        ("3", "Execution", ["Build / configure / procure", "Integration and preparation"]),
        ("4", "Testing & Acceptance", ["System testing", "User acceptance and sign-off"]),
        ("5", "Deployment & Closure", ["Training / readiness", "Deployment and handover"]),
    ]

    for idx, text in enumerate(candidates, 1):
        sid = _id("SOW", text, idx)
        sow_items.append(
            {
                "sow_id": sid,
                "statement": text,
                "type": "Scope / Deliverable",
                "explicit": True,
                "priority": "Medium",
            }
        )
        aid = _id("ACT", text, idx)
        activities.append(
            {
                "wbs_id": f"3.{idx}",
                "activity_id": aid,
                "activity_name": text[:100],
                "phase": "Execution",
                "duration_days": 5,
                "dependency_ids": [],
                "owner_role": "Project Team",
                "deliverable": text[:120],
                "milestone": False,
                "source_sow_ids": [sid],
                "planning_note": "Fallback activity generated from an SOW statement; PM review required.",
            }
        )
        traceability.append(
            {
                "sow_id": sid,
                "activity_ids": [aid],
                "status": "Mapped",
                "reason": "Directly mapped from extracted SOW statement.",
            }
        )

    milestones = [
        {"milestone_id": "MS-001", "name": "Project kickoff", "target": "TBD", "source": "Planning proposal"},
        {"milestone_id": "MS-002", "name": "Requirements baseline", "target": "TBD", "source": "Planning proposal"},
        {"milestone_id": "MS-003", "name": "UAT / acceptance", "target": "TBD", "source": "Planning proposal"},
        {"milestone_id": "MS-004", "name": "Go-live / handover", "target": "TBD", "source": "Planning proposal"},
    ]

    return {
        "summary": {
            "project_name": project_name,
            "project_type": "Other / To be confirmed",
            "description": "Fallback project plan generated from SOW text. Use the AI mode for richer decomposition.",
            "confidence": "Low",
        },
        "scope": {"in_scope": [], "out_of_scope": []},
        "sow_items": sow_items,
        "wbs": [{"wbs_id": w, "phase": p} for w, p, _ in phase_templates],
        "activities": activities,
        "milestones": milestones,
        "assumptions": ["Durations, owners and dependencies are provisional where the SOW is silent."],
        "constraints": [],
        "gaps": [
            {
                "gap_id": "GAP-001",
                "category": "Planning completeness",
                "description": "Detailed durations, owners, entry/exit criteria and acceptance criteria may be missing from the SOW.",
                "severity": "Medium",
                "recommendation": "Have the PM validate the generated plan before baselining.",
            }
        ],
        "risks": [],
        "traceability": traceability,
        "metadata": {"engine": "fallback", "source_characters": len(sow_text)},
    }


def validate_and_normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    default = build_fallback_plan("", plan.get("summary", {}).get("project_name", "Project"))
    result = dict(default)
    if not isinstance(plan, dict):
        return result
    for key in result:
        value = plan.get(key)
        if value is not None and isinstance(value, type(result[key])):
            result[key] = value
    # Normalize common missing values.
    for activity in result.get("activities", []):
        activity.setdefault("dependency_ids", [])
        activity.setdefault("source_sow_ids", [])
        activity.setdefault("milestone", False)
    return result
