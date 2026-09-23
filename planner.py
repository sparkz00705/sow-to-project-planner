from __future__ import annotations

import copy
import hashlib
import re
from difflib import SequenceMatcher
from typing import Any


def _id(prefix: str, text: str, index: int) -> str:
    h = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
    return f"{prefix}-{index:03d}-{h}"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _split_list(text: str) -> list[str]:
    parts = re.split(r";|\n|\|", text)
    return [p.strip(" -•\t") for p in parts if p.strip(" -•\t")]


def _classify_section(title: str, body: str) -> tuple[str, bool]:
    t = _norm(title)
    b = _norm(body)
    if "out of scope" in t:
        return "Out of Scope", True
    if "deliverable" in t:
        return "Deliverable", True
    if "milestone" in t:
        return "Milestone", True
    if "dependency" in t:
        return "Dependency", True
    if "risk" in t or "constraint" in t:
        return "Risk / Constraint", True
    if "acceptance" in t:
        return "Acceptance", True
    if "responsibilit" in t:
        return "Responsibility", True
    if "assumption" in t or "commercial" in t or "schedule" in t:
        return "Assumption", True
    if "purpose" in t or "objective" in t:
        return "Objective", True
    if "workstream" in t or "scope" in t:
        return "Scope / Workstream", True
    # Generic prose: keep it as contextual SOW content, not as a task.
    return "Context", False


def parse_sow_items(sow_text: str) -> list[dict[str, Any]]:
    """Convert an SOW into typed source items without turning every sentence into a task."""
    lines = [line.strip() for line in sow_text.splitlines()]
    sections: list[tuple[str, str]] = []
    current_title = "SOW Context"
    current: list[str] = []

    heading_re = re.compile(r"^(?:section\s+)?(\d+)[\.)]\s*(.+)$", re.I)
    for line in lines:
        if not line:
            continue
        m = heading_re.match(line)
        if m:
            if current:
                sections.append((current_title, " ".join(current).strip()))
            current_title = f"{m.group(1)}. {m.group(2).strip() }"
            current = []
        else:
            current.append(line)
    if current:
        sections.append((current_title, " ".join(current).strip()))

    if not sections:
        sections = [("SOW Content", " ".join(x.strip() for x in lines if x.strip()))]

    items: list[dict[str, Any]] = []
    counter = 1
    for title, body in sections:
        if not body and not title:
            continue
        item_type, explicit = _classify_section(title, body)
        content = f"{title}: {body}" if body else title
        items.append(
            {
                "sow_id": _id("SOW", content, counter),
                "statement": body or title,
                "section": title,
                "type": item_type,
                "explicit": explicit,
                "priority": "High" if item_type in {"Scope / Workstream", "Deliverable", "Milestone", "Acceptance"} else "Medium",
            }
        )
        counter += 1

    return items


def _workstream_key(section: str, statement: str) -> str:
    text = _norm(f"{section} {statement}")
    patterns = [
        ("governance", "Governance"),
        ("project management", "Governance"),
        ("discovery", "Discovery & Requirements"),
        ("requirements", "Discovery & Requirements"),
        ("future state", "Process Design"),
        ("process design", "Process Design"),
        ("solution design", "Solution Design & Configuration"),
        ("configuration", "Solution Design & Configuration"),
        ("erp integration", "Integration"),
        ("integration", "Integration"),
        ("identity", "Identity & Access"),
        ("access management", "Identity & Access"),
        ("document management", "Document Management"),
        ("data migration", "Data Migration"),
        ("migration", "Data Migration"),
        ("testing", "Testing & Acceptance"),
        ("quality", "Testing & Acceptance"),
        ("training", "Training & Change"),
        ("change management", "Training & Change"),
        ("deployment", "Deployment & Cutover"),
        ("cutover", "Deployment & Cutover"),
        ("hypercare", "Hypercare & Handover"),
        ("handover", "Hypercare & Handover"),
    ]
    for token, phase in patterns:
        if token in text:
            return phase
    return "General Delivery"


