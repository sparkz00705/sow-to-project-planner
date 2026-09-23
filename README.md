# SOW → Project Planner

A domain-agnostic Streamlit application that transforms a Statement of Work into an AI-assisted project plan.

## Features

- PDF, DOCX, XLSX/XLSM, TXT and Markdown SOW input
- Qwen 3.8 27B through Groq
- SOW item extraction
- WBS generation
- Activities and dependencies
- Milestones
- Assumptions and constraints
- Gaps and planning risks
- SOW-to-activity traceability
- Excel export
- Saved project history
- PostgreSQL-ready database layer with SQLite fallback
- Selenium wake-up script for scheduled automation

## Streamlit Cloud

Deploy `app.py` from this repository.

Required Streamlit secret for AI:

```toml
GROQ_API_KEY = "..."
GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
```

Optional persistent database:

```toml
DATABASE_URL = "postgresql://user:password@host:5432/dbname"
```

If `DATABASE_URL` is omitted, the app uses local SQLite. Streamlit Community Cloud does not guarantee persistence of local files across restarts, so use hosted PostgreSQL when saved project history must persist.

## Wake-up automation

`wake_streamlit.py` contains the Selenium wake-up logic. It expects the environment variable `STREAMLIT_APP_URL` to contain the deployed app URL, including `?bot=wake`.

For scheduled execution, place the script in a GitHub Actions workflow and store the URL as an Actions secret.

## Design principle

The AI proposes. The Project Manager reviews and decides.

The SOW is the source of truth. Inferred planning content is explicitly treated as a proposal or assumption rather than a contractual commitment.
