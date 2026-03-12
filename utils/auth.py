"""
Authentication & role-based access control for the NSIA dashboard.

Roles:
    admin     — Full access, can edit exceptions and all settings
    board     — All pages, read-only on editable sections
    club_rep  — Ice Utilization (own club section only) + limited pages

Usage in any page:
    from utils.auth import require_auth, has_role, get_user_club

    user = require_auth()          # blocks page if not logged in
    if has_role("admin"):          # check permissions
        st.data_editor(...)        # show editable widget
    club = get_user_club()         # "Winnetka", "Wilmette", or None
"""

import os
import streamlit as st
import streamlit_authenticator as stauth
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "auth.yaml")

# Pages each role can access (page file stems, lowercase).
# None means all pages.
ROLE_PAGES = {
    "admin": None,  # all pages
    "board": None,  # all pages
    "club_rep": [
        "1_financial_overview",
        "4_operations",
        "9_ice_utilization",
    ],
}

# Map usernames to their club affiliation (for club_rep filtering)
USER_CLUBS = {
    "winnetka": "Winnetka",
    "wilmette": "Wilmette",
}


def _load_config():
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _get_role(username: str) -> str:
    """Look up role from the config for a given username."""
    config = _load_config()
    user_entry = config.get("credentials", {}).get("usernames", {}).get(username, {})
    return user_entry.get("role", "board")


def init_authenticator():
    """Create and return the authenticator object. Call once in app.py."""
    config = _load_config()
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
    return authenticator


def require_auth(allowed_roles=None):
    """Gate a page behind authentication. Returns username if authorized.

    Args:
        allowed_roles: list of role strings that can access this page.
                       None means any authenticated user.

    Returns the username, or stops the page with st.stop().
    """
    if not st.session_state.get("authentication_status"):
        st.warning("Please log in from the Home page to access this content.")
        st.stop()

    username = st.session_state.get("username", "")
    role = _get_role(username)

    if allowed_roles and role not in allowed_roles:
        st.error("You don't have permission to view this page.")
        st.stop()

    return username


def has_role(*roles) -> bool:
    """Check if the current user has one of the given roles."""
    username = st.session_state.get("username", "")
    if not username:
        return False
    user_role = _get_role(username)
    return user_role in roles


def get_user_role() -> str:
    """Return the current user's role, or empty string."""
    username = st.session_state.get("username", "")
    if not username:
        return ""
    return _get_role(username)


def get_user_club() -> str | None:
    """Return the club name for club_rep users, or None for admin/board."""
    username = st.session_state.get("username", "")
    return USER_CLUBS.get(username)


def can_access_page(page_stem: str) -> bool:
    """Check if the current user can access a given page."""
    role = get_user_role()
    if not role:
        return False
    allowed = ROLE_PAGES.get(role)
    if allowed is None:
        return True  # all pages
    return page_stem.lower() in allowed
