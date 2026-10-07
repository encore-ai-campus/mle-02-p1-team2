"""Data driven SVG infographics for the incident dashboard."""

from __future__ import annotations

from datetime import date
from html import escape
from math import ceil, cos, pi, sin
import re

import pandas as pd

from shining_chatbot.incident_data import SEVERITIES
from shining_chatbot.ui import GRAPH_DARK, GRAPH_LIGHT, GRAPH_MID


SHADES = (GRAPH_DARK, GRAPH_MID, GRAPH_LIGHT)


def _safe_chart_id(value: str) -> str:
    """Keep caller-provided SVG IDs out of markup and CSS syntax."""
    candidate = re.sub(r"[-_]{2,}", "-", re.sub(r"[^A-Za-z0-9_-]", "-", str(value))[:64]).strip("-_")
    if not candidate or not candidate[0].isalpha():
        candidate = f"chart-{candidate}"
    return candidate


def monthly_infographic(frame: pd.DataFrame, start: date, end: date, chart_id: str = "incident") -> str:
    chart_id = _safe_chart_id(chart_id)
    month_count = (end.year - start.year) * 12 + end.month - start.month + 1
    if month_count > 36:
        labels = [str(year) for year in range(start.year, end.year + 1)]
        period_key = frame["발생일"].dt.year.astype(str)
        grain = "연도별"
    else:
        labels = [
            month.strftime("%y.%m")
            for month in pd.date_range(
                pd.Timestamp(start).to_period("M").start_time,
                pd.Timestamp(end).to_period("M").start_time,
                freq="MS",
            )
        ]
        period_key = frame["발생일"].dt.strftime("%y.%m")
        grain = "월별"

    severity_labels = SEVERITIES if "재해정도" in frame.columns else ("재해정도 미기록",)
    severity_values = frame["재해정도"] if "재해정도" in frame.columns else pd.Series(
        "재해정도 미기록", index=frame.index,
    )
    grouped = frame.assign(_period=period_key, _severity=severity_values).groupby(["_period", "_severity"]).size()
    values = [[int(grouped.get((label, severity), 0)) for severity in severity_labels] for label in labels]
    totals = [sum(items) for items in values]
    peak = max(totals, default=0)
    ceiling = max(4, ceil(peak / 4) * 4)
    left, right, top, bottom = 44, 752, 18, 170
    plot_height = bottom - top
    step = (right - left) / max(len(labels), 1)
    bar_width = min(21, max(3, step * .56))

    svg = [
        '<svg class="trend-svg" viewBox="0 0 780 218" preserveAspectRatio="xMidYMid meet" '
        'role="img" aria-label="선택 기간의 기간별 사고 건수와 재해정도 구성">'
        '<defs>'
        f'<linearGradient id="{chart_id}-tone-dark" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#666D67"/><stop offset="1" stop-color="#454C46"/>'
        '</linearGradient>'
        f'<linearGradient id="{chart_id}-tone-mid" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#A2A9A2"/><stop offset="1" stop-color="#7C847D"/>'
        '</linearGradient>'
        f'<linearGradient id="{chart_id}-tone-light" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#D8DCD8"/><stop offset="1" stop-color="#B8BEB8"/>'
        '</linearGradient></defs>'
    ]
    popovers = []
    popover_rules = []
    for tick in range(5):
        value = ceiling * tick / 4
        y = bottom - plot_height * tick / 4
        svg.append(
            f'<line x1="{left}" x2="{right}" y1="{y:.1f}" y2="{y:.1f}" '
            'stroke="#ECEFEC" stroke-width="1"/>'
            f'<text x="{left - 9}" y="{y + 3:.1f}" text-anchor="end" '
            f'class="chart-axis">{value:g}</text>'
        )
    every = max(1, ceil(len(labels) / 8))
    for index, (label, segments) in enumerate(zip(labels, values)):
        x = left + step * (index + .5)
        y = bottom
        tooltip = f"{label} · 전체 {totals[index]:,}건 · " + " · ".join(
            f"{severity} {count:,}건" for severity, count in zip(severity_labels, segments)
        )
        svg.append(
            f'<g class="timeline-period" data-period="{index}" tabindex="0" role="group" '
            f'aria-label="{escape(tooltip, quote=True)}">'
            f'<rect class="period-focus" x="{x - step * .47:.1f}" y="{top - 7}" '
            f'width="{step * .94:.1f}" height="{plot_height + 14}" rx="5" '
            'fill="#F1F4F0"/>'
            f'<rect class="period-hit" x="{x - step / 2:.1f}" y="{top - 7}" '
            f'width="{step:.1f}" height="{plot_height + 34}" fill="transparent"/>'
        )
        details = " · ".join(
            f"{severity} {count:,}" for severity, count in zip(severity_labels, segments)
        )
        popovers.append(
            f'<div class="month-popover month-popover-{index}" role="tooltip" '
            f'style="left:clamp(88px,{x / 780 * 100:.2f}%,calc(100% - 88px))">'
            f'<span>{escape(label)}</span><strong>{totals[index]:,}건</strong>'
            f'<small>{escape(details)}</small></div>'
        )
        popover_rules.append(
            f'.trend-panel:has(.timeline-period[data-period="{index}"]:hover) '
            f'.month-popover-{index},'
            f'.trend-panel:has(.timeline-period[data-period="{index}"]:focus-visible) '
            f'.month-popover-{index},'
            f'.trend-panel:has(.timeline-period[data-period="{index}"]:focus) '
            f'.month-popover-{index}'
            '{opacity:1;visibility:visible;}'
        )
        if totals[index]:
            total_height = totals[index] / ceiling * plot_height
            cap_y = bottom - total_height
            radius = min(3, total_height / 2)
            bar_left = x - bar_width / 2
            bar_right = x + bar_width / 2
            cap = (
                f'M {bar_left:.3f} {bottom:.3f} L {bar_left:.3f} {cap_y + radius:.3f} '
                f'Q {bar_left:.3f} {cap_y:.3f} {bar_left + radius:.3f} {cap_y:.3f} '
                f'L {bar_right - radius:.3f} {cap_y:.3f} '
                f'Q {bar_right:.3f} {cap_y:.3f} {bar_right:.3f} {cap_y + radius:.3f} '
                f'L {bar_right:.3f} {bottom:.3f} Z'
            )
            svg.append(
                f'<defs><clipPath id="{chart_id}-timeline-bar-{index}"><path d="{cap}"/></clipPath></defs>'
                f'<g class="period-column" clip-path="url(#{chart_id}-timeline-bar-{index})">'
            )
        for count, tone in zip(segments, ("dark", "mid", "light")):
            if count:
                height = count / ceiling * plot_height
                y -= height
                svg.append(
                    f'<rect x="{x - bar_width / 2:.1f}" y="{y:.1f}" '
                    f'width="{bar_width:.1f}" height="{height:.1f}" '
                    f'fill="url(#{chart_id}-tone-{tone})"/>'
                )
        if totals[index]:
            svg.append('</g>')
        if index % every == 0 or index == len(labels) - 1:
            svg.append(
                f'<text x="{x:.1f}" y="198" text-anchor="middle" class="chart-axis period-axis">'
                f'{escape(label)}</text>'
            )
        svg.append('</g>')
    svg.append('</svg>')
    legend = "".join(
        f'<span><i style="background:{color}"></i>{severity}</span>'
        for severity, color in zip(severity_labels, SHADES)
    )
    return (
        '<div class="infographic-panel trend-panel">'
        '<div class="infographic-head"><div><div class="infographic-kicker">INCIDENT TIMELINE / 01</div>'
        f'<h3>{grain} 발생 추이</h3><p>막대 하나가 한 기간의 사고 기록을 뜻합니다.</p></div>'
        f'<div class="infographic-highlight"><strong>{len(frame):,}</strong><span>TOTAL INCIDENTS</span></div></div>'
        '<div class="infographic-chart">' + ''.join(svg) + ''.join(popovers) + '</div>'
        '<style>' + ''.join(popover_rules) + '</style>'
        '<div class="infographic-footer">'
        f'<div class="chart-legend">{legend}</div>'
        '</div></div>'
    )


