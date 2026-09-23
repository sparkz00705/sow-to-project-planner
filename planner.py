from __future__ import annotations

import copy
import hashlib
import re
from typing import Any


def _id(prefix: str, text: str, index: int) -> str:
    h = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
    return f"{prefix}-{index:03d}-{h}"


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip(" ;,.-")


def _sectionize(sow_text: str) -> list[tuple[str, str]]:
    lines = [x.strip() for x in sow_text.splitlines() if x.strip()]
    chunks: list[tuple[str, str]] = []
    current: str | None = None
    buffer: list[str] = []
    for line in lines:
        normalized = re.sub(r"^\d+[.)]\s+", "", line).strip()
        heading = False
        if re.match(r"^Workstream\s+[A-Za-z0-9]+\s*[-:]", line, re.I):
            heading = True
        elif re.match(r"^\d+[.)]\s+[A-Za-z].*", line):
            heading = True
        elif normalized.lower() in {
            "purpose", "objectives", "scope", "in scope", "out of scope", "geography and functions",
            "major deliverables", "milestones", "dependencies", "responsibilities", "commercial assumptions",
            "schedule assumptions", "acceptance criteria", "risks and constraints", "deliberate clarifications",
        }:
            heading = True
        if heading:
            if current is not None and buffer:
                chunks.append((current, _clean(" ".join(buffer))))
            current = normalized
            buffer = []
        else:
            if current is None:
                current = "General"
            buffer.append(line)
    if current is not None and buffer:
        chunks.append((current, _clean(" ".join(buffer))))
    return [(s, t) for s, t in chunks if t]


def _key(section: str) -> str:
    return re.sub(r"^\d+[.)]\s*", "", section.lower().strip())


def _is_workstream(section: str) -> bool:
    return section.lower().startswith("workstream")


def _workstream_name(section: str) -> str:
    m = re.match(r"Workstream\s+[A-Za-z0-9]+\s*[-:]\s*(.+)", section, re.I)
    return _clean(m.group(1) if m else section)


def _list_split(text: str, mode: str) -> list[str]:
    """Split only where the SOW structure supports itemization."""
    text = text.replace("•", "\n").replace("\r", "\n")
    if mode in {"semicolon", "sentence"}:
        pattern = r";|\n+" if mode == "semicolon" else r"(?<=[.!?])\s+|\n+"
        return [_clean(x) for x in re.split(pattern, text) if _clean(x)]
    return [_clean(x) for x in re.split(r"\n+", text) if _clean(x)]


def _section_items(section: str, text: str) -> list[str]:
    s = _key(section)
    if _is_workstream(section):
        # Keep the workstream as one source item. Activity decomposition happens separately.
        return [text]
    if "major deliverables" in s or s == "milestones" or s == "dependencies" or "risks and constraints" in s or "schedule assumptions" in s or "in scope" == s or "out of scope" == s or s == "objectives":
        return _list_split(text, "semicolon")
    if "deliberate clarifications" in s or "acceptance criteria" in s or "purpose" in s:
        return _list_split(text, "sentence")
    if "responsibilities" in s:
        # Preserve Client / Partner responsibility blocks as two source items.
        pieces = re.split(r"(?=(?:Client|Implementation Partner)\s*:)", text)
        return [_clean(x) for x in pieces if _clean(x)]
    return [text]


def _classify(section: str, text: str) -> tuple[str, str, bool]:
    s = _key(section)
    low = text.lower()
    if "out of scope" == s:
        return "Out of Scope", "Reference", False
    if "major deliverables" in s:
        return "Deliverable", "Reference", False
    if s == "milestones":
        return "Milestone", "Control", False
    if s == "dependencies":
        return "Dependency", "Constraint", False
    if s == "responsibilities":
        return "Responsibility", "Reference", False
    if "commercial assumptions" in s:
        return "Commercial Assumption", "Assumption", False
    if "schedule assumptions" in s:
        return "Schedule Assumption", "Assumption", False
    if "acceptance criteria" in s:
        return "Acceptance Criterion", "Control", False
    if "risks and constraints" in s:
        return "Risk / Constraint", "Risk / Constraint", False
    if "deliberate clarifications" in s or "not defined" in low or "does not define" in low or "no numerical target" in low or "no entry/exit criteria" in low:
        return "Clarification / Gap", "Gap", False
    if "purpose" in s or "objective" in s:
        return "Objective", "Scope", False
    if s == "in scope" or _is_workstream(section):
        return "Scope / Activity", "Executable", True
    return "Reference", "Reference", False


