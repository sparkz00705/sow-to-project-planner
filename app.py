from __future__ import annotations

from datetime import datetime, timezone
import re

import pandas as pd
import requests
import streamlit as st

from ai import generate_ai_advice, get_groq_config
from db import create_project, init_db
from exporter import build_excel_workbook
from extract import extract_document
from planner import (
    build_deterministic_plan,
    merge_ai_advice,
    validate_and_normalize_plan,
)


st.set_page_config(
    page_title="SOW → Project Planner",
    page_icon="📋",
    layout="wide",
)


# -----------------------------------------------------------------------------
# Complex test SOW used during MVP / QA validation.
# This is the same end-to-end sample used for the Build SOW Project Plan tests:
# 40 weeks, 12 sites, ~2,500 users, 3 deployment waves, migration, integration,
# testing, training, hypercare, explicit milestones, risks, assumptions,
# constraints, acceptance criteria and SOW ambiguities.
# -----------------------------------------------------------------------------
COMPLEX_SAMPLE_SOW = """# Statement of Work (SOW)
## Enterprise Digital Operations Platform Implementation

SOW Reference: EDP-2026-017
Planned Duration: 40 weeks
Target Countries: India, United Kingdom, Germany, United States, Singapore
Target Users: Approximately 2,500 users across 12 sites

## 1. Purpose
The Client intends to implement a centralized Digital Operations Platform to replace multiple legacy processes currently managed through spreadsheets, email, shared drives, and three departmental applications.

## 2. Project Objectives
The project objectives are to implement a centralized enterprise platform for approximately 2,500 users, standardize operational workflows across 12 sites, migrate agreed historical data, integrate with ERP, identity management, email, collaboration and document-management environments, establish role-based access and segregation of duties, provide management dashboards and audit history, train users and support teams, complete formal testing and business acceptance, deploy in three production waves, and transition to business-as-usual support.

## 3. Scope
### Workstream 1 - Project Management and Governance
The Implementation Partner shall provide project management and implementation governance.
The project will establish project kickoff, governance structure, Steering Committee, weekly project reporting, RAID management, decision management, dependency management, financial tracking, schedule management, change control, and stakeholder communications.

### Workstream 2 - Discovery and Requirements
The Implementation Partner shall conduct stakeholder interviews, current-state process assessment, process inventory, requirements workshops, business requirements documentation, non-functional requirements, reporting requirements, security requirements, data requirements, integration requirements, requirements validation, and requirements sign-off.

### Workstream 3 - Future-State Process Design
The Implementation Partner shall design standardized future-state workflows, roles, approval matrices, exception handling, escalation rules, and notification rules.
A maximum of 15% of the current-state processes may require local variations.
Any variation above this threshold will require Steering Committee review.

### Workstream 4 - Solution Design and Configuration
The Implementation Partner shall complete solution architecture and configure Development, Test, Validation and Production environments.
The Implementation Partner shall configure workflows, business rules, user roles, permissions, notifications, dashboards, reports, and audit logging.

### Workstream 5 - ERP Integration
The new platform will exchange employee master data, organizational units, cost centers, supplier information, and selected transaction reference data with the Client ERP.
The integration will use REST APIs where available and secure file transfer where an API is not available.
The Client will provide API specifications and test credentials by Week 8.

### Workstream 6 - Identity and Access Management
The solution shall integrate with the Client enterprise identity provider.
The scope includes Single Sign-On, user provisioning, role mapping, group mapping, deprovisioning, access review support, and privileged administrator access.
Multi-factor authentication will be provided through the existing Client identity platform and is not part of the application implementation.

### Workstream 7 - Document Management
The solution will integrate with the Client existing document-management platform for metadata mapping, document upload and retrieval, version reference, permission enforcement, and document-link migration for agreed records.
Migration of document binaries is excluded from the base scope.

### Workstream 8 - Data Migration
The project will migrate up to seven years of historical data from Legacy Application A, Legacy Application B, departmental spreadsheets, and selected CSV extracts.
The migration approach will include source assessment, data profiling, data mapping, data cleansing, transformation rules, migration scripts, trial migration, reconciliation, business validation, and production migration.
The Client is responsible for ownership and approval of source-data cleansing rules.

### Workstream 9 - Testing and Quality
Testing will include test strategy, test planning, functional testing, System Integration Testing, regression testing, performance testing, security testing coordination, User Acceptance Testing, defect management, retesting, and test summary reporting.
The Implementation Partner will resolve Severity 1 and Severity 2 defects identified during testing before production deployment unless formally waived by the Client.
Severity 3 defects may be deferred subject to documented business approval.

### Workstream 10 - Training and Change Management
Training shall cover end users, power users, site administrators, global administrators, and service desk personnel.
Training materials will include user guides, quick reference guides, administrator guides, training presentations, and recorded demonstrations.
The Client will nominate site champions for each participating location.

### Workstream 11 - Deployment and Cutover
The production deployment will use three waves.
Wave 1: India and Singapore.
Wave 2: United Kingdom and Germany.
Wave 3: United States.
Each deployment wave will include cutover readiness assessment, final data migration, configuration verification, access validation, business smoke testing, production deployment, business confirmation, and hypercare initiation.
A minimum of five business days is required between production waves unless the Steering Committee approves an exception.

### Workstream 12 - Hypercare and Handover
The Implementation Partner will provide 30 calendar days of hypercare after the final production deployment.
Hypercare includes incident triage, defect support, configuration corrections, user support, daily issue review during the first two weeks, weekly issue review thereafter, knowledge transfer, operational documentation, and final handover.

## 4. Out of Scope
The following items are excluded unless approved through formal change control: replacement of the Client ERP; replacement of the Client identity-management platform; development of a new enterprise data warehouse; replacement of the corporate document-management system; mobile application development; custom functionality requiring more than 20 person-days per feature; historical data older than seven years unless approved; migration of unstructured personal working files; hardware procurement; network infrastructure upgrades; third-party license procurement; and ongoing production support after the 30-day hypercare period.

## 5. Major Deliverables
The following deliverables are required: Project Charter; Integrated Project Management Plan; Stakeholder Register; Governance Plan; RAID Log; Requirements Catalogue; Requirements Traceability Matrix; Current-State Process Catalogue; Future-State Process Design; Solution Design Document; Security and Access Design; Integration Design Specifications; Data Migration Strategy; Data Mapping Specifications; Data Cleansing Rules; Migration Reconciliation Report; configured Development, Test, Validation and Production environments; System Test Plan; SIT Results; Performance Test Results; UAT Plan; UAT Results; Defect Register; Training Plan; Training Materials; Cutover Plan; Go-Live Readiness Assessment; Production Deployment Report; Hypercare Report; Knowledge Transfer Package; Operational Support Documentation; Project Closure Report.

## 6. Major Milestones
Project Kickoff Week 1; Discovery Complete Week 5; Requirements Sign-off Week 8; Future-State Design Approved Week 11; Solution Design Approved Week 13; Configuration Complete Week 21; Integration Build Complete Week 23; Trial Data Migration Complete Week 24; SIT Complete Week 28; UAT Readiness Week 29; UAT Complete Week 32; Wave 1 Go-Live Week 34; Wave 2 Go-Live Week 36; Wave 3 Go-Live Week 38; Hypercare Complete Week 40.

## 7. Dependencies
Key dependencies include Client availability of business SMEs, availability of ERP API specifications, availability of integration test environments, identity-provider configuration, document-management APIs, source-data extracts, completion of data cleansing, requirements and design approvals, availability of test users, timely resolution of business defects, availability of site champions, infrastructure readiness, security review completion, and production change-window approval.
The Implementation Partner is not responsible for delays caused exclusively by Client or third-party dependency delays unless otherwise agreed.

## 8. Client Responsibilities
The Client shall provide executive sponsorship, business and technical SMEs, timely access to relevant systems, required environments and credentials, source data, requirements and design approvals, data-cleansing decisions, UAT resources, site champions, defect decisions, cutover approval, and operational support resources after handover.

## 9. Implementation Partner Responsibilities
The Implementation Partner shall provide project management, solution and functional resources, platform configuration, agreed integrations, migration utilities, documentation, testing coordination, training materials, cutover support, hypercare, and knowledge transfer.

## 10. Resources
Indicative Implementation Partner roles include Program/Project Manager, Business Analyst, Solution Architect, Technical Architect, Integration Lead, Data Migration Lead, Configuration Lead, Test Manager, Security Specialist, Training Lead, Change Management Lead, Deployment Lead, and Application Support Specialist.

## 11. Commercial Assumptions
The base implementation fee is USD 780,000.
The fee includes professional services within the agreed scope.
Third-party licenses, direct cloud infrastructure charges, travel unless explicitly included, major custom development outside the agreed scope, sites beyond 12, historical data beyond seven years, and major process redesign beyond the 15% local-variation threshold are excluded.

## 12. Schedule Assumptions
The 40-week schedule assumes Client SMEs are available at least 20 hours per week during requirements and UAT; source data is delivered by Week 10; ERP API specifications are available by Week 8; security review begins by Week 18; UAT users are confirmed by Week 26; and production change windows are approved at least 15 business days before deployment.

## 13. Acceptance Criteria
A deliverable is accepted when it has been provided, reviewed, comments addressed, and approved by the designated Client approver.
Production go-live requires critical functionality successfully tested, no open Severity 1 defects, Severity 2 defects resolved or formally accepted, UAT completed, required production access configured, production data migration completed and reconciled, cutover checklist completed, and business owner approval.

## 14. Risks and Constraints
Initial known risks include legacy data quality, undocumented legacy interfaces, ERP API delays, local process variation, UAT resource constraints, migration reconciliation issues, additional security controls, limited production windows, third-party system changes, and additional requirements during discovery.
The following ambiguities require clarification: the phrase “complete audit history” is not further defined; security testing coordination is included but ownership of the actual penetration test is not stated; performance testing has no numerical target; the SOW does not define exact migrated record volume; and business smoke testing has no entry/exit criteria.

## 15. Governance
Governance will include a weekly project team meeting, a biweekly Steering Committee, and a monthly Executive Review covering schedule, budget, major risks, decisions, scope changes, and benefits indicators.

## 16. Reporting
The Implementation Partner will provide a weekly status report containing overall project status, milestone status, schedule variance, budget status, RAID summary, decisions required, dependency status, change requests, workstream status, and planned activities for the following two weeks.

## 17. Change Control
Any requested change affecting scope, schedule, cost, resources, deliverables, interfaces, number of sites, data volume, or acceptance criteria shall be documented as a Change Request with business justification and impact assessment.

## 18. Definition of Done
The project will be considered complete when all agreed deliverables have been accepted, all three deployment waves are operational, required data migration has been completed and reconciled, required integrations are operational, UAT has been completed, knowledge transfer is complete, operational documentation has been delivered, hypercare is complete, open items have owners and target dates, and final project acceptance has been obtained."""


