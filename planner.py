
from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any


PLANNER_VERSION = "v4.0"


def _stable_id(prefix: str, text: str, index: int = 0) -> str:
    digest = hashlib.sha1(f"{index}:{text}".encode("utf-8", errors="ignore")).hexdigest()[:6].upper()
    return f"{prefix}-{index:03d}-{digest}"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _sentences(text: str) -> list[tuple[str, str]]:
    """Return (section, statement) pairs from prose/markdown SOW text."""
    current_section = "Unspecified"
    out: list[tuple[str, str]] = []
    raw_lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
    for line in raw_lines:
        clean = re.sub(r"^#{1,6}\s*", "", line).strip()
        clean = re.sub(r"^\*\*(.+?)\*\*$", r"\1", clean).strip()
        # Table rows and bullets are treated as content, not headings.
        heading = (
            len(clean) <= 90
            and not clean.startswith(("-", "*", "•"))
            and not "|" in clean
            and (
                re.match(r"^\d+(\.\d+)*[\.)]?\s+[A-Za-z]", clean)
                or clean.lower() in {
                    "purpose", "project objectives", "scope", "in scope", "out of scope",
                    "dependencies", "client responsibilities", "implementation partner responsibilities",
                    "resources", "major deliverables", "deliverables", "major milestones",
                    "schedule assumptions", "commercial assumptions", "acceptance criteria",
                    "risks and constraints", "governance", "reporting", "change control",
                    "definition of done", "geographic and organizational scope",
                }
                or clean.lower().startswith(("workstream ", "section "))
            )
        )
        if heading and len(clean.split()) <= 12 and not clean.endswith("."):
            current_section = clean
            continue

        # Split semicolon-delimited sentences only when they clearly represent separate directives.
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", clean) if p.strip()]
        if len(parts) == 1 and ";" in clean and len(clean) > 240:
            # Preserve long contractual lists as one SOW item. They are often deliverable inventories.
            parts = [clean]
        for part in parts:
            if len(part) >= 12:
                out.append((current_section, _norm(part)))
    return out


def _contains_any(text: str, phrases: list[str]) -> bool:
    t = text.lower()
    return any(p in t for p in phrases)


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
    if any(p in s for p in ["not defined", "not stated", "unclear", "not specified", "does not define", "undefined", "no entry/exit", "no numerical target"]):
        return "Clarification / Gap", False, "High"
    if "schedule assumptions" in sec or "assumption" in sec or s.startswith("assume") or "available at least" in s or "expected to be completed" in s:
        return "Assumption", False, "High"
    if "not responsible for" in s:
        return "Contractual Condition", False, "High"
    if "weekly status report" in s or "reporting" in sec:
        return "Reporting / Control", False, "Medium"
    if "dependencies" in sec or (
        s.startswith("the client will provide") and re.search(r"\bweek\s+\d+\b", s)
    ) or "required by week" in s:
        return "Dependency", False, "High"
    if "acceptance" in sec or "definition of done" in sec or "accepted when" in s or "go-live requires" in s:
        return "Acceptance Criterion", False, "High"
    if "major milestones" in sec or (re.search(r"\bweek\s+\d+\b", s) and any(k in s for k in ["kickoff", "complete", "sign-off", "approved", "readiness", "go-live", "build"])):
        return "Milestone", False, "High"
    if "risks and constraints" in sec or sec == "risks" or s.startswith("initial known risks"):
        return "Risk / Constraint", False, "High"
    if "change control" in sec:
        return "Change Control / Governance", False, "High"
    if sec == "resources":
        return "Resource Definition", False, "Medium"
    if "major deliverables" in sec:
        return "Deliverable", False, "High"
    if "deliverable" in s or "document" in s and _contains_any(s, ["produce", "provide", "deliver"]):
        return "Deliverable", True, "Medium"
    if s.startswith("workstream ") or (len(statement) < 90 and not re.search(r"\b(?:implement|configure|design|migrate|integrate|test|train|deploy|assess|conduct|create|establish)\b", s)):
        return "Reference / Heading", False, "Low"
    if _contains_any(s, [
        "implement", "configure", "design", "migrate", "integrate", "test", "train", "deploy",
        "develop", "build", "conduct", "assess", "establish", "provide", "create", "execute",
        "standardize", "transition", "handover", "support", "manage",
    ]):
        return "Scope / Work", True, "High"
    return "Reference / Narrative", False, "Low"


