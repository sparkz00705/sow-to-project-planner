from __future__ import annotations
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import planner


def extract_assignment(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    if not isinstance(value, str):
                        raise TypeError(f"{name} is not a string fixture")
                    return value
    raise KeyError(f"Fixture {name} not found in {path}")

SMALL = extract_assignment(ROOT / "test_small_sow_exact.py", "SMALL")
MEDIUM = extract_assignment(ROOT / "regression_v7.py", "MEDIUM")
COMPLEX = extract_assignment(ROOT / "app.py", "COMPLEX_SAMPLE_SOW")

EXPECTED = {
    "Small": dict(items=54, executable=26, activities=14, milestones=7, gaps=0, risks=4, assumptions=3, constraints=0, coverage=100.0, finish=10),
    "Medium": dict(items=23, executable=9, activities=21, milestones=8, gaps=1, risks=4, assumptions=2, constraints=0, coverage=100.0, finish=20),
    "Complex": dict(items=67, executable=33, activities=28, milestones=15, gaps=5, risks=10, assumptions=6, constraints=6, coverage=100.0, finish=40),
}


def common_gate(plan: dict, label: str) -> None:
    m = plan["metadata"]
    assert m["qa_status"] == "PASS", (label, m["reconciliation_errors"])
    assert len(plan["traceability"]) == len(plan["sow_items"])
    assert len({x["sow_id"] for x in plan["sow_items"]}) == len(plan["sow_items"])
    assert len({x["activity_id"] for x in plan["activities"]}) == len(plan["activities"])
    assert len({x["milestone_id"] for x in plan["milestones"]}) == len(plan["milestones"])
    assert len(m["schedule_review_rows"]) == m["explicit_milestone_count"]
    assert sum(m["schedule_status_counts"].values()) == m["explicit_milestone_count"]
    sow_ids = {x["sow_id"] for x in plan["sow_items"]}
    for activity in plan["activities"]:
        assert set(activity.get("source_sow_ids", [])) <= sow_ids
        note = str(activity.get("planning_note", "")).lower()
        if activity.get("source_sow_ids"):
            assert "sow-linked" in note or "source linkage" in note
        else:
            assert "planning-derived" in note


results = {}
for label, sow in (("Small", SMALL), ("Medium", MEDIUM), ("Complex", COMPLEX)):
    plan = planner.build_deterministic_plan(sow, label)
    common_gate(plan, label)
    m = plan["metadata"]
    e = EXPECTED[label]
    actual = {
        "sow_items": m["sow_item_count"],
        "executable": m["executable_sow_item_count"],
        "activities": m["activity_count"],
        "milestones": m["explicit_milestone_count"],
        "gaps": m["sow_gap_count"],
        "risks": m["sow_risk_count"],
        "assumptions": m["sow_assumption_count"],
        "constraints": m["constraint_register_count"],
        "coverage": m["traceability_coverage_percent"],
        "finish_week": m["planned_finish_week"],
        "schedule_status": m["schedule_status_counts"],
        "qa": m["qa_status"],
    }
    for key, expected_value in e.items():
        actual_key = {
            "items": "sow_items", "executable": "executable", "activities": "activities",
            "milestones": "milestones", "gaps": "gaps", "risks": "risks",
            "assumptions": "assumptions", "constraints": "constraints", "coverage": "coverage",
            "finish": "finish_week",
        }.get(key, key)
        assert actual[actual_key] == expected_value, (label, key, actual[actual_key], expected_value)
    results[label] = actual

# AI contradiction/duplication gate on the Complex SOW.
ai = {
    "gaps": [
        "No defined timeline or milestones beyond Week 8",
        "Specific legacy application details and data volume unspecified",
        "Success criteria and acceptance thresholds undefined",
    ],
    "risks": [
        "Data quality issues from 7 years of heterogeneous sources",
        "Integration delays if Client API specs are late",
        "Scope creep from local process variations exceeding 15%",
    ],
    "assumptions": [
        "Client ERP and IdP are stable and available for integration",
        "Client will timely approve data cleansing rules",
        "Existing infrastructure supports required environments",
    ],
}
merged = planner.merge_ai_advice(planner.build_deterministic_plan(COMPLEX, "Complex"), ai)
mm = merged["metadata"]
assert mm["sow_gap_count"] == 5
assert mm["ai_advisory_gap_count"] == 0
assert mm["sow_risk_count"] == 10
assert mm["ai_advisory_risk_count"] == 0
assert mm["sow_assumption_count"] == 6
assert mm["ai_advisory_assumption_count"] == 1
assert mm["ai_advisory_rejection_count"] == 8
results["AI quality gate"] = {
    "sow_gaps": mm["sow_gap_count"],
    "ai_advisory_gaps": mm["ai_advisory_gap_count"],
    "sow_risks": mm["sow_risk_count"],
    "ai_advisory_risks": mm["ai_advisory_risk_count"],
    "sow_assumptions": mm["sow_assumption_count"],
    "ai_advisory_assumptions": mm["ai_advisory_assumption_count"],
    "rejections": mm["ai_advisory_rejection_count"],
    "gap_register_total": mm["gap_register_count"],
}

# Structural negative test.
neg = planner.build_deterministic_plan(SMALL, "Negative")
neg["activities"][0]["activity_id"] = neg["activities"][1]["activity_id"]
neg["activities"][2]["dependency_ids"] = ["ACT-999"]
neg = planner.validate_and_normalize_plan(neg)
assert neg["metadata"]["qa_status"] == "ERROR"
assert any("Duplicate activities IDs" in e for e in neg["metadata"]["reconciliation_errors"])
assert any("missing dependency" in e for e in neg["metadata"]["reconciliation_errors"])
results["Negative structural gate"] = "PASS"

# Version/UI release gate.
planner_text = (ROOT / "planner.py").read_text(encoding="utf-8")
app_text = (ROOT / "app.py").read_text(encoding="utf-8")
assert 'PLANNER_VERSION = "v11.0"' in planner_text
assert "planner-v11 + groq-qwen38-advice" in app_text
assert "s1, s2 = st.columns(2" in app_text
assert "s3, s4 = st.columns(2" in app_text
results["Version and UI gate"] = "PASS"

print(json.dumps(results, indent=2))
print("MVP PUBLIC-LAUNCH GATE V11: PASS")
