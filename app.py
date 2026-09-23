from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ai import generate_plan_with_groq, get_groq_config
from db import create_project, init_db, list_projects, load_project, record_visit
from exporter import build_excel_workbook
from extract import extract_document
from planner import build_fallback_plan, validate_and_normalize_plan

st.set_page_config(page_title="SOW → Project Planner", page_icon="📋", layout="wide")

SAMPLE_SOW = r'''
STATEMENT OF WORK (SOW)
Enterprise Digital Operations Platform Implementation
SOW Reference: EDP-2026-017 | Planned Duration: 40 weeks | Users: ~2,500 | Sites: 12 across India, UK, Germany, US and Singapore
1. Purpose
The Client will implement a centralized Digital Operations Platform replacing multiple legacy processes managed through spreadsheets, email, shared drives and three departmental applications. The solution will standardize operational requests, document management, approvals, issue management, reporting, audit trails, notifications and management dashboards.
2. Objectives
Implement the platform for approximately 2,500 users; standardize workflows across 12 sites; migrate agreed historical data; integrate with ERP, identity management, email, collaboration and document-management environments; establish role-based access and segregation of duties; provide dashboards and reporting; enable audit history; train end users, power users, administrators and support teams; complete formal testing and business acceptance; deploy in three production waves and transition to business-as-usual support.
3. In Scope
Project management and governance; discovery and current-state assessment; future-state process design; requirements workshops; functional and technical design; platform and workflow configuration; role and permission configuration; notifications; dashboards and reports; data cleansing support; historical data migration; ERP integration; identity and SSO integration; email integration; document-management integration; collaboration notifications; system integration testing; performance testing; security testing coordination; UAT support; migration rehearsal; cutover planning; end-user and administrator training; production deployment; hypercare; knowledge transfer; operational handover.
4. Out of Scope
Replacement of the ERP or identity platform; new enterprise data warehouse; replacement of the corporate document-management system; mobile application development; custom functionality requiring more than 20 person-days per feature; data older than seven years unless approved; migration of unstructured personal working files; hardware procurement; network infrastructure upgrades; third-party license procurement; ongoing production support after the 30-day hypercare period.
5. Geography and Functions
India 4 sites, UK 2, Germany 2, US 3 and Singapore 1. Participating functions: Operations, Quality, Finance, Procurement, IT, Human Resources and Corporate Services. Up to two additional sites may be added during the project subject to schedule and impact assessment.
6. Workstream A - Project Management and Governance
Establish project charter, governance structure and Steering Committee; maintain weekly status reports, RAID log, decisions, dependencies, financial tracking, schedule, change control and stakeholder communications.
7. Workstream B - Discovery and Requirements
Conduct stakeholder interviews, current-state assessment, process inventory, requirements workshops, business and non-functional requirements, reporting, security, data and integration requirements. Validate and obtain requirements sign-off.
8. Workstream C - Future-State Process Design
Design standardized future-state workflows, roles, approval matrices, exception handling, escalation and notification rules. A maximum of 15% of current-state processes may require local variations; variations above this threshold require Steering Committee review.
9. Workstream D - Solution Design and Configuration
Create solution architecture and configure Development, Test, Validation and Production environments. Configure workflows, business rules, roles, permissions, notifications, dashboards, reports and audit logging.
10. Workstream E - ERP Integration
Exchange employee master data, organizational units, cost centers, supplier information and selected transaction reference data with the ERP. Use REST APIs where available and secure file transfer where an API is unavailable. The Client will provide API specifications and test credentials by Week 8.
11. Workstream F - Identity and Access Management
Implement SSO, user provisioning, role and group mapping, deprovisioning, access review support and privileged administrator access. Multi-factor authentication remains with the existing identity platform.
12. Workstream G - Document Management
Integrate with the existing document-management platform for metadata mapping, document upload and retrieval, version reference, permission enforcement and document-link migration for agreed records. Migration of document binaries is excluded.
13. Workstream H - Data Migration
Migrate up to seven years of historical data from Legacy Application A, Legacy Application B, departmental spreadsheets and selected CSV extracts. Perform source assessment, profiling, mapping, cleansing, transformation, migration scripts, trial migration, reconciliation, business validation and production migration. The Client owns approval of source-data cleansing rules.
14. Workstream I - Testing and Quality
Create test strategy and execute functional testing, SIT, regression testing, performance testing, security testing coordination, UAT, defect management and retesting. Severity 1 and Severity 2 defects must be resolved before production unless formally waived. Severity 3 defects may be deferred with business approval.
15. Workstream J - Training and Change Management
Train end users, power users, site administrators, global administrators and service desk personnel. Deliver user guides, quick reference guides, administrator guides, training presentations and recorded demonstrations. The Client will nominate site champions.
16. Workstream K - Deployment and Cutover
Deploy in three waves: Wave 1 India and Singapore; Wave 2 UK and Germany; Wave 3 US. Each wave requires readiness assessment, final data migration, configuration verification, access validation, business smoke testing, production deployment, business confirmation and hypercare initiation. Minimum five business days are required between waves unless the Steering Committee approves an exception.
17. Workstream L - Hypercare and Handover
Provide 30 calendar days of hypercare after the final production deployment including incident triage, defect support, configuration corrections, user support, daily issue review for two weeks, weekly review thereafter, knowledge transfer and final operational handover.
18. Major Deliverables
Project Charter; Integrated Project Management Plan; Stakeholder Register; Governance Plan; RAID Log; Requirements Catalogue; Requirements Traceability Matrix; Current-State Process Catalogue; Future-State Process Design; Solution Design Document; Security and Access Design; Integration Design Specifications; Data Migration Strategy; Data Mapping Specifications; Data Cleansing Rules; Migration Reconciliation Report; configured Development, Test, Validation and Production environments; System Test Plan; SIT Results; Performance Test Results; UAT Plan; UAT Results; Defect Register; Training Plan; Training Materials; Cutover Plan; Go-Live Readiness Assessment; Production Deployment Report; Hypercare Report; Knowledge Transfer Package; Operational Support Documentation; Project Closure Report.
19. Milestones
Project Kickoff Week 1; Discovery Complete Week 5; Requirements Sign-off Week 8; Future-State Design Approved Week 11; Solution Design Approved Week 13; Configuration Complete Week 21; Integration Build Complete Week 23; Trial Data Migration Complete Week 24; SIT Complete Week 28; UAT Readiness Week 29; UAT Complete Week 32; Wave 1 Go-Live Week 34; Wave 2 Go-Live Week 36; Wave 3 Go-Live Week 38; Hypercare Complete Week 40.
20. Dependencies
Client SME availability; ERP API specifications; integration test environments; identity-provider configuration; document-management APIs; source-data extracts; data cleansing; requirements and design approvals; test users; timely defect resolution; site champions; infrastructure readiness; security review; production change-window approval. The implementation partner is not responsible for delays caused exclusively by Client or third-party dependencies.
21. Responsibilities
Client: executive sponsorship, SMEs, access, environments, credentials, source data, approvals, cleansing decisions, UAT resources, site champions, defect decisions, cutover approval and operational resources after handover. Implementation Partner: project management, solution and functional resources, platform configuration, integrations, migration utilities, documentation, testing coordination, training materials, cutover support, hypercare and knowledge transfer.
22. Commercial Assumptions
Base implementation fee USD 780,000. Excludes third-party licenses, direct cloud infrastructure charges, travel unless included, major custom development outside scope, sites beyond 12, data beyond seven years and major process redesign beyond the 15% local-variation threshold.
23. Schedule Assumptions
Client SMEs available at least 20 hours/week during requirements and UAT; source data delivered by Week 10; ERP API specifications by Week 8; security review starts by Week 18; UAT users confirmed by Week 26; production change windows approved at least 15 business days before deployment.
24. Acceptance Criteria
Deliverables are accepted when provided, reviewed and approved by the designated Client approver. Go-live requires critical functionality tested, no open Severity 1 defects, Severity 2 defects resolved or formally accepted, UAT completed, production access configured, production data migrated and reconciled, cutover checklist completed and business owner approval. Final acceptance occurs after all three waves, hypercare, documentation, knowledge transfer and transfer of outstanding actions.
25. Risks and Constraints
Legacy data quality; undocumented legacy interfaces; ERP API delays; local process variation; UAT resource constraints; migration reconciliation issues; additional security controls; limited production windows; third-party system changes; additional requirements during discovery.
26. Deliberate Clarifications
The Client may add up to two sites subject to schedule and impact assessment. The phrase “complete audit history” is not further defined. Security testing coordination is included but ownership of the actual penetration test is not stated. Performance testing has no numerical target. The SOW does not define exact migrated record volume. The 15% local-variation threshold has no measurement method. Severity 2 acceptance has no numerical limit. Business smoke testing has no entry/exit criteria.
'''.strip()


