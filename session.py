"""
session.py

Current user context.

Right now this always returns user_id=1 (single-user app).
When auth is added, replace current_user_id() to read from
st.session_state or a JWT/cookie — every other file just calls this function.
"""


def current_user_id() -> int:
    return 1
