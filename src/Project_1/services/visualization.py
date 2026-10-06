"""Day 7의 Bar Chart와 Day 8의 추세선을 산업 중심 화면에 맞게 재사용한다."""

from math import log10

import pandas as pd
import plotly.express as px


def plot_industry_bar(totals: pd.DataFrame, metric: str, selected_industry: str | None = None, top_n: int = 15):
    """Day 7 가로 막대를 산업별 합계로 그리고 선택 산업을 함께 강조한다."""
    ranked = totals.nlargest(top_n, "값")
    if selected_industry and selected_industry not in set(ranked["산업중분류"]):
        ranked = pd.concat([ranked, totals.loc[totals["산업중분류"] == selected_industry]])
    ranked = ranked.sort_values("값")
    colors = ["#e36b38" if name == selected_industry else "#2878b8" for name in ranked["산업중분류"]]
    fig = px.bar(
        ranked, x="값", y="산업중분류", orientation="h",
        labels={"값": metric, "산업중분류": ""},
        title=f"산업중분류별 {metric}",
    )
    fig.update_traces(marker_color=colors)
    fig.update_layout(height=max(430, min(750, 34 * len(ranked) + 140)), margin=dict(l=220, r=20, t=60, b=45))
    return fig


def plot_death_rate_comparison(table: pd.DataFrame, selected_industry: str | None, size: str | None):
    """절대 사망자수와 상대 지표를 비교한다. 큰 극단값 때문에 비율 축만 log(1+x)로 표시한다."""
    chart = table.dropna(subset=["비교 사망만인율"]).copy()
    chart["비율 표시축"] = chart["비교 사망만인율"].map(lambda value: log10(1 + value))
    chart["선택"] = chart["산업중분류"].eq(selected_industry).map({True: "선택 산업", False: "다른 산업"})
    chart["표시 이름"] = chart["산업중분류"].where(chart["산업중분류"].eq(selected_industry), "")
    rate_label = "사망만인율" if size else "규모별 사망만인율 중앙값"
    fig = px.scatter(
        chart, x="사고사망자수", y="비율 표시축", color="선택", text="표시 이름",
        hover_name="산업중분류", hover_data={"비교 사망만인율": ":.2f", "비율 표시축": False, "표시 이름": False},
        color_discrete_map={"선택 산업": "#e36b38", "다른 산업": "#2878b8"},
        labels={"사고사망자수": "사고사망자수 (명)", "비율 표시축": rate_label},
        title="사고사망자수와 사망만인율 비교",
    )
    fig.update_traces(textposition="top center", marker_size=10)
    ticks = [0, 0.1, 1, 10, 100, 1000]
    fig.update_yaxes(tickvals=[log10(1 + value) for value in ticks], ticktext=[str(value) for value in ticks])
    fig.update_layout(height=500, margin=dict(l=50, r=30, t=60, b=50), legend_title_text="")
    return fig


def plot_six_year_line(trend: pd.DataFrame, industry: str, metric: str, selected_year: int, size: str | None):
    """Day 8의 2020~2025 선 그래프를 산업 기준으로 그린다. 없는 연도는 연결하지 않는다."""
    metric_label = f"{metric} (규모별 중앙값)" if metric == "사망만인율" and size is None else metric
    fig = px.line(
        trend, x="연도", y="값", markers=True,
        labels={"값": metric_label},
        title=f"{industry} · {metric_label} 변화 (2020~2025)",
    )
    fig.update_traces(connectgaps=False)
    fig.update_xaxes(tickvals=list(range(2020, 2026)), dtick=1)
    fig.add_vline(x=selected_year, line_dash="dot", line_color="#6b7280")
    fig.update_layout(height=430, margin=dict(l=40, r=30, t=60, b=40))
    return fig
