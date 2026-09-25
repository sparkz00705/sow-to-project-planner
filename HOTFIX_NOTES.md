# SOW → Project Planner v11.4 Hotfix

Fixes the deployed NameError: `database is not defined`.

The prior deployed app called `database()` but the function was missing. This hotfix adds the database initializer back into `app.py` using the existing `db.init_db()` implementation.

No planner logic is changed.
