"""M8 앱 - 대시보드 + RAG 챗봇 (Streamlit)

실행 (프로젝트 폴더 unit1_project 에서):
    streamlit run app/app.py

필요한 것:
  - data/processed/*.csv           (M2 전처리 결과)
  - data/analysis/m3_*.csv         (M3 분석 결과)
  - data/chroma                    (M4/M7 벡터DB. sif_v3 → sif_v2 → sif 순서로 있는 것을 사용)
  - .env 의 OPENAI_API_KEY         (챗봇에만 필요. 없어도 대시보드는 동작)
"""
import os
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# ── 0. 페이지 기본 설정 (가장 먼저 한 번만) ────────────────────────────
st.set_page_config(page_title="산업재해 사례 검색 · 분석", layout="wide")

# ── 1. 프로젝트 폴더 찾기 ──────────────────────────────────────────────
# app.py 위치에서 위로 올라가며 data/processed 가 있는 폴더를 찾는다.
def find_root():
    env = os.getenv("APP_ROOT")
    if env and (Path(env) / "data" / "processed").exists():
        return Path(env)
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents, Path.cwd(), *Path.cwd().parents]:
        if (p / "data" / "processed").exists():
            return p
    return None

ROOT = find_root()
if ROOT is None:
    st.error("data/processed 폴더를 찾지 못했습니다. unit1_project 폴더 안에서 실행하거나 APP_ROOT 환경변수를 지정하세요.")
    st.stop()

NO_EVIDENCE = "제공된 사례에서 근거를 찾을 수 없습니다."
MIN_SIM = 0.40            # 05 노트북 5-1절에서 정한 값: 범위 밖 최고 0.353 < 0.40 < 범위 안 최저 0.438
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

# ── 2. 데이터 읽기 (한 번 읽고 캐시) ───────────────────────────────────
def read_csv(path):
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")


@st.cache_data
def load_cases():
    """사고사례 6,032건 (제조업등 + 건설업). 대시보드 집계에 필요한 열만 쓴다."""
    # 맥은 한글 파일명이 분해형(NFD)이라 '1_SIF' 로만 찾는다 (두 파일 모두 이 접두어로 시작)
    files = sorted((ROOT / "data" / "processed").glob("1_SIF*.csv"))
    frames = []
    for f in files:
        d = read_csv(f)
        frames.append(d[["업종구분", "기인물_표준", "재해연도"]])
    df = pd.concat(frames, ignore_index=True)
    df["재해연도"] = pd.to_numeric(df["재해연도"], errors="coerce")
    return df.dropna(subset=["재해연도"]).astype({"재해연도": int})


@st.cache_data
def load_deaths():
    """규모별 사고사망자수 (3번 파일)를 '규모, 연도, 사망자' 긴 형태로 바꾼다."""
    f = sorted((ROOT / "data" / "processed").glob("3_*.csv"))[0]
    d = read_csv(f)
    years = [c for c in d.columns if re.fullmatch(r"\d{4}년", str(c))]
    long = d.melt(id_vars="구분", value_vars=years, var_name="연도", value_name="사망자")
    long["연도"] = long["연도"].str[:4].astype(int)
    long["사망자"] = pd.to_numeric(long["사망자"].astype(str).str.replace(",", ""), errors="coerce")
    long = long.rename(columns={"구분": "규모"}).dropna(subset=["사망자"])
    return long, list(d["구분"])          # 두 번째 값: 파일에 적힌 규모 순서


@st.cache_data
def load_per_site():
    """규모별 사업장 1,000곳당 재해자수 (M3 분석 결과)."""
    for f in sorted((ROOT / "data" / "analysis").glob("m3_*.csv")):
        d = read_csv(f)
        if "사업장 1,000곳당 재해자수" in d.columns:
            d = d.rename(columns={d.columns[0]: "규모"})
            return d[["규모", "사업장 1,000곳당 재해자수"]]
    return None


def draw(chart):
    """차트를 칸 너비에 맞춰 그린다 (altair 쪽 container 너비 사용 → streamlit 버전에 덜 민감)."""
    st.altair_chart(chart.properties(width="container", height=300))


cases = load_cases()
deaths, size_order = load_deaths()
per_site = load_per_site()
YMIN, YMAX = int(deaths["연도"].min()), int(deaths["연도"].max())      # 2004~2025

