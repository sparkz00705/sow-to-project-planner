# Architecture

## Core pipeline
SOW document/text → extraction → SOW classification → deterministic planning model → optional Groq/Qwen compact advice → quality registers → persistence → Excel export.

## Principles
1. The SOW is the source of truth.
2. Only executable scope becomes project-plan activities.
3. Commercials, exclusions, responsibilities, assumptions, risks, gaps and acceptance criteria are not activities.
4. Explicit SOW milestones are preserved separately from tasks.
5. AI is advisory; deterministic logic produces the consistent full plan.
6. PostgreSQL is supported through `DATABASE_URL`; SQLite is the no-setup fallback.
7. No configuration or database details are shown in the end-user UI.