@st.cache_resource
def database():
    return init_db(get_secret("DATABASE_URL", ""))


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


def _coverage(plan: dict) -> tuple[int, int, float]:
    sow_items = plan.get("sow_items", [])
    executable = [x for x in sow_items if x.get("executable")]
    trace = plan.get("traceability", [])
    mapped = sum(1 for x in trace if x.get("status") == "Mapped")
    pct = round(mapped / len(executable) * 100, 1) if executable else 100.0
    return mapped, len(executable), pct


def _df(items: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(items) if items else pd.DataFrame([{"Info": "No records"}])


def show_plan(plan: dict) -> None:
    summary = plan.get("summary", {})
    sow_items = plan.get("sow_items", [])
    activities = plan.get("activities", [])
    milestones = plan.get("milestones", [])
    gaps = plan.get("gaps", [])
    risks = plan.get("risks", [])
    assumptions = plan.get("assumptions", [])
    constraints = plan.get("constraints", [])
    traceability = plan.get("traceability", [])
    mapped, executable_count, coverage = _coverage(plan)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("SOW items", len(sow_items))
    c2.metric("Activities", len(activities))
    c3.metric("Milestones", len(milestones))
    c4.metric("Gaps / Risks", len(gaps) + len(risks))
    c5.metric("Executable coverage", f"{coverage}%")

    st.divider()
    st.subheader("Project summary")
    st.write(summary.get("description") or "No summary returned.")
    st.caption(
        f"Project type: {summary.get('project_type', 'Unknown')} · "
        f"Planning confidence: {summary.get('confidence', 'N/A')} · "
        f"Mapped executable SOW items: {mapped}/{executable_count}"
    )

    tabs = st.tabs(["Project Plan", "SOW Items", "Traceability", "Gaps & Risks", "Assumptions", "Raw JSON"])

    with tabs[0]:
        if activities:
            df = pd.DataFrame(activities)
            cols = ["wbs_id", "activity_id", "activity_name", "phase", "duration_days", "dependency_ids", "owner_role", "deliverable", "milestone", "source_sow_ids", "planning_note"]
            visible = [c for c in cols if c in df.columns]
            st.dataframe(df[visible], use_container_width=True, hide_index=True)
        else:
            st.info("No executable activities were generated.")
        st.markdown("#### Milestones")
        st.dataframe(_df(milestones), use_container_width=True, hide_index=True)

    with tabs[1]:
        if sow_items:
            cols = ["sow_id", "section", "statement", "type", "category", "executable", "explicit", "priority"]
            sdf = pd.DataFrame(sow_items)
            visible = [c for c in cols if c in sdf.columns]
            st.dataframe(sdf[visible], use_container_width=True, hide_index=True)
        else:
            st.info("No SOW items were extracted.")

    with tabs[2]:
        if traceability:
            td = pd.DataFrame(traceability)
            st.dataframe(td, use_container_width=True, hide_index=True)
            unmapped = td[td.get("status", "") == "Unmapped"] if "status" in td.columns else pd.DataFrame()
            if not unmapped.empty:
                st.warning(f"{len(unmapped)} executable SOW item(s) need PM review.")
        else:
            st.info("No traceability records were generated.")

    with tabs[3]:
        st.markdown("#### Gaps")
        st.dataframe(_df(gaps), use_container_width=True, hide_index=True)
        st.markdown("#### Risks")
        st.dataframe(_df(risks), use_container_width=True, hide_index=True)

    with tabs[4]:
        st.markdown("#### Assumptions")
        if assumptions and isinstance(assumptions[0], dict):
            st.dataframe(_df(assumptions), use_container_width=True, hide_index=True)
        else:
            st.write(assumptions or ["No assumptions returned."])
        st.markdown("#### Constraints / Dependencies")
        if constraints and isinstance(constraints[0], dict):
            st.dataframe(_df(constraints), use_container_width=True, hide_index=True)
        else:
            st.write(constraints or ["No constraints returned."])

    with tabs[5]:
        st.json(plan)

    excel_bytes = build_excel_workbook(plan)
    st.download_button(
        "⬇️ Download Project Plan (Excel)",
        data=excel_bytes,
        file_name="sow_project_plan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def show_footer(visit_count: int) -> None:
    st.markdown("---")
    st.markdown("**Projects**")
    st.markdown(
        '[SOW → Project Planner](#) | '
        '[GxP AI Readiness & Governance Assessment](https://gxp-ai-readiness-governance.streamlit.app/) | '
        '[AI Risk & Issue Dashboard](https://ai-risk-issue-dashboard.streamlit.app/)'
    )
    st.markdown("© 2026 Sriram Sampath. All rights reserved.")
    st.markdown('[LinkedIn](https://www.linkedin.com/in/sriramsampath81/)')
    st.caption(f"👁️ Visits: {visit_count}")


def main() -> None:
    db = database()
    if "visit_recorded" not in st.session_state:
        try:
            st.session_state["visit_count"] = record_visit(db)
        except Exception:
            st.session_state["visit_count"] = 0
        st.session_state["visit_recorded"] = True

    st.title("📋 SOW → Project Planner")
    st.caption("AI-assisted, domain-agnostic project planning. The AI proposes; the Project Manager decides.")
    if st.query_params.get("bot") == "wake":
        st.success("App is awake.")
        st.stop()

    groq_cfg = get_groq_config(
        api_key=get_secret("GROQ_API_KEY", ""),
        model=get_secret("GROQ_MODEL", "qwen/qwen3.8-27b"),
        base_url=get_secret("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )
    use_ai = bool(groq_cfg.api_key)

    projects = list_projects(db)
    with st.sidebar:
        st.markdown("**Saved projects**")
        if projects:
            choice = st.selectbox("Open project", options=["—"] + [p["label"] for p in projects], label_visibility="collapsed")
            if choice != "—":
                selected = next(p for p in projects if p["label"] == choice)
                loaded = load_project(db, selected["id"])
                if loaded:
                    st.session_state["plan"] = loaded["plan"]
                    st.session_state["project_name"] = loaded["name"]
                    st.success("Project loaded.")
        else:
            st.caption("No saved projects yet.")

    st.markdown("### Test with the built-in sample")
    if st.button("🧪 Load Complex Enterprise SOW"):
        st.session_state["sample_loaded"] = True
        st.session_state["pasted_sow"] = SAMPLE_SOW
        st.session_state["project_name"] = "Enterprise Digital Operations Platform"
    if st.session_state.get("sample_loaded"):
        st.info("Built-in complex enterprise SOW loaded. Review it below, then click Generate Project Plan.")

    left, right = st.columns([1, 1])
    with left:
        project_name = st.text_input("Project name", value=st.session_state.get("project_name", ""), placeholder="e.g. CRM Implementation")
        uploaded = st.file_uploader("Upload SOW", type=["pdf", "docx", "xlsx", "xlsm", "txt", "md"])
    with right:
        pasted = st.text_area("Or paste SOW text", value=st.session_state.get("pasted_sow", ""), key="pasted_sow", height=300, placeholder="Paste the SOW here or load the built-in complex sample...")

    if uploaded is not None:
        try:
            extracted_text = extract_document(uploaded.getvalue(), uploaded.name)
            st.info(f"Extracted {len(extracted_text):,} characters from `{uploaded.name}`.")
            with st.expander("Preview extracted text"):
                st.text(extracted_text[:12000])
        except Exception as exc:
            extracted_text = ""
            st.error(f"Document extraction failed: {exc}")
    else:
        extracted_text = pasted.strip()

    generate = st.button("🚀 Generate Project Plan", type="primary", use_container_width=True)
    if generate:
        if not project_name.strip():
            st.error("Enter a project name.")
            st.stop()
        if not extracted_text.strip():
            st.error("Upload an SOW or paste SOW text.")
            st.stop()
        with st.spinner("Analyzing the SOW and building the project plan..."):
            source = uploaded.name if uploaded else "Pasted SOW"
            if use_ai:
                try:
                    plan = generate_plan_with_groq(extracted_text, project_name, groq_cfg)
                    engine = "Groq AI planner"
                except Exception as exc:
                    st.warning(f"Groq AI planning was unavailable, so the built-in planner was used instead. Details: {exc}")
                    plan = build_fallback_plan(extracted_text, project_name)
                    engine = "Built-in planner"
            else:
                plan = build_fallback_plan(extracted_text, project_name)
                engine = "Built-in planner"
            plan = validate_and_normalize_plan(plan)
            project_id = create_project(db, name=project_name.strip(), source_name=source, plan=plan, engine_name=engine)
            st.session_state["plan"] = plan
            st.session_state["project_name"] = project_name.strip()
            st.session_state["project_id"] = project_id
            st.session_state["generated_at"] = datetime.now(timezone.utc).isoformat()
        st.success(f"Project plan created and saved. {engine}")

    if "plan" in st.session_state:
        show_plan(st.session_state["plan"])
    show_footer(st.session_state.get("visit_count", 0))


if __name__ == "__main__":
    main()