def extract_sow_items(sow_text: str) -> list[dict[str, Any]]:
    pairs = _sentences(sow_text)
    items: list[dict[str, Any]] = []
    admin_prefixes = ("sow reference:", "planned duration:", "target countries:", "target users:", "project type:")
    for idx, (section, statement) in enumerate(pairs, 1):
        if statement.lower().startswith(admin_prefixes):
            continue
        item_type, executable, priority = _classify(section, statement)
        items.append({
            "sow_id": _stable_id("SOW", statement, idx),
            "statement": statement,
            "type": item_type,
            "section": section,
            "explicit": True,
            "executable": executable,
            "priority": priority,
        })

    # Remove duplicate/near-duplicate statements while preserving order.
    seen = set()
    deduped = []
    for row in items:
        key = re.sub(r"[^a-z0-9]+", " ", row["statement"].lower()).strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def _find(items: list[dict[str, Any]], *terms: str) -> list[dict[str, Any]]:
    results = []
    for row in items:
        text = f"{row.get('statement','')} {row.get('section','')}".lower()
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
        (["hypercare"], 30), (["knowledge transfer", "handover"], 5),
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
        "Acceptance Criterion", "Assumption", "Reporting / Control"
    }
    return [row["sow_id"] for row in _find(items, *terms) if row.get("type") in allowed][:5]


def _add_activity(activities, phase_num, phase, name, source_ids, dep_ids=None, deliverable=None, milestone=False):
    aid = f"ACT-{len(activities)+1:03d}"
    wbs_id = f"{phase_num}.{sum(1 for a in activities if a['phase']==phase)+1}"
    activities.append({
        "wbs_id": wbs_id,
        "activity_id": aid,
        "activity_name": name,
        "phase": phase,
        "duration_days": _duration(name),
        "dependency_ids": dep_ids or [],
        "owner_role": _owner(name),
        "deliverable": deliverable or name,
        "milestone": milestone,
        "source_sow_ids": source_ids,
        "planning_note": "Deterministic planning recommendation derived from executable SOW scope; PM review required.",
    })
    return aid