def _activity_templates(phase: str, statement: str) -> list[str]:
    s = _norm(statement)
    templates: dict[str, list[str]] = {
        "Governance": [
            "Project kickoff and charter approval",
            "Establish governance, RAID, decisions and change control",
            "Integrated schedule, status reporting and steering reviews",
        ],
        "Discovery & Requirements": [
            "Stakeholder discovery and current-state assessment",
            "Requirements workshops and requirements catalogue",
            "Requirements validation and business sign-off",
        ],
        "Process Design": [
            "Future-state process and workflow design",
            "Roles, approvals, exceptions and escalation design",
            "Future-state design review and approval",
        ],
        "Solution Design & Configuration": [
            "Solution architecture and environment readiness",
            "Platform, workflow and business-rule configuration",
            "Configuration validation and design baseline",
        ],
        "Integration": [
            "Interface design and source/target mapping",
            "Integration development and system connectivity",
            "Integration testing and reconciliation",
        ],
        "Identity & Access": [
            "Identity and access design",
            "SSO, provisioning and role mapping configuration",
            "Access validation and privileged-access review",
        ],
        "Document Management": [
            "Document integration and metadata mapping",
            "Document upload/retrieval and permission configuration",
            "Document integration testing and validation",
        ],
        "Data Migration": [
            "Source data profiling and migration scope confirmation",
            "Data mapping, cleansing and transformation rules",
            "Trial migration, reconciliation and business validation",
            "Production data migration and reconciliation",
        ],
        "Testing & Acceptance": [
            "Test strategy, test cases and environment readiness",
            "System Integration Testing and defect resolution",
            "Performance and security testing coordination",
            "User Acceptance Testing and business sign-off",
        ],
        "Training & Change": [
            "Training and change-readiness plan",
            "Training materials, delivery and site readiness",
        ],
        "Deployment & Cutover": [
            "Cutover planning and go-live readiness",
            "Production deployment Wave 1 and stabilization",
            "Production deployment Wave 2 and stabilization",
            "Production deployment Wave 3 and stabilization",
        ],
        "Hypercare & Handover": [
            "Hypercare incident and defect management",
            "Knowledge transfer and operational handover",
            "Project closure and outstanding-action transition",
        ],
        "General Delivery": [
            "Detailed scope analysis and delivery planning",
            "Execute agreed work package",
            "Validate deliverable and obtain stakeholder acceptance",
        ],
    }
    rows = templates.get(phase, templates["General Delivery"])

    # Keep only activities that are supported by the section where possible.
    # For a generic domain, all three are reasonable planning decompositions.
    if phase == "Deployment & Cutover" and "three wave" not in s and "three waves" not in s:
        return rows[:2]
    return rows