VISIT_COUNTER_URL = (
    "https://abacus.jasoncameron.dev/hit/"
    "sow-to-project-planner.streamlit.app/visits"
)


@st.cache_resource
def database():
    return init_db(get_secret("DATABASE_URL", ""))


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


def _coverage(plan: dict) -> float:
    meta = plan.get("metadata", {})
    return float(meta.get("traceability_coverage_percent", 0) or 0)


def _week_number(value: object) -> int | None:
    match = re.search(r"\bweek\s+(\d+)\b", str(value or ""), flags=re.I)
    return int(match.group(1)) if match else None


def _schedule_review(plan: dict) -> list[dict[str, object]]:
    """Compare every explicit SOW milestone with the dependency-driven activity plan.

    Leadership reporting must not create false unmapped milestones merely because
    the SOW uses a different wording from the generated activity. Matching priority:
    1) shared SOW source ID, 2) milestone-specific planning synonyms, 3) token overlap.
    """
    synonym_rules = {
        "project kickoff": ["kickoff", "charter"],
        "discovery complete": ["discovery", "current-state", "assessment"],
        "requirements sign-off": ["requirements", "requirement", "validate requirements", "approved requirements"],
        "requirements approved": ["requirements", "requirement", "validate requirements", "approved requirements"],
        "future-state design approved": ["future-state", "future state", "process design", "workflow", "approval rules"],
        "solution design approved": ["solution architecture", "solution design", "technical design", "architecture"],
        "configuration complete": ["configure", "configuration", "platform workflows", "roles", "reporting"],
        "integration build complete": ["integration", "erp", "enterprise-system", "sso", "identity"],
        "source data received": ["source data", "data extract", "data profiling", "historical data", "migration data"],
        "trial data migration complete": ["trial migration", "rehearsal", "migration"],
        "sit complete": ["system integration testing", "sit", "functional testing"],
        "uat readiness": ["test strategy", "test plan", "uat readiness", "readiness"],
        "uat complete": ["uat", "business acceptance", "uat sign-off", "acceptance"],
        "production go-live": ["production deployment", "go-live", "deploy", "cutover"],
        "wave 1 go-live": ["wave 1 production", "wave 1", "production deployment"],
        "wave 2 go-live": ["wave 2 production", "wave 2", "production deployment"],
        "wave 3 go-live": ["wave 3 production", "wave 3", "production deployment"],
        "hypercare complete": ["hypercare", "stabilize production", "post-go-live support", "stabilization"],
    }

    def norm(text: object) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()

    def terms_for(name: str) -> list[str]:
        n = norm(name)
        for label, terms in synonym_rules.items():
            if label in n:
                return terms
        # Generic normalization for names such as "UAT Approval" or
        # "Production Deployment" that are not exact canonical labels.
        terms = [t for t in n.split() if len(t) > 2]
        return terms

    activities = plan.get("activities", []) or []
    explicit_milestones = [
        m for m in (plan.get("milestones", []) or [])
        if m.get("source") == "Explicit SOW milestone"
    ]

    rows: list[dict[str, object]] = []
    for milestone in explicit_milestones:
        target = _week_number(milestone.get("target"))
        milestone_name = str(milestone.get("name", "")).strip()
        source_ids = set(milestone.get("source_sow_ids", []) or [])
        if target is None:
            rows.append({
                "Milestone": milestone_name,
                "SOW target": milestone.get("target", "—"),
                "Planned finish": "—",
                "Variance (weeks)": None,
                "Status": "Unmapped",
                "Match basis": "No explicit week target",
            })
            continue

        name_lower = norm(milestone_name)
        preferred_terms = [norm(t) for t in terms_for(milestone_name) if norm(t)]

        scored: list[tuple[int, int, dict]] = []
        for activity in activities:
            activity_name = norm(activity.get("activity_name", ""))
            deliverable = norm(activity.get("deliverable", ""))
            phase = norm(activity.get("phase", ""))
            activity_source_ids = set(activity.get("source_sow_ids", []) or [])
            searchable = f"{activity_name} {deliverable} {phase}".strip()

            source_match = bool(source_ids & activity_source_ids)
            semantic_hits = sum(1 for term in preferred_terms if term and term in searchable)
            token_overlap = len(set(name_lower.split()) & set(searchable.split()))

            # A shared source ID alone is not enough: a single "Major Milestones"
            # SOW sentence can be the source for several different activities.
            # Require at least one semantic/token link before using source evidence.
            if source_match and semantic_hits:
                score = 100 + semantic_hits * 10 + token_overlap
                basis_rank = 3
            elif semantic_hits:
                score = 50 + semantic_hits * 10 + token_overlap
                basis_rank = 2
            elif token_overlap >= 1:
                score = 10 + token_overlap
                basis_rank = 1
            else:
                continue
            scored.append((score, basis_rank, activity))

        scored.sort(key=lambda x: (x[0], x[1], int(x[2].get("finish_week") or 0)), reverse=True)

        if not scored:
            rows.append({
                "Milestone": milestone_name,
                "SOW target": f"Week {target}",
                "Planned finish": "—",
                "Variance (weeks)": None,
                "Status": "Unmapped",
                "Match basis": "No confident activity link",
            })
            continue

        # Use the best evidence-backed activity. For a milestone such as
        # "Integration Build Complete", multiple integration activities can exist;
        # use the latest finish among activities that are tied to the same milestone
        # semantics/source evidence.
        best_score = scored[0][0]
        best_rank = scored[0][1]
        selected = [item[2] for item in scored if item[0] >= best_score - (10 if best_rank >= 2 else 0)]
        planned_finish = max(int(a.get("finish_week") or 0) for a in selected)
        variance = planned_finish - target
        match_basis = {
            3: "Shared SOW source ID",
            2: "Planning-language match",
            1: "Token match",
        }[best_rank]
        rows.append({
            "Milestone": milestone_name,
            "SOW target": f"Week {target}",
            "Planned finish": f"Week {planned_finish}" if planned_finish else "—",
            "Variance (weeks)": variance,
            "Status": (
                "Review"
                if variance > 1
                else "Aligned"
                if variance <= 0
                else "Watch"
            ),
            "Match basis": match_basis,
        })
    return rows


