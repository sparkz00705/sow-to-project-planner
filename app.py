from __future__ import annotations

from datetime import datetime, timezone
import re

import pandas as pd
import streamlit as st

from ai import generate_ai_advice, get_groq_config
from db import create_project, init_db, record_visit
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

# Responsive PMO metric-card styling. Streamlit metric labels/captions can
# truncate long leadership wording on narrower cards; allow natural wrapping
# without changing the underlying values or terminology.
st.markdown(
    """
    <style>
    div[data-testid="stMetricLabel"] p {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.2 !important;
        word-break: normal !important;
        overflow-wrap: anywhere !important;
    }
    div[data-testid="stMetricValue"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.1 !important;
        overflow-wrap: anywhere !important;
    }
    div[data-testid="stCaptionContainer"] p {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.35 !important;
        overflow-wrap: anywhere !important;
    }
    @media (max-width: 1100px) {
        div[data-testid="stMetricValue"] {
            font-size: 1.55rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
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


@st.cache_resource
def database():
    """Initialize the configured application database for the current Streamlit process."""
    try:
        database_url = st.secrets.get("DATABASE_URL", "")
    except Exception:
        database_url = ""
    return init_db(str(database_url or ""))


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
    st.caption(f"👁️ Visits: {0 if visit_count is None else visit_count}")


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

    # Count one human page visit per Streamlit session. Wake-up traffic is
    # excluded above, and session_state prevents reruns from incrementing it.
    if "visit_recorded" not in st.session_state:
        try:
            st.session_state["visit_count"] = record_visit(db)
        except Exception:
            # Visitor analytics must never prevent the planner from loading.
            st.session_state["visit_count"] = 0
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
                        "planner-v11.1 + groq-qwen38-advice"
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

            try:
                create_project(
                    db,
                    name=project_name.strip(),
                    source_name=uploaded.name if uploaded else "Pasted SOW",
                    plan=plan,
                    engine_name=engine,
                )
            except Exception as exc:
                # Persistence must never block plan generation in the MVP.
                plan.setdefault("metadata", {})["persistence_error"] = str(exc)[:1000]
                st.warning("The project plan was generated successfully, but persistent project storage was unavailable for this run.")

            st.session_state["plan"] = plan
            st.session_state["generated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

        st.success("Project plan prepared for PM review.")

    # IMPORTANT: render the project plan exactly once per Streamlit run.
    # The previous version rendered show_plan() both before and after generation,
    # which caused DuplicateElementId on the download button.
    if "plan" in st.session_state:
        show_plan(st.session_state["plan"])

    # Visit counter is intentionally shown as a clean zero baseline for this release.
    show_footer(st.session_state.get("visit_count", 0))


if __name__ == "__main__":
    main()
