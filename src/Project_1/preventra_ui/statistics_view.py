"""Thin presentation layer over existing statistics and Plotly services."""
import pandas as pd
import streamlit as st

from services.statistics import filter_statistics, industry_trend, kpi_value
from services.visualization import plot_six_year_line
from preventra_runtime import load_cloud_statistics, require_storage

COUNT_METRICS = ("사고재해자수", "사고사망자수")


def get_statistics():
    require_storage()
    return _cached_statistics()


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_statistics():
    return load_cloud_statistics()


def read_statistics():
    try:
        return get_statistics()
    except (RuntimeError, ValueError, OSError):
        st.warning("통계를 불러오지 못했습니다. 데이터 파일 또는 저장소 연결을 확인해 주세요. 다른 화면은 계속 이용할 수 있습니다.")
        return None


def render_statistics_banner():
    st.markdown("### 데이터로 살펴보는 산업안전")
    st.caption("확보된 산업재해 통계의 규모와 흐름을 확인하세요.")
    data = read_statistics()
    if data is None:
        return
    counts = data.loc[data["지표"].isin(COUNT_METRICS)].dropna(subset=["값"])
    if counts.empty:
        st.info("표시할 산업재해 통계가 없습니다. 통계 데이터가 준비되면 대표 수치와 추세를 표시합니다.")
        return
    year = int(counts["연도"].max())
    rows = filter_statistics(data, year=year)
    st.caption(f"기준연도 {year}년 · 확보된 산업중분류 전체 · 사업장 규모 전체 · 누락값 제외 건수 합계")
    summary, chart = st.columns([1, 2], gap="large")
    with summary:
        for metric in COUNT_METRICS:
            value = kpi_value(data, year, None, None, metric)
            st.metric(metric, "자료 없음" if value is None else f"{value:,.0f}명")
            coverage = filter_statistics(rows, metric=metric)
            if not coverage.empty:
                st.caption(f"{coverage['산업중분류'].nunique()}개 산업중분류 · {coverage['규모'].nunique()}개 규모 구간 · 유효 셀 {coverage['값'].notna().sum():,}/{len(coverage):,}")
        st.caption("출처: 한국산업안전보건공단, 산업중분류별 규모별 사고재해자수·사고사망자수 CSV. 확보된 자료의 합계이며 전국 전체 통계와의 일치 여부는 별도 확인이 필요합니다.")
    with chart:
        industries = sorted(counts["산업중분류"].unique().tolist())
        # Selection is local to this banner, not an assistant-wide context filter.
        if st.session_state.get("preventra_trend_industry") not in industries:
            st.session_state.preventra_trend_industry = "건설업" if "건설업" in industries else industries[0]
        industry = st.selectbox("추세를 볼 산업중분류", industries, key="preventra_trend_industry")
        trend = industry_trend(data, industry, "사고사망자수")
        if trend["값"].notna().any():
            figure = plot_six_year_line(trend, industry, "사고사망자수", year, None)
            figure.update_traces(line_color="#09877f", marker_color="#09877f")
            figure.update_layout(height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#153047", margin=dict(l=15, r=15, t=45, b=25))
            st.plotly_chart(figure, width="stretch", config={"displayModeBar": False}, key="preventra_home_trend")
            present = trend.loc[trend["값"].notna(), "연도"].astype(str).tolist()
            st.caption(f"{industry} · 규모 전체 사고사망자수 합계 · 수록연도: {', '.join(present)} · 출처: 한국산업안전보건공단 CSV")
            missing = trend.loc[trend["값"].isna(), "연도"].astype(str).tolist()
            if missing:
                st.caption("자료가 없는 연도는 연결하지 않습니다: " + ", ".join(missing))
        else:
            st.info("선택한 산업의 사고사망자수 추세 자료가 없습니다.")


def render_loaded_coverage():
    data = read_statistics()
    if data is None:
        return
    if data.empty:
        st.info("현재 불러온 통계가 없습니다. 아래 수록 범위는 프로젝트 파일 매핑을 기준으로 합니다.")
        return
    coverage = []
    for metric, rows in data.groupby("지표", sort=False):
        valid = rows.dropna(subset=["값"])
        coverage.append({
            "지표": metric,
            "값이 있는 연도": ", ".join(str(int(year)) for year in sorted(valid["연도"].unique())),
            "산업중분류 수": valid["산업중분류"].nunique(),
            "규모 구간 수": valid["규모"].nunique(),
        })
    st.dataframe(pd.DataFrame(coverage), hide_index=True, width="stretch")
