# QA / Architecture Review of Submitted Test Workbook

## Source
User-supplied `sow_project_plan.xlsx` representing the complex enterprise SOW test.

## Findings
### Critical defects observed
- 43 SOW rows were classified uniformly as `Scope / Deliverable`.
- Non-executable contractual content (commercial fee, out-of-scope items, responsibilities, assumptions, risks, clarifications) was converted into schedule activities.
- Almost all activities were assigned 5 days.
- Almost all activities used `Execution` as the phase.
- Owners defaulted to `Project Team`.
- Traceability marked non-executable content as `Mapped` simply because it had an activity ID.
- Milestones were missing the explicit Week targets from the SOW and instead showed only three AI proposals with `TBD`.
- Assumptions were reduced to a single generic sentence.
- Risks and gaps were too generic and lacked source linkage.
- The Project Plan was therefore not schedule-ready and did not preserve the semantic distinction between scope, control content and planning information.

## Final architecture response
- Replace statement-to-task fallback with semantic SOW classification.
- Build workstream activities from executable scope.
- Preserve explicit milestone targets.
- Maintain separate registers for gaps, risks, assumptions and constraints.
- Trace executable SOW scope to activities; track controlled/non-executable items separately.
- Use Groq only for compact advisory enrichment due the observed account OTPM limit.
- Never replace a good deterministic plan with the old weak fallback if AI is unavailable.

## Test exit criteria
A regression pass should confirm:
- No commercial statement becomes an activity.
- No risk/constraint becomes an activity.
- No responsibility statement becomes an activity.
- Explicit Week milestones are retained.
- Activity durations are not uniformly 5 days.
- Dependencies form a usable chain.
- Every executable SOW item is mapped or explicitly flagged for review.
- Gaps, risks, assumptions and constraints carry source SOW IDs.
- AI failures leave a usable deterministic plan and do not silently label it as AI-generated.