def severity_infographic(frame: pd.DataFrame) -> str:
    counts = [int(frame["재해정도"].eq(severity).sum()) for severity in SEVERITIES]
    total = sum(counts)
    progress = 0.0
    rings = [
        '<svg class="donut-svg" viewBox="0 0 180 180" role="img" '
        'aria-label="경상, 중상, 사망 사고 비중">'
        '<circle cx="90" cy="90" r="63" fill="none" stroke="#EDF0ED" stroke-width="21"/>'
    ]
    for tick in range(36):
        angle = (tick / 36) * 2 * pi - pi / 2
        outer, inner = 87, (82 if tick % 3 == 0 else 84)
        rings.append(
            f'<line x1="{90 + cos(angle) * inner:.2f}" y1="{90 + sin(angle) * inner:.2f}" '
            f'x2="{90 + cos(angle) * outer:.2f}" y2="{90 + sin(angle) * outer:.2f}" '
            'stroke="#D5DAD5" stroke-width="1"/>'
        )
    for index, (severity, count, color) in enumerate(zip(SEVERITIES, counts, SHADES)):
        share = count / total * 100 if total else 0
        if share:
            visible = max(share - .65, .2)
            rings.append(
                f'<circle class="donut-segment tone-{index}" cx="90" cy="90" r="63" '
                f'pathLength="100" fill="none" tabindex="0" role="img" '
                f'aria-label="{escape(severity, quote=True)} {count:,}건, {share:.1f}%" '
                f'stroke="{color}" stroke-width="21" stroke-dasharray="{visible:.4f} {100 - visible:.4f}" '
                f'stroke-dashoffset="{-progress:.4f}" transform="rotate(-90 90 90)"/>'
            )
        progress += share
    rings.append(
        '<g class="donut-default">'
        f'<text x="90" y="86" text-anchor="middle" class="donut-total">{total:,}</text>'
        '<text x="90" y="104" text-anchor="middle" class="donut-label">INCIDENTS</text></g>'
    )
    for index, (severity, count) in enumerate(zip(SEVERITIES, counts)):
        rings.append(
            f'<g class="donut-hover-value tone-{index}">'
            f'<text x="90" y="86" text-anchor="middle" class="donut-total">{count:,}</text>'
            f'<text x="90" y="104" text-anchor="middle" class="donut-label">'
            f'{severity} · {count / total:.0%}</text></g>'
        )
    rings.append('</svg>')
    legend = "".join(
        f'<div class="severity-legend-row tone-{index}" tabindex="0">'
        f'<i style="background:{color}"></i><span>{severity}</span>'
        f'<strong>{count:,}<small>건</small></strong>'
        f'<em>{count / total:.0%}</em>'
        f'<div class="severity-share-track"><span style="width:{count / total * 100:.1f}%;background:{color}"></span></div>'
        '</div>'
        for index, (severity, count, color) in enumerate(zip(SEVERITIES, counts, SHADES))
    )
    return (
        '<div class="infographic-panel severity-panel">'
        '<div class="infographic-head"><div><div class="infographic-kicker">SEVERITY PROFILE / 02</div>'
        '<h3>재해정도 구성</h3><p>사고 기록 건수 기준</p></div></div>'
        f'<div class="severity-visual">{"".join(rings)}<div class="severity-legend">{legend}</div></div>'
        '<div class="infographic-footer"><span>재해자 수가 아닌 사고 건수의 비중입니다.</span></div>'
        '</div>'
    )


