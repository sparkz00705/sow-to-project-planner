# SOW → Project Planner

Domain-agnostic Streamlit application that converts an SOW into a PM-reviewable project plan.

## Design
AI provides compact planning advice; the deterministic planning engine owns the executable schedule, WBS, milestones, traceability and quality registers.

## Required Streamlit Secret
```toml
GROQ_API_KEY = "your-rotated-key"
GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
```

`DATABASE_URL` is optional. Without it the app uses SQLite locally/runtime. With it the same data layer can use PostgreSQL.

## Deployment
Deploy `app.py` from the repository root in Streamlit Community Cloud.

## Keep-awake
`wake_streamlit.py` can be run by a GitHub Actions scheduled workflow. The workflow file is intentionally kept out of the repository root because GitHub requires `.github/workflows/`. A copy/paste workflow is provided in `KEEP_AWAKE_WORKFLOW.yml.txt`.

## Visit counter
The footer uses the same lightweight external counter pattern as the existing Risk & Issue Dashboard. It counts once per browser session and does not depend on the project database. If the counter service is unavailable, the UI shows `—` rather than falsely showing `0`.