# ── 3. 사이드바: 두 탭이 함께 쓰는 필터 ────────────────────────────────
with st.sidebar:
    st.header("필터")
    industry = st.selectbox("업종", ["전체", "제조업등", "건설업"])
    year_range = st.slider("재해 연도", YMIN, YMAX, (YMIN, YMAX))
    st.caption("사고사례는 2013~2024년, 사망자 통계는 2004~2025년 자료입니다.")
    st.divider()
    st.header("검색 설정")
    top_k = st.slider("근거 사례 수 (k)", 1, 5, 3)
    st.caption(f"유사도 {MIN_SIM:.2f} 미만의 사례는 근거로 쓰지 않습니다.")

st.title("산업재해 사례 검색 · 분석")
st.caption("산업재해 사례를 근거로 답하는 RAG 챗봇과 분석 대시보드")

tab_dash, tab_chat = st.tabs(["대시보드", "챗봇"])

# ── 4. 대시보드 ────────────────────────────────────────────────────────
with tab_dash:
    y0, y1 = year_range
    cf = cases[(cases["재해연도"] >= y0) & (cases["재해연도"] <= y1)]
    if industry != "전체":
        cf = cf[cf["업종구분"] == industry]

    # 핵심 지표 4개
    st.subheader("핵심 지표")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("분석 사례 수", f"{len(cf):,}건")

    tot = deaths.groupby("연도")["사망자"].sum()
    if y1 in tot.index:
        k2.metric(f"{y1}년 사고사망자", f"{int(tot[y1]):,}명")
    else:
        k2.metric(f"{y1}년 사고사망자", "—")

    top = cf["기인물_표준"].dropna().value_counts()
    if len(top):
        k3.metric("가장 많은 기인물", top.index[0], f"{top.iloc[0] / len(cf) * 100:.1f}%", delta_color="off")
    else:
        k3.metric("가장 많은 기인물", "—")

    if y0 in tot.index and y1 in tot.index and y0 != y1 and tot[y0] > 0:
        chg = (tot[y1] - tot[y0]) / tot[y0] * 100
        k4.metric(f"사망자 변화 ({y0}→{y1})", f"{chg:+.1f}%", f"{int(tot[y1] - tot[y0]):+,}명", delta_color="inverse")
    else:
        k4.metric("사망자 변화", "—")

    if len(cf) == 0:
        st.info("선택한 조건에 맞는 사고사례가 없습니다. 사이드바 필터를 넓혀 보세요.")

    # 차트 4개 (2열 배치)
    st.subheader("차트")
    left, right = st.columns(2)

    with left:
        st.markdown("**연도별 사고사례 수**")
        by_year = cf.groupby(["재해연도", "업종구분"]).size().reset_index(name="건수")
        if len(by_year):
            draw(
                alt.Chart(by_year).mark_bar().encode(
                    x=alt.X("재해연도:O", title="재해연도"),
                    y=alt.Y("건수:Q", title="사례 수"),
                    color=alt.Color("업종구분:N", title="업종"),
                    tooltip=["재해연도", "업종구분", "건수"],
                ),
            )
        else:
            st.caption("표시할 데이터가 없습니다.")

    with right:
        st.markdown("**기인물 상위 10** (분류 불가 제외)")
        topn = top.head(10).rename_axis("기인물").reset_index(name="건수")
        if len(topn):
            draw(
                alt.Chart(topn).mark_bar().encode(
                    y=alt.Y("기인물:N", sort="-x", title=None),
                    x=alt.X("건수:Q", title="사례 수"),
                    tooltip=["기인물", "건수"],
                ),
            )
        else:
            st.caption("표시할 데이터가 없습니다.")

    left2, right2 = st.columns(2)
    with left2:
        st.markdown(f"**규모별 사고사망자수** ({y0}~{y1}년 합계)")
        dsel = deaths[(deaths["연도"] >= y0) & (deaths["연도"] <= y1)].groupby("규모", as_index=False)["사망자"].sum()
        draw(
            alt.Chart(dsel).mark_bar().encode(
                x=alt.X("규모:N", sort=size_order, title="사업장 규모"),
                y=alt.Y("사망자:Q", title="사고사망자수(명)"),
                tooltip=["규모", "사망자"],
            ),
        )
        st.caption("사망자 통계는 업종과 무관한 규모별 자료입니다.")

    with right2:
        st.markdown("**규모별 사업장 1,000곳당 재해자수**")
        if per_site is not None:
            draw(
                alt.Chart(per_site).mark_bar().encode(
                    x=alt.X("규모:N", sort=size_order, title="사업장 규모"),
                    y=alt.Y("사업장 1,000곳당 재해자수:Q", title="재해자수"),
                    tooltip=["규모", "사업장 1,000곳당 재해자수"],
                ),
            )
        else:
            st.caption("data/analysis 에서 M3 결과 파일을 찾지 못했습니다.")
        st.caption("전체 기간 기준이라 연도·업종 필터와 무관합니다.")

