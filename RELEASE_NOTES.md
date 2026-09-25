# SOW → Project Planner v11.3 — Database/Visit Counter Hotfix

## Fix
- Restored the complete production `app.py` from the v11 release candidate.
- Restored the cached `database()` function used by `main()`.
- Reconnected visitor counting to the existing persistent `db.py` `record_visit()` function.
- Removed the external visitor-counter HTTP dependency and `requests` import.
- Counts one visit per Streamlit browser session and excludes `?bot=wake` traffic.
- Visitor analytics failures cannot prevent the planner from loading.
- Added visible runtime marker: Release v11.3.

## Validation
- Python compilation: PASS
- Static database-call check: PASS
- Visitor-counter integration check: PASS
