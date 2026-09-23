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


def merge_ai_seed_into_plan(base_plan: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    """Merge a compact AI planning seed into the deterministic full plan.

    The AI is intentionally not asked for full traceability/WBS JSON because the
    user's Groq org currently enforces a 1,000 output-token/minute limit. The
    deterministic planner owns the full shape; the AI supplies domain/context
    intelligence on top of it.
    """
    import copy
    import re

    result = copy.deepcopy(base_plan)
    summary = result.setdefault("summary", {})
    if seed.get("project_type"):
        summary["project_type"] = str(seed["project_type"]).strip()
    if seed.get("description"):
        summary["description"] = str(seed["description"]).strip()
    if seed.get("confidence"):
        summary["confidence"] = str(seed["confidence"]).strip()

    phase_rows = seed.get("phases") if isinstance(seed.get("phases"), list) else []
    if phase_rows:
        wbs = []
        for idx, row in enumerate(phase_rows[:5], 1):
            phase = str(row.get("phase", "")).strip()
            if not phase:
                continue
            wbs.append({"wbs_id": str(idx), "phase": phase, "parent_wbs_id": ""})
        if wbs:
            result["wbs"] = wbs

    # Normalize AI key activities. They become the lead activities, while the
    # deterministic plan retains SOW-derived activities so every SOW statement
    # still has a traceability path.
    ai_activities = seed.get("key_activities") if isinstance(seed.get("key_activities"), list) else []
    if ai_activities:
        phases = [str(w.get("phase", "")) for w in result.get("wbs", [])]
        lead = []
        for idx, row in enumerate(ai_activities[:6], 1):
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            phase = str(row.get("phase", "")).strip() or (phases[min(idx - 1, len(phases) - 1)] if phases else "Execution")
            duration = row.get("duration_days", 5)
            try:
                duration = max(1, int(duration))
            except Exception:
                duration = 5
            owner = str(row.get("owner_role", "Project Team")).strip() or "Project Team"
            refs = row.get("source_indexes", []) if isinstance(row.get("source_indexes"), list) else []
            actual_source_ids = []
            for ref in refs:
                try:
                    ref_idx = int(ref)
                except Exception:
                    continue
                if 1 <= ref_idx <= len(result.get("sow_items", [])):
                    actual_source_ids.append(result["sow_items"][ref_idx - 1].get("sow_id"))
            actual_source_ids = [x for x in actual_source_ids if x]
            lead.append(
                {
                    "wbs_id": f"AI.{min(idx, 5)}",
                    "activity_id": f"AI-ACT-{idx:03d}",
                    "activity_name": name[:120],
                    "phase": phase,
                    "duration_days": duration,
                    "dependency_ids": [f"AI-ACT-{idx-1:03d}"] if idx > 1 else [],
                    "owner_role": owner[:80],
                    "deliverable": name[:140],
                    "milestone": False,
                    "source_sow_ids": actual_source_ids[:3],
                    "planning_note": "AI-generated planning recommendation; PM review required.",
                }
            )
        if lead:
            # Avoid overwhelming the plan. Keep AI lead activities first, then
            # retain fallback activities for uncovered SOW statements.
            existing = result.get("activities", [])
            lead_names = {a["activity_name"].strip().lower() for a in lead}
            remainder = [a for a in existing if a.get("activity_name", "").strip().lower() not in lead_names]
            result["activities"] = lead + remainder

            # Add AI activity IDs to the existing deterministic traceability map.
            by_sow = {row.get("sow_id"): row for row in result.get("traceability", [])}
            for activity in lead:
                for sid in activity.get("source_sow_ids", []):
                    row = by_sow.get(sid)
                    if row is not None:
                        ids = row.setdefault("activity_ids", [])
                        if activity["activity_id"] not in ids:
                            ids.append(activity["activity_id"])

    seed_milestones = seed.get("milestones") if isinstance(seed.get("milestones"), list) else []
    if seed_milestones:
        milestones = []
        for idx, item in enumerate(seed_milestones[:5], 1):
            name = str(item.get("name", "")).strip()
            target = str(item.get("target", "TBD")).strip() or "TBD"
            if name:
                milestones.append({
                    "milestone_id": f"AI-MS-{idx:03d}",
                    "name": name[:120],
                    "target": target[:60],
                    "source": "AI-generated planning recommendation; PM review required.",
                })
        if milestones:
            result["milestones"] = milestones

    # Keep deterministic traceability, but surface AI-suggested refs as review
    # status where they point to statements that are not present in the local map.
    seed_gaps = seed.get("gaps") if isinstance(seed.get("gaps"), list) else []
    if seed_gaps:
        gaps = result.setdefault("gaps", [])
        existing_text = {str(g.get("description", "")).strip().lower() for g in gaps}
        for idx, item in enumerate(seed_gaps[:4], 1):
            text = str(item).strip()
            if text and text.lower() not in existing_text:
                gaps.append(
                    {
                        "gap_id": f"AI-GAP-{idx:03d}",
                        "category": "AI review",
                        "description": text[:240],
                        "severity": "Review",
                        "recommendation": "PM to validate before baselining.",
                    }
                )

    seed_risks = seed.get("risks") if isinstance(seed.get("risks"), list) else []
    if seed_risks:
        risks = result.setdefault("risks", [])
        existing_text = {str(r.get("risk", "")).strip().lower() for r in risks}
        for idx, item in enumerate(seed_risks[:4], 1):
            text = str(item).strip()
            if text and text.lower() not in existing_text:
                risks.append(
                    {
                        "risk_id": f"AI-RISK-{idx:03d}",
                        "risk": text[:240],
                        "impact": "Medium",
                        "probability": "Medium",
                        "mitigation": "PM to assess and assign an owner.",
                    }
                )

    seed_assumptions = seed.get("assumptions") if isinstance(seed.get("assumptions"), list) else []
    if seed_assumptions:
        assumptions = result.setdefault("assumptions", [])
        for item in seed_assumptions[:4]:
            text = str(item).strip()
            if text and text not in assumptions:
                assumptions.append(text)

    # Recalculate metadata after merge.
    result.setdefault("metadata", {})
    result["metadata"]["ai_seed_used"] = True
    return result
