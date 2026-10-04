"""Preventra requires Supabase; legacy applications keep their own defaults."""
from urllib.parse import unquote, urlsplit


class CloudConfigurationError(RuntimeError):
    """Safe error text: never include a secret, hostname or connection string."""


def validate_database_url(database_url, supabase_url):
    try:
        api = urlsplit(supabase_url or "")
        db = urlsplit(database_url or "")
        if (api.scheme != "https" or not (api.hostname or "").endswith(".supabase.co")
                or api.path not in ("", "/") or api.query or api.fragment or api.username or api.password
                or api.port not in (None, 443)):
            raise ValueError
        project = api.hostname.removesuffix(".supabase.co")
        host = db.hostname or ""
        pooler = host.endswith(".pooler.supabase.com")
        same_project = (unquote(db.username or "").endswith("." + project) if pooler
                        else host == f"db.{project}.supabase.co")
        if (db.scheme not in ("postgresql", "postgres") or db.port not in (None, 5432)
                or not same_project or not db.password or not db.path.strip("/")
                or db.fragment):
            raise ValueError
    except (ValueError, TypeError):
        raise CloudConfigurationError(
            "같은 Supabase 프로젝트의 PostgreSQL DATABASE_URL이 필요합니다. "
            "Connect 메뉴의 Session pooler(5432) 연결 문자열을 Cloud Secrets에 설정해 주세요."
        ) from None


def require_database():
    from services.safety_rag import DB_URL, DB_CONFIG_ERROR, DATABASE_URL_CONFIGURED, setting
    if not DATABASE_URL_CONFIGURED or DB_CONFIG_ERROR:
        raise CloudConfigurationError("Supabase PostgreSQL DATABASE_URL 또는 SUPABASE_DB_URL 설정을 확인해 주세요.")
    validate_database_url(DB_URL, setting("SUPABASE_URL"))
    return DB_URL


def require_storage():
    from services.safety_rag import setting
    if not all(setting(name) for name in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_STORAGE_BUCKET")):
        raise CloudConfigurationError("Supabase 통계 저장소 설정이 필요합니다. 로컬 파일로 대체하지 않습니다.")


def load_cloud_statistics():
    from services.statistics import load_statistics
    require_storage()
    return load_statistics()
