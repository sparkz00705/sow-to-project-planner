from __future__ import annotations

import hashlib
import math
import re
from copy import deepcopy
from typing import Any

PLANNER_VERSION = "v5.0"


def _stable_id(prefix: str, text: str, index: int = 0) -> str:
    digest = hashlib.sha1(f"{index}:{text}".encode("utf-8", errors="ignore")).hexdigest()[:8].upper()
    return f"{prefix}-{index:03d}-{digest}"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _contains_any(text: str, phrases: list[str]) -> bool:
    t = text.lower()
    return any(p.lower() in t for p in phrases)


def _sentences(text: str) -> list[tuple[str, str]]:
    """Return (section, statement) pairs from prose/markdown SOW text."""
    current_section = "Unspecified"
    out: list[tuple[str, str]] = []
    raw_lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
    for line in raw_lines:
        clean = re.sub(r"^#{1,6}\s*", "", line).strip()
        clean = re.sub(r"^\*\*(.+?)\*\*$", r"\1", clean).strip()
        heading = (
            len(clean) <= 90
            and not clean.startswith(("-", "*", "•"))
            and "|" not in clean
            and (
                re.match(r"^\d+(\.\d+)*[\.)]?\s+[A-Za-z]", clean)
                or clean.lower() in {
                    "purpose", "project objectives", "scope", "in scope", "out of scope",
                    "dependencies", "client responsibilities", "implementation partner responsibilities",
                    "resources", "major deliverables", "deliverables", "major milestones",
                    "schedule assumptions", "commercial assumptions", "acceptance criteria",
                    "risks and constraints", "risks", "governance", "reporting", "change control",
                    "definition of done", "geographic and organizational scope",
                }
                or clean.lower().startswith(("workstream ", "section "))
            )
        )
        if heading and len(clean.split()) <= 12 and not clean.endswith("."):
            current_section = clean
            continue

        # Treat bullets and table-like rows as content. Split on sentence boundaries;
        # preserve long contractual semicolon lists as a single source statement so
        # downstream parsing can split them intentionally by register type.
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", clean) if p.strip()]
        if len(parts) == 1 and ";" in clean and len(clean) > 240:
            parts = [clean]
        for part in parts:
            part = re.sub(r"^(?:[-*•]\s+|\d+[.)]\s+)", "", part).strip()
            if len(part) >= 12:
                out.append((current_section, _norm(part)))
    return out


def _classify(section: str, statement: str) -> tuple[str, bool, str]:
    s = statement.lower()
    sec = section.lower()
    if "out of scope" in sec or "excludes" in s or "excluded" in s or "outside the scope" in s:
        return "Out of Scope", False, "High"
    if "commercial" in sec or "fee" in s or re.search(r"\b(?:usd|eur|gbp|inr)\s*[\d,]+", s):
        return "Commercial", False, "Medium"
    if "client responsibilities" in sec or "implementation partner responsibilities" in sec:
        return "Responsibility", False, "High"
    if s.startswith("client:") or s.startswith("implementation partner:"):
        return "Responsibility", False, "High"
    # A dedicated milestone section is authoritative. Preserve every listed
    # milestone even when its target is a date, quarter, or not stated.
    if "major milestones" in sec or sec == "milestones" or sec.endswith(" milestones"):
        return "Milestone", False, "High"
    if any(
        p in s
        for p in [
            "not defined", "not stated", "unclear", "not specified", "does not define",
            "undefined", "no entry/exit", "no numerical target", "not provided", "tbd",
        ]
    ):
        return "Clarification / Gap", False, "High"
    if "schedule assumptions" in sec or "assumption" in sec or s.startswith("assume") or "available at least" in s or "expected to be completed" in s:
        return "Assumption", False, "High"
    if "not responsible for" in s:
        return "Contractual Condition", False, "High"
    if "weekly status report" in s or "reporting" in sec:
        return "Reporting / Control", False, "Medium"
    if "dependencies" in sec or (s.startswith("the client will provide") and re.search(r"\bweek\s+\d+\b", s)) or "required by week" in s:
        return "Dependency", False, "High"
    if "acceptance" in sec or "definition of done" in sec or "accepted when" in s or "go-live requires" in s:
        return "Acceptance Criterion", False, "High"
    if "risks and constraints" in sec or sec == "risks" or s.startswith(("initial known risks", "known risks", "risks include")):
        return "Risk / Constraint", False, "High"
    if "change control" in sec:
        return "Change Control / Governance", False, "High"
    if sec == "resources":
        return "Resource Definition", False, "Medium"
    if "major deliverables" in sec:
        return "Deliverable", False, "High"
    if "deliverable" in s or ("document" in s and _contains_any(s, ["produce", "provide", "deliver"])):
        return "Deliverable", True, "Medium"
    if s.startswith("workstream ") or (
        len(statement) < 90
        and not re.search(r"\b(?:implement|configure|design|migrate|integrate|test|train|deploy|assess|conduct|create|establish|execute|manage|transition|handover)\b", s)
    ):
        return "Reference / Heading", False, "Low"
    if _contains_any(
        s,
        [
            "implement", "configure", "design", "migrate", "integrate", "test", "train", "deploy",
            "develop", "build", "conduct", "assess", "establish", "provide", "create", "execute",
            "standardize", "transition", "handover", "support", "manage", "deliver",
        ],
    ):
        return "Scope / Work", True, "High"
    return "Reference / Narrative", False, "Low"


def extract_sow_items(sow_text: str) -> list[dict[str, Any]]:
    pairs = _sentences(sow_text)
    items: list[dict[str, Any]] = []
    admin_prefixes = (
        "sow reference:", "planned duration:", "target countries:", "target users:",
        "project type:", "project name:", "planned schedule:",
    )
    for idx, (section, statement) in enumerate(pairs, 1):
        if statement.lower().startswith(admin_prefixes):
            continue
        item_type, executable, priority = _classify(section, statement)
        items.append(
            {
                "sow_id": _stable_id("SOW", statement, idx),
                "statement": statement,
                "type": item_type,
                "section": section,
                "explicit": True,
                "executable": executable,
                "priority": priority,
            }
        )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in items:
        key = re.sub(r"[^a-z0-9]+", " ", row["statement"].lower()).strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def _find(items: list[dict[str, Any]], *terms: str) -> list[dict[str, Any]]:
    results = []
    for row in items:
        text = f"{row.get('statement', '')} {row.get('section', '')}".lower()
        if any(t.lower() in text for t in terms):
            results.append(row)
    return results


