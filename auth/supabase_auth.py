
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()

_SESSION_USER_ID_KEY = "user_id"
_SESSION_ACCESS_TOKEN_KEY = "access_token"


def _is_dns_or_addr_failure(exc: BaseException) -> bool:
    seen: set[int] = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if getattr(cur, "errno", None) == 11001:
            return True
        if "getaddrinfo failed" in str(cur).lower():
            return True
        cur = (
            getattr(cur, "__cause__", None)
            or getattr(cur, "__context__", None)
        )
    return False


def _format_supabase_error(exc: BaseException, fallback: str) -> str:
    msg = str(exc).strip() or fallback
    low = msg.lower()

    if _is_dns_or_addr_failure(exc):
        return (
            "Network/DNS error (getaddrinfo failed). This app uses **supabase-py** over "
            "HTTPS, not direct Postgres. Set `SUPABASE_URL` to the **Project URL** "
            "(`https://YOUR_REF.supabase.co` from Dashboard → Settings → API), **not** a "
            "`postgresql://…pooler…` string. (Pooler URIs with user `postgres.YOUR_REF` "
            "are auto-converted—restart Streamlit after changing `.env`.) Also check "
            "firewall/VPN if the URL is already correct."
        )
    if "duplicate key" in low or "unique constraint" in low or "23505" in msg:
        return "An account with this email already exists."
    if "invalid url" in low or "invalid_url" in low:
        return (
            "Supabase URL is invalid or was not loaded. Put a `.env` file in the project "
            f"folder (next to `app.py`) with `SUPABASE_URL=https://YOUR_REF.supabase.co` "
            f"and restart the app. Current project root: {_PROJECT_ROOT}"
        )
    if "permission denied" in low or "401" in msg or "403" in msg:
        return (
            "Supabase refused the request. Check SUPABASE_URL and your API key "
            "(service_role for server-side inserts/selects)."
        )
    return msg[:500] if len(msg) > 500 else msg


def _rest_url_from_supabase_postgres_uri(raw: str) -> Optional[str]:
    
    u = raw.strip().strip('"').strip("'")
    low = u.lower()
    if not low.startswith(("postgres://", "postgresql://")):
        return None

    parsed = urlparse(u)
    user_part = parsed.username or ""
    if user_part.startswith("postgres.") and len(user_part) > len("postgres."):
        project_ref = user_part.split("postgres.", 1)[1].strip()
        if project_ref and project_ref.replace("_", "").isalnum():
            return f"https://{project_ref}.supabase.co".rstrip("/")
    return None


def _normalize_supabase_url(raw: str) -> str:
    
    u = raw.strip().strip('"').strip("'")
    if not u:
        return ""

    rest_from_pg = _rest_url_from_supabase_postgres_uri(u)
    if rest_from_pg:
        return rest_from_pg

    low = u.lower()
    if low.startswith(("postgres://", "postgresql://")):
        raise ValueError(
            "SUPABASE_URL must be the **HTTPS Project URL** for Supabase REST (used by "
            "supabase-py), not a PostgreSQL connection string. In the Supabase Dashboard: "
            "**Project Settings → API → Project URL** — it looks like "
            "`https://xxxxxxxx.supabase.co`. Optionally use a pool URI where the username "
            "is `postgres.YOUR_PROJECT_REF` and this app will infer the HTTPS URL."
        )

    if not u.startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            "SUPABASE_URL must be a full URL, e.g. https://YOUR_PROJECT_REF.supabase.co "
            "(Dashboard → Project Settings → API → Project URL)."
        )
    host = parsed.netloc.split("@")[-1]
    if not host.endswith(".supabase.co") and "localhost" not in host:
        pass
    return u.rstrip("/")


def get_supabase_client() -> Client:
    url = _normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip().strip('"').strip("'")
        or os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")
    )
    if not url:
        raise ValueError(
            "SUPABASE_URL is missing or empty. Create `.env` in the project root "
            f"{_PROJECT_ROOT} with SUPABASE_URL=https://....supabase.co"
        )
    if not key:
        raise ValueError(
            "No Supabase key found. Set SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) "
            "in .env (Dashboard → Project Settings → API → service_role)."
        )
    try:
        return create_client(url, key)
    except Exception as e:
        low = str(e).lower()
        if "invalid url" in low:
            raise ValueError(
                "SUPABASE_URL could not be parsed. Use the exact Project URL from Supabase, "
                f"e.g. `https://xxxxx.supabase.co` in {_PROJECT_ROOT / '.env'}"
            ) from e
        raise


def get_current_user_id() -> Optional[str]:
    uid = st.session_state.get(_SESSION_USER_ID_KEY)
    return str(uid) if uid else None


def sign_up(email: str, password: str) -> str:
    
    email_clean = email.strip().lower()
    password_str = password
    if not email_clean:
        raise ValueError("Email is required.")
    if not password_str:
        raise ValueError("Password is required.")

    try:
        sb = get_supabase_client()
        existing = (
            sb.table("users").select("id").eq("email", email_clean).limit(1).execute()
        )
        if getattr(existing, "data", None):
            raise ValueError("Email is already registered. Try signing in instead.")

        inserted = (
            sb.table("users")
            .insert({"email": email_clean, "password": password_str})
            .select("id")
            .execute()
        )
        rows = getattr(inserted, "data", None) or []
        if not rows or "id" not in rows[0]:
            raise RuntimeError(
                "Sign-up succeeded but no user id was returned. Check Supabase policies "
                "and inserts on public.users."
            )
        user_id = str(rows[0]["id"])
        return user_id
    except ValueError:
        raise
    except BaseException as e:
        err_text = str(e).lower()
        if "duplicate key" in err_text or "23505" in err_text:
            raise ValueError(
                "An account with this email already exists."
            ) from e
        raise RuntimeError(_format_supabase_error(e, "Sign-up failed.")) from e


def sign_in(email: str, password: str) -> Dict[str, Any]:
    
    email_clean = email.strip().lower()
    if not email_clean:
        raise ValueError("Email is required.")
    if not password:
        raise ValueError("Password is required.")

    try:
        sb = get_supabase_client()
        result = (
            sb.table("users")
            .select("id", "email", "password")
            .eq("email", email_clean)
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        if not rows:
            raise ValueError("Invalid email or password.")
        row = rows[0]
        if row.get("password") != password:
            raise ValueError("Invalid email or password.")

        user_id = str(row["id"])
        return {"user_id": user_id, "email": row.get("email", email_clean)}
    except ValueError:
        raise
    except BaseException as e:
        raise RuntimeError(_format_supabase_error(e, "Sign-in failed.")) from e


def sign_out() -> None:
    for k in (
        _SESSION_USER_ID_KEY,
        _SESSION_ACCESS_TOKEN_KEY,
        "messages",
        "authenticated",
    ):
        if k in st.session_state:
            del st.session_state[k]


def issue_session_after_sign_in(user_id: str) -> str:
    
    token = str(uuid.uuid4())
    st.session_state[_SESSION_USER_ID_KEY] = user_id
    st.session_state[_SESSION_ACCESS_TOKEN_KEY] = token
    st.session_state["authenticated"] = True
    return token
