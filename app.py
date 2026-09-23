from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from ai import generate_plan_with_openrouter, get_openrouter_config
from db import create_project, init_db, list_projects, load_project, record_visit
from exporter import build_excel_workbook
from extract import extract_document
from planner import build_fallback_plan, validate_and_normalize_plan

st.set_page_config(
    page_title="SOW → Project Planner",
    page_icon="📋",
    layout="wide",
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


def show_plan(plan: dict) -> None:
    summary = plan.get("summary", {})
    sow_items = plan.get("sow_items", [])
    activities = plan.get("activities", [])
    milestones = plan.get("milestones", [])
    gaps = plan.get("gaps", [])
    risks = plan.get("risks", [])
    traceability = plan.get("traceability", [])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("SOW items", len(sow_items))
    c2.metric("Activities", len(activities))
    c3.metric("Milestones", len(milestones))
    c4.metric("Gaps", len(gaps))
    mapped = sum(1 for x in traceability if x.get("status") == "Mapped")
    coverage = round((mapped / len(sow_items)) * 100) if sow_items else 0
    c5.metric("SOW coverage", f"{coverage}%")

    st.divider()
    st.subheader("Project summary")
    st.write(summary.get("description") or "No summary returned.")
    st.caption(
        f"Project type: {summary.get('project_type', 'Unknown')} · "
        f"AI confidence: {summary.get('confidence', 'N/A')}"
    )

    tabs = st.tabs(
        [
            "Project Plan",
            "SOW Items",
            "Traceability",
            "Gaps & Risks",
            "Assumptions",
            "Raw JSON",
        ]
    )

    with tabs[0]:
        if activities:
            df = pd.DataFrame(activities)
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
            ]
            visible = [c for c in cols if c in df.columns]
            st.dataframe(df[visible], use_container_width=True, hide_index=True)
        else:
            st.info("No activities were generated.")

        if milestones:
            st.markdown("#### Milestones")
            st.dataframe(pd.DataFrame(milestones), use_container_width=True, hide_index=True)

    with tabs[1]:
        if sow_items:
            st.dataframe(pd.DataFrame(sow_items), use_container_width=True, hide_index=True)
        else:
            st.info("No SOW items were extracted.")

    with tabs[2]:
        if traceability:
            td = pd.DataFrame(traceability)
            st.dataframe(td, use_container_width=True, hide_index=True)
            unmapped = td[td.get("status", "") != "Mapped"] if "status" in td.columns else pd.DataFrame()
            if not unmapped.empty:
                st.warning(f"{len(unmapped)} SOW item(s) need PM review.")
        else:
            st.info("No traceability records were generated.")

    with tabs[3]:
        if gaps:
            st.markdown("#### Gaps")
            st.dataframe(pd.DataFrame(gaps), use_container_width=True, hide_index=True)
        else:
            st.success("No planning gaps were identified.")
        if risks:
            st.markdown("#### Risks")
            st.dataframe(pd.DataFrame(risks), use_container_width=True, hide_index=True)
        else:
            st.success("No planning risks were identified.")

    with tabs[4]:
        assumptions = plan.get("assumptions", [])
        constraints = plan.get("constraints", [])
        a, b = st.columns(2)
        with a:
            st.markdown("#### Assumptions")
            st.write(assumptions or ["No assumptions returned."])
        with b:
            st.markdown("#### Constraints")
            st.write(constraints or ["No constraints returned."])

    with tabs[5]:
        st.json(plan)

    excel_bytes = build_excel_workbook(plan)
    st.download_button(
        "⬇️ Download Project Plan (Excel)",
        data=excel_bytes,
        file_name="sow_project_plan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
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
    st.caption(
        "AI-assisted, domain-agnostic project planning. The AI proposes; the Project Manager decides."
    )

    query_params = st.query_params
    if query_params.get("bot") == "wake":
        st.success("App is awake.")
        st.stop()

    # Internal configuration is intentionally hidden from end users.
    # The app uses OpenRouter/Qwen automatically when the secret is configured;
    # otherwise it falls back to the built-in planner.
    or_cfg = get_openrouter_config(
        api_key=get_secret("OPENROUTER_API_KEY", ""),
        model=get_secret("OPENROUTER_MODEL", "qwen/qwen3.6-27b"),
        base_url=get_secret("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        site_url=get_secret("OPENROUTER_SITE_URL", ""),
        app_name=get_secret("OPENROUTER_APP_NAME", "SOW Project Planner"),
    )
    use_ai = bool(or_cfg.api_key)

    projects = list_projects(db)
    with st.sidebar:
        st.markdown("**Saved projects**")
        if projects:
            choice = st.selectbox(
                "Open project",
                options=["—"] + [p["label"] for p in projects],
                label_visibility="collapsed",
            )
            if choice != "—":
                selected = next(p for p in projects if p["label"] == choice)
                loaded = load_project(db, selected["id"])
                if loaded:
                    st.session_state["plan"] = loaded["plan"]
                    st.session_state["project_name"] = loaded["name"]
                    st.success("Project loaded.")
        else:
            st.caption("No saved projects yet.")

    left, right = st.columns([1, 1])
    with left:
        project_name = st.text_input(
            "Project name",
            value=st.session_state.get("project_name", ""),
            placeholder="e.g. CRM Implementation",
        )
        uploaded = st.file_uploader(
            "Upload SOW",
            type=["pdf", "docx", "xlsx", "xlsm", "txt", "md"],
        )
    with right:
        pasted = st.text_area(
            "Or paste SOW text",
            height=230,
            placeholder="Paste the SOW here...",
        )

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
                    plan = generate_plan_with_openrouter(extracted_text, project_name, or_cfg)
                    engine = "AI planner"
                except Exception:
                    st.warning("AI planning was unavailable, so the built-in planner was used instead.")
                    plan = build_fallback_plan(extracted_text, project_name)
                    engine = "Built-in planner"
            else:
                plan = build_fallback_plan(extracted_text, project_name)
                engine = "Built-in planner"

            plan = validate_and_normalize_plan(plan)
            project_id = create_project(
                db,
                name=project_name.strip(),
                source_name=source,
                plan=plan,
                engine_name=engine,
            )
            st.session_state["plan"] = plan
            st.session_state["project_name"] = project_name.strip()
            st.session_state["project_id"] = project_id
            st.session_state["generated_at"] = datetime.now(timezone.utc).isoformat()

        st.success(f"Project plan created and saved. Engine: {engine}")

    if "plan" in st.session_state:
        show_plan(st.session_state["plan"])

    show_footer(st.session_state.get("visit_count", 0))


if __name__ == "__main__":
    main()