# ── 5. 챗봇: 05 노트북의 RAG 체인을 그대로 옮긴 것 ─────────────────────
SYSTEM = """당신은 산업재해 예방을 돕는 안전 어시스턴트입니다. 아래 [사례]에 적힌 내용만 근거로 답하세요.
- 사고 사례 질문은 '1) 사고 원인', '2) 예방 대책' 순서로 쓰고, 각 항목마다 근거가 된 사례 번호를 [사례N] 형식으로 표시하세요.
- [통계] 자료에 대한 질문은 표에 적힌 숫자를 그대로 인용하고 [사례N]을 표시하세요. 원인·대책 형식은 쓰지 않아도 됩니다.
- 사례에 없는 내용은 추측하거나 지어내지 마세요. 법령 조항 번호도 사례에 없으면 쓰지 마세요.
- 사례만으로 질문에 답할 수 없으면 다른 말 없이 정확히 '제공된 사례에서 근거를 찾을 수 없습니다.'라고만 답하세요."""


@st.cache_resource
def get_rag():
    """OpenAI 클라이언트와 ChromaDB 컬렉션을 한 번만 만든다. 실패 사유는 문자열로 돌려준다."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    if not os.getenv("OPENAI_API_KEY"):
        return None, None, "", f"{ROOT / '.env'} 에 OPENAI_API_KEY=키값 을 넣고 앱을 다시 실행하세요."
    chroma_dir = ROOT / "data" / "chroma"
    if not chroma_dir.exists():
        return None, None, "", "data/chroma 가 없습니다. 04 노트북으로 벡터DB를 먼저 만드세요."
    import chromadb
    from openai import OpenAI
    client = OpenAI(timeout=60, max_retries=2)
    db = chromadb.PersistentClient(path=str(chroma_dir))
    for name in ("sif_v3", "sif_v2", "sif"):        # 07에서 만든 개선본이 있으면 우선 사용
        try:
            return client, db.get_collection(name), name, ""
        except Exception:
            continue
    return None, None, "", "sif 컬렉션이 없습니다. 04 노트북을 먼저 실행하세요."


def build_where(industry, years):
    conds = []
    if industry != "전체":
        conds.append({"업종구분": industry})
    if tuple(years) != (YMIN, YMAX):                # 연도를 좁힌 경우에만 연도 조건을 건다
        conds += [{"재해연도": {"$gte": int(years[0])}}, {"재해연도": {"$lte": int(years[1])}}]
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def _clip(text, limit=140):
    """limit 안에서 단어(띄어쓰기) 경계로 자르고, 잘렸으면 '…'를 붙인다."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.· ") + "…"


def overview_of(doc):
    if "[재해개요]" in doc:
        return _clip(doc.split("[재해개요]")[-1].split("\n[기인물]")[0])
    return _clip(doc.replace("\n", " "))


def retrieve(client, col, question, k, where):
    emb = client.embeddings.create(model=EMBED_MODEL, input=[question[:6000]]).data[0].embedding
    res = col.query(query_embeddings=[emb], n_results=k, where=where)
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        sim = 1 - dist
        if sim >= MIN_SIM:
            hits.append({"similarity": round(sim, 3), "document": doc, "meta": meta})
    return hits


def build_prompt(question, hits):
    blocks = []
    for n, h in enumerate(hits, 1):
        m = h["meta"]
        head = f"[사례{n}] (업종구분: {m.get('업종구분', '')}, 기인물: {m.get('기인물') or '미분류'}, 재해연도: {m.get('재해연도', '')})"
        blocks.append(head + "\n" + h["document"])
    return "\n\n".join(blocks) + f"\n\n질문: {question}"


