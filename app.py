
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

from ai import generate_ai_advice, get_groq_config
from db import create_project, init_db, list_projects, load_project
from exporter import build_excel_workbook
from extract import extract_document
from planner import build_deterministic_plan, merge_ai_advice, validate_and_normalize_plan


st.set_page_config(page_title="SOW → Project Planner", page_icon="📋", layout="wide")


COMPLEX_SAMPLE_SOW = '# Statement of Work (SOW)\n## Enterprise Digital Operations Platform Implementation\n\nSOW Reference: EDP-2026-017\nPlanned Duration: 40 weeks\nTarget Countries: India, United Kingdom, Germany, United States, Singapore\nTarget Users: Approximately 2,500 users across 12 sites\n\n## 1. Purpose\nThe Client intends to implement a centralized Digital Operations Platform to replace multiple legacy processes currently managed through spreadsheets, email, shared drives, and three departmental applications.\n\n## 2. Project Objectives\nThe project objectives are to implement a centralized enterprise platform for approximately 2,500 users, standardize operational workflows across 12 sites, migrate agreed historical data, integrate with ERP, identity management, email, collaboration and document-management environments, establish role-based access and segregation of duties, provide management dashboards and audit history, train users and support teams, complete formal testing and business acceptance, deploy in three production waves, and transition to business-as-usual support.\n\n## 3. Scope\n### Workstream 1 - Project Management and Governance\nThe Implementation Partner shall provide project management and implementation governance.\nThe project will establish project kickoff, governance structure, Steering Committee, weekly project reporting, RAID management, decision management, dependency management, financial tracking, schedule management, change control, and stakeholder communications.\n\n### Workstream 2 - Discovery and Requirements\nThe Implementation Partner shall conduct stakeholder interviews, current-state process assessment, process inventory, requirements workshops, business requirements documentation, non-functional requirements, reporting requirements, security requirements, data requirements, integration requirements, requirements validation, and requirements sign-off.\n\n### Workstream 3 - Future-State Process Design\nThe Implementation Partner shall design standardized future-state workflows, roles, approval matrices, exception handling, escalation rules, and notification rules.\nA maximum of 15% of the current-state processes may require local variations. Any variation above this threshold will require Steering Committee review.\n\n### Workstream 4 - Solution Design and Configuration\nThe Implementation Partner shall complete solution architecture and configure Development, Test, Validation and Production environments.\nThe Implementation Partner shall configure workflows, business rules, user roles, permissions, notifications, dashboards, reports, and audit logging.\n\n### Workstream 5 - ERP Integration\nThe new platform will exchange employee master data, organizational units, cost centers, supplier information, and selected transaction reference data with the Client ERP.\nThe integration will use REST APIs where available and secure file transfer where an API is not available.\nThe Client will provide API specifications and test credentials by Week 8.\n\n### Workstream 6 - Identity and Access Management\nThe solution shall integrate with the Client enterprise identity provider.\nThe scope includes Single Sign-On, user provisioning, role mapping, group mapping, deprovisioning, access review support, and privileged administrator access.\nMulti-factor authentication will be provided through the existing Client identity platform and is not part of the application implementation.\n\n### Workstream 7 - Document Management\nThe solution will integrate with the Client existing document-management platform for metadata mapping, document upload and retrieval, version reference, permission enforcement, and document-link migration for agreed records.\nMigration of document binaries is excluded from the base scope.\n\n### Workstream 8 - Data Migration\nThe project will migrate up to seven years of historical data from Legacy Application A, Legacy Application B, departmental spreadsheets, and selected CSV extracts.\nThe migration approach will include source assessment, data profiling, data mapping, data cleansing, transformation rules, migration scripts, trial migration, reconciliation, business validation, and production migration.\nThe Client is responsible for ownership and approval of source-data cleansing rules.\n\n### Workstream 9 - Testing and Quality\nTesting will include test strategy, test planning, functional testing, System Integration Testing, regression testing, performance testing, security testing coordination, User Acceptance Testing, defect management, retesting, and test summary reporting.\nThe Implementation Partner will resolve Severity 1 and Severity 2 defects identified during testing before production deployment unless formally waived by the Client.\nSeverity 3 defects may be deferred subject to documented business approval.\n\n### Workstream 10 - Training and Change Management\nTraining shall cover end users, power users, site administrators, global administrators, and service desk personnel.\nTraining materials will include user guides, quick reference guides, administrator guides, training presentations, and recorded demonstrations.\nThe Client will nominate site champions for each participating location.\n\n### Workstream 11 - Deployment and Cutover\nThe production deployment will use three waves.\nWave 1: India and Singapore.\nWave 2: United Kingdom and Germany.\nWave 3: United States.\nEach deployment wave will include cutover readiness assessment, final data migration, configuration verification, access validation, business smoke testing, production deployment, business confirmation, and hypercare initiation.\nA minimum of five business days is required between production waves unless the Steering Committee approves an exception.\n\n### Workstream 12 - Hypercare and Handover\nThe Implementation Partner will provide 30 calendar days of hypercare after the final production deployment.\nHypercare includes incident triage, defect support, configuration corrections, user support, daily issue review during the first two weeks, weekly issue review thereafter, knowledge transfer, operational documentation, and final handover.\n\n## 4. Out of Scope\nThe following items are excluded unless approved through formal change control: replacement of the Client ERP; replacement of the Client identity-management platform; development of a new enterprise data warehouse; replacement of the corporate document-management system; mobile application development; custom functionality requiring more than 20 person-days per feature; historical data older than seven years unless approved; migration of unstructured personal working files; hardware procurement; network infrastructure upgrades; third-party license procurement; and ongoing production support after the 30-day hypercare period.\n\n## 5. Major Deliverables\nThe following deliverables are required: Project Charter; Integrated Project Management Plan; Stakeholder Register; Governance Plan; RAID Log; Requirements Catalogue; Requirements Traceability Matrix; Current-State Process Catalogue; Future-State Process Design; Solution Design Document; Security and Access Design; Integration Design Specifications; Data Migration Strategy; Data Mapping Specifications; Data Cleansing Rules; Migration Reconciliation Report; configured Development, Test, Validation and Production environments; System Test Plan; SIT Results; Performance Test Results; UAT Plan; UAT Results; Defect Register; Training Plan; Training Materials; Cutover Plan; Go-Live Readiness Assessment; Production Deployment Report; Hypercare Report; Knowledge Transfer Package; Operational Support Documentation; Project Closure Report.\n\n## 6. Major Milestones\nProject Kickoff Week 1; Discovery Complete Week 5; Requirements Sign-off Week 8; Future-State Design Approved Week 11; Solution Design Approved Week 13; Configuration Complete Week 21; Integration Build Complete Week 23; Trial Data Migration Complete Week 24; SIT Complete Week 28; UAT Readiness Week 29; UAT Complete Week 32; Wave 1 Go-Live Week 34; Wave 2 Go-Live Week 36; Wave 3 Go-Live Week 38; Hypercare Complete Week 40.\n\n## 7. Dependencies\nKey dependencies include Client availability of business SMEs, availability of ERP API specifications, availability of integration test environments, identity-provider configuration, document-management APIs, source-data extracts, completion of data cleansing, requirements and design approvals, availability of test users, timely resolution of business defects, availability of site champions, infrastructure readiness, security review completion, and production change-window approval.\n\nThe Implementation Partner is not responsible for delays caused exclusively by Client or third-party dependency delays unless otherwise agreed.\n\n## 8. Client Responsibilities\nThe Client shall provide executive sponsorship, business and technical SMEs, timely access to relevant systems, required environments and credentials, source data, requirements and design approvals, data-cleansing decisions, UAT resources, site champions, defect decisions, cutover approval, and operational support resources after handover.\n\n## 9. Implementation Partner Responsibilities\nThe Implementation Partner shall provide project management, solution and functional resources, platform configuration, agreed integrations, migration utilities, documentation, testing coordination, training materials, cutover support, hypercare, and knowledge transfer.\n\n## 10. Resources\nIndicative Implementation Partner roles include Program/Project Manager, Business Analyst, Solution Architect, Technical Architect, Integration Lead, Data Migration Lead, Configuration Lead, Test Manager, Security Specialist, Training Lead, Change Management Lead, Deployment Lead, and Application Support Specialist.\n\n## 11. Commercial Assumptions\nThe base implementation fee is USD 780,000.\nThe fee includes professional services within the agreed scope.\nThird-party licenses, direct cloud infrastructure charges, travel unless explicitly included, major custom development outside the agreed scope, sites beyond 12, historical data beyond seven years, and major process redesign beyond the 15% local-variation threshold are excluded.\n\n## 12. Schedule Assumptions\nThe 40-week schedule assumes Client SMEs are available at least 20 hours per week during requirements and UAT; source data is delivered by Week 10; ERP API specifications are available by Week 8; security review begins by Week 18; UAT users are confirmed by Week 26; and production change windows are approved at least 15 business days before deployment.\n\n## 13. Acceptance Criteria\nA deliverable is accepted when it has been provided, reviewed, comments addressed, and approved by the designated Client approver.\nProduction go-live requires critical functionality successfully tested, no open Severity 1 defects, Severity 2 defects resolved or formally accepted, UAT completed, required production access configured, production data migration completed and reconciled, cutover checklist completed, and business owner approval.\n\n## 14. Risks and Constraints\nInitial known risks include legacy data quality, undocumented legacy interfaces, ERP API delays, local process variation, UAT resource constraints, migration reconciliation issues, additional security controls, limited production windows, third-party system changes, and additional requirements during discovery.\n\nThe following ambiguities require clarification: the phrase “complete audit history” is not further defined; security testing coordination is included but ownership of the actual penetration test is not stated; performance testing has no numerical target; the SOW does not define exact migrated record volume; and business smoke testing has no entry/exit criteria.\n\n## 15. Governance\nGovernance will include a weekly project team meeting, a biweekly Steering Committee, and a monthly Executive Review covering schedule, budget, major risks, decisions, scope changes, and benefits indicators.\n\n## 16. Reporting\nThe Implementation Partner will provide a weekly status report containing overall project status, milestone status, schedule variance, budget status, RAID summary, decisions required, dependency status, change requests, workstream status, and planned activities for the following two weeks.\n\n## 17. Change Control\nAny requested change affecting scope, schedule, cost, resources, deliverables, interfaces, number of sites, data volume, or acceptance criteria shall be documented as a Change Request with business justification and impact assessment.\n\n## 18. Definition of Done\nThe project will be considered complete when all agreed deliverables have been accepted, all three deployment waves are operational, required data migration has been completed and reconciled, required integrations are operational, UAT has been completed, knowledge transfer is complete, operational documentation has been delivered, hypercare is complete, open items have owners and target dates, and final project acceptance has been obtained.'


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return default


