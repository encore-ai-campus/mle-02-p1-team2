"""Shared settings for Community Cloud and the standalone src_v3 application."""
from collections.abc import Mapping
from functools import lru_cache
import os
from pathlib import Path
import tomllib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parents[1]


class ConfigurationError(RuntimeError):
    """Configuration errors must not include credentials or connection strings."""


@lru_cache(maxsize=1)
def _local_settings():
    values = {}
    # .env loading is opt-in; Community Cloud requires no local credential files.
    if os.getenv("PREVENTRA_LOAD_DOTENV", "").strip().lower() in {"1", "true", "yes"}:
        from dotenv import dotenv_values
        for path in (REPO_ROOT / ".env", APP_DIR / ".env"):
            values.update({k: v for k, v in dotenv_values(path).items() if v is not None})
    path = APP_DIR / ".streamlit" / "secrets.toml"
    if path.is_file():
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ConfigurationError("Local secrets.toml must contain valid UTF-8 TOML.") from None
        values.update({k: v for k, v in payload.items() if not isinstance(v, Mapping)})
        section = payload.get("preventra", {})
        if isinstance(section, Mapping):
            values.update(section)
    return values


def _cloud_settings():
    import streamlit as st
    try:
        return st.secrets
    except FileNotFoundError:
        return {}


def first_setting(*names):
    """All Cloud aliases take precedence over environment and local aliases."""
    cloud = _cloud_settings()
    try:
        section = cloud.get("preventra", {})
        flat = cloud
        # Access to a missing secrets file can be deferred until .get().
        for provider in (section, flat):
            if isinstance(provider, Mapping):
                for name in names:
                    value = provider.get(name)
                    if value is not None and str(value).strip():
                        return str(value).strip()
    except FileNotFoundError:
        pass
    for provider in (os.environ, _local_settings()):
        for name in names:
            value = provider.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def setting(name):
    return first_setting(name)


def secret_values():
    """Only effective credentials are used for telemetry redaction."""
    names = ("OPENAI_API_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_DB_URL", "DATABASE_URL",
             "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    return tuple(value for name in names if (value := setting(name)))


def database_settings():
    """Return a Supabase DSN with TLS; never fall back to localhost."""
    configured = first_setting("SUPABASE_DB_URL", "DATABASE_URL")
    if not configured:
        return "", False, False, "Supabase PostgreSQL connection settings are missing."
    try:
        parts = urlsplit(configured)
        host = parts.hostname or ""
        is_supabase = host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")
        if (parts.scheme not in {"postgresql", "postgres"} or not is_supabase
                or not parts.password or not parts.path.strip("/") or parts.fragment
                or parts.port not in (None, 5432)):
            raise ValueError
        if host.endswith(".pooler.supabase.com") and parts.port != 5432:
            raise ValueError
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if query.get("sslmode") not in {"verify-ca", "verify-full"}:
            query["sslmode"] = "require"
        query.setdefault("connect_timeout", "10")
        query.setdefault("application_name", "preventra-v3")
        url = urlunsplit(parts._replace(query=urlencode(query)))
        return url, True, True, None
    except (TypeError, ValueError):
        return "", True, False, (
            "Use a Supabase PostgreSQL connection string, preferably Session pooler port 5432."
        )