def ranking_infographic(frame: pd.DataFrame, column: str, title: str, index: str) -> str:
    counts = frame[column].value_counts()
    maximum = max(int(counts.max()), 1)
    total = len(frame)
    leader_label = str(counts.index[0])
    leader_count = int(counts.iloc[0])
    rows = []
    for rank, (label, count) in enumerate(counts.items(), 1):
        bar_width = count / maximum * 100
        share = count / total * 100
        rows.append(
            f'<div class="rank-row" tabindex="0" aria-label="{escape(str(label), quote=True)}: {count:,}건, 전체의 {share:.1f}%">'
            f'<div class="rank-line"><span class="rank-order">{rank:02d}</span>'
            f'<span class="rank-name">{escape(str(label))}</span>'
            f'<span class="rank-count">{count:,}<small>건</small></span></div>'
            f'<div class="rank-track"><span style="width:{bar_width:.1f}%"></span></div>'
            f'<div class="rank-share">{share:.1f}% OF INCIDENTS</div></div>'
        )
    return (
        '<div class="infographic-panel rank-panel">'
        f'<div class="infographic-kicker">DISTRIBUTION / {escape(index)}</div>'
        f'<h3>{escape(title)}</h3>'
        f'<p class="rank-description">전체 {total:,}건 · {len(counts)}개 항목</p>'
        '<div class="rank-leader"><div><span>TOP CATEGORY</span>'
        f'<strong>{escape(leader_label)}</strong></div>'
        f'<em>{leader_count / total:.1%}<small> / {leader_count:,}건</small></em></div>'
        f'<div class="rank-list">{"".join(rows)}</div></div>'
    )