def _register_breakdown(rows: list[dict], kind: str) -> dict[str, int]:
    """Separate deterministic/SOW-linked register rows from AI-added review rows."""
    total = len(rows)
    ai = 0
    for row in rows:
        source_ids = row.get("source_sow_ids") or []
        category = str(row.get("category", "")).strip().lower()
        basis = str(row.get("basis", "")).strip().lower()
        identifier = str(
            row.get(f"{kind}_id", row.get("gap_id", row.get("risk_id", row.get("assumption_id", ""))))
        ).upper()
        if identifier.startswith("AI-") or category == "ai review" or basis == "ai planning recommendation" or not source_ids:
            ai += 1
    return {"total": total, "sow_or_plan": total - ai, "ai": ai}


def _risk_profile(rows: list[dict]) -> dict[str, int]:
    """Return evidence-based risk counts without implying an unsupported high-risk rating."""
    total = len(rows)
    medium_medium = 0
    other = 0
    for row in rows:
        impact = str(row.get("impact", "")).strip().lower()
        probability = str(row.get("probability", "")).strip().lower()
        if impact == "medium" and probability == "medium":
            medium_medium += 1
        else:
            other += 1
    return {"total": total, "medium_medium": medium_medium, "other": other}

def _show_df(
    rows: list[dict],
    *,
    empty_message: str,
    columns: list[str] | None = None,
    key: str | None = None,
) -> None:
    df = pd.DataFrame(rows)
    if df.empty:
        st.info(empty_message)
        return
    if columns:
        visible = [c for c in columns if c in df.columns]
        df = df[visible]
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        key=key,
    )