def _duration(activity_name: str) -> int:
    n = activity_name.lower()
    rules = [
        (["kickoff"], 2), (["governance"], 5), (["stakeholder"], 5),
        (["current-state", "discovery", "assessment"], 10),
        (["requirements workshop", "requirements"], 15),
        (["future-state", "solution architecture", "solution design"], 15),
        (["environment"], 7), (["configuration", "configure"], 20),
        (["erp integration", "integration"], 15), (["sso", "identity"], 10),
        (["document-management", "email integration", "collaboration"], 8),
        (["data profiling", "data mapping", "data cleansing"], 10),
        (["trial migration", "rehearsal"], 12), (["data migration"], 15),
        (["test strategy"], 5), (["sit", "system integration testing"], 10),
        (["performance testing", "security testing"], 7), (["uat"], 10),
        (["defect"], 8), (["training materials"], 7), (["training"], 10),
        (["cutover", "readiness"], 5), (["wave 1", "wave 2", "wave 3"], 3),
        (["hypercare"], 22), (["knowledge transfer", "handover"], 5),
        (["closure"], 3),
    ]
    for keys, days in rules:
        if any(k in n for k in keys):
            return days
    return 5


def _owner(activity_name: str) -> str:
    n = activity_name.lower()
    if any(k in n for k in ["governance", "raid", "change control", "kickoff", "charter"]):
        return "Project Manager"
    if any(k in n for k in ["requirements", "current-state", "future-state", "process"]):
        return "Business Analyst / Process Lead"
    if any(k in n for k in ["architecture", "configuration", "configure", "environment", "workflow"]):
        return "Solution / Technical Lead"
    if any(k in n for k in ["integration", "sso", "data", "migration"]):
        return "Integration / Data Lead"
    if any(k in n for k in ["test", "uat", "defect"]):
        return "Test Lead"
    if any(k in n for k in ["training", "change"]):
        return "Change / Training Lead"
    if any(k in n for k in ["deployment", "cutover", "hypercare", "handover", "closure"]):
        return "Deployment / PM Lead"
    return "Project Manager"


def _sources(items: list[dict[str, Any]], *terms: str) -> list[str]:
    allowed = {
        "Scope / Work", "Deliverable", "Milestone", "Dependency",
        "Acceptance Criterion", "Assumption", "Reporting / Control",
    }
    return [row["sow_id"] for row in _find(items, *terms) if row.get("type") in allowed][:50]


def _add_activity(
    activities: list[dict[str, Any]], phase_num: int, phase: str, name: str,
    source_ids: list[str], dep_ids: list[str] | None = None, deliverable: str | None = None,
    milestone: bool = False,
    milestone_name: str | None = None,
) -> str:
    aid = f"ACT-{len(activities) + 1:03d}"
    wbs_id = f"{phase_num}.{sum(1 for a in activities if a['phase'] == phase) + 1}"
    activities.append(
        {
            "wbs_id": wbs_id,
            "activity_id": aid,
            "activity_name": name,
            "phase": phase,
            "duration_days": _duration(name),
            "dependency_ids": dep_ids or [],
            "dependency_lag_days": 0,
            "owner_role": _owner(name),
            "deliverable": deliverable or name,
            "milestone": milestone,
            "milestone_name": milestone_name or "",
            "source_sow_ids": list(source_ids),
            "planning_note": "Deterministic planning recommendation derived from SOW evidence; PM review required.",
        }
    )
    return aid


def _target_week(target: object) -> int | None:
    m = re.search(r"\bweek\s+(\d+)\b", str(target or ""), flags=re.I)
    return int(m.group(1)) if m else None


def _parse_duration(sow_text: str) -> dict[str, Any]:
    patterns = [
        r"planned\s+duration\s*:\s*(\d+)\s*(weeks?|months?|calendar\s+days?|business\s+days?|days?)",
        r"duration\s*[:=]\s*(\d+)\s*(weeks?|months?|calendar\s+days?|business\s+days?|days?)",
        r"\b(\d+)\s*-?\s*(week|weeks|month|months)\s+(?:planned|project)?\s*duration\b",
    ]
    match = None
    for pattern in patterns:
        match = re.search(pattern, sow_text, flags=re.I)
        if match:
            break
    if not match:
        return {"value": None, "unit": None, "week_equivalent": None, "source": "Not stated"}
    value = int(match.group(1))
    unit = re.sub(r"\s+", " ", match.group(2).lower())
    if unit.startswith("week"):
        weeks = value
    elif unit.startswith("month"):
        weeks = value * 4
    elif "business" in unit:
        weeks = math.ceil(value / 5)
    elif "calendar" in unit or unit.startswith("day"):
        weeks = math.ceil(value / 7)
    else:
        weeks = None
    return {"value": value, "unit": unit, "week_equivalent": weeks, "source": "Explicit SOW planned duration"}


