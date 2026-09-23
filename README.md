# SOW → Project Planner

A domain-agnostic Streamlit application that transforms a Statement of Work into an AI-assisted project plan.

## Features

- PDF, DOCX, XLSX/XLSM, TXT and Markdown SOW input
- Qwen3.6 27B through OpenRouter
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
- GitHub Actions Selenium wake-up workflow

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

Deploy `app.py` from this repository.

Required secret for AI:

```toml
OPENROUTER_API_KEY = "..."
OPENROUTER_MODEL = "qwen/qwen3.6-27b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_SITE_URL = "https://YOUR-APP.streamlit.app"
OPENROUTER_APP_NAME = "SOW Project Planner"
```

Optional persistent database:

```toml
DATABASE_URL = "postgresql://user:password@host:5432/dbname"
```

If `DATABASE_URL` is omitted, the app uses `data/planner.sqlite3`. Streamlit Community Cloud does not guarantee persistence of local files, so hosted PostgreSQL should be used before treating the app as a production system.

## GitHub Actions wake-up

Create an Actions repository secret:

```text
STREAMLIT_APP_URL=https://YOUR-APP.streamlit.app/?bot=wake
```

The workflow runs every 10 minutes and opens the application with Selenium. If Streamlit displays its sleep page, the workflow clicks the wake-up button.

## Design principle

The AI proposes. The Project Manager reviews and decides.

The SOW is the source of truth. Inferred planning content is explicitly treated as a proposal or assumption rather than a contractual commitment.


## Flat GitHub deployment package

All application Python modules are intentionally kept in the repository root so the files can be uploaded directly through the GitHub web interface without nested application folders.

The optional GitHub Actions workflow is not embedded in this flat package; `wake_streamlit.py` is included as the Selenium wake-up script. A GitHub Actions workflow can be added separately later.
