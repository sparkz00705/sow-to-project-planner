# Architecture

## Logical flow

SOW input → document extraction → AI SOW analysis → planning model → validation → database → PM review → Excel export

## AI

OpenRouter REST API using `qwen/qwen3.6-27b` with structured JSON output.

## Database

`SQLAlchemy` provides the database abstraction. The application uses PostgreSQL when `DATABASE_URL` is configured and otherwise falls back to SQLite. Application code does not depend on a particular database engine.

## Persistence

SQLite is suitable for local development. Streamlit Community Cloud local storage is not guaranteed to persist across restarts, so PostgreSQL is the recommended deployment configuration once project history matters.

## Security

API credentials are read from Streamlit Secrets. Secrets must never be committed to GitHub.

## Wake-up

GitHub Actions runs `.github/scripts/wake_streamlit.py` on a schedule. Selenium opens the configured Streamlit URL and clicks the wake-up button when Streamlit presents it.