def _first_value(row: dict, names: list[str], default: str = "") -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).strip().lower() not in {"nan", "none"}:
            return str(value).strip()
    return default


def _management_action(text_value: str, kind: str) -> str:
    text_value = text_value.lower()
    if any(term in text_value for term in ["clarif", "ambigu", "not defined", "undefined"]):
        return "Confirm scope, owner and acceptance criteria before baseline."
    if any(term in text_value for term in ["data", "migration", "reconciliation", "cleansing"]):
        return "Baseline data ownership, quality checks, reconciliation rules and decision dates."
    if any(term in text_value for term in ["api", "integration", "interface", "identity"]):
        return "Confirm external dependency, technical owner, readiness date and fallback path."
    if any(term in text_value for term in ["uat", "testing", "test", "defect"]):
        return "Confirm test entry/exit criteria, business capacity and defect decision path."
    if any(term in text_value for term in ["security", "penetration", "access"]):
        return "Confirm control ownership, evidence requirements and approval date."
    if kind == "risk":
        return "Assign an accountable owner, trigger, mitigation and review date."
    return "Assign an owner and target date, then close through the project decision log."


def _management_rows(rows: list[dict], kind: str) -> list[dict]:
    output: list[dict] = []
    for index, row in enumerate(rows, start=1):
        description = _first_value(
            row,
            [
                "description",
                "gap",
                "risk",
                "risk_description",
                "issue",
                "name",
                "title",
                "statement",
                "text",
            ],
            default=f"{kind.title()} {index}",
        )
        severity = _first_value(
            row,
            ["severity", "priority", "rating", "risk_level", "impact"],
            default="Review",
        )
        owner = _first_value(
            row,
            ["owner", "owner_role", "responsible", "assigned_to"],
            default="Assign in PM review",
        )
        existing_action = _first_value(
            row,
            ["action", "mitigation", "response", "next_action", "recommendation", "resolution"],
        )
        due = _first_value(
            row,
            ["due", "due_date", "target_date", "target_week", "decision_date"],
            default="Set in PM review",
        )
        status = _first_value(
            row,
            ["status", "state", "disposition"],
            default="Open for review",
        )
        output.append(
            {
                "ID": _first_value(row, ["id", "gap_id", "risk_id", "item_id"], default=f"{kind[:1].upper()}{index:02d}"),
                "Item": description,
                "Severity / Priority": severity,
                "PM action": existing_action or _management_action(description, kind),
                "Owner": owner,
                "Target / Due": due,
                "Status": status,
            }
        )
    return output


