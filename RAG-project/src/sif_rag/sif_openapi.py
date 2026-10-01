"""Client for the KOSHA SIF archive OpenAPI."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://apis.data.go.kr/B552468/sifArchive/view"
CALL_API_ID = "1170"
SOURCE_URL = "https://www.data.go.kr/data/15161362/openapi.do"


def load_local_env(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without overwriting the current shell environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, value = entry.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class SIFCase:
    cateSeNm: str = ""
    sifLclsfNm: str = ""
    sifMclsfNm: str = ""
    sifSclsfNm: str = ""
    disasterType: str = ""
    disasterOverview: str = ""
    orgtNm: str = ""
    situation: str = ""
    disasterFactor: str = ""
    dcrsCntrplnCn: str = ""

    @property
    def case_id(self) -> str:
        stable = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)
        return sha256(stable.encode("utf-8")).hexdigest()[:20]

    def page_content(self) -> str:
        labels = (
            ("업종 구분", self.cateSeNm),
            ("산재업종 대분류", self.sifLclsfNm),
            ("산재업종 중분류", self.sifMclsfNm),
            ("산재업종 소분류", self.sifSclsfNm),
            ("재해종류", self.disasterType),
            ("재해개요", self.disasterOverview),
            ("기인물", self.orgtNm),
            ("고위험작업·상황", self.situation),
            ("재해유발요인", self.disasterFactor),
            ("위험성 감소대책", self.dcrsCntrplnCn),
        )
        return "\n".join(f"{label}: {value}" for label, value in labels if value)

    @classmethod
    def from_api(cls, row: dict[str, Any]) -> "SIFCase":
        fields = cls.__dataclass_fields__
        return cls(**{key: str(row.get(key) or "").strip() for key in fields})


class SIFOpenAPI:
    def __init__(self, service_key: str | None = None, category_code: str = "1") -> None:
        load_local_env()
        self.service_key = service_key or os.getenv("DATA_GO_KR_SERVICE_KEY", "")
        if not self.service_key:
            raise ValueError(
                "DATA_GO_KR_SERVICE_KEY가 없습니다. .env에 공공데이터포털 발급 키를 설정하세요."
            )
        self.category_code = category_code

    def _get_page(self, keyword: str, page_no: int, rows: int) -> tuple[list[dict[str, Any]], int]:
        params = urlencode(
            {
                "serviceKey": self.service_key,
                "callApiId": CALL_API_ID,
                "cateSeCd": self.category_code,
                "disasterOverview": keyword,
                "pageNo": page_no,
                "numOfRows": rows,
                "_type": "json",
            }
        )
        request = Request(f"{BASE_URL}?{params}", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as exc:
            raise RuntimeError(f"SIF API HTTP 오류 ({exc.code})") from exc
        except URLError as exc:
            raise RuntimeError(f"SIF API 연결 오류: {exc.reason}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("SIF API 응답을 JSON으로 읽지 못했습니다. 응답 형식과 키 권한을 확인하세요.") from exc

        response_data = payload.get("response", payload)
        header = response_data.get("header", {})
        result_code = str(header.get("resultCode", "00"))
        if result_code not in {"00", "0", "200"}:
            raise RuntimeError(
                f"SIF API 오류 {result_code}: {header.get('resultMsg', '메시지 없음')}"
            )

        body = response_data.get("body", {})
        total_count = int(body.get("totalCount") or 0)
        item = body.get("items", {}).get("item", [])
        if isinstance(item, dict):
            item = [item]
        return list(item or []), total_count

    def search(self, keyword: str, rows: int = 100, max_pages: int = 3) -> Iterator[SIFCase]:
        """Search by incident overview. A keyword search is not a complete archive export."""
        keyword = keyword.strip()
        if not keyword:
            raise ValueError("검색어가 비어 있습니다.")
        if not 1 <= rows <= 1000:
            raise ValueError("rows는 1~1000 사이여야 합니다.")
        if max_pages < 1:
            raise ValueError("max_pages는 1 이상이어야 합니다.")

        seen: set[str] = set()
        for page_no in range(1, max_pages + 1):
            raw_rows, total_count = self._get_page(keyword, page_no, rows)
            for raw_row in raw_rows:
                case = SIFCase.from_api(raw_row)
                if case.page_content() and case.case_id not in seen:
                    seen.add(case.case_id)
                    yield case
            if not raw_rows or page_no * rows >= total_count:
                break
            time.sleep(0.15)


def collect_queries(
    client: SIFOpenAPI,
    queries: list[str],
    output_path: Path,
    rows: int = 100,
    max_pages: int = 3,
) -> int:
    """Collect seeded searches into an append-only JSONL file, deduplicated by content."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids: set[str] = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8") as source:
            for line in source:
                if line.strip():
                    existing_ids.add(json.loads(line)["case_id"])

    added = 0
    with output_path.open("a", encoding="utf-8", newline="\n") as target:
        for query in queries:
            for case in client.search(query, rows=rows, max_pages=max_pages):
                if case.case_id in existing_ids:
                    continue
                record = {
                    "case_id": case.case_id,
                    "source_url": SOURCE_URL,
                    "retrieved_query": query,
                    "category_code": client.category_code,
                    "fields": asdict(case),
                    "page_content": case.page_content(),
                }
                target.write(json.dumps(record, ensure_ascii=False) + "\n")
                existing_ids.add(case.case_id)
                added += 1
            time.sleep(0.15)
    return added


def read_queries(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]