def _parse_explicit_milestones(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    milestones: list[dict[str, Any]] = []
    idx = 1
    for row in items:
        if row.get("type") != "Milestone":
            continue
        statement = row["statement"]
        chunks = [p.strip() for p in re.split(r";\s*", statement) if p.strip()]
        if not chunks:
            chunks = [statement]
        for chunk in chunks:
            week_match = re.search(r"\bweek\s+(\d+)\b", chunk, flags=re.I)
            date_match = re.search(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b", chunk)
            quarter_match = re.search(r"\b(Q[1-4]\s+20\d{2})\b", chunk, flags=re.I)
            if week_match:
                target = f"Week {int(week_match.group(1))}"
                clean_name = re.sub(r"\s*[-–—]?\s*Week\s+\d+\b", "", chunk, flags=re.I).strip(" .;:-")
            elif date_match:
                target = date_match.group(1)
                clean_name = re.sub(r"\s*[-–—]?\s*20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", "", chunk).strip(" .;:-")
            elif quarter_match:
                target = quarter_match.group(1).upper()
                clean_name = re.sub(r"\s*[-–—]?\s*Q[1-4]\s+20\d{2}\b", "", chunk, flags=re.I).strip(" .;:-")
            else:
                target = "Not stated"
                clean_name = chunk.strip(" .;:-")
            clean_name = re.sub(r"^\s*(?:and|then)\s+", "", clean_name, flags=re.I)
            if len(clean_name) < 3:
                continue
            milestones.append(
                {
                    "milestone_id": f"MS-{idx:03d}",
                    "name": clean_name,
                    "target": target,
                    "source": "Explicit SOW milestone",
                    "source_sow_ids": [row["sow_id"]],
                    "origin": "SOW",
                }
            )
            idx += 1
    return milestones


def _proposed_milestones(existing: list[dict[str, Any]], activities: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(existing) >= 3:
        return existing
    names = {m["name"].lower() for m in existing}
    proposals = [
        ("Requirements baseline", "Planning proposal"),
        ("Solution design approved", "Planning proposal"),
        ("Acceptance complete", "Planning proposal"),
        ("Production deployment complete", "Planning proposal"),
        ("Project closure", "Planning proposal"),
    ]
    out = list(existing)
    next_id = len(out) + 1
    for name, source in proposals:
        if name.lower() not in names and len(out) < 5:
            out.append(
                {
                    "milestone_id": f"MS-{next_id:03d}",
                    "name": name,
                    "target": "TBD",
                    "source": source,
                    "source_sow_ids": [],
                }
            )
            next_id += 1
    return out


def _build_workstream_activities(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    acts: list[dict[str, Any]] = []
    a1 = _add_activity(acts, 1, "Governance", "Project kickoff and charter approval", _sources(items, "kickoff", "project charter"))
    a2 = _add_activity(acts, 1, "Governance", "Establish governance, RAID, decisions and change control", _sources(items, "governance", "raid", "change control"), [a1])
    a3 = _add_activity(acts, 2, "Discovery & Requirements", "Conduct discovery and current-state assessment", _sources(items, "discovery", "current-state"), [a2])
    a4 = _add_activity(acts, 2, "Discovery & Requirements", "Conduct requirements workshops and consolidate requirements", _sources(items, "requirements", "requirements workshops"), [a3])
    a5 = _add_activity(acts, 2, "Discovery & Requirements", "Validate requirements and obtain requirements sign-off", _sources(items, "requirements sign-off", "requirements"), [a4])
    a6 = _add_activity(acts, 3, "Process & Solution Design", "Design future-state processes, workflows and approval rules", _sources(items, "future-state", "workflows", "approval matrices"), [a5])
    a7 = _add_activity(acts, 3, "Process & Solution Design", "Complete solution architecture and technical design", _sources(items, "solution architecture", "technical design", "solution design"), [a5])
    a8 = _add_activity(acts, 4, "Build & Configuration", "Prepare Development, Test, Validation and Production environments", _sources(items, "environments"), [a7])
    a9 = _add_activity(acts, 4, "Build & Configuration", "Configure platform workflows, rules, roles, permissions and reporting", _sources(items, "configure workflows", "business rules", "roles", "dashboards"), [a6, a8])
    a10 = _add_activity(acts, 5, "Integration & Data", "Implement ERP and enterprise-system integrations", _sources(items, "erp integration", "erp", "integration"), [a7, a8])
    a11 = _add_activity(acts, 5, "Integration & Data", "Implement identity, SSO and access controls", _sources(items, "sso", "identity", "provisioning"), [a7, a8])
    a12 = _add_activity(acts, 5, "Integration & Data", "Implement document, email and collaboration integrations", _sources(items, "document-management", "email", "collaboration"), [a7, a8])
    a13 = _add_activity(acts, 5, "Integration & Data", "Profile, map and cleanse migration data", _sources(items, "data profiling", "data mapping", "data cleansing", "historical data"), [a3])
    a13b = _add_activity(acts, 5, "Integration & Data", "Confirm source data receipt and migration readiness", _sources(items, "source data", "data extract", "data delivery", "source-data"), [a3])
    next(a for a in acts if a["activity_id"] == a13b)["duration_days"] = 1
    a14 = _add_activity(acts, 5, "Integration & Data", "Execute trial migration and reconcile results", _sources(items, "trial migration", "reconciliation"), [a13, a13b, a9])
    a15 = _add_activity(acts, 6, "Testing & Acceptance", "Develop test strategy and test plan", _sources(items, "test strategy", "test plan"), [a5])
    a16 = _add_activity(acts, 6, "Testing & Acceptance", "Execute functional testing and System Integration Testing", _sources(items, "functional testing", "sit"), [a15, a9, a10, a11, a12, a14])
    a17 = _add_activity(acts, 6, "Testing & Acceptance", "Execute performance and security testing", _sources(items, "performance testing", "security testing"), [a16])
    a18 = _add_activity(acts, 6, "Testing & Acceptance", "Support UAT, defect resolution and retesting", _sources(items, "uat", "defect", "retesting"), [a16, a17])
    a19 = _add_activity(acts, 6, "Testing & Acceptance", "Obtain business acceptance / UAT sign-off", _sources(items, "business acceptance", "go-live requires", "acceptance"), [a18])
    a20 = _add_activity(acts, 7, "Training & Change", "Develop training materials and change-readiness content", _sources(items, "training materials", "change management"), [a6])
    a21 = _add_activity(acts, 7, "Training & Change", "Deliver end-user, administrator and support training", _sources(items, "train end users", "administrator training", "training"), [a20])
    a22 = _add_activity(acts, 8, "Deployment & Transition", "Complete cutover and deployment readiness assessment", _sources(items, "cutover", "readiness"), [a19, a21, a14])

    has_waves = any("wave 1" in r["statement"].lower() and "wave 2" in r["statement"].lower() for r in items)
    if has_waves:
        a23 = _add_activity(acts, 8, "Deployment & Transition", "Wave 1 production deployment", _sources(items, "wave 1"), [a22], milestone=True, milestone_name="Wave 1 Go-Live")
        a24 = _add_activity(acts, 8, "Deployment & Transition", "Wave 2 production deployment", _sources(items, "wave 2"), [a23], milestone=True, milestone_name="Wave 2 Go-Live")
        a25 = _add_activity(acts, 8, "Deployment & Transition", "Wave 3 production deployment", _sources(items, "wave 3"), [a24], milestone=True, milestone_name="Wave 3 Go-Live")
        next(a for a in acts if a["activity_id"] == a24)["dependency_lag_days"] = 4
        next(a for a in acts if a["activity_id"] == a25)["dependency_lag_days"] = 4
        last_wave = a25
    else:
        last_wave = _add_activity(acts, 8, "Deployment & Transition", "Production deployment", _sources(items, "production deployment", "deploy", "go-live"), [a22], milestone=True, milestone_name="Production Go-Live")

    a26 = _add_activity(acts, 9, "Hypercare & Closure", "Provide hypercare and stabilize production", _sources(items, "hypercare"), [last_wave])
    hypercare_activity = next(a for a in acts if a["activity_id"] == a26)
    if any("calendar days" in i["statement"].lower() and "hypercare" in i["statement"].lower() for i in items):
        hypercare_activity["duration_days"] = 22
        hypercare_activity["duration_basis"] = "30 calendar days approximated as 22 working days; PM/date-calendar review required."
    _add_activity(acts, 9, "Hypercare & Closure", "Complete knowledge transfer, operational handover and project closure", _sources(items, "knowledge transfer", "handover", "project closure"), [a26])

    keep_always = {
        "Project kickoff and charter approval",
        "Establish governance, RAID, decisions and change control",
        "Develop test strategy and test plan",
        "Complete cutover and deployment readiness assessment",
    }
    kept = [a for a in acts if a["source_sow_ids"] or a["activity_name"] in keep_always]

    if not kept:
        kept.append(
            {
                "wbs_id": "1.1",
                "activity_id": "ACT-001",
                "activity_name": "PM mobilization and delivery baseline",
                "phase": "Mobilization",
                "duration_days": 1,
                "dependency_ids": [],
                "dependency_lag_days": 0,
                "owner_role": "Project Manager",
                "deliverable": "Initial delivery baseline",
                "milestone": False,
                "milestone_name": "",
                "source_sow_ids": [],
                "planning_note": "Fallback planning proposal because no executable SOW work was identified.",
            }
        )

    # Repair dependencies across pruned template activities. The previous implementation
    # silently dropped dependencies when an optional activity was removed, which could
    # move UAT/deployment earlier than the evidence-backed predecessor actually allows.
    all_by_id = {a["activity_id"]: a for a in acts}
    kept_old_ids = {a["activity_id"] for a in kept}

    def retained_predecessors(aid: str, seen: set[str] | None = None) -> set[str]:
        seen = seen or set()
        if aid in seen:
            return set()
        seen.add(aid)
        if aid in kept_old_ids:
            return {aid}
        found: set[str] = set()
        for dep in all_by_id.get(aid, {}).get("dependency_ids", []) or []:
            found |= retained_predecessors(dep, seen)
        return found

    for a in kept:
        repaired: set[str] = set()
        for dep in a.get("dependency_ids", []) or []:
            repaired |= retained_predecessors(dep)
        repaired.discard(a["activity_id"])
        a["dependency_ids"] = sorted(repaired, key=lambda x: int(str(x).split("-")[-1]))

    old_to_new = {a["activity_id"]: f"ACT-{i + 1:03d}" for i, a in enumerate(kept)}
    for a in kept:
        old_id = a["activity_id"]
        a["activity_id"] = old_to_new[old_id]
        a["dependency_ids"] = [old_to_new[d] for d in a.get("dependency_ids", []) if d in old_to_new]

    phase_order = list(dict.fromkeys(a["phase"] for a in kept))
    phase_nums = {phase: i + 1 for i, phase in enumerate(phase_order)}
    phase_counts = {phase: 0 for phase in phase_order}
    for a in kept:
        phase_counts[a["phase"]] += 1
        a["wbs_id"] = f"{phase_nums[a['phase']]}.{phase_counts[a['phase']]}"

    by_id = {a["activity_id"]: a for a in kept}
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def finish_day(aid: str) -> int:
        if aid in memo:
            return memo[aid]
        if aid in visiting:
            raise ValueError(f"Activity dependency cycle detected at {aid}")
        visiting.add(aid)
        a = by_id[aid]
        pred_finish = max((finish_day(d) + max(int(a.get("dependency_lag_days") or 0), 0) for d in a.get("dependency_ids", []) if d in by_id), default=0)
        start_day = pred_finish + 1
        finish = pred_finish + max(int(a.get("duration_days") or 1), 1)
        a["start_day"] = start_day
        a["finish_day"] = finish
        a["start_week"] = (start_day - 1) // 5 + 1
        a["finish_week"] = (finish - 1) // 5 + 1
        memo[aid] = finish
        visiting.remove(aid)
        return finish

    for aid in by_id:
        finish_day(aid)

    phase_rows = []
    for idx, phase in enumerate(phase_order, 1):
        phase_rows.append(
            {
                "wbs_id": str(idx),
                "phase": phase,
                "objective": f"Deliver the {phase.lower()} outcomes required by the SOW.",
                "parent_wbs_id": "",
            }
        )
    return kept, phase_rows


def _build_scope_sets(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    in_scope: list[str] = []
    out_scope: list[str] = []
    for row in items:
        if row["type"] in {"Scope / Work", "Deliverable"}:
            in_scope.append(row["statement"])
        elif row["type"] == "Out of Scope":
            out_scope.append(row["statement"])
    return in_scope, out_scope


def _build_quality_records(
    items: list[dict[str, Any]], activities: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    # Traceability: prefer actual source SOW IDs. Keyword-only mapping is a fallback
    # and requires meaningful evidence (>=2 shared tokens) rather than a single word.
    trace: list[dict[str, Any]] = []
    activity_tokens = [(a, _tokens(a["activity_name"])) for a in activities]
    for row in items:
        sid = row["sow_id"]
        if not row.get("executable"):
            trace.append(
                {
                    "sow_id": sid,
                    "item_type": row["type"],
                    "executable": False,
                    "activity_ids": [],
                    "milestone_ids": [],
                    "status": "Reference / Controlled",
                    "reason": f"Classified as {row['type']}; tracked outside the executable schedule.",
                }
            )
            continue

        direct = [a for a in activities if sid in (a.get("source_sow_ids") or [])]
        if direct:
            mapped = direct[:3]
            reason = "Mapped by explicit SOW source linkage from the planning activity."
        else:
            s_tokens = _tokens(row["statement"])
            scored = sorted(
                [(len(s_tokens & at), a) for a, at in activity_tokens],
                key=lambda x: (x[0], int(x[1].get("finish_week") or 0)),
                reverse=True,
            )
            mapped = [a for score, a in scored[:3] if score >= 2]
            reason = "Mapped by strong scope/keyword alignment." if mapped else "No confident activity mapping; PM review required."

        trace.append(
            {
                "sow_id": sid,
                "item_type": row["type"],
                "executable": True,
                "activity_ids": [a["activity_id"] for a in mapped],
                "milestone_ids": [],
                "status": "Mapped" if mapped else "Review",
                "reason": reason,
            }
        )

    gaps: list[dict[str, Any]] = []
    gap_idx = 1
    for row in items:
        if row["type"] != "Clarification / Gap":
            continue
        raw = row["statement"].strip()
        if raw.lower().startswith("the following ambiguities require clarification:"):
            tail = re.sub(r"^the following ambiguities require clarification:\s*", "", raw, flags=re.I)
            gap_parts = [re.sub(r"^(?:and)\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r";\s*", tail) if p.strip()]
        else:
            gap_parts = [raw]
        for part in gap_parts:
            gaps.append(
                {
                    "gap_id": f"GAP-{gap_idx:03d}",
                    "category": "SOW Clarification",
                    "description": part,
                    "severity": "High",
                    "recommendation": "Clarify and document the missing acceptance criterion, ownership or measurable target before baselining.",
                    "source_sow_ids": [row["sow_id"]],
                }
            )
            gap_idx += 1

    risks: list[dict[str, Any]] = []
    risk_idx = 1
    for row in items:
        if row["type"] != "Risk / Constraint":
            continue
        raw = row["statement"].strip()
        if raw.lower().startswith(("initial known risks include", "known risks include", "risks include")):
            tail = re.sub(r"^(?:initial known risks include|known risks include|risks include)\s*", "", raw, flags=re.I).strip(" .")
            risk_parts = [p.strip(" .") for p in tail.split(",") if p.strip()]
        else:
            parts = [re.sub(r"^(?:and)\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r";\s*", raw) if p.strip()]
            risk_parts = parts if len(parts) > 1 else [raw]
        for part in risk_parts:
            risks.append(
                {
                    "risk_id": f"RISK-{risk_idx:03d}",
                    "risk": part,
                    "impact": "Medium",
                    "probability": "Medium",
                    "mitigation": "Assign a named owner, response action and review cadence during project initiation.",
                    "source_sow_ids": [row["sow_id"]],
                    "origin": "SOW",
                }
            )
            risk_idx += 1

    assumptions: list[dict[str, Any]] = []
    ass_idx = 1
    for row in items:
        if row["type"] != "Assumption":
            continue
        raw = row["statement"].strip()
        parts = [re.sub(r"^(?:and)\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r";\s*", raw) if p.strip()]
        for part in parts:
            assumptions.append(
                {
                    "assumption_id": f"ASM-{ass_idx:03d}",
                    "assumption": part,
                    "basis": "Explicit SOW assumption",
                    "status": "To Validate",
                    "source_sow_ids": [row["sow_id"]],
                    "origin": "SOW",
                }
            )
            ass_idx += 1

    constraints: list[dict[str, Any]] = []
    con_idx = 1
    constraint_patterns = [
        "maximum", "minimum", "threshold", "no more than", "calendar days", "business days",
        "person-days", "seven years", "15%", "40-week", "40 weeks", "five business days",
    ]
    for row in items:
        s = row["statement"].lower()
        if row["type"] not in {"Out of Scope", "Commercial"} and any(k in s for k in constraint_patterns):
            constraints.append(
                {
                    "constraint_id": f"CON-{con_idx:03d}",
                    "constraint": row["statement"],
                    "source_sow_ids": [row["sow_id"]],
                }
            )
            con_idx += 1
    return trace, gaps, risks, assumptions, constraints


_SCHEDULE_SYNONYMS = {
    "project kickoff": ["project kickoff", "kickoff", "charter"],
    "discovery complete": ["discovery", "current state", "current-state", "assessment"],
    "requirements sign-off": ["requirements sign off", "requirements sign-off", "requirements approved", "validate requirements"],
    "requirements approved": ["requirements approved", "requirements sign off", "requirements sign-off", "validate requirements"],
    "future-state design approved": ["future state", "future-state", "process design", "workflow design", "approval matrix"],
    "solution design approved": ["solution design", "solution architecture", "technical design", "architecture"],
    "configuration complete": ["configuration complete", "configure", "configuration", "workflow configuration", "business rules"],
    "integration build complete": ["integration build", "integration", "erp integration", "enterprise integration", "sso"],
    "source data received": ["source data received", "source data", "data extract", "data delivery", "migration data"],
    "trial data migration complete": ["trial data migration", "trial migration", "migration rehearsal"],
    "sit complete": ["sit complete", "system integration testing", "sit"],
    "uat readiness": ["uat readiness", "test strategy", "test plan", "uat preparation"],
    "uat complete": ["uat complete", "uat", "business acceptance", "uat sign-off"],
    "production go-live": ["production go-live", "go-live", "production deployment", "cutover"],
    "hypercare complete": ["hypercare complete", "hypercare", "stabilization", "post go-live support"],
}


def _schedule_terms(name: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    for label, terms in _SCHEDULE_SYNONYMS.items():
        if label in normalized:
            return [re.sub(r"[^a-z0-9]+", " ", t.lower()).strip() for t in terms]
    return [t for t in normalized.split() if len(t) > 2]


def _phrase_hit(term: str, text: str) -> bool:
    term = re.sub(r"\s+", " ", str(term or "").lower()).strip()
    text = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if not term:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))


_SCHEDULE_ACTIVITY_RULES = {
    "project kickoff": ["project kickoff and charter approval"],
    "discovery complete": ["conduct discovery and current-state assessment"],
    "requirements sign-off": ["validate requirements and obtain requirements sign-off"],
    "requirements approved": ["validate requirements and obtain requirements sign-off"],
    "future-state design approved": ["design future-state processes, workflows and approval rules"],
    "solution design approved": ["complete solution architecture and technical design"],
    "configuration complete": ["configure platform workflows, rules, roles, permissions and reporting"],
    "integration build complete": ["implement erp and enterprise-system integrations", "implement identity, sso and access controls", "implement document, email and collaboration integrations"],
    "source data received": ["profile, map and cleanse migration data"],
    "trial data migration complete": ["execute trial migration and reconcile results"],
    "sit complete": ["execute functional testing and system integration testing"],
    "uat readiness": ["develop test strategy and test plan"],
    "uat complete": ["support uat, defect resolution and retesting", "obtain business acceptance / uat sign-off"],
    "production go-live": ["production deployment"],
    "hypercare complete": ["provide hypercare and stabilize production"],
}


def build_schedule_review(milestones: list[dict[str, Any]], activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Single source of truth for explicit SOW milestone reconciliation."""
    rows: list[dict[str, Any]] = []
    for milestone in milestones:
        if milestone.get("source") != "Explicit SOW milestone":
            continue
        name = _norm(milestone.get("name", ""))
        target = _target_week(milestone.get("target"))
        source_ids = set(str(x).strip() for x in (milestone.get("source_sow_ids") or []) if str(x).strip())
        base = {
            "Milestone": name,
            "SOW target": milestone.get("target", "—"),
            "Planned finish": "—",
            "Variance (weeks)": None,
            "Status": "Unmapped",
            "Match basis": "No confident activity link",
            "Linked activities": "",
        }
        if target is None:
            base["Match basis"] = "No explicit week target"
            rows.append(base)
            continue

        normalized_name = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        label_key = next((k for k in _SCHEDULE_ACTIVITY_RULES if k in normalized_name), None)
        target_activity_names = {re.sub(r"[^a-z0-9]+", " ", x.lower()).strip() for x in _SCHEDULE_ACTIVITY_RULES.get(label_key, [])}
        candidates: list[tuple[int, int, dict[str, Any], str]] = []

        for activity in activities:
            aname = _norm(activity.get("activity_name", ""))
            aname_norm = re.sub(r"[^a-z0-9]+", " ", aname.lower()).strip()
            mname = re.sub(r"[^a-z0-9]+", " ", str(activity.get("milestone_name", "")).lower()).strip()
            activity_source_ids = set(str(x).strip() for x in (activity.get("source_sow_ids") or []) if str(x).strip())
            source_match = bool(source_ids & activity_source_ids)
            exact_marker = bool(mname) and (mname == normalized_name or normalized_name in mname or mname in normalized_name)
            label_match = aname_norm in target_activity_names if target_activity_names else False
            if exact_marker:
                candidates.append((1100 + (100 if source_match else 0), 4, activity, "Explicit activity milestone label"))
                continue
            if label_match:
                score = 800 + (100 if source_match else 0)
                # For integration/UAT milestones, use a controlled multi-activity set.
                candidates.append((score, 3, activity, "Milestone-specific activity match"))
                continue

            # Conservative fallback only: require meaningful phrase/token evidence.
            terms = _schedule_terms(name)
            searchable = f"{aname_norm} {re.sub(r'[^a-z0-9]+', ' ', str(activity.get('deliverable', '')).lower())}"
            hits = sum(1 for term in terms if _phrase_hit(term, searchable))
            if source_match and hits >= 1:
                candidates.append((600 + hits * 10, 2, activity, "Shared SOW source + semantic match"))
            elif hits >= 2:
                candidates.append((350 + hits * 10, 1, activity, "Strong planning-language match"))

        if not candidates:
            rows.append(base)
            continue

        candidates.sort(key=lambda x: (x[0], x[1], int(x[2].get("finish_week") or 0)), reverse=True)
        best_score, best_rank, best_activity, basis = candidates[0]

        # Integration completion can be legitimately represented by multiple integration activities.
        if label_key == "integration build complete":
            selected = [
                x[2] for x in candidates
                if x[1] >= best_rank
                and not any(term in x[2].get("activity_name", "").lower() for term in ["testing", "uat", "test plan"])
                and x[0] >= best_score - 25
            ]
            if not selected:
                selected = [best_activity]
        elif label_key == "uat complete":
            selected = [best_activity]
        else:
            selected = [best_activity]

        planned_finish = max(int(a.get("finish_week") or 0) for a in selected)
        variance = planned_finish - target
        rows.append(
            {
                **base,
                "SOW target": f"Week {target}",
                "Planned finish": f"Week {planned_finish}" if planned_finish else "—",
                "Variance (weeks)": variance,
                "Status": "Review" if variance > 1 else "Watch" if variance == 1 else "Aligned",
                "Match basis": basis,
                "Linked activities": ", ".join(str(a.get("activity_name", "")) for a in selected),
            }
        )
    return rows


def _is_ai_row(row: dict[str, Any], kind: str) -> bool:
    category = str(row.get("category", "")).strip().lower()
    basis = str(row.get("basis", "")).strip().lower()
    origin = str(row.get("origin", "")).strip().lower()
    identifier = str(row.get(f"{kind}_id", row.get("id", ""))).upper()
    return identifier.startswith("AI-") or category == "ai review" or basis == "ai planning recommendation" or origin == "ai"


def _gap_counts(gaps: list[dict[str, Any]]) -> dict[str, int]:
    schedule = sum(1 for g in gaps if str(g.get("category", "")).strip().lower() == "schedule fit")
    ai = sum(
        1
        for g in gaps
        if str(g.get("category", "")).strip().lower() != "schedule fit"
        and _is_ai_row(g, "gap")
    )
    scope = len(gaps) - schedule
    high = sum(
        1
        for g in gaps
        if str(g.get("category", "")).strip().lower() != "schedule fit"
        and not _is_ai_row(g, "gap")
        and str(g.get("severity", g.get("priority", ""))).strip().lower() in {"high", "critical", "severe"}
    )
    return {
        "register_total": len(gaps),
        "scope_or_review_gaps": scope,
        "sow_gaps": scope - ai,
        "ai_review_gaps": ai,
        "schedule_findings": schedule,
        "high_severity_sow_gaps": high,
    }


def _add_schedule_findings_to_gap_register(gaps: list[dict[str, Any]], schedule_rows: list[dict[str, Any]]) -> None:
    existing = {str(g.get("description", "")).strip().lower() for g in gaps}
    for row in schedule_rows:
        if row.get("Status") != "Review":
            continue
        description = (
            f"{row.get('Milestone')} is targeted for {row.get('SOW target')}, "
            f"but the linked activity sequence currently finishes around {row.get('Planned finish')}."
        )
        if description.lower() in existing:
            continue
        gaps.append(
            {
                "gap_id": f"GAP-SCH-{sum(1 for g in gaps if str(g.get('category', '')).lower() == 'schedule fit') + 1:03d}",
                "category": "Schedule Fit",
                "description": description,
                "severity": "High",
                "recommendation": "PM to review duration assumptions, eligible parallelization, dependency dates, or an approved milestone exception before baseline.",
                "source_sow_ids": [],
                "source_milestone_id": None,
                "origin": "Schedule",
            }
        )


def _register_ids(plan: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "sow_items": [str(r.get("sow_id", "")) for r in plan.get("sow_items", []) if r.get("sow_id")],
        "activities": [str(r.get("activity_id", "")) for r in plan.get("activities", []) if r.get("activity_id")],
        "milestones": [str(r.get("milestone_id", "")) for r in plan.get("milestones", []) if r.get("milestone_id")],
        "gaps": [str(r.get("gap_id", "")) for r in plan.get("gaps", []) if r.get("gap_id")],
        "risks": [str(r.get("risk_id", "")) for r in plan.get("risks", []) if r.get("risk_id")],
        "assumptions": [str(r.get("assumption_id", "")) for r in plan.get("assumptions", []) if r.get("assumption_id")],
        "constraints": [str(r.get("constraint_id", "")) for r in plan.get("constraints", []) if r.get("constraint_id")],
    }


def _reconcile_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Recompute every leadership metric from the actual registers and schedule."""
    out = deepcopy(plan)
    items = out.get("sow_items", []) or []
    activities = out.get("activities", []) or []
    milestones = out.get("milestones", []) or []
    trace = out.get("traceability", []) or []
    gaps = out.get("gaps", []) or []
    risks = out.get("risks", []) or []
    assumptions = out.get("assumptions", []) or []
    constraints = out.get("constraints", []) or []
    metadata = out.setdefault("metadata", {})

    # Rebuild the schedule after every mutation (including AI merge) from the same logic.
    schedule_rows = build_schedule_review(milestones, activities)
    _add_schedule_findings_to_gap_register(gaps, schedule_rows)
    out["gaps"] = gaps

    # Milestone trace links are derived from the actual milestone register.
    milestone_by_source: dict[str, list[str]] = {}
    for m in milestones:
        for sid in m.get("source_sow_ids", []) or []:
            milestone_by_source.setdefault(str(sid), []).append(str(m.get("milestone_id", "")))
    for row in trace:
        row["milestone_ids"] = milestone_by_source.get(str(row.get("sow_id", "")), [])

    explicit_milestones = [m for m in milestones if m.get("source") == "Explicit SOW milestone"]
    executable_items = [i for i in items if i.get("executable")]
    mapped_exec = sum(1 for t in trace if t.get("executable") and t.get("status") == "Mapped")
    exec_count = len(executable_items)
    coverage = round(mapped_exec / exec_count * 100, 1) if exec_count else 0.0

    duration = metadata.get("sow_duration", {}) if isinstance(metadata.get("sow_duration"), dict) else {}
    duration_value = duration.get("value")
    duration_unit = duration.get("unit")
    duration_week = duration.get("week_equivalent")
    explicit_weeks = [_target_week(m.get("target")) for m in explicit_milestones]
    explicit_weeks = [w for w in explicit_weeks if w is not None]
    latest_target_week = max(explicit_weeks, default=0)
    if duration_week is None and latest_target_week:
        duration_week = latest_target_week
        duration_source = "Latest explicit SOW milestone target"
    else:
        duration_source = str(duration.get("source") or "Not stated")

    planned_finish = max((int(a.get("finish_week") or 0) for a in activities), default=0)
    gap_counts = _gap_counts(gaps)
    ai_risks = sum(1 for r in risks if _is_ai_row(r, "risk"))
    ai_assumptions = sum(1 for a in assumptions if _is_ai_row(a, "assumption"))
    sow_backed_activities = sum(1 for a in activities if a.get("source_sow_ids"))

    errors: list[str] = []
    warnings: list[str] = []
    ids = _register_ids(out)
    for register, values in ids.items():
        duplicates = sorted({v for v in values if v and values.count(v) > 1})
        if duplicates:
            errors.append(f"Duplicate {register} IDs: {', '.join(duplicates[:5])}")

    activity_ids = set(ids["activities"])
    for a in activities:
        for dep in a.get("dependency_ids", []) or []:
            if dep not in activity_ids:
                errors.append(f"Activity {a.get('activity_id')} references missing dependency {dep}.")

    sow_ids = set(ids["sow_items"])
    trace_sow_ids = {str(t.get("sow_id")) for t in trace if t.get("sow_id")}
    if len(trace) != len(items):
        errors.append(f"Traceability row count {len(trace)} does not equal SOW item count {len(items)}.")
    missing_trace = sorted(sow_ids - trace_sow_ids)
    if missing_trace:
        errors.append(f"{len(missing_trace)} SOW item(s) are missing from traceability.")

    if not 0 <= coverage <= 100:
        errors.append(f"Traceability coverage is outside 0-100%: {coverage}.")
    if len(schedule_rows) != len(explicit_milestones):
        errors.append(
            f"Schedule review rows {len(schedule_rows)} do not equal explicit SOW milestones {len(explicit_milestones)}."
        )

    for row in schedule_rows:
        status = row.get("Status")
        variance = row.get("Variance (weeks)")
        if status in {"Aligned", "Watch", "Review"} and not isinstance(variance, int):
            errors.append(f"Schedule row {row.get('Milestone')} has non-integer variance.")
        if status == "Review" and (not isinstance(variance, int) or variance <= 1):
            errors.append(f"Schedule row {row.get('Milestone')} is Review without variance > 1 week.")
        if status == "Watch" and variance != 1:
            errors.append(f"Schedule row {row.get('Milestone')} is Watch without variance = 1 week.")

    status_counts = {s: sum(1 for r in schedule_rows if r.get("Status") == s) for s in ["Aligned", "Watch", "Review", "Unmapped"]}
    if sum(status_counts.values()) != len(explicit_milestones):
        errors.append("Schedule status counts do not reconcile to explicit milestone count.")

    # AI-only rows must never be counted as SOW-backed registers.
    for collection_name, rows, kind in [
        ("gaps", gaps, "gap"),
        ("risks", risks, "risk"),
        ("assumptions", assumptions, "assumption"),
    ]:
        ai_rows = [r for r in rows if _is_ai_row(r, kind)]
        for r in ai_rows:
            if r.get("source_sow_ids"):
                warnings.append(f"AI {collection_name} row {r.get(kind + '_id')} has source SOW IDs; treated as AI by explicit marker.")

    # Confidence is a deterministic planning-quality indicator, not an AI opinion.
    if errors:
        deterministic_confidence = "Low"
    elif coverage >= 90 and status_counts.get("Unmapped", 0) == 0:
        deterministic_confidence = "High"
    else:
        deterministic_confidence = "Medium"

    out.setdefault("summary", {})["confidence"] = deterministic_confidence

    metadata.update(
        {
            "engine": metadata.get("engine", "deterministic"),
            "planner_version": PLANNER_VERSION,
            "engine_version": metadata.get("engine_version") or PLANNER_VERSION,
            "sow_item_count": len(items),
            "executable_sow_item_count": exec_count,
            "activity_count": len(activities),
            "sow_backed_activity_count": sow_backed_activities,
            "planning_proposal_activity_count": len(activities) - sow_backed_activities,
            "traceability_row_count": len(trace),
            "mapped_executable_sow_item_count": mapped_exec,
            "traceability_coverage_percent": coverage,
            "explicit_milestone_count": len(explicit_milestones),
            "milestone_register_count": len(milestones),
            "planned_finish_week": planned_finish,
            "latest_explicit_target_week": latest_target_week,
            "sow_duration": duration,
            "sow_duration_week": duration_week,
            "sow_duration_source": duration_source,
            "gap_register_count": gap_counts["register_total"],
            "scope_or_review_gap_count": gap_counts["scope_or_review_gaps"],
            "sow_gap_count": gap_counts["sow_gaps"],
            "ai_review_gap_count": gap_counts["ai_review_gaps"],
            "schedule_finding_count": gap_counts["schedule_findings"],
            "high_severity_sow_gap_count": gap_counts["high_severity_sow_gaps"],
            "risk_register_count": len(risks),
            "sow_risk_count": len(risks) - ai_risks,
            "ai_review_risk_count": ai_risks,
            "assumption_register_count": len(assumptions),
            "sow_assumption_count": len(assumptions) - ai_assumptions,
            "ai_review_assumption_count": ai_assumptions,
            "constraint_register_count": len(constraints),
            "schedule_review_rows": schedule_rows,
            "schedule_status_counts": status_counts,
            "reconciliation_errors": errors,
            "reconciliation_warnings": warnings,
            "qa_status": "ERROR" if errors else "PASS",
        }
    )
    out["metadata"] = metadata
    return out


def build_deterministic_plan(sow_text: str, project_name: str) -> dict[str, Any]:
    items = extract_sow_items(sow_text)
    activities, wbs = _build_workstream_activities(items)
    milestones = _proposed_milestones(_parse_explicit_milestones(items), activities, items)
    trace, gaps, risks, assumptions, constraints = _build_quality_records(items, activities)
    sow_duration = _parse_duration(sow_text)

    text = sow_text.lower()
    if any(k in text for k in ["implement", "platform", "integration", "migration", "deployment", "erp", "sso"]):
        project_type = "Enterprise Technology Implementation"
    elif any(k in text for k in ["construction", "site works", "civil", "building"]):
        project_type = "Construction / Capital Project"
    elif any(k in text for k in ["marketing", "campaign", "brand"]):
        project_type = "Marketing / Campaign"
    elif any(k in text for k in ["research", "study", "clinical"]):
        project_type = "Research / Study"
    elif any(k in text for k in ["process", "operating model", "policy", "procedure"]):
        project_type = "Business Process / Operating Model"
    else:
        project_type = "General Business Project"

    plan = {
        "summary": {
            "project_name": project_name,
            "project_type": project_type,
            "description": (
                f"The SOW has been converted into a structured project plan covering {len(wbs)} workstreams "
                f"and {len(activities)} planned activities. Explicit SOW milestones, dependencies, risks, gaps "
                "and traceability are retained for PM review; contractual commitments are not changed by the tool."
            ),
            "confidence": "Medium",
        },
        "scope": {"in_scope": [r["statement"] for r in items if r["type"] in {"Scope / Work", "Deliverable"}], "out_of_scope": [r["statement"] for r in items if r["type"] == "Out of Scope"]},
        "sow_items": items,
        "wbs": wbs,
        "activities": activities,
        "milestones": milestones,
        "assumptions": assumptions,
        "constraints": constraints,
        "gaps": gaps,
        "risks": risks,
        "traceability": trace,
        "metadata": {
            "engine": "deterministic",
            "engine_version": PLANNER_VERSION,
            "source_characters": len(sow_text),
            "sow_duration": sow_duration,
        },
    }
    return _reconcile_plan(plan)


def merge_ai_advice(base_plan: dict[str, Any], ai: dict[str, Any] | None) -> dict[str, Any]:
    if not ai:
        return _reconcile_plan(base_plan)
    result = deepcopy(base_plan)
    summary = result.setdefault("summary", {})
    # AI advice is advisory data only. It must not author the application's
    # user-facing summary, project type, or confidence message. Those values
    # remain deterministic and PMO-controlled.

    existing_gap_text = {g.get("description", "").lower() for g in result.get("gaps", [])}
    existing_risk_text = {r.get("risk", "").lower() for r in result.get("risks", [])}
    existing_assumption_text = {a.get("assumption", "").lower() for a in result.get("assumptions", [])}

    for idx, g in enumerate(ai.get("gaps", [])[:3], 1):
        text = _norm(g)
        if text and text.lower() not in existing_gap_text:
            result["gaps"].append(
                {
                    "gap_id": f"AI-GAP-{idx:03d}",
                    "category": "AI Review",
                    "description": text,
                    "severity": "Review",
                    "recommendation": "PM to validate the clarification before baseline.",
                    "source_sow_ids": [],
                    "origin": "AI",
                }
            )
            existing_gap_text.add(text.lower())

    for idx, r in enumerate(ai.get("risks", [])[:3], 1):
        text = _norm(r)
        if text and text.lower() not in existing_risk_text:
            result["risks"].append(
                {
                    "risk_id": f"AI-RISK-{idx:03d}",
                    "risk": text,
                    "impact": "Medium",
                    "probability": "Medium",
                    "mitigation": "PM to validate, assign owner and define response.",
                    "source_sow_ids": [],
                    "origin": "AI",
                }
            )
            existing_risk_text.add(text.lower())

    for idx, a in enumerate(ai.get("assumptions", [])[:3], 1):
        text = _norm(a)
        if text and text.lower() not in existing_assumption_text:
            result["assumptions"].append(
                {
                    "assumption_id": f"AI-ASM-{idx:03d}",
                    "assumption": text,
                    "basis": "AI planning recommendation",
                    "status": "To Validate",
                    "source_sow_ids": [],
                    "origin": "AI",
                }
            )
            existing_assumption_text.add(text.lower())

    result.setdefault("metadata", {})["ai_seed_used"] = True
    return _reconcile_plan(result)


def validate_and_normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return build_deterministic_plan("", "Project")
    keys = [
        "summary", "scope", "sow_items", "wbs", "activities", "milestones",
        "assumptions", "constraints", "gaps", "risks", "traceability", "metadata",
    ]
    out = {k: deepcopy(plan.get(k)) for k in keys}
    for k in keys:
        if out[k] is None:
            out[k] = {} if k in {"summary", "scope", "metadata"} else []
    for a in out["activities"]:
        a.setdefault("dependency_ids", [])
        a.setdefault("source_sow_ids", [])
        a.setdefault("milestone", False)
        a.setdefault("planning_note", "PM review required.")
    return _reconcile_plan(out)


# Compatibility aliases used by older versions.
build_fallback_plan = build_deterministic_plan