def _parse_explicit_milestones(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    milestones = []
    idx = 1
    for row in items:
        if row.get("type") != "Milestone":
            continue
        stmt = row["statement"]
        matches = re.findall(r"([^;]+?)\s+Week\s+(\d+)", stmt, flags=re.I)
        for name, week in matches:
            clean_name = re.sub(r"^\s*(?:and|then)\s+", "", name.strip(" .;:"))
            if len(clean_name) < 3:
                continue
            milestones.append({
                "milestone_id": f"MS-{idx:03d}",
                "name": clean_name,
                "target": f"Week {week}",
                "source": "Explicit SOW milestone",
                "source_sow_ids": [row["sow_id"]],
            })
            idx += 1
    return milestones


def _proposed_milestones(existing: list[dict[str, Any]], activities: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer explicit SOW milestones. Only add a small proposal set when the SOW
    # contains too few usable milestones to support schedule governance.
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
            out.append({
                "milestone_id": f"MS-{next_id:03d}",
                "name": name,
                "target": "TBD",
                "source": source,
                "source_sow_ids": [],
            })
            next_id += 1
    return out


def _build_workstream_activities(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    acts = []
    # 1 Governance
    a1 = _add_activity(acts, 1, "Governance", "Project kickoff and charter approval", _sources(items, "kickoff", "project charter"))
    a2 = _add_activity(acts, 1, "Governance", "Establish governance, RAID, decisions and change control", _sources(items, "governance", "raid", "change control"), [a1])

    # 2 Discovery & Requirements
    a3 = _add_activity(acts, 2, "Discovery & Requirements", "Conduct discovery and current-state assessment", _sources(items, "discovery", "current-state"), [a2])
    a4 = _add_activity(acts, 2, "Discovery & Requirements", "Conduct requirements workshops and consolidate requirements", _sources(items, "requirements", "requirements workshops"), [a3])
    a5 = _add_activity(acts, 2, "Discovery & Requirements", "Validate requirements and obtain requirements sign-off", _sources(items, "requirements sign-off", "requirements"), [a4])

    # 3 Process & Solution Design
    a6 = _add_activity(acts, 3, "Process & Solution Design", "Design future-state processes, workflows and approval rules", _sources(items, "future-state", "workflows", "approval matrices"), [a5])
    a7 = _add_activity(acts, 3, "Process & Solution Design", "Complete solution architecture and technical design", _sources(items, "solution architecture", "technical design", "solution design"), [a5])

    # 4 Build / Configuration
    a8 = _add_activity(acts, 4, "Build & Configuration", "Prepare Development, Test, Validation and Production environments", _sources(items, "environments"), [a7])
    a9 = _add_activity(acts, 4, "Build & Configuration", "Configure platform workflows, rules, roles, permissions and reporting", _sources(items, "configure workflows", "business rules", "roles", "dashboards"), [a6, a8])

    # 5 Integration & Data
    a10 = _add_activity(acts, 5, "Integration & Data", "Implement ERP and enterprise-system integrations", _sources(items, "erp integration", "erp", "integration"), [a7, a8])
    a11 = _add_activity(acts, 5, "Integration & Data", "Implement identity, SSO and access controls", _sources(items, "sso", "identity", "provisioning"), [a7, a8])
    a12 = _add_activity(acts, 5, "Integration & Data", "Implement document, email and collaboration integrations", _sources(items, "document-management", "email", "collaboration"), [a7, a8])
    a13 = _add_activity(acts, 5, "Integration & Data", "Profile, map and cleanse migration data", _sources(items, "data profiling", "data mapping", "data cleansing", "historical data"), [a3])
    a14 = _add_activity(acts, 5, "Integration & Data", "Execute trial migration and reconcile results", _sources(items, "trial migration", "reconciliation"), [a13, a9])

    # 6 Testing & Acceptance
    a15 = _add_activity(acts, 6, "Testing & Acceptance", "Develop test strategy and test plan", _sources(items, "test strategy", "test plan"), [a9, a10, a11, a12, a14])
    a16 = _add_activity(acts, 6, "Testing & Acceptance", "Execute functional testing and System Integration Testing", _sources(items, "functional testing", "sit"), [a15])
    a17 = _add_activity(acts, 6, "Testing & Acceptance", "Execute performance and security testing", _sources(items, "performance testing", "security testing"), [a16])
    a18 = _add_activity(acts, 6, "Testing & Acceptance", "Support UAT, defect resolution and retesting", _sources(items, "uat", "defect", "retesting"), [a16, a17])
    a19 = _add_activity(acts, 6, "Testing & Acceptance", "Obtain business acceptance / UAT sign-off", _sources(items, "business acceptance", "go-live requires"), [a18])

    # 7 Training & Change
    a20 = _add_activity(acts, 7, "Training & Change", "Develop training materials and change-readiness content", _sources(items, "training materials", "change management"), [a6])
    a21 = _add_activity(acts, 7, "Training & Change", "Deliver end-user, administrator and support training", _sources(items, "train end users", "administrator training"), [a20, a19])

    # 8 Deployment & Transition
    a22 = _add_activity(acts, 8, "Deployment & Transition", "Complete cutover and deployment readiness assessment", _sources(items, "cutover", "readiness"), [a19, a21, a14])
    # Three waves only if the SOW mentions waves
    has_waves = any("wave 1" in r["statement"].lower() and "wave 2" in r["statement"].lower() for r in items)
    if has_waves:
        a23 = _add_activity(acts, 8, "Deployment & Transition", "Wave 1 production deployment", _sources(items, "wave 1", "india", "singapore"), [a22], milestone=True)
        a24 = _add_activity(acts, 8, "Deployment & Transition", "Wave 2 production deployment", _sources(items, "wave 2", "uk", "germany"), [a23], milestone=True)
        a25 = _add_activity(acts, 8, "Deployment & Transition", "Wave 3 production deployment", _sources(items, "wave 3", "us"), [a24], milestone=True)
        last_wave = a25
    else:
        last_wave = _add_activity(acts, 8, "Deployment & Transition", "Production deployment", _sources(items, "production deployment", "deploy"), [a22], milestone=True)

    # 9 Hypercare & Closure
    a26 = _add_activity(acts, 9, "Hypercare & Closure", "Provide hypercare and stabilize production", _sources(items, "hypercare"), [last_wave])
    a27 = _add_activity(acts, 9, "Hypercare & Closure", "Complete knowledge transfer, operational handover and project closure", _sources(items, "knowledge transfer", "handover", "project closure"), [a26])

    # Remove optional workstreams that are not supported by the SOW.
    keep_always = {
        "Project kickoff and charter approval",
        "Establish governance, RAID, decisions and change control",
        "Develop test strategy and test plan",
        "Complete cutover and deployment readiness assessment",
    }
    kept = []
    for a in acts:
        if a["source_sow_ids"] or a["activity_name"] in keep_always:
            kept.append(a)

    # Remap IDs and dependencies after pruning, preserving the deliberate dependency graph.
    old_to_new = {a["activity_id"]: f"ACT-{i+1:03d}" for i, a in enumerate(kept)}
    for a in kept:
        old_id = a["activity_id"]
        a["activity_id"] = old_to_new[old_id]
        a["dependency_ids"] = [old_to_new[d] for d in a.get("dependency_ids", []) if d in old_to_new]

    # Renumber WBS within each phase while retaining explicit cross-phase dependencies.
    phase_order = list(dict.fromkeys(a["phase"] for a in kept))
    phase_nums = {phase: i + 1 for i, phase in enumerate(phase_order)}
    phase_counts = {phase: 0 for phase in phase_order}
    for a in kept:
        phase_counts[a["phase"]] += 1
        a["wbs_id"] = f"{phase_nums[a['phase']]}.{phase_counts[a['phase']]}"

    activities = kept
    # Derive relative working-day schedule from the dependency graph (no calendar date is invented).
    by_id = {a["activity_id"]: a for a in activities}
    memo = {}

    def finish_day(aid: str, visiting=None) -> int:
        visiting = visiting or set()
        if aid in memo:
            return memo[aid]
        if aid in visiting:
            return 0
        visiting.add(aid)
        a = by_id[aid]
        pred_finish = max((finish_day(d, visiting) for d in a.get("dependency_ids", []) if d in by_id), default=0)
        start_day = pred_finish + 1
        finish = pred_finish + int(a.get("duration_days") or 1)
        a["start_day"] = start_day
        a["finish_day"] = finish
        a["start_week"] = (start_day - 1) // 5 + 1
        a["finish_week"] = (finish - 1) // 5 + 1
        memo[aid] = finish
        visiting.remove(aid)
        return finish

    for aid in by_id:
        finish_day(aid)

    # Domain-neutral safety net: if the SOW is not a technology-style project,
    # ensure the plan still contains executable delivery activities.
    if len(activities) < 6:
        existing_names = {a["activity_name"].lower() for a in activities}
        extra_specs = [
            ("Delivery baseline and mobilization", "Planning / Mobilization"),
            ("Execute core SOW deliverables", "Delivery"),
            ("Validate deliverables and acceptance", "Validation & Acceptance"),
            ("Transition and close the project", "Transition & Closure"),
        ]
        phase_num_base = len(phase_order)
        for name, phase in extra_specs:
            if name.lower() in existing_names:
                continue
            aid = f"ACT-{len(activities)+1:03d}"
            activities.append({
                "wbs_id": f"{phase_num_base+1}.1",
                "activity_id": aid,
                "activity_name": name,
                "phase": phase,
                "duration_days": _duration(name),
                "dependency_ids": [activities[-1]["activity_id"]] if activities else [],
                "owner_role": _owner(name),
                "deliverable": name,
                "milestone": False,
                "source_sow_ids": [],
                "planning_note": "Domain-neutral planning recommendation; PM review required.",
            })
            existing_names.add(name.lower())
        # Recompute derived schedule fields after additions.
        by_id = {a["activity_id"]: a for a in activities}
        memo = {}
        for aid in by_id:
            finish_day(aid)

    phase_rows = []
    for idx, phase in enumerate(dict.fromkeys(a["phase"] for a in activities), 1):
        phase_rows.append({
            "wbs_id": str(idx),
            "phase": phase,
            "objective": f"Deliver the {phase.lower()} outcomes required by the SOW.",
            "parent_wbs_id": "",
        })
    return activities, phase_rows


def _build_scope_sets(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    in_scope = []
    out_scope = []
    for row in items:
        if row["type"] in {"Scope / Work", "Deliverable"}:
            in_scope.append(row["statement"])
        elif row["type"] == "Out of Scope":
            out_scope.append(row["statement"])
    return in_scope, out_scope


def _build_quality_records(items: list[dict[str, Any]], activities: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    exec_items = [i for i in items if i.get("executable")]
    activity_tokens = []
    for a in activities:
        activity_tokens.append((a, set(re.findall(r"[a-z0-9]+", a["activity_name"].lower()))))

    trace = []
    for row in items:
        sid = row["sow_id"]
        if not row.get("executable"):
            trace.append({
                "sow_id": sid,
                "item_type": row["type"],
                "executable": False,
                "activity_ids": [],
                "milestone_ids": [],
                "status": "Reference / Controlled",
                "reason": f"Classified as {row['type']}; tracked outside executable schedule.",
            })
            continue
        s_tokens = set(re.findall(r"[a-z0-9]+", row["statement"].lower()))
        scores = []
        for a, a_tokens in activity_tokens:
            overlap = len(s_tokens & a_tokens)
            scores.append((overlap, a))
        scores.sort(key=lambda x: x[0], reverse=True)
        mapped = [a for score, a in scores[:3] if score >= 1]
        if not mapped:
            # fallback to relevant phase by statement keywords
            mapped = []
            st = row["statement"].lower()
            phase_hint = (
                "Integration & Data" if any(k in st for k in ["integrat", "migration", "data", "sso", "erp"]) else
                "Testing & Acceptance" if any(k in st for k in ["test", "uat", "defect"]) else
                "Training & Change" if any(k in st for k in ["train"]) else
                "Deployment & Transition" if any(k in st for k in ["deploy", "cutover"]) else
                "Process & Solution Design" if any(k in st for k in ["design", "workflow"]) else
                "Discovery & Requirements" if any(k in st for k in ["requirement", "discovery"]) else
                "Governance"
            )
            same = [a for a in activities if a["phase"] == phase_hint]
            mapped = same[:1]
        trace.append({
            "sow_id": sid,
            "item_type": row["type"],
            "executable": True,
            "activity_ids": [a["activity_id"] for a in mapped],
            "milestone_ids": [],
            "status": "Mapped" if mapped else "Review",
            "reason": "Mapped to executable planning activity by scope/keyword alignment." if mapped else "No confident activity mapping; PM review required.",
        })

    gaps = []
    gap_idx = 1
    for row in items:
        s = row["statement"]
        if row["type"] == "Clarification / Gap":
            raw = s.strip()
            if raw.lower().startswith("the following ambiguities require clarification:"):
                tail = re.sub(r"^the following ambiguities require clarification:\s*", "", raw, flags=re.I)
                gap_parts = [re.sub(r"^(?:and)\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r";\s*", tail) if p.strip()]
            else:
                gap_parts = [raw]
            for part in gap_parts:
                gaps.append({
                    "gap_id": f"GAP-{gap_idx:03d}",
                    "category": "SOW Clarification",
                    "description": part,
                    "severity": "High",
                    "recommendation": "Clarify and document the missing acceptance criterion, ownership or measurable target before baselining.",
                    "source_sow_ids": [row["sow_id"]],
                })
                gap_idx += 1

    risks = []
    risk_idx = 1
    for row in items:
        if row["type"] == "Risk / Constraint":
            raw = row["statement"].strip()
            if raw.lower().startswith("initial known risks include"):
                tail = re.sub(r"^initial known risks include\s*", "", raw, flags=re.I).strip(" .")
                risk_parts = [p.strip(" .") for p in tail.split(",") if p.strip()]
            else:
                parts = [re.sub(r"^(?:and)\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r";\s*", raw) if p.strip()]
                risk_parts = parts if len(parts) > 1 else [raw]
            for part in risk_parts[:8]:
                risks.append({
                    "risk_id": f"RISK-{risk_idx:03d}",
                    "risk": part,
                    "impact": "Medium",
                    "probability": "Medium",
                    "mitigation": "Assign a named owner, response action and review cadence during project initiation.",
                    "source_sow_ids": [row["sow_id"]],
                })
                risk_idx += 1

    assumptions = []
    ass_idx = 1
    for row in items:
        if row["type"] == "Assumption":
            raw = row["statement"].strip()
            parts = [re.sub(r"^(?:and)\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r";\s*", raw) if p.strip()]
            for part in parts:
                assumptions.append({
                    "assumption_id": f"ASM-{ass_idx:03d}",
                    "assumption": part,
                    "basis": "Explicit SOW assumption",
                    "status": "To Validate",
                    "source_sow_ids": [row["sow_id"]],
                })
                ass_idx += 1

    constraints = []
    con_idx = 1
    for row in items:
        s = row["statement"].lower()
        if row["type"] not in {"Out of Scope", "Commercial"} and any(k in s for k in ["maximum", "minimum", "threshold", "no more than", "calendar days", "business days", "15%", "person-days", "seven years", "40-week"]):
            constraints.append({
                "constraint_id": f"CON-{con_idx:03d}",
                "constraint": row["statement"],
                "source_sow_ids": [row["sow_id"]],
            })
            con_idx += 1

    return trace, gaps, risks, assumptions, constraints



def _schedule_alignment_gaps(milestones: list[dict[str, Any]], activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare explicit milestone targets to the most relevant planned activity."""
    mapping_rules = [
        ("discovery complete", ["discovery and current-state"]),
        ("requirements sign-off", ["requirements sign-off"]),
        ("future-state design approved", ["future-state processes"]),
        ("solution design approved", ["solution architecture"]),
        ("configuration complete", ["configure platform"]),
        ("integration build complete", ["erp and enterprise-system integrations", "identity, sso", "document, email"]),
        ("trial data migration complete", ["trial migration"]),
        ("sit complete", ["system integration testing"]),
        ("uat readiness", ["test strategy", "uat"]),
        ("uat complete", ["business acceptance", "uat sign-off"]),
        ("wave 1 go-live", ["wave 1 production"]),
        ("wave 2 go-live", ["wave 2 production"]),
        ("wave 3 go-live", ["wave 3 production"]),
        ("hypercare complete", ["hypercare"]),
    ]
    out = []
    for m in milestones:
        if m.get("source") != "Explicit SOW milestone":
            continue
        match = re.search(r"\bweek\s+(\d+)\b", str(m.get("target", "")), flags=re.I)
        if not match:
            continue
        target = int(match.group(1))
        name = str(m.get("name", "")).strip().lower()
        keywords = next((keys for label, keys in mapping_rules if label in name), None)
        if not keywords:
            continue
        candidates = [a for a in activities if any(k in a["activity_name"].lower() for k in keywords)]
        if not candidates:
            continue
        finish = max(a.get("finish_week", 0) or 0 for a in candidates)
        if finish > target + 1:
            out.append({
                "gap_id": f"GAP-SCH-{len(out)+1:03d}",
                "category": "Schedule Fit",
                "description": f"{m['name']} is targeted for Week {target}, but the linked activity sequence currently finishes around Week {finish}.",
                "severity": "High",
                "recommendation": "PM to review duration assumptions, parallelize eligible work, or rebaseline the SOW milestone before approval.",
                "source_sow_ids": m.get("source_sow_ids", []),
            })
    return out


def build_deterministic_plan(sow_text: str, project_name: str) -> dict[str, Any]:
    items = extract_sow_items(sow_text)
    activities, wbs = _build_workstream_activities(items)
    milestones = _proposed_milestones(_parse_explicit_milestones(items), activities, items)
    trace, gaps, risks, assumptions, constraints = _build_quality_records(items, activities)
    schedule_gaps = _schedule_alignment_gaps(milestones, activities)
    gaps.extend(schedule_gaps)

    # Link explicit milestone SOW items to the milestone register.
    milestone_by_source = {}
    for m in milestones:
        for sid in m.get("source_sow_ids", []):
            milestone_by_source.setdefault(sid, []).append(m["milestone_id"])
    for row in trace:
        row["milestone_ids"] = milestone_by_source.get(row["sow_id"], [])

    in_scope, out_scope = _build_scope_sets(items)

    # Infer project type deterministically from strongest signals.
    text = sow_text.lower()
    if any(k in text for k in ["implement", "platform", "integration", "migration", "deployment", "erp", "sso"]):
        project_type = "Enterprise Technology Implementation"
    elif any(k in text for k in ["construction", "site works", "civil", "building"]):
        project_type = "Construction / Capital Project"
    elif any(k in text for k in ["marketing", "campaign", "brand"]):
        project_type = "Marketing / Campaign"
    elif any(k in text for k in ["research", "study", "clinical"]):
        project_type = "Research / Study"
    else:
        project_type = "General Business Project"

    mapped_exec = sum(1 for t in trace if t["executable"] and t["status"] == "Mapped")
    exec_count = sum(1 for i in items if i["executable"])
    coverage = round(mapped_exec / exec_count * 100, 1) if exec_count else 0.0

    return {
        "summary": {
            "project_name": project_name,
            "project_type": project_type,
            "description": f"Executable work extracted from the SOW and organized into {len(wbs)} workstreams with PM-reviewable durations, dependencies and traceability.",
            "confidence": "Medium",
        },
        "scope": {"in_scope": in_scope, "out_of_scope": out_scope},
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
            "sow_item_count": len(items),
            "executable_sow_item_count": exec_count,
            "activity_count": len(activities),
            "traceability_coverage_percent": coverage,
            "explicit_milestone_count": sum(1 for m in milestones if m.get("source") == "Explicit SOW milestone"),
            "planned_finish_week": max((a.get("finish_week", 0) or 0) for a in activities) if activities else 0,
            "latest_explicit_target_week": max(
                [int(re.search(r"\bweek\s+(\d+)\b", str(m.get("target", "")), flags=re.I).group(1))
                 for m in milestones
                 if m.get("source") == "Explicit SOW milestone" and re.search(r"\bweek\s+(\d+)\b", str(m.get("target", "")), flags=re.I)]
                or [0]
            ),
        },
    }


def merge_ai_advice(base_plan: dict[str, Any], ai: dict[str, Any] | None) -> dict[str, Any]:
    if not ai:
        return base_plan
    result = deepcopy(base_plan)
    summary = result["summary"]
    if ai.get("project_type"):
        summary["project_type"] = _norm(ai["project_type"])[:100]
    if ai.get("summary"):
        summary["description"] = _norm(ai["summary"])[:500]
    if ai.get("confidence"):
        summary["confidence"] = str(ai["confidence"])

    # Add only genuinely new AI advice to quality registers. Do NOT duplicate activities.
    existing_gap_text = {g["description"].lower() for g in result["gaps"]}
    for idx, g in enumerate(ai.get("gaps", [])[:3], 1):
        text = _norm(g)
        if text and text.lower() not in existing_gap_text:
            result["gaps"].append({
                "gap_id": f"AI-GAP-{idx:03d}",
                "category": "AI Review",
                "description": text,
                "severity": "Review",
                "recommendation": "PM to validate the clarification before baseline.",
                "source_sow_ids": [],
            })

    existing_risk_text = {r["risk"].lower() for r in result["risks"]}
    for idx, r in enumerate(ai.get("risks", [])[:3], 1):
        text = _norm(r)
        if text and text.lower() not in existing_risk_text:
            result["risks"].append({
                "risk_id": f"AI-RISK-{idx:03d}",
                "risk": text,
                "impact": "Medium",
                "probability": "Medium",
                "mitigation": "PM to validate, assign owner and define response.",
                "source_sow_ids": [],
            })

    existing_assumptions = {a["assumption"].lower() for a in result["assumptions"]}
    for idx, a in enumerate(ai.get("assumptions", [])[:3], 1):
        text = _norm(a)
        if text and text.lower() not in existing_assumptions:
            result["assumptions"].append({
                "assumption_id": f"AI-ASM-{idx:03d}",
                "assumption": text,
                "basis": "AI planning recommendation",
                "status": "To Validate",
                "source_sow_ids": [],
            })
    result["metadata"]["ai_seed_used"] = True
    return result


def validate_and_normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return build_deterministic_plan("", "Project")
    keys = ["summary", "scope", "sow_items", "wbs", "activities", "milestones", "assumptions", "constraints", "gaps", "risks", "traceability", "metadata"]
    out = {k: deepcopy(plan.get(k)) for k in keys}
    for k in keys:
        if out[k] is None:
            out[k] = {} if k in {"summary", "scope", "metadata"} else []
    for a in out["activities"]:
        a.setdefault("dependency_ids", [])
        a.setdefault("source_sow_ids", [])
        a.setdefault("milestone", False)
        a.setdefault("planning_note", "PM review required.")
    return out


# Compatibility aliases used by older versions.
build_fallback_plan = build_deterministic_plan
