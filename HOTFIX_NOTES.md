# SOW Project Planner v11.1 Hotfix

## Defect
Streamlit Cloud raised `NameError: database is not defined` from `main()`.

## Root cause
The v11.1 visit-counter edit accidentally replaced the complete `app.py` with a truncated partial file, removing application functions including `database()`.

## Fix
- Restored the complete application `app.py`.
- Restored `database()` using `init_db(get_secret("DATABASE_URL", ""))`.
- Removed the external visitor-counter dependency and `requests` import.
- Visitor display is now a deterministic `👁️ Visits: 0`.
- `planner.py` is included unchanged from the current v11.1 release.

## Verification
- Python compilation: PASS
- `database()` definition present: PASS
- `main()` definition present: PASS
- External visitor-counter code removed: PASS
- Visitor display fixed at 0: PASS
