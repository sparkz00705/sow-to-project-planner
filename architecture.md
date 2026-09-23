# Architecture

## Logical flow

SOW input → document extraction → Groq/Qwen SOW analysis → planning model → validation → database → PM review → Excel export

## AI

Groq REST API using `qwen/qwen3.8-27b` with strict structured JSON output. Groq documents JSON Schema support for this model.

## Database

SQLAlchemy provides the database abstraction. The application uses PostgreSQL when `DATABASE_URL` is configured and otherwise falls back to SQLite.

## Persistence

SQLite is suitable for local development. Streamlit Community Cloud local file storage is not guaranteed to persist across restarts, so PostgreSQL is recommended when project history must persist.

## Security

API credentials are read from Streamlit Secrets. Secrets must never be committed to GitHub.

## Wake-up

`wake_streamlit.py` uses Selenium to open the deployed Streamlit URL and click the wake-up button when the sleep page is displayed. The script can be called from a GitHub Actions scheduled workflow.
