# SOW Project Planner — v11 Release Candidate

## Replace
Replace these files in the Streamlit/GitHub project:
- `app.py`
- `planner.py`

Keep the existing repository support files (`ai.py`, `db.py`, `extract.py`, `exporter.py`, `requirements.txt`, etc.).

## Release verification
Run:
`python qa_public_launch_gate_v11.py`

Expected final line:
`MVP PUBLIC-LAUNCH GATE V11: PASS`

## Release intent
v11 is the consolidated release candidate after the parser, schedule, traceability, AI advisory and leadership-UI fixes identified during Small/Medium/Complex testing.

## Deployment gate
After deployment, confirm the application reports the v11 engine marker. This is a version-alignment check, not another SOW-testing cycle.