def _priority(text: str, item_type: str) -> str:
    low = text.lower()
    if any(k in low for k in ["go-live", "production", "security", "acceptance", "sign-off", "critical"]):
        return "High"
    if item_type in {"Deliverable", "Milestone", "Dependency", "Clarification / Gap"}:
        return "High"
    return "Medium"


def _parse_sow_items(sow_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1
    for section, text in _sectionize(sow_text):
        for piece in _section_items(section, text):
            if len(piece) < 10:
                continue
            typ, category, executable = _classify(section, piece)
            sid = _id("SOW", f"{section}:{piece}", n)
            rows.append({
                "sow_id": sid,
                "section": section,
                "statement": piece,
                "type": typ,
                "category": category,
                "executable": executable,
                "explicit": True,
                "priority": _priority(piece, typ),
            })
            n += 1
    return rows


def _phase_map(name: str) -> tuple[str, str]:
    low = name.lower()
    pairs = [
        ("project management", "Initiation & Governance", "Establish governance, controls and delivery cadence."),
        ("discovery", "Discovery & Requirements", "Understand current state and baseline requirements."),
        ("future-state", "Future-State Process Design", "Design target processes, roles and controls."),
        ("solution design", "Solution Design & Configuration", "Design the solution and configure environments."),
        ("configuration", "Solution Design & Configuration", "Configure the solution and required environments."),
        ("erp integration", "Integration & Interfaces", "Build and validate enterprise interfaces."),
        ("identity", "Security & Access", "Implement identity, access and security controls."),
        ("access management", "Security & Access", "Implement identity, access and security controls."),
        ("document management", "Content & Document Integration", "Integrate document/content services."),
        ("data migration", "Data Migration", "Profile, transform, migrate and reconcile data."),
        ("testing", "Testing & Acceptance", "Validate functional, integration, performance and acceptance requirements."),
        ("training", "Change & Training", "Prepare users, support teams and adoption materials."),
        ("deployment", "Deployment & Cutover", "Prepare and execute production rollout."),
        ("hypercare", "Hypercare & Handover", "Stabilize the solution and complete operational transition."),
    ]
    for key, phase, purpose in pairs:
        if key in low:
            return phase, purpose
    return _clean(name) or "Delivery Workstream", "Deliver the workstream scope stated in the SOW."


def _normalize_activity(phrase: str, phase: str) -> str:
    p = _clean(phrase)
    if not p:
        return ""
    p = re.sub(r"^(activities include|scope includes|the project will|the solution will)\s+", "", p, flags=re.I)
    if re.match(r"^(establish|maintain|conduct|assess|create|define|design|configure|implement|integrate|migrate|perform|execute|train|deliver|deploy|provide|complete|validate|obtain|prepare|develop|support|transition|reconcile|map|profile|cleanse|build|approve|review|plan|coordinate|test)\b", p, re.I):
        return p.rstrip(".")
    verb = {
        "Initiation & Governance": "Establish",
        "Discovery & Requirements": "Conduct",
        "Future-State Process Design": "Design",
        "Solution Design & Configuration": "Configure",
        "Integration & Interfaces": "Implement",
        "Security & Access": "Implement",
        "Content & Document Integration": "Integrate",
        "Data Migration": "Prepare",
        "Testing & Acceptance": "Execute",
        "Change & Training": "Prepare",
        "Deployment & Cutover": "Prepare",
        "Hypercare & Handover": "Complete",
    }.get(phase, "Complete")
    return f"{verb} {p[0].lower() + p[1:] if p else p}".rstrip(".")


def _workstream_activity_phrases(section: str, text: str, phase: str) -> list[str]:
    candidates: list[str] = []
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    for sentence in sentences:
        # Workstream clauses are usually semicolon-delimited actions.
        for part in re.split(r";", sentence):
            part = _clean(part)
            if not part:
                continue
            low = part.lower()
            # Exclude obligations/constraints that are not executable work.
            if any(x in low for x in [
                "may require", "above this threshold", "the client will provide", "the client owns",
                "the implementation partner is not responsible", "remains with the existing",
                "subject to schedule", "unless formally waived",
            ]):
                continue
            # Split clearly enumerated activity lists, but don't split ordinary prose.
            if part.count(",") >= 2 and len(part) < 200 and not any(v in low for v in ["not defined", "does not define"]):
                chunks = [_clean(x) for x in part.split(",") if _clean(x)]
                # Strip conjunctions from the final chunk where possible.
                if 2 <= len(chunks) <= 6:
                    candidates.extend(_normalize_activity(x, phase) for x in chunks)
                    continue
            candidates.append(_normalize_activity(part, phase))
    out: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        item = _clean(item)
        if len(item) < 12:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", item.lower()).strip()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:10]


def _owner_for(phase: str, activity: str) -> str:
    low = activity.lower()
    if any(k in low for k in ["uat", "requirements", "acceptance", "approval", "sign-off"]):
        return "Business / Product Owner"
    if any(k in low for k in ["integration", "api", "configuration", "migration", "sso", "security", "environment"]):
        return "Technical Lead"
    if any(k in low for k in ["test", "defect", "regression", "performance"]):
        return "Test Lead"
    if any(k in low for k in ["training", "change", "knowledge transfer"]):
        return "Change / Training Lead"
    if any(k in low for k in ["deploy", "cutover", "go-live", "hypercare"]):
        return "Deployment Lead"
    if "governance" in low or "charter" in low:
        return "Project Manager"
    return "Workstream Lead"


def _duration(activity: str, phase: str) -> int:
    low = activity.lower()
    base = {
        "Initiation & Governance": 5,
        "Discovery & Requirements": 8,
        "Future-State Process Design": 10,
        "Solution Design & Configuration": 12,
        "Integration & Interfaces": 12,
        "Security & Access": 8,
        "Content & Document Integration": 8,
        "Data Migration": 12,
        "Testing & Acceptance": 10,
        "Change & Training": 7,
        "Deployment & Cutover": 5,
        "Hypercare & Handover": 10,
    }.get(phase, 7)
    if any(k in low for k in ["kickoff", "approval", "sign-off", "readiness", "go-live", "handover"]):
        return 1
    if any(k in low for k in ["workshop", "assessment", "review", "profiling", "mapping", "planning"]):
        return max(3, base // 2)
    return base


def _deliverable_for(activity: str) -> str:
    low = activity.lower()
    if any(k in low for k in ["requirements", "baseline"]):
        return "Approved requirements baseline"
    if any(k in low for k in ["design", "architecture"]):
        return "Approved design package"
    if any(k in low for k in ["configuration", "configure"]):
        return "Configured solution"
    if any(k in low for k in ["integrat", "api"]):
        return "Validated integration"
    if any(k in low for k in ["migration", "migrate", "reconcile"]):
        return "Migration / reconciliation package"
    if any(k in low for k in ["test", "uat", "acceptance"]):
        return "Test / acceptance evidence"
    if any(k in low for k in ["train", "change"]):
        return "Training / change package"
    if any(k in low for k in ["deploy", "cutover", "go-live"]):
        return "Deployment / cutover completion"
    if any(k in low for k in ["handover", "hypercare"]):
        return "Operational handover"
    return f"Completed: {activity}"


def _sow_to_activity_match(item: dict[str, Any], activities: list[dict[str, Any]]) -> list[str]:
    if not activities:
        return []
    stmt = item["statement"].lower()
    tokens = set(re.findall(r"[a-z]{5,}", stmt))
    candidates: list[tuple[int, str]] = []
    for a in activities:
        at = set(re.findall(r"[a-z]{5,}", a["activity_name"].lower()))
        score = len(tokens & at)
        if score:
            candidates.append((score, a["activity_id"]))
    if candidates:
        candidates.sort(reverse=True)
        return [aid for score, aid in candidates[:2] if score >= 1]
    # Section/keyword-based fallback mapping so broad in-scope items do not remain falsely unmapped.
    low = stmt
    hints = []
    for keyword, phase in [
        ("require", "Discovery & Requirements"), ("workflow", "Future-State Process Design"),
        ("role", "Security & Access"), ("permission", "Security & Access"),
        ("dashboard", "Solution Design & Configuration"), ("report", "Solution Design & Configuration"),
        ("notification", "Solution Design & Configuration"), ("configure", "Solution Design & Configuration"),
        ("integrat", "Integration & Interfaces"), ("erp", "Integration & Interfaces"),
        ("sso", "Security & Access"), ("identity", "Security & Access"),
        ("document", "Content & Document Integration"), ("data", "Data Migration"),
        ("migrat", "Data Migration"), ("test", "Testing & Acceptance"),
        ("uat", "Testing & Acceptance"), ("train", "Change & Training"),
        ("cutover", "Deployment & Cutover"), ("deploy", "Deployment & Cutover"),
        ("hypercare", "Hypercare & Handover"), ("handover", "Hypercare & Handover"),
        ("governance", "Initiation & Governance"), ("project management", "Initiation & Governance"),
    ]:
        if keyword in low:
            hints.append(phase)
    for phase in hints:
        phase_acts = [a for a in activities if a["phase"] == phase]
        if phase_acts:
            return [phase_acts[0]["activity_id"]]
    return []


def _build_gaps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1
    for item in items:
        if item["type"] != "Clarification / Gap":
            continue
        low = item["statement"].lower()
        category = "SOW clarification"
        severity = "Medium"
        recommendation = "Clarify and document before the related baseline or approval gate."
        if "ownership" in low:
            category, severity, recommendation = "Ownership", "High", "Assign an accountable owner for the activity or control."
        elif "performance" in low or "numerical target" in low:
            category, severity, recommendation = "Missing performance target", "Medium", "Define measurable performance thresholds and acceptance criteria."
        elif "record volume" in low or "does not define exact" in low:
            category, severity, recommendation = "Missing data volume", "Medium", "Define data volumes and reconciliation thresholds."
        elif "entry/exit" in low:
            category, severity, recommendation = "Test readiness criteria", "High", "Define entry/exit criteria and sign-off authority."
        elif "15%" in low or "variation" in low:
            category, severity, recommendation = "Scope variation rule", "Medium", "Define how the local-variation threshold will be measured."
        elif "severity 2" in low:
            category, severity, recommendation = "Defect acceptance rule", "High", "Define the maximum accepted Severity 2 backlog and approval authority."
        rows.append({
            "gap_id": f"GAP-{n:03d}",
            "category": category,
            "description": item["statement"],
            "severity": severity,
            "recommendation": recommendation,
            "source_sow_ids": [item["sow_id"]],
        })
        n += 1
    if not rows:
        rows.append({
            "gap_id": "GAP-001",
            "category": "Planning completeness",
            "description": "Some detailed durations, resource allocations or dependency dates may be implicit in the SOW.",
            "severity": "Medium",
            "recommendation": "PM to validate planning assumptions before baseline.",
            "source_sow_ids": [],
        })
    return rows


def _build_risks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1
    for item in items:
        if item["type"] != "Risk / Constraint":
            continue
        desc = item["statement"]
        low = desc.lower()
        impact = "High" if any(k in low for k in ["data", "security", "delay", "migration", "production", "acceptance"]) else "Medium"
        rows.append({
            "risk_id": f"RISK-{n:03d}",
            "risk": desc,
            "category": "SOW-identified risk / constraint",
            "impact": impact,
            "probability": "Medium",
            "mitigation": "Assign an owner, define trigger/threshold, and track through RAID governance.",
            "owner_role": "Project Manager",
            "source_sow_ids": [item["sow_id"]],
        })
        n += 1
    return rows


def _build_assumptions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1
    for item in items:
        if item["type"] in {"Schedule Assumption", "Commercial Assumption"}:
            rows.append({
                "assumption_id": f"ASM-{n:03d}",
                "category": "Commercial" if item["type"] == "Commercial Assumption" else "Schedule / Delivery",
                "statement": item["statement"],
                "explicit": True,
                "source_sow_ids": [item["sow_id"]],
                "confidence": "High",
                "review_status": "PM review required",
            })
            n += 1
    if not rows:
        rows.append({
            "assumption_id": "ASM-001",
            "category": "Planning",
            "statement": "Where the SOW is silent, duration, owner and dependency values are provisional planning assumptions.",
            "explicit": False,
            "source_sow_ids": [],
            "confidence": "Medium",
            "review_status": "PM review required",
        })
    return rows


def _build_constraints(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1
    for item in items:
        if item["type"] == "Dependency":
            rows.append({
                "constraint_id": f"CON-{n:03d}",
                "category": "Dependency",
                "statement": item["statement"],
                "source_sow_ids": [item["sow_id"]],
                "review_status": "PM review required",
            })
            n += 1
        elif item["type"] == "Risk / Constraint" and any(k in item["statement"].lower() for k in ["maximum", "minimum", "limited", "must", "requires", "at least", "no more than"]):
            rows.append({
                "constraint_id": f"CON-{n:03d}",
                "category": "SOW constraint",
                "statement": item["statement"],
                "source_sow_ids": [item["sow_id"]],
                "review_status": "PM review required",
            })
            n += 1
    return rows


def _build_wbs_and_activities(sow_items: list[dict[str, Any]], sow_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sections = _sectionize(sow_text)
    wbs: list[dict[str, Any]] = []
    activities: list[dict[str, Any]] = []
    previous_id: str | None = None
    phase_seen: dict[str, int] = {}
    for section, text in sections:
        if not _is_workstream(section):
            continue
        name = _workstream_name(section)
        phase, purpose = _phase_map(name)
        if phase not in phase_seen:
            phase_seen[phase] = len(wbs) + 1
            wbs.append({"wbs_id": str(len(wbs) + 1), "phase": phase, "purpose": purpose, "source_sections": [section]})
        phase_no = phase_seen[phase]
        source = [x for x in sow_items if x["section"] == section and x["executable"]]
        phrases = _workstream_activity_phrases(section, text, phase)
        if not phrases:
            phrases = [f"Deliver {phase.lower()} scope"]
        for idx, name2 in enumerate(phrases, 1):
            aid = _id("ACT", f"{section}:{name2}", len(activities) + 1)
            # Section source is the primary traceability anchor; add up to two strong related items.
            src_ids = [x["sow_id"] for x in source]
            if not src_ids:
                src_ids = [_id("SOW", f"{section}:{text}", 1)]
            activity = {
                "wbs_id": f"{phase_no}.{idx}",
                "activity_id": aid,
                "activity_name": name2[:160],
                "phase": phase,
                "duration_days": _duration(name2, phase),
                "dependency_ids": [previous_id] if previous_id else [],
                "owner_role": _owner_for(phase, name2),
                "deliverable": _deliverable_for(name2),
                "milestone": False,
                "source_sow_ids": src_ids[:6],
                "planning_note": "Activity derived from executable SOW scope; duration, owner and dependency are planning recommendations for PM review.",
            }
            activities.append(activity)
            previous_id = aid
    return wbs, activities


def _build_milestones(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n = 1
    for item in items:
        if item["type"] != "Milestone":
            continue
        # A milestone section is semicolon-delimited; each SOW item should therefore already be one milestone.
        name, target = _parse_milestone(item["statement"])
        rows.append({
            "milestone_id": f"MS-{n:03d}",
            "name": name,
            "target": target,
            "source_sow_ids": [item["sow_id"]],
            "status": "Planned",
            "planning_note": "Explicit SOW milestone; target retained from source where stated.",
        })
        n += 1
    if not rows:
        for name in ["Project kickoff", "Requirements baseline", "Business acceptance", "Production handover"]:
            rows.append({
                "milestone_id": f"MS-{n:03d}",
                "name": name,
                "target": "TBD",
                "source_sow_ids": [],
                "status": "Planning proposal",
                "planning_note": "Planning proposal because the SOW did not provide an explicit milestone.",
            })
            n += 1
    return rows


def _parse_milestone(text: str) -> tuple[str, str]:
    p = _clean(text)
    m = re.match(r"(.+?)\s+(Week\s*\d+|Day\s*\d+|Q[1-4]|\d{4}-\d{2}-\d{2})$", p, re.I)
    return (_clean(m.group(1)), _clean(m.group(2))) if m else (p, "TBD")


def _infer_project_type(text: str) -> str:
    low = text.lower()
    checks = [
        (["construction", "civil works", "site work"], "Construction / Infrastructure"),
        (["platform implementation", "software implementation", "erp", "crm", "sso", "api", "configuration"], "Enterprise Technology Implementation"),
        (["data migration", "data warehouse", "etl"], "Data / Migration"),
        (["change management", "operating model", "process redesign"], "Business Transformation"),
        (["manufacturing line", "plant", "production line"], "Manufacturing / Operations"),
        (["marketing campaign", "brand launch"], "Marketing / Commercial"),
    ]
    for keys, label in checks:
        if any(k in low for k in keys):
            return label
    return "General Project / To be confirmed"


def build_fallback_plan(sow_text: str, project_name: str) -> dict[str, Any]:
    items = _parse_sow_items(sow_text)
    wbs, activities = _build_wbs_and_activities(items, sow_text)

    # Map executable SOW items to actual activities.
    traceability: list[dict[str, Any]] = []
    for item in items:
        mapped = _sow_to_activity_match(item, activities) if item["executable"] else []
        if item["executable"]:
            status = "Mapped" if mapped else "Unmapped"
            reason = "Executable SOW scope mapped to planning activities." if mapped else "Executable SOW scope requires PM mapping review."
        elif item["type"] == "Clarification / Gap":
            status = "Gap"
            reason = "Clarification is handled in the Gaps tab, not as an activity."
        else:
            status = "Reference"
            reason = f"{item['type']} is retained as control/reference content rather than an executable activity."
        traceability.append({
            "sow_id": item["sow_id"],
            "section": item["section"],
            "statement": item["statement"],
            "item_type": item["type"],
            "activity_ids": mapped,
            "status": status,
            "reason": reason,
        })

    executable = [x for x in items if x["executable"]]
    mapped_n = sum(1 for x in traceability if x["status"] == "Mapped")
    coverage = round(mapped_n / len(executable) * 100, 1) if executable else 100.0

    return {
        "summary": {
            "project_name": project_name,
            "project_type": _infer_project_type(sow_text),
            "description": _build_summary(sow_text),
            "confidence": "Medium",
        },
        "scope": {
            "in_scope": [x["statement"] for x in items if x["category"] == "Executable"],
            "out_of_scope": [x["statement"] for x in items if x["type"] == "Out of Scope"],
        },
        "sow_items": items,
        "wbs": wbs,
        "activities": activities,
        "milestones": _build_milestones(items),
        "assumptions": _build_assumptions(items),
        "constraints": _build_constraints(items),
        "gaps": _build_gaps(items),
        "risks": _build_risks(items),
        "traceability": traceability,
        "metadata": {
            "engine": "domain_agnostic_planner_v3",
            "schema_version": "3.0",
            "source_characters": len(sow_text),
            "sow_item_count": len(items),
            "executable_sow_items": len(executable),
            "activity_count": len(activities),
            "milestone_count": len(_build_milestones(items)),
            "gap_count": len(_build_gaps(items)),
            "risk_count": len(_build_risks(items)),
            "assumption_count": len(_build_assumptions(items)),
            "constraint_count": len(_build_constraints(items)),
            "traceability_coverage": coverage,
            "ai_seed_used": False,
        },
    }


def _build_summary(text: str) -> str:
    for section, value in _sectionize(text):
        if "purpose" in section.lower() and value:
            return value[:500]
    return "Project plan derived from the SOW. PM review is required before baselining."


def validate_and_normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return build_fallback_plan("", "Project")
    result = copy.deepcopy(plan)
    for key, default in {
        "summary": {},
        "scope": {"in_scope": [], "out_of_scope": []},
        "sow_items": [], "wbs": [], "activities": [], "milestones": [],
        "assumptions": [], "constraints": [], "gaps": [], "risks": [], "traceability": [], "metadata": {},
    }.items():
        result.setdefault(key, default)
    for a in result["activities"]:
        a.setdefault("dependency_ids", [])
        a.setdefault("source_sow_ids", [])
        a.setdefault("milestone", False)
        a.setdefault("owner_role", "Workstream Lead")
        a.setdefault("planning_note", "PM review required.")
    for t in result["traceability"]:
        t.setdefault("activity_ids", [])
        t.setdefault("status", "Reference")
        t.setdefault("reason", "")
    result["metadata"]["schema_version"] = "3.0"
    return result


def merge_ai_seed_into_plan(base_plan: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    """Merge compact AI intelligence without replacing the structured SOW-derived model."""
    result = validate_and_normalize_plan(base_plan)
    seed = seed if isinstance(seed, dict) else {}
    summary = result["summary"]
    for src, dest in [("project_type", "project_type"), ("description", "description"), ("confidence", "confidence")]:
        if seed.get(src):
            summary[dest] = _clean(seed[src])

    # Surface AI phase labels as recommendations, without creating duplicate WBS rows.
    ai_phases = seed.get("phases") if isinstance(seed.get("phases"), list) else []
    ai_phase_names = []
    for p in ai_phases[:8]:
        name = _clean(p.get("phase") if isinstance(p, dict) else p)
        if name:
            ai_phase_names.append(name)
    for i, row in enumerate(result.get("wbs", [])):
        if i < len(ai_phase_names):
            row["ai_recommended_label"] = ai_phase_names[i]

    # AI key activities are attached to the closest existing activity rather than appended as duplicates.
    for ai_row in seed.get("key_activities", []) if isinstance(seed.get("key_activities"), list) else []:
        if not isinstance(ai_row, dict):
            continue
        name = _clean(ai_row.get("name"))
        if not name:
            continue
        at = set(re.findall(r"[a-z]{4,}", name.lower()))
        best = None
        best_score = 0
        for a in result["activities"]:
            bt = set(re.findall(r"[a-z]{4,}", a.get("activity_name", "").lower()))
            score = len(at & bt)
            if score > best_score:
                best = a
                best_score = score
        if best is not None and best_score >= 1:
            best["ai_flag"] = "AI-identified key activity"
            best["ai_note"] = "Qwen identified this as a key planning activity; PM review required."

    # Merge AI gaps/risks/assumptions as additive insights.
    for category, key, id_prefix, defaults in [
        ("gaps", "description", "AI-GAP", {"category": "AI planning review", "severity": "Review", "recommendation": "PM to validate before baselining.", "source_sow_ids": []}),
        ("risks", "risk", "AI-RISK", {"category": "AI planning review", "impact": "Review", "probability": "Review", "mitigation": "PM to assess and assign an owner.", "owner_role": "Project Manager", "source_sow_ids": []}),
    ]:
        rows = result.setdefault(category, [])
        existing = {str(x.get(key, "")).strip().lower() for x in rows if isinstance(x, dict)}
        for text in seed.get(category, []) if isinstance(seed.get(category), list) else []:
            desc = _clean(text)
            if desc and desc.lower() not in existing:
                row = dict(defaults)
                row[key] = desc
                rows.append(row)
                existing.add(desc.lower())
        id_key = "gap_id" if category == "gaps" else "risk_id"
        for i, row in enumerate(rows, 1):
            row.setdefault(id_key, f"{id_prefix}-{i:03d}")

    assumptions = result.setdefault("assumptions", [])
    existing = {str(a.get("statement", a)).strip().lower() if isinstance(a, dict) else str(a).strip().lower() for a in assumptions}
    for text in seed.get("assumptions", []) if isinstance(seed.get("assumptions"), list) else []:
        desc = _clean(text)
        if desc and desc.lower() not in existing:
            assumptions.append({
                "assumption_id": f"AI-ASM-{len(assumptions)+1:03d}",
                "category": "AI planning review",
                "statement": desc,
                "explicit": False,
                "source_sow_ids": [],
                "confidence": "Medium",
                "review_status": "PM review required",
            })

    executable = [x for x in result.get("sow_items", []) if x.get("executable")]
    mapped_n = sum(1 for x in result.get("traceability", []) if x.get("status") == "Mapped")
    result["metadata"]["traceability_coverage"] = round(mapped_n / len(executable) * 100, 1) if executable else 100.0
    result["metadata"]["ai_seed_used"] = True
    result["metadata"]["schema_version"] = "3.0"
    return result
