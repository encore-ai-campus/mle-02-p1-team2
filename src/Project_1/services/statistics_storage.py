"""Private Supabase Storage에서 통계 CSV를 읽는다."""
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dotenv import load_dotenv
import os
import streamlit as st

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class StatisticsStorageError(RuntimeError):
    """키나 응답 본문을 포함하지 않는 Storage 오류."""


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _setting(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None
    return str(value) if value else os.getenv(name)


def download_csvs(files: dict[tuple[str, int], str]) -> dict[tuple[str, int], bytes] | None:
    """Storage 설정이 없으면 None, 설정되면 모든 지정 파일을 내려받는다."""
    base = (_setting("SUPABASE_URL") or "").rstrip("/")
    key = _setting("SUPABASE_SECRET_KEY")
    bucket = _setting("SUPABASE_STORAGE_BUCKET")
    if not any((base, key, bucket)):
        return None
    if not all((base, key, bucket)):
        raise StatisticsStorageError("Storage 주소·서버 키·버킷 설정이 모두 필요합니다.")
    address = urlsplit(base)
    if (address.scheme != "https"
            or not (address.hostname or "").endswith(".supabase.co")
            or address.path or address.query or address.fragment
            or address.username or address.password or address.port not in (None, 443)):
        raise StatisticsStorageError("Storage 프로젝트 주소 형식을 확인해 주세요.")
    if not key.startswith("sb_secret_"):
        raise StatisticsStorageError("Storage 서버용 Secret key 설정을 확인해 주세요.")

    opener = build_opener(_NoRedirects())
    contents = {}
    for source, filename in files.items():
        url = (f"{base}/storage/v1/object/authenticated/"
               f"{quote(bucket, safe='')}/{quote(filename, safe='/')}")
        request = Request(url, headers={"apikey": key})
        try:
            with opener.open(request, timeout=30) as response:
                contents[source] = response.read()
        except HTTPError as error:
            raise StatisticsStorageError(
                f"통계 파일 {filename}을 읽지 못했습니다 (HTTP {error.code})."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise StatisticsStorageError("통계 저장소에 연결하지 못했습니다.") from None
    return contents