def _decision_rows(schedule_rows: list[dict], gaps: list[dict], risks: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for row in schedule_rows:
        if row.get("Status") in {"Review", "Watch"}:
            variance = row.get("Variance (weeks)", 0)
            action = (
                "Re-sequence dependencies or obtain an approved milestone exception."
                if row.get("Status") == "Review"
                else "Confirm dependency dates and monitor before baseline."
            )
            rows.append(
                {
                    "Decision area": "Schedule",
                    "Decision / issue": row.get("Milestone", ""),
                    "Evidence": f"SOW {row.get('SOW target', '—')} vs planned {row.get('Planned finish', '—')} ({variance:+g} weeks)",
                    "PM action": action,
                }
            )

    for item in _management_rows(gaps, "gap")[:4]:
        rows.append(
            {
                "Decision area": "Gap",
                "Decision / issue": item["Item"],
                "Evidence": item["Severity / Priority"],
                "PM action": item["PM action"],
            }
        )

    for item in _management_rows(risks, "risk")[:4]:
        rows.append(
            {
                "Decision area": "Risk",
                "Decision / issue": item["Item"],
                "Evidence": item["Severity / Priority"],
                "PM action": item["PM action"],
            }
        )
    return rows[:10]


def _leader_status(
    schedule_rows: list[dict],
    gaps: list[dict],
    risks: list[dict],
    coverage: float,
    sow_duration_week: int | None,
    planned_finish_week: int | None,
) -> tuple[str, str]:
    reviews = sum(1 for row in schedule_rows if row.get("Status") == "Review")
    unmapped = sum(1 for row in schedule_rows if row.get("Status") == "Unmapped")
    gap_breakdown = _register_breakdown(gaps, "gap")
    risk_breakdown = _register_breakdown(risks, "risk")
    high_gaps = sum(
        1
        for row in gaps
        if _first_value(row, ["severity", "priority", "rating"], "").lower()
        in {"high", "critical", "severe"}
    )
    finish_variance = (
        planned_finish_week - sow_duration_week
        if planned_finish_week is not None and sow_duration_week is not None
        else None
    )

    details = [
        f"{reviews} schedule exception(s)",
        f"{unmapped} unmapped milestone(s)",
        f"{high_gaps} high-severity gap(s)",
        f"{risk_breakdown['total']} risk(s) identified",
    ]
    if finish_variance is not None and finish_variance > 0:
        details.append(
            f"dependency-driven finish is {finish_variance} week(s) beyond the {sow_duration_week}-week SOW duration"
        )

    if reviews or unmapped or high_gaps or risk_breakdown["total"] or (finish_variance or 0) > 0:
        return "PM review required", ", ".join(details) + "."
    if coverage >= 100:
        return "Ready for PM review", "Executable traceability is complete and no schedule exception is currently surfaced."
    return "PM review required", f"Executable traceability coverage is {coverage:g}%; review uncovered scope before baseline."


def show_plan(plan: dict) -> None:
    summary = plan.get("summary", {}) or {}
    sow_items = plan.get("sow_items", []) or []
    activities = plan.get("activities", []) or []
    milestones = plan.get("milestones", []) or []
    traceability = plan.get("traceability", []) or []
    gaps = plan.get("gaps", []) or []
    risks = plan.get("risks", []) or []
    assumptions = plan.get("assumptions", []) or []
    constraints = plan.get("constraints", []) or []
    wbs = plan.get("wbs", []) or []
    metadata = plan.get("metadata", {}) or {}

    st.subheader("Leadership & PM Review")

    # Leadership metrics are deliberately split between SOW/deterministic data
    # and AI-added review suggestions. This prevents AI additions from looking
    # like contractual SOW facts.
    schedule_rows = _schedule_review(plan)
    sow_milestones = [m for m in milestones if m.get("source") == "Explicit SOW milestone"]
    gap_breakdown = _register_breakdown(gaps, "gap")
    risk_breakdown = _register_breakdown(risks, "risk")
    assumption_breakdown = _register_breakdown(assumptions, "assumption")
    unmapped_count = sum(1 for row in schedule_rows if row.get("Status") == "Unmapped")
    review_count = sum(1 for row in schedule_rows if row.get("Status") == "Review")
    watch_count = sum(1 for row in schedule_rows if row.get("Status") == "Watch")
    aligned_count = sum(1 for row in schedule_rows if row.get("Status") == "Aligned")
    high_gaps = sum(
        1
        for row in gaps
        if _first_value(row, ["severity", "priority", "rating"], "").lower()
        in {"high", "critical", "severe"}
    )
    planned_finish_week = metadata.get("planned_finish_week")
    sow_duration_week = metadata.get("latest_explicit_target_week")
    try:
        planned_finish_week = int(planned_finish_week) if planned_finish_week not in (None, "") else None
    except (TypeError, ValueError):
        planned_finish_week = None
    try:
        sow_duration_week = int(sow_duration_week) if sow_duration_week not in (None, "") else None
    except (TypeError, ValueError):
        sow_duration_week = None
    finish_variance = (
        planned_finish_week - sow_duration_week
        if planned_finish_week is not None and sow_duration_week is not None
        else None
    )

    leader_status, leader_detail = _leader_status(
        schedule_rows,
        gaps,
        risks,
        _coverage(plan),
        sow_duration_week,
        planned_finish_week,
    )
    st.info(
        f"**Plan status: {leader_status}** · {leader_detail} "
        "This is a decision-support view; PM / sponsor approval is still required before baseline."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("SOW items", len(sow_items))
    c2.metric("Activities", len(activities))
    c3.metric("SOW milestones", len(sow_milestones))
    c4.metric("Gaps", gap_breakdown["total"])
    c5.metric("Executable coverage", f"{_coverage(plan):g}%")

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Risks", risk_breakdown["total"])
    c7.metric("Assumptions", assumption_breakdown["total"])
    c8.metric("Constraints", len(constraints))
    c9.metric(
        "Dependency-driven finish",
        f"Week {planned_finish_week}" if planned_finish_week is not None else "—",
        delta=(f"+{finish_variance} week" if finish_variance == 1 else f"+{finish_variance} weeks" if finish_variance and finish_variance > 1 else None),
        delta_color="inverse" if finish_variance and finish_variance > 0 else "normal",
    )

    st.caption(
        f"Register totals after AI review: {len(gaps)} gaps ({gap_breakdown['sow_or_plan']} SOW/plan + {gap_breakdown['ai']} AI), "
        f"{len(risks)} risks ({risk_breakdown['sow_or_plan']} SOW/plan + {risk_breakdown['ai']} AI), "
        f"{len(assumptions)} assumptions ({assumption_breakdown['sow_or_plan']} SOW + {assumption_breakdown['ai']} AI)."
    )
    st.caption(
        "Leadership totals include AI review additions. The source breakdown above is informational; AI rows are not contractual SOW commitments."
    )

    if len(schedule_rows) != len(sow_milestones):
        st.error(
            f"Schedule-fit reconciliation error: {len(schedule_rows)} rows returned for {len(sow_milestones)} explicit SOW milestones."
        )

    if unmapped_count:
        st.warning(
            f"{unmapped_count} of {len(sow_milestones)} explicit SOW milestones could not be linked confidently to a planning activity. "
            "Review the unmapped milestone before baseline."
        )

    st.divider()

    st.subheader("Executive brief")
    st.write(summary.get("description") or "No summary returned.")
    eb1, eb2, eb3, eb4, eb5 = st.columns(5)
    eb1.metric("SOW items", len(sow_items))
    eb2.metric("Executable coverage", f"{_coverage(plan):g}%")
    eb3.metric("Schedule exceptions", review_count)
    eb4.metric("Watch items", watch_count)
    eb5.metric("High gaps", high_gaps)
    st.caption(
        f"Risks identified: {len(risks)} · SOW duration target: "
        f"{f'Week {sow_duration_week}' if sow_duration_week is not None else '—'} · "
        f"Dependency-driven finish: {f'Week {planned_finish_week}' if planned_finish_week is not None else '—'}"
        + (f" · Planning variance: +{finish_variance} week(s)" if finish_variance and finish_variance > 0 else "")
        + f" · Project type: {summary.get('project_type', 'Unknown')} · Planning confidence: {summary.get('confidence', 'N/A')} · Planning engine: {metadata.get('engine', 'Unknown')}"
    )
    st.caption(
        "Coverage represents executable SOW items mapped to planning activities. "
        "It does not mean every narrative, governance, commercial or out-of-scope statement is executable."
    )

    decision_rows = _decision_rows(schedule_rows, gaps, risks)
    if decision_rows:
        st.subheader("PM / sponsor attention")
        st.dataframe(
            pd.DataFrame(decision_rows),
            use_container_width=True,
            hide_index=True,
            key="pm_sponsor_attention_table",
        )
        st.caption(
            "These items are surfaced from explicit SOW targets, deterministic planning checks and AI review. "
            "Where the SOW does not provide an owner or due date, the application marks it for PM assignment rather than inventing one."
        )

    # PM-level schedule fit review. Every explicit SOW milestone is shown,
    # including unmapped milestones, so the leadership math reconciles exactly.
    if schedule_rows:
        st.subheader("Schedule fit review")
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("SOW milestones", len(sow_milestones))
        sc2.metric("Aligned", aligned_count)
        sc3.metric("Watch", watch_count)
        sc4.metric("Exceptions", review_count)
        sc5.metric("Unmapped", unmapped_count)
        st.caption(
            "Each explicit SOW milestone is compared with the finish of its linked planning activity. "
            "'Review' means more than one week late; 'Watch' means one week late; 'Unmapped' means no confident activity link. "
            "This is a planning check, not a revised contractual milestone."
        )
        st.dataframe(
            pd.DataFrame(schedule_rows),
            use_container_width=True,
            hide_index=True,
            key="schedule_fit_review_table",
        )
        if review_count:
            pressure_points = ", ".join(
                str(row.get("Milestone", ""))
                for row in schedule_rows
                if row.get("Status") == "Review"
            )
            st.warning(
                "Schedule-fit exceptions require PM review before baseline: "
                f"{pressure_points}."
            )
        if finish_variance is not None and finish_variance > 0:
            st.warning(
                f"The dependency-driven plan finishes around Week {planned_finish_week}, "
                f"which is {finish_variance} week(s) beyond the latest explicit SOW target of Week {sow_duration_week}."
            )

    tabs = st.tabs(
        [
            "Project Plan",
            "WBS",
            "Milestones",
            "SOW Items",
            "Traceability",
            "Gaps",
            "Risks",
            "Assumptions",
            "Raw JSON",
        ]
    )

    with tabs[0]:
        st.caption("Executable activities derived from the SOW; PM review remains required.")
        df = pd.DataFrame(activities)
        if not df.empty:
            cols = [
                "wbs_id",
                "activity_id",
                "activity_name",
                "phase",
                "duration_days",
                "dependency_ids",
                "owner_role",
                "deliverable",
                "milestone",
                "source_sow_ids",
                "planning_note",
                "start_week",
                "finish_week",
            ]
            visible = [c for c in cols if c in df.columns]
            st.dataframe(
                df[visible],
                use_container_width=True,
                hide_index=True,
                key="project_plan_table",
            )
        else:
            st.info("No executable activities were generated.")

    with tabs[1]:
        _show_df(
            wbs,
            empty_message="No WBS phases were generated.",
            columns=["wbs_id", "phase", "objective", "parent_wbs_id"],
            key="wbs_table",
        )

    with tabs[2]:
        st.caption("Explicit SOW milestones are kept distinct from planning proposals.")
        _show_df(
            milestones,
            empty_message="No milestones were identified.",
            columns=["milestone_id", "name", "target", "source", "source_sow_ids"],
            key="milestones_table",
        )

    with tabs[3]:
        sdf = pd.DataFrame(sow_items)
        if sdf.empty:
            st.info("No SOW items were extracted.")
        else:
            f1, f2, f3 = st.columns(3)
            item_types = ["All"] + sorted(
                [str(v) for v in sdf["type"].dropna().unique().tolist()]
            ) if "type" in sdf.columns else ["All"]
            selected_type = f1.selectbox(
                "Type",
                item_types,
                key="sow_items_type_filter",
            )
            selected_exec = f2.selectbox(
                "Executable",
                ["All", "Executable", "Controlled / non-executable"],
                key="sow_items_exec_filter",
            )
            selected_priority = f3.selectbox(
                "Priority",
                ["All"] + sorted(
                    [str(v) for v in sdf["priority"].dropna().unique().tolist()]
                )
                if "priority" in sdf.columns
                else ["All"],
                key="sow_items_priority_filter",
            )
            filtered = sdf.copy()
            if selected_type != "All" and "type" in filtered:
                filtered = filtered[filtered["type"] == selected_type]
            if selected_exec == "Executable" and "executable" in filtered:
                filtered = filtered[filtered["executable"] == True]  # noqa: E712
            elif selected_exec == "Controlled / non-executable" and "executable" in filtered:
                filtered = filtered[filtered["executable"] == False]  # noqa: E712
            if selected_priority != "All" and "priority" in filtered:
                filtered = filtered[filtered["priority"] == selected_priority]
            st.caption(f"Showing {len(filtered)} of {len(sdf)} SOW items.")
            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True,
                key="sow_items_table",
            )

    with tabs[4]:
        tdf = pd.DataFrame(traceability)
        if tdf.empty:
            st.info("No traceability records were generated.")
        else:
            mapped = int((tdf["status"] == "Mapped").sum()) if "status" in tdf else 0
            controlled = int(
                (tdf["status"] != "Mapped").sum()
            ) if "status" in tdf else 0
            tc1, tc2, tc3 = st.columns(3)
            tc1.metric("Traceability rows", len(tdf))
            tc2.metric("Mapped", mapped)
            tc3.metric("Controlled / review", controlled)
            st.dataframe(
                tdf,
                use_container_width=True,
                hide_index=True,
                key="traceability_table",
            )
            st.caption(
                f"{controlled} non-executable or controlled items remain outside the executable schedule."
            )

    with tabs[5]:
        gdf = pd.DataFrame(gaps)
        if gdf.empty:
            st.success("No planning gaps were identified.")
        else:
            high_count = int((gdf["severity"].astype(str).str.lower().isin(["high", "critical", "severe"])).sum()) if "severity" in gdf else 0
            st.metric("High-severity gaps", high_count)
            st.dataframe(
                pd.DataFrame(_management_rows(gaps, "gap")),
                use_container_width=True,
                hide_index=True,
                key="gap_management_table",
            )
            with st.expander("View extracted gap detail"):
                st.dataframe(gdf, use_container_width=True, hide_index=True, key="gaps_detail_table")

    with tabs[6]:
        rdf = pd.DataFrame(risks)
        if rdf.empty:
            st.success("No planning risks were identified.")
        else:
            high_count = int((rdf["severity"].astype(str).str.lower().isin(["high", "critical", "severe"])).sum()) if "severity" in rdf else 0
            st.metric("Risks", len(rdf))
            st.dataframe(
                pd.DataFrame(_management_rows(risks, "risk")),
                use_container_width=True,
                hide_index=True,
                key="risk_management_table",
            )
            with st.expander("View extracted risk detail"):
                st.dataframe(rdf, use_container_width=True, hide_index=True, key="risks_detail_table")

    with tabs[7]:
        adf = pd.DataFrame(assumptions)
        if not adf.empty:
            st.dataframe(
                adf,
                use_container_width=True,
                hide_index=True,
                key="assumptions_table",
            )
        else:
            st.info("No explicit assumptions were extracted.")
        cdf = pd.DataFrame(constraints)
        if not cdf.empty:
            st.markdown("#### Constraints")
            st.dataframe(
                cdf,
                use_container_width=True,
                hide_index=True,
                key="constraints_table",
            )
        else:
            st.info("No planning constraints were identified.")

    with tabs[8]:
        with st.expander("Show raw machine-readable plan"):
            st.json(plan)
        st.caption(
            "Raw JSON is retained for audit/debugging and integrations; leaders should use the Executive brief and PM / sponsor attention view."
        )

    st.divider()
    st.subheader("Management export")
    st.caption(
        "The Excel export contains the detailed project-plan data for PM review, governance and downstream reporting."
    )
    excel_bytes = build_excel_workbook(plan)
    st.download_button(
        "⬇️ Download Project Plan (Excel)",
        data=excel_bytes,
        file_name="sow_project_plan_management_pack.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_project_plan_excel",
        on_click="ignore",
    )


def record_external_visit() -> int | None:
    """Increment a lightweight external visit counter. Returns None on failure."""
    response = requests.get(VISIT_COUNTER_URL, timeout=5)
    response.raise_for_status()
    payload = response.json()
    value = payload.get("value")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def show_footer(visit_count: int | None) -> None:
    st.markdown("---")
    st.markdown("**Projects**")
    st.markdown(
        "[SOW → Project Planner](#) · "
        "[GxP AI Readiness & Governance Assessment](https://gxp-ai-readiness-governance.streamlit.app/) · "
        "[AI Risk & Issue Dashboard](https://ai-risk-issue-dashboard.streamlit.app/)"
    )
    st.markdown("© 2026 Sriram Sampath. All rights reserved.")
    st.markdown("[LinkedIn](https://www.linkedin.com/in/sriramsampath81/)")
    if visit_count is None:
        # Never show 0 when the counter is unavailable.
        st.caption("👁️ Visits: —")
    else:
        st.caption(f"👁️ Visits: {visit_count}")


def main() -> None:
    st.title("📋 SOW → Project Planner")
    st.caption(
        "AI-assisted, domain-agnostic project planning. "
        "The AI proposes; the Project Manager decides."
    )

    # Wake-up traffic must not be counted as a human page visit.
    if st.query_params.get("bot") == "wake":
        st.success("App is awake.")
        st.stop()

    db = database()

    # Count once per browser session; wake-up bot requests are excluded above.
    if "visit_recorded" not in st.session_state:
        try:
            st.session_state["visit_count"] = record_external_visit()
        except Exception:
            st.session_state["visit_count"] = None
        st.session_state["visit_recorded"] = True

    cfg = get_groq_config(
        api_key=get_secret("GROQ_API_KEY", ""),
        model=get_secret("GROQ_MODEL", "qwen/qwen3.8-27b"),
        base_url=get_secret("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )

    with st.sidebar:
        st.markdown("### Test / Sample")
        if st.button(
            "🧪 Load Complex Sample SOW",
            use_container_width=True,
            key="load_complex_sample",
        ):
            # These keys belong to the widgets created immediately below and are
            # intentionally populated before those widgets are instantiated.
            st.session_state["project_name_input"] = (
                "Enterprise Digital Operations Platform"
            )
            st.session_state["sow_text_input"] = COMPLEX_SAMPLE_SOW
            st.session_state.pop("plan", None)
            st.success("Complex sample SOW loaded.")

    project_name = st.text_input(
        "Project name",
        placeholder="e.g. CRM Implementation",
        key="project_name_input",
    )

    sow_text = st.text_area(
        "Statement of Work",
        height=320,
        placeholder="Upload an SOW below or paste the SOW here...",
        key="sow_text_input",
    )

    uploaded = st.file_uploader(
        "Upload SOW",
        type=["pdf", "docx", "xlsx", "xlsm", "txt", "md"],
        key="sow_file_uploader",
    )

    extracted_text = sow_text.strip()
    if uploaded is not None:
        try:
            extracted_text = extract_document(uploaded.getvalue(), uploaded.name)
            st.info(
                f"Extracted {len(extracted_text):,} characters from `{uploaded.name}`."
            )
            with st.expander("Preview extracted text"):
                st.text(extracted_text[:12000])
        except Exception as exc:
            st.error(f"Document extraction failed: {exc}")

    generate = st.button(
        "🚀 Generate Project Plan",
        type="primary",
        use_container_width=True,
        key="generate_project_plan",
    )

    if generate:
        if not project_name.strip():
            st.error("Enter a project name.")
            st.stop()
        if not extracted_text.strip():
            st.error("Upload an SOW or paste the SOW text.")
            st.stop()

        with st.spinner("Analyzing the SOW and building the project plan..."):
            plan = build_deterministic_plan(
                extracted_text,
                project_name.strip(),
            )
            engine = "Built-in planning engine"

            if cfg.api_key:
                try:
                    ai_advice = generate_ai_advice(
                        plan["sow_items"],
                        project_name.strip(),
                        cfg,
                    )
                    plan = merge_ai_advice(plan, ai_advice)
                    plan["metadata"]["engine"] = "groq_qwen38_hybrid"
                    plan["metadata"]["engine_version"] = (
                        "planner-v4 + groq-qwen38-advice"
                    )
                    engine = "Groq AI planner + planning engine"
                except Exception as exc:
                    # Retain the deterministic plan if AI advice fails.
                    plan["metadata"]["ai_error"] = str(exc)[:1000]
                    st.warning(
                        "AI assistance was unavailable for this run. "
                        "A full deterministic project plan was generated instead."
                    )

            plan = validate_and_normalize_plan(plan)

            create_project(
                db,
                name=project_name.strip(),
                source_name=uploaded.name if uploaded else "Pasted SOW",
                plan=plan,
                engine_name=engine,
            )

            st.session_state["plan"] = plan
            st.session_state["generated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

        st.success(f"Project plan generated for PM review. {engine}")

    # IMPORTANT: render the project plan exactly once per Streamlit run.
    # The previous version rendered show_plan() both before and after generation,
    # which caused DuplicateElementId on the download button.
    if "plan" in st.session_state:
        show_plan(st.session_state["plan"])

    # IMPORTANT: default to None, not 0, so a failed counter does not appear as a
    # misleading zero.
    show_footer(st.session_state.get("visit_count"))


if __name__ == "__main__":
    main()
