# SOW Project Planner — v11 Public Launch Certification

## Engineering gate
The v11 release candidate passes the deterministic regression gate across the controlled Small, Medium and Complex SOW fixtures, the AI advisory quality gate, the structural negative test, and the version/UI gate.

## Controlled regression

| Test | SOW Items | Executable | Activities | Milestones | SOW Gaps | SOW Risks | SOW Assumptions | Constraints | Coverage | Finish |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Small | 54 | 26 | 14 | 7 | 0 | 4 | 3 | 0 | 100% | Week 10 |
| Medium | 23 | 9 | 21 | 8 | 1 | 4 | 2 | 0 | 100% | Week 20 |
| Complex | 67 | 33 | 28 | 15 | 5 | 10 | 6 | 6 | 100% | Week 40 |

All three deterministic cases returned `QA PASS`, all explicit milestones reconciled to the milestone register, and all activity source references resolved to known SOW IDs or were explicitly labelled planning-derived.

## AI quality gate
The controlled Complex-SOW AI seed produced:

- 0 accepted AI gaps where the candidate contradicted explicit milestones/acceptance criteria or duplicated a known SOW clarification.
- 0 accepted AI risks that duplicated contractual SOW risks.
- 1 accepted AI assumption after duplicate filtering.
- 8 AI advisory observations rejected by the quality filter.

AI advisory rows remain separate from contractual SOW registers.

## Release hardening included
- Planner version aligned to `v11.0`.
- Planning-derived activities are labelled as such instead of implying direct SOW linkage.
- Activity SOW references are validated against the SOW register.
- Milestone SOW records are required to have milestone trace links.
- SOW gaps are explicitly marked with `origin="SOW"`.
- AI gap contradiction/duplication filtering added.
- AI risk duplication filtering added.
- AI assumption duplication filtering added.
- Existing responsive 2x2 leadership review layout retained.

## Live deployment limitation
The Streamlit endpoint could not be interactively driven from the test environment because it redirected to Streamlit authentication. Therefore this certification is for the **v11 release candidate and deterministic engineering gate**, not a live browser end-to-end certification.

## Public-launch condition
Deploy the certified `app.py` and `planner.py` to the GitHub branch used by Streamlit and confirm the v11 engine marker in the deployed application. This final check establishes that the certified code is the code actually running in production.