def ask(question, k, where):
    client, col, _, _ = get_rag()
    hits = retrieve(client, col, question, k, where)
    sources = [{
        "사례": n, "유사도": h["similarity"],
        "업종구분": h["meta"].get("업종구분", ""), "중분류": h["meta"].get("중분류", ""),
        "기인물": h["meta"].get("기인물") or "미분류", "재해연도": h["meta"].get("재해연도", ""),
        "개요": overview_of(h["document"]),
    } for n, h in enumerate(hits, 1)]
    if not hits:                                    # 근거가 없으면 LLM을 부르지 않는다 (비용·환각 방지)
        return {"answer": NO_EVIDENCE, "sources": [], "grounded": False, "retrieved": []}
    resp = client.chat.completions.create(
        model=CHAT_MODEL, temperature=0,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": build_prompt(question, hits)}])
    answer = resp.choices[0].message.content.strip()
    grounded = NO_EVIDENCE not in answer
    return {"answer": answer, "sources": sources if grounded else [], "grounded": grounded, "retrieved": sources}


def set_question(text):                             # 예시 버튼: 질문칸을 채우고 바로 실행
    st.session_state["q"] = text
    st.session_state["run"] = True


def request_run():                                  # '질문하기' 버튼
    st.session_state["run"] = True


with tab_chat:
    client, col, col_name, rag_err = get_rag()

    st.subheader("질문하기")
    if rag_err:
        st.warning(rag_err)
    else:
        st.caption(f"검색 대상: {col_name} ({col.count():,}건)")

    st.write("예시 질문")
    ex = ["지게차 작업 중 협착 사고 예방은?",
          "이동식 사다리에서 떨어진 사고를 막으려면?",
          "컨베이어에 끼인 사고는 어떻게 예방하나요?"]
    for c, text in zip(st.columns(3), ex):
        c.button(text, on_click=set_question, args=(text,), disabled=bool(rag_err))

    st.text_input("질문을 입력하세요", key="q", placeholder="예: 비계에서 추락한 사고를 예방하려면?")
    st.button("질문하기", type="primary", on_click=request_run, disabled=bool(rag_err))

    where = build_where(industry, year_range)
    flt = f"업종 {industry} · 연도 {year_range[0]}~{year_range[1]} · k={top_k}"
    st.caption("적용 필터: " + flt + (" (사망자 통계 질문은 업종 '전체'에서 답합니다)" if industry != "전체" else ""))

    if st.session_state.get("run"):
        st.session_state["run"] = False
        q = (st.session_state.get("q") or "").strip()
        if not rag_err and q:
            with st.spinner("사례를 검색하고 답변을 만드는 중…"):
                try:
                    st.session_state["last"] = {"q": q, "flt": flt, **ask(q, top_k, where)}
                except Exception as e:           # API 오류 등은 화면에 보여주고 앱은 계속 동작
                    st.session_state["last"] = {"q": q, "flt": flt, "error": f"{type(e).__name__}: {e}"}
        elif not q:
            st.info("질문을 입력해 주세요.")

    last = st.session_state.get("last")
    st.divider()
    if last:
        st.markdown(f"**Q. {last['q']}**")
        if last.get("error"):
            st.error("답변을 만들지 못했습니다. " + last["error"])
        else:
            st.markdown("**답변**")
            if last["grounded"]:
                st.markdown(last["answer"])
            else:
                st.info(NO_EVIDENCE)
                if last["retrieved"]:
                    names = ", ".join(x["기인물"] for x in last["retrieved"])
                    st.caption(f"검색은 됐지만 질문과 맞지 않아 답하지 않았습니다. (검색된 기인물: {names})")
                else:
                    st.caption("유사도 기준을 넘는 사례가 없었습니다.")
            if last["sources"]:
                st.markdown("**출처**")
                for s in last["sources"]:
                    with st.container(border=True):
                        kind = "통계 자료" if s["업종구분"] == "통계" else f"{s['업종구분']} > {s['중분류']}"
                        st.markdown(f"**[사례{s['사례']}]** {kind} · 유사도 {s['유사도']}")
                        st.caption(f"기인물 {s['기인물']} · {s['재해연도']}년" if s["업종구분"] != "통계" else "규모별 사고사망자수")
                        st.write(s["개요"])
            st.caption("질문 당시 필터: " + last["flt"])
    else:
        st.caption("질문을 입력하거나 예시 버튼을 눌러 보세요.")
