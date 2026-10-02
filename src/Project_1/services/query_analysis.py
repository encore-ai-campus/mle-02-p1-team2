"""작업·장비 질문을 두 Retriever가 쓸 Work Context로 변환한다."""

from dataclasses import dataclass


EQUIPMENT_ALIASES = {
    "고소작업대": ("고소작업대", "스카이차"),
    "지게차": ("지게차", "포크리프트"),
    "굴착기": ("굴착기", "굴삭기", "백호우"),
    "컨베이어": ("컨베이어", "컨베어"),
    "사다리": ("사다리",),
    "비계": ("비계",),
    "크레인": ("크레인", "기중기"),
    "전기설비": ("전기설비", "전기작업", "전선", "정전", "활선"),
    "용접기": ("용접기", "절단기"),
    "작업발판": ("작업발판",),
}
EQUIPMENT_CATEGORY = {
    "고소작업대": "고소작업대", "지게차": "지게차", "굴착기": "굴착기",
    "사다리": "작업발판·비계·사다리", "비계": "작업발판·비계·사다리",
    "작업발판": "작업발판·비계·사다리", "크레인": "크레인·줄걸이",
    "전기설비": "전기작업", "용접기": "용접·용단",
}
WORK_RULES = (
    ("용접·용단", ("용접", "용단", "화기작업")),
    ("정전·전기보수", ("정전", "전기설비", "전기작업", "활선")),
    ("줄걸이·인양", ("줄걸이", "인양", "양중")),
    ("굴착·터파기", ("굴착", "터파기", "토공")),
    ("컨베이어 정비·청소", ("컨베이어", "컨베어")),
    ("고소작업·설비 교체", ("고소작업대", "스카이차")),
    ("운반·하역", ("운반", "하역", "적재", "상하차", "팔레트")),
    ("비계·작업발판 작업", ("비계", "작업발판")),
    ("사다리 승강·작업", ("사다리",)),
)
HAZARD_ALIASES = {
    "추락": ("추락", "떨어짐", "떨어질"),
    "충돌·깔림": ("충돌", "부딪", "깔림"),
    "끼임": ("끼임", "협착"),
    "화재·폭발": ("화재", "폭발", "가연", "인화"),
    "감전": ("감전",),
    "매몰·붕괴": ("매몰", "붕괴", "굴착면"),
    "낙하": ("낙하", "떨어지는 자재"),
    "전도": ("전도", "전복"),
}
INTENT_TERMS = {
    "점검": "작업 전 점검사항 안전장치 확인 사전조사",
    "예방": "사고 예방 안전조치 금지사항 작업방법",
    "위험": "작업 위험요인 안전조치 작업방법",
    "일반": "안전작업 방법 점검사항 예방조치",
}


@dataclass(frozen=True)
class WorkContext:
    original_question: str
    resolved_question: str
    equipment: str | None
    work_type: str | None
    hazard: tuple[str, ...]
    intent: str
    kosha_category: str | None
    sif_query: str
    kosha_query: str


def analyze_query(question: str, resolved_question: str | None = None) -> WorkContext:
    """명시된 작업·장비를 먼저 읽고 안전 분야별 검색 문장을 따로 만든다."""
    resolved = (resolved_question or question).strip()
    text = resolved.lower()
    equipment = next(
        (name for name, aliases in EQUIPMENT_ALIASES.items() if any(alias in text for alias in aliases)), None
    )
    work_type = next((name for name, aliases in WORK_RULES if any(alias in text for alias in aliases)), None)
    hazards = tuple(name for name, aliases in HAZARD_ALIASES.items() if any(alias in text for alias in aliases))
    # 후속 질문의 요청 목적은 이전 작업 설명보다 현재 발화를 우선한다.
    intent_text = question.lower() if any(term in question.lower() for term in (
        "작업 전", "사전", "점검", "확인", "예방", "방지", "조치", "막으", "위험", "사고"
    )) else text
    if any(term in intent_text for term in ("작업 전", "사전", "점검", "확인")):
        intent = "점검"
    elif any(term in intent_text for term in ("예방", "방지", "조치", "막으")):
        intent = "예방"
    elif any(term in intent_text for term in ("위험", "사고")):
        intent = "위험"
    else:
        intent = "일반"
    category = EQUIPMENT_CATEGORY.get(equipment)
    if category is None:
        if work_type == "용접·용단":
            category = "용접·용단"
        elif work_type == "정전·전기보수":
            category = "전기작업"
        elif work_type == "줄걸이·인양":
            category = "크레인·줄걸이"

    core = " ".join(part for part in (equipment, work_type, *hazards) if part)
    sif_query = f"{core} 산업재해 유사 사고사례 사고 원인 재해유발요인".strip()
    kosha_query = f"{core} {INTENT_TERMS[intent]}".strip()
    return WorkContext(question.strip(), resolved, equipment, work_type, hazards, intent,
                       category, sif_query, kosha_query)
