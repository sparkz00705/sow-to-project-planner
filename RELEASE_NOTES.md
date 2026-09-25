# SOW → Project Planner v11.2

## Visitor counter fix
- Restores persistent visitor counting using the existing database `record_visit()` function.
- Counts one visit per Streamlit session to avoid rerun inflation.
- Excludes `?bot=wake` traffic.
- The old external visitor-counter service is not used.
- If analytics storage is unavailable, the app safely displays 0 without blocking the planner.

## Deployment
Replace `app.py` and `planner.py` in the Streamlit-connected GitHub repository.
The existing `db.py` must remain in place; it already provides `record_visit()`.