def _extract_explicit_milestones(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    milestones: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") != "Milestone":
            continue
        for name, week in re.findall(r"([^;]+?)\s+Week\s+(\d+)", item.get("statement", ""), flags=re.I):
            milestones.append(
                {
                    "milestone_id": f"MS-{len(milestones)+1:03d}",
                    "name": name.strip(" ;"),
                    "target": f"Week {week}",
                    "source": "Explicit SOW milestone",
                }
            )
    if milestones:
        return milestones
    return [
        {"milestone_id": "MS-001", "name": "Project kickoff", "target": "TBD", "source": "Planning proposal"},
        {"milestone_id": "MS-002", "name": "Requirements baseline", "target": "TBD", "source": "Planning proposal"},
        {"milestone_id": "MS-003", "name": "UAT / business acceptance", "target": "TBD", "source": "Planning proposal"},
        {"milestone_id": "MS-004", "name": "Production go-live / handover", "target": "TBD", "source": "Planning proposal"},
    ]


def _extract_gaps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    texts = " ".join(i.get("statement", "") for i in items)
    normalized = _norm(texts)
    checks = [
        ("complete audit history", "Acceptance / scope", "Define exactly which transactions, fields, events and retention period constitute complete audit history."),
        ("no numerical target", "Performance", "Define measurable performance targets, workload and acceptance thresholds."),
        ("not define exact", "Data", "Confirm data volumes, record counts and migration boundaries."),
        ("not stated", "Security", "Clarify ownership for penetration testing and security remediation."),
        ("15%", "Process variation", "Define the measurement method for the local-variation threshold."),
        ("severity 2", "Defect acceptance", "Define the maximum permitted Severity 2 defects and formal waiver authority at go-live."),
        ("smoke testing", "Go-live", "Define business smoke-test entry/exit criteria and evidence requirements."),
        ("subject to", "Scope / Change", "Define the decision process and schedule/cost impact for conditional scope additions."),
    ]
    for needle, category, rec in checks:
        if needle in normalized:
            gaps.append(
                {
                    "gap_id": f"GAP-{len(gaps)+1:03d}",
                    "category": category,
                    "description": rec,
                    "severity": "Review",
                    "recommendation": "PM to clarify before baselining.",
                }
            )
    return gaps


def _extract_risks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for item in items:
        if item.get("type") != "Risk / Constraint":
            continue
        for text in _split_list(item.get("statement", "")):
            if len(text) < 8:
                continue
            risks.append(
                {
                    "risk_id": f"RISK-{len(risks)+1:03d}",
                    "risk": text,
                    "impact": "Medium",
                    "probability": "Medium",
                    "mitigation": "Assess, assign owner and track in the project RAID log.",
                }
            )
    return risks


def _extract_scope(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    in_scope: list[str] = []
    out_scope: list[str] = []
    for item in items:
        if item.get("type") not in {"Scope / Workstream", "Out of Scope"}:
            continue
        parts = _split_list(item.get("statement", ""))
        if item.get("type") == "Out of Scope":
            out_scope.extend(parts)
        else:
            in_scope.extend(parts)
    return in_scope, out_scope


def _make_activities(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    activities: list[dict[str, Any]] = []
    trace_map: dict[str, list[str]] = {i["sow_id"]: [] for i in items}
    workstream_items = [i for i in items if "workstream" in _norm(i.get("section", ""))]
    if not workstream_items:
        # Generic domain-agnostic planning when the SOW has no explicit workstreams.
        workstream_items = [i for i in items if i.get("type") == "Scope / Workstream"][:8]

    previous_by_phase: dict[str, str] = {}
    for item in workstream_items:
        phase = _workstream_key(item.get("section", ""), item.get("statement", ""))
        templates = _activity_templates(phase, item.get("statement", ""))
        for template in templates:
            idx = len(activities) + 1
            aid = f"ACT-{idx:03d}-{hashlib.sha1(template.encode()).hexdigest()[:6].upper()}"
            dep = []
            if phase in previous_by_phase:
                dep = [previous_by_phase[phase]]
            else:
                # Link each workstream to the most recently created activity from another phase.
                if activities:
                    dep = [activities[-1]["activity_id"]]
            activity = {
                "wbs_id": "",
                "activity_id": aid,
                "activity_name": template,
                "phase": phase,
                "duration_days": 5,
                "dependency_ids": dep,
                "owner_role": "Project Team",
                "deliverable": template,
                "milestone": False,
                "source_sow_ids": [item["sow_id"]],
                "planning_note": "Structured planning activity derived from SOW workstream; PM review required.",
            }
            activities.append(activity)
            trace_map[item["sow_id"]].append(aid)
            previous_by_phase[phase] = aid

    # Assign WBS numbers by phase appearance.
    phase_numbers: dict[str, str] = {}
    phase_counters: dict[str, int] = {}
    for activity in activities:
        phase = activity["phase"]
        if phase not in phase_numbers:
            phase_numbers[phase] = str(len(phase_numbers) + 1)
            phase_counters[phase] = 0
        phase_counters[phase] += 1
        activity["wbs_id"] = f"{phase_numbers[phase]}.{phase_counters[phase]}"

    # Non-workstream scope statements are traceable but are not falsely converted into tasks.
    traceability: list[dict[str, Any]] = []
    for item in items:
        mapped = trace_map.get(item["sow_id"], [])
        if mapped:
            traceability.append(
                {
                    "sow_id": item["sow_id"],
                    "activity_ids": mapped,
                    "status": "Mapped",
                    "reason": "Mapped to structured planning activities for the relevant workstream.",
                }
            )
        elif item.get("type") in {"Out of Scope", "Assumption", "Dependency", "Responsibility", "Risk / Constraint", "Acceptance", "Milestone"}:
            traceability.append(
                {
                    "sow_id": item["sow_id"],
                    "activity_ids": [],
                    "status": "Reference",
                    "reason": "SOW item informs planning but is not itself a project activity.",
                }
            )
        else:
            traceability.append(
                {
                    "sow_id": item["sow_id"],
                    "activity_ids": [],
                    "status": "Needs Mapping",
                    "reason": "PM review required to determine whether this SOW statement needs a dedicated activity.",
                }
            )
    return activities, traceability


def build_fallback_plan(sow_text: str, project_name: str) -> dict[str, Any]:
    """Deterministic, domain-agnostic planner used as the full-plan construction layer."""
    items = parse_sow_items(sow_text)
    activities, traceability = _make_activities(items)
    in_scope, out_scope = _extract_scope(items)
    milestones = _extract_explicit_milestones(items)
    gaps = _extract_gaps(items)
    risks = _extract_risks(items)

    duration_match = re.search(r"(?:duration|completed|implementation).*?(\d+)\s+weeks", sow_text, flags=re.I)
    target_duration = f"{duration_match.group(1)} weeks" if duration_match else "Not stated"

    return {
        "summary": {
            "project_name": project_name,
            "project_type": "Project type to be confirmed",
            "description": f"Structured project plan derived from the SOW. Target duration in the SOW: {target_duration}.",
            "confidence": "Medium",
        },
        "scope": {"in_scope": in_scope, "out_of_scope": out_scope},
        "sow_items": items,
        "wbs": [],
        "activities": activities,
        "milestones": milestones,
        "assumptions": [
            "Durations and owners are provisional where the SOW is silent.",
            "Dependencies are planning proposals and require PM validation.",
        ],
        "constraints": [
            item["statement"] for item in items if item.get("type") == "Risk / Constraint"
        ],
        "gaps": gaps or [
            {
                "gap_id": "GAP-001",
                "category": "Planning completeness",
                "description": "Confirm durations, owners, entry/exit criteria and acceptance criteria before baselining.",
                "severity": "Review",
                "recommendation": "PM to validate the generated plan before baselining.",
            }
        ],
        "risks": risks,
        "traceability": traceability,
        "metadata": {"engine": "structured_planner", "source_characters": len(sow_text)},
    }


def validate_and_normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    project_name = "Project"
    if isinstance(plan, dict):
        project_name = plan.get("summary", {}).get("project_name", "Project") if isinstance(plan.get("summary"), dict) else "Project"
    default = build_fallback_plan("", project_name)
    result = copy.deepcopy(default)
    if not isinstance(plan, dict):
        return result
    for key in result:
        value = plan.get(key)
        if value is not None and isinstance(value, type(result[key])):
            result[key] = value
    for activity in result.get("activities", []):
        activity.setdefault("dependency_ids", [])
        activity.setdefault("source_sow_ids", [])
        activity.setdefault("milestone", False)
    return result


def merge_ai_seed_into_plan(base_plan: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    """Apply compact AI guidance to the full deterministic plan without duplicating SOW prose as activities."""
    result = copy.deepcopy(base_plan)
    summary = result.setdefault("summary", {})
    if seed.get("project_type"):
        summary["project_type"] = str(seed["project_type"]).strip()
    if seed.get("description"):
        summary["description"] = str(seed["description"]).strip()
    if seed.get("confidence"):
        summary["confidence"] = str(seed["confidence"]).strip()

    # AI suggestions are supplemental; the structured planner owns the complete WBS.
    phase_rows = seed.get("phases") if isinstance(seed.get("phases"), list) else []
    result.setdefault("metadata", {})["ai_suggested_phases"] = [
        str(x.get("phase", "")).strip() for x in phase_rows if isinstance(x, dict) and str(x.get("phase", "")).strip()
    ][:5]

    # Map AI activities to actual SOW section IDs. Do not create duplicate "one sentence = one task" rows.
    sow_items = result.get("sow_items", [])
    for row in (seed.get("key_activities") or [])[:4]:
        if not isinstance(row, dict) or not str(row.get("name", "")).strip():
            continue
        refs = row.get("source_indexes") if isinstance(row.get("source_indexes"), list) else []
        source_ids = []
        for ref in refs:
            try:
                idx = int(ref)
            except Exception:
                continue
            if 1 <= idx <= len(sow_items):
                source_ids.append(sow_items[idx - 1].get("sow_id"))
        source_ids = [x for x in source_ids if x]

        # Prefer an existing activity with a similar name; otherwise add one supplemental AI activity.
        name = str(row["name"]).strip()
        best = None
        best_score = 0.0
        for activity in result.get("activities", []):
            score = SequenceMatcher(None, _norm(name), _norm(activity.get("activity_name", ""))).ratio()
            if score > best_score:
                best_score = score
                best = activity
        if best is not None and best_score >= 0.58:
            best["planning_note"] = "AI-guided planning activity; PM review required."
            if source_ids:
                best["source_sow_ids"] = list(dict.fromkeys(best.get("source_sow_ids", []) + source_ids))
            continue

        aid = f"AI-ACT-{len([a for a in result.get('activities', []) if str(a.get('activity_id','')).startswith('AI-ACT-')])+1:03d}"
        phase = str(row.get("phase", "General Delivery")).strip() or "General Delivery"
        activity = {
            "wbs_id": "AI.1",
            "activity_id": aid,
            "activity_name": name[:120],
            "phase": phase,
            "duration_days": max(1, int(row.get("duration_days", 5) or 5)),
            "dependency_ids": [],
            "owner_role": str(row.get("owner_role", "Project Team")).strip() or "Project Team",
            "deliverable": name[:140],
            "milestone": False,
            "source_sow_ids": source_ids,
            "planning_note": "AI-guided planning activity; PM review required.",
        }
        result["activities"].insert(0, activity)

    # AI milestones supplement explicit SOW milestones only when the SOW did not provide that milestone.
    if seed.get("milestones"):
        existing = {_norm(m.get("name", "")) for m in result.get("milestones", [])}
        for item in seed["milestones"][:3]:
            name = str(item.get("name", "")).strip() if isinstance(item, dict) else str(item).strip()
            if name and _norm(name) not in existing:
                result["milestones"].append(
                    {
                        "milestone_id": f"AI-MS-{len(result.get('milestones', []))+1:03d}",
                        "name": name[:120],
                        "target": str(item.get("target", "TBD")).strip() if isinstance(item, dict) else "TBD",
                        "source": "AI planning recommendation; PM review required.",
                    }
                )

    for label, key, prefix in [("gap", "gaps", "GAP"), ("risk", "risks", "RISK")]:
        for item in (seed.get(key) or [])[:4]:
            text = str(item).strip()
            if not text:
                continue
            collection = result.setdefault(key, [])
            existing = {_norm(x.get("description", x.get("risk", ""))) for x in collection}
            if _norm(text) in existing:
                continue
            if label == "gap":
                collection.append({
                    "gap_id": f"AI-{prefix}-{len(collection)+1:03d}",
                    "category": "AI review",
                    "description": text[:240],
                    "severity": "Review",
                    "recommendation": "PM to clarify before baselining.",
                })
            else:
                collection.append({
                    "risk_id": f"AI-{prefix}-{len(collection)+1:03d}",
                    "risk": text[:240],
                    "impact": "Medium",
                    "probability": "Medium",
                    "mitigation": "PM to assess and assign an owner.",
                })

    # Build a cleaner WBS directly from actual activity phases.
    phases: list[str] = []
    for activity in result.get("activities", []):
        phase = str(activity.get("phase", "General Delivery"))
        if phase not in phases:
            phases.append(phase)
    result["wbs"] = [{"wbs_id": str(i), "phase": phase, "parent_wbs_id": ""} for i, phase in enumerate(phases, 1)]
    phase_to_num = {phase: str(i) for i, phase in enumerate(phases, 1)}
    counters: dict[str, int] = {}
    for activity in result.get("activities", []):
        phase = str(activity.get("phase", "General Delivery"))
        counters[phase] = counters.get(phase, 0) + 1
        activity["wbs_id"] = f"{phase_to_num.get(phase, '1')}.{counters[phase]}"

    result.setdefault("metadata", {})["ai_seed_used"] = True
    result["metadata"]["engine"] = "groq_qwen38_guided_structured_planner"
    return result