@st.cache_resource
def database():
    return init_db(get_secret("DATABASE_URL", ""))


def _coverage(plan: dict) -> float:
    meta = plan.get("metadata", {})
    return float(meta.get("traceability_coverage_percent", 0))


def show_plan(plan: dict) -> None:
    summary = plan.get("summary", {})
    sow_items = plan.get("sow_items", [])
    activities = plan.get("activities", [])
    milestones = plan.get("milestones", [])
    traceability = plan.get("traceability", [])
    gaps = plan.get("gaps", [])
    risks = plan.get("risks", [])
    assumptions = plan.get("assumptions", [])
    constraints = plan.get("constraints", [])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("SOW items", len(sow_items))
    c2.metric("Activities", len(activities))
    c3.metric("Milestones", len(milestones))
    c4.metric("Gaps", len(gaps))
    c5.metric("Executable coverage", f"{_coverage(plan):g}%")

    st.divider()
    st.subheader("Project summary")
    st.write(summary.get("description") or "No summary returned.")
    st.caption(
        f"Project type: {summary.get('project_type', 'Unknown')} · "
        f"Planning confidence: {summary.get('confidence', 'N/A')}"
    )

    tabs = st.tabs([
        "Project Plan", "WBS", "Milestones", "SOW Items", "Traceability",
        "Gaps", "Risks", "Assumptions", "Raw JSON"
    ])

    with tabs[0]:
        df = pd.DataFrame(activities)
        if not df.empty:
            cols = ["wbs_id","activity_id","activity_name","phase","duration_days","dependency_ids","owner_role",
                    "deliverable","milestone","source_sow_ids","planning_note","start_week","finish_week"]
            visible = [c for c in cols if c in df.columns]
            st.dataframe(df[visible], use_container_width=True, hide_index=True)
        else:
            st.info("No executable activities were generated.")

    with tabs[1]:
        wdf = pd.DataFrame(plan.get("wbs", []))
        if not wdf.empty:
            st.dataframe(wdf, use_container_width=True, hide_index=True)
        else:
            st.info("No WBS phases were generated.")

    with tabs[2]:
        mdf = pd.DataFrame(milestones)
        if not mdf.empty:
            st.dataframe(mdf, use_container_width=True, hide_index=True)
        else:
            st.info("No milestones were identified.")

    with tabs[3]:
        sdf = pd.DataFrame(sow_items)
        if not sdf.empty:
            st.dataframe(sdf, use_container_width=True, hide_index=True)
        else:
            st.info("No SOW items were extracted.")

    with tabs[4]:
        tdf = pd.DataFrame(traceability)
        if not tdf.empty:
            st.dataframe(tdf, use_container_width=True, hide_index=True)
            controlled = int((tdf["status"] != "Mapped").sum()) if "status" in tdf else 0
            st.caption(f"{controlled} non-executable/controlled items require tracking outside the executable schedule.")
        else:
            st.info("No traceability records were generated.")

    with tabs[5]:
        gdf = pd.DataFrame(gaps)
        if not gdf.empty:
            st.dataframe(gdf, use_container_width=True, hide_index=True)
        else:
            st.success("No planning gaps were identified.")

    with tabs[6]:
        rdf = pd.DataFrame(risks)
        if not rdf.empty:
            st.dataframe(rdf, use_container_width=True, hide_index=True)
        else:
            st.success("No planning risks were identified.")

    with tabs[7]:
        adf = pd.DataFrame(assumptions)
        if not adf.empty:
            st.dataframe(adf, use_container_width=True, hide_index=True)
        else:
            st.info("No explicit assumptions were extracted.")
        cdf = pd.DataFrame(constraints)
        if not cdf.empty:
            st.markdown("#### Constraints")
            st.dataframe(cdf, use_container_width=True, hide_index=True)

    with tabs[8]:
        st.json(plan)

    excel_bytes = build_excel_workbook(plan)
    st.download_button(
        "⬇️ Download Project Plan (Excel)",
        data=excel_bytes,
        file_name="sow_project_plan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


VISIT_COUNTER_URL = "https://abacus.jasoncameron.dev/hit/sow-to-project-planner.streamlit.app/visits"


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
        st.caption("👁️ Visits: —")
    else:
        st.caption(f"👁️ Visits: {visit_count}")


def main() -> None:
    st.title("📋 SOW → Project Planner")
    st.caption("AI-assisted, domain-agnostic project planning. The AI proposes; the Project Manager decides.")

    # Wake-up traffic must not be counted as a human page visit.
    if st.query_params.get("bot") == "wake":
        st.success("App is awake.")
        st.stop()

    db = database()

    # Use the same lightweight external counter pattern as the existing Risk & Issue Dashboard.
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

    projects = list_projects(db)
    with st.sidebar:
        st.markdown("**Saved projects**")
        if projects:
            choice = st.selectbox("Open project", ["—"] + [p["label"] for p in projects], label_visibility="collapsed")
            if choice != "—":
                selected = next(p for p in projects if p["label"] == choice)
                loaded = load_project(db, selected["id"])
                if loaded:
                    st.session_state["plan"] = loaded["plan"]
                    st.session_state["project_name"] = loaded["name"]
                    st.success("Project loaded.")
        else:
            st.caption("No saved projects yet.")

        st.markdown("---")
        if st.button("🧪 Load Complex Sample SOW", use_container_width=True):
            st.session_state["project_name"] = "Enterprise Digital Operations Platform"
            st.session_state["sow_text"] = COMPLEX_SAMPLE_SOW

    project_name = st.text_input(
        "Project name",
        value=st.session_state.get("project_name", ""),
        placeholder="e.g. CRM Implementation",
    )
    sow_text = st.text_area(
        "Statement of Work",
        value=st.session_state.get("sow_text", ""),
        height=320,
        placeholder="Upload an SOW below or paste the SOW here...",
    )
    st.session_state["sow_text"] = sow_text

    uploaded = st.file_uploader("Upload SOW", type=["pdf","docx","xlsx","xlsm","txt","md"])
    extracted_text = sow_text.strip()
    if uploaded is not None:
        try:
            extracted_text = extract_document(uploaded.getvalue(), uploaded.name)
            st.info(f"Extracted {len(extracted_text):,} characters from `{uploaded.name}`.")
            with st.expander("Preview extracted text"):
                st.text(extracted_text[:12000])
            st.session_state["sow_text"] = extracted_text
        except Exception as exc:
            st.error(f"Document extraction failed: {exc}")

    generate = st.button("🚀 Generate Project Plan", type="primary", use_container_width=True)

    if "plan" in st.session_state and not generate:
        show_plan(st.session_state["plan"])

    if generate:
        if not project_name.strip():
            st.error("Enter a project name.")
            st.stop()
        if not extracted_text.strip():
            st.error("Upload an SOW or paste SOW text.")
            st.stop()

        with st.spinner("Analyzing the SOW and building the project plan..."):
            plan = build_deterministic_plan(extracted_text, project_name.strip())
            engine = "Built-in planning engine"
            if cfg.api_key:
                try:
                    ai_advice = generate_ai_advice(plan["sow_items"], project_name.strip(), cfg)
                    plan = merge_ai_advice(plan, ai_advice)
                    plan["metadata"]["engine"] = "groq_qwen38_hybrid"
                    plan["metadata"]["engine_version"] = "planner-v4 + groq-qwen38-advice"
                    engine = "Groq AI planner + planning engine"
                except Exception as exc:
                    # Keep the high-quality deterministic plan. Do not replace it with a weaker fallback.
                    plan["metadata"]["ai_error"] = str(exc)[:1000]
                    st.warning("AI assistance was unavailable for this run. A full deterministic project plan was generated instead.")
            plan = validate_and_normalize_plan(plan)
            create_project(
                db,
                name=project_name.strip(),
                source_name=uploaded.name if uploaded else "Pasted SOW",
                plan=plan,
                engine_name=engine,
            )
            st.session_state["plan"] = plan
            st.session_state["project_name"] = project_name.strip()
            st.session_state["generated_at"] = datetime.now(timezone.utc).isoformat()

        st.success(f"Project plan created and saved. {engine}")

    if "plan" in st.session_state:
        show_plan(st.session_state["plan"])

    show_footer(st.session_state.get("visit_count", 0))


if __name__ == "__main__":
    main()
