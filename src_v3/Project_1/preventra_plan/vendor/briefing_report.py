"""Compact visual report for chat based safety briefings."""

from __future__ import annotations

from html import escape


def _text(value: object, fallback: str = "") -> str:
    return escape(str(value if value is not None else fallback))


def _truncate(value: object, limit: int = 110) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def safety_briefing_html(report: dict, *, show_cases: bool = True) -> str:
    """Render an at-a-glance report with secondary details kept collapsed."""
    tasks = report.get("tasks") if isinstance(report.get("tasks"), list) else []
    windows = report.get("weather_windows") if isinstance(report.get("weather_windows"), list) else []
    cases = report.get("cases") if isinstance(report.get("cases"), list) else []

    scope = _text(report.get("scope") or "선택한 작업")
    task_rows = []
    for task in tasks[:8]:
        guidance = []
        if task.get("equipment"):
            guidance.append(f'<span><b>장비</b> {_text(task.get("equipment"))}</span>')
        if task.get("controls"):
            guidance.append(f'<span><b>조치</b> {_text(_truncate(task.get("controls"), 90))}</span>')
        if task.get("check"):
            guidance.append(f'<span><b>시작 전</b> {_text(_truncate(task.get("check"), 75))}</span>')
        task_rows.append(
            '<article class="sr-task-card"><div class="sr-task-row">'
            f'<time>{_text(task.get("time"))}<small>{_text(task.get("area"), "구역 미입력")}</small></time>'
            f'<div class="sr-task-main"><strong>{_text(task.get("activity"))}</strong>'
            f'<div class="sr-task-guidance">{"".join(guidance) if guidance else ""}</div>'
            f'<small>{_text(task.get("source", ""))}</small>'
            + (f'<details class="sr-details"><summary>계획 내용 전체·누락 항목</summary><div class="sr-details-body">{_text(task.get("detail", ""))}</div></details>' if task.get('detail') else '')
            + '</div></div></article>'
        )
    if len(tasks) > 8:
        task_rows.append(f'<div class="sr-more">외 {len(tasks) - 8}개 작업</div>')
    if not task_rows:
        task_rows.append('<div class="sr-empty">선택한 범위의 계획 작업 없음</div>')

    weather_label = str(report.get("weather_label") or "미연결")
    location = str(report.get("location") or "").strip()
    location_missing = not location or location in {"계획서 지역 미입력", "현장 지역 미입력", "미입력"}
    weather_brief = weather_label if weather_label != "미연결" else "지역 예보 미연결"
    if weather_label == "미연결" and location_missing:
        weather_brief = "현장 지역 미입력 · 예보 미연결"
    season = str(report.get("season") or "계절 미확인")
    weather_notes = report.get("weather_notes") if isinstance(report.get("weather_notes"), list) else []
    context_notes = [str(note).strip() for note in weather_notes[:1] if str(note).strip()]
    if report.get("season_note"):
        context_notes.append(str(report.get("season_note")).strip())
    if weather_label == "미연결" and location_missing:
        context_notes.insert(0, "계획서에 현장 지역을 입력하면 작업 시간대별 예보를 확인할 수 있습니다.")
    context_note = _text(_truncate(" · ".join(context_notes), 145) or "현장 기상과 계절별 유의사항을 작업 전에 확인하세요.")
    weather_rows = []
    for window in windows[:3]:
        checks = window.get("checks") if isinstance(window.get("checks"), list) else []
        weather_rows.append(
            '<div class="sr-weather-row">'
            f'<b>{_text(window.get("time"))} · {_text(window.get("activity"))}</b>'
            f'<span>{_text(window.get("detail"))}</span>'
            + (f'<small>확인 · {_text(" · ".join(map(str, checks)))}</small>' if checks else "")
            + '</div>'
        )
    if not windows and report.get("weather") and weather_label != "미연결":
        weather_rows.append(f'<div class="sr-weather-row"><span>{_text(_truncate(report.get("weather"), 105))}</span></div>')
    extra_weather_rows = []
    for window in windows[3:]:
        extra_weather_rows.append(
            f'<li><b>{_text(window.get("time"))} · {_text(window.get("activity"))}</b> · {_text(window.get("detail"))}</li>'
        )

    case_cards = []
    for case in cases[:4]:
        if not isinstance(case, dict):
            continue
        counts = case.get("counts") if isinstance(case.get("counts"), list) else []
        counts = [
            {"name": str(row.get("name") or "기타"), "count": max(0, int(row.get("count", 0)))}
            for row in counts[:3] if isinstance(row, dict)
        ]
        total = max(0, int(case.get("total", 0)))
        category_sum = sum(row["count"] for row in counts)
        remainder = max(0, total - category_sum)
        chart_rows = [row for row in counts if row["count"] > 0]
        if remainder:
            chart_rows.append({"name": "기타·미분류", "count": remainder})
        denominator = max(total, sum(row["count"] for row in chart_rows), 1)
        circumference = 2 * 3.141592653589793 * 32
        donut_slices = []
        legend_rows = []
        palette = ("#397FE8", "#6AA9EB", "#9BC8F0", "#D4E4F5")
        offset = 0.0
        for index, row in enumerate(chart_rows):
            count = row["count"]
            length = circumference * count / denominator
            color = palette[min(index, len(palette) - 1)]
            name = _text(row["name"])
            percent = round(count / denominator * 100)
            donut_slices.append(
                f'<circle class="sr-donut-slice" data-index="{index}" cx="44" cy="44" r="32" '
                f'stroke="{color}" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
                f'stroke-dashoffset="{-offset:.2f}" aria-label="{name} {count:,}건, {percent}%">'
                f'<title>{name} {count:,}건 · {percent}%</title></circle>'
            )
            legend_rows.append(
                f'<div class="sr-legend-row" data-index="{index}" title="{name} {count:,}건 · {percent}%">'
                f'<i style="--sr-swatch:{color}"></i><span>{name}</span>'
                f'<b>{count:,}건</b><small>{percent}%</small></div>'
            )
            offset += length
        donut = (
            '<div class="sr-chart-row"><div class="sr-donut-wrap">'
            '<svg class="sr-donut" viewBox="0 0 88 88" role="img" aria-label="사고 유형 비율 그래프">'
            '<circle class="sr-donut-track" cx="44" cy="44" r="32" />'
            + "".join(donut_slices)
            + f'<text class="sr-donut-total" x="44" y="42">{(total or category_sum):,}</text>'
            + '<text class="sr-donut-caption" x="44" y="54">사례</text></svg></div>'
            + (f'<div class="sr-legend">{"".join(legend_rows)}</div>' if legend_rows else '<p class="sr-muted">사고 유형 집계 없음</p>')
            + '</div>'
        )
        controls = case.get("controls") if isinstance(case.get("controls"), list) else []
        case_cards.append(
            '<article class="sr-case"><div class="sr-case-title">'
            f'<strong>{_text(case.get("activity"))}</strong><span>{_text(case.get("total"))}건 사례</span></div>'
            + donut
            + (f'<p class="sr-action"><b>교육 포인트</b> {_text(_truncate(controls[0], 125))}</p>' if controls else "")
            + '</article>'
        )
    if not case_cards:
        case_cards.append('<div class="sr-empty">연결 가능한 유사 사고 통계가 없습니다. 작업 전 위험성평가를 확인하세요.</div>')
    extra_cases = []
    for case in cases[4:]:
        if not isinstance(case, dict):
            continue
        types = " · ".join(
            f'{_text(row.get("name"))} {int(row.get("count", 0)):,}건'
            for row in (case.get("counts") or [])[:3] if isinstance(row, dict)
        )
        extra_cases.append(f'<li>{_text(case.get("activity"))} · {_text(case.get("total"))}건 · {types}</li>')

    preview = bool(report.get("preview"))
    preview_banner = (
        f'<span class="sr-preview">다음 계획일 사전 브리핑 · {_text(report.get("date"))}</span>'
        if preview else '<span class="sr-preview sr-preview-today">계획서 기반 브리핑</span>'
    )
    summary = _text(report.get("summary"), "작업별 계획 조치와 시작 전 확인사항을 검토하세요.")
    html = f'''<section class="safety-report" aria-label="{scope} 안전 브리핑">
<style>
.safety-report{{--sr-ink:#202A38;--sr-muted:#778397;--sr-line:#E8EDF3;color:var(--sr-ink);font-family:var(--font-ui,"Pretendard",sans-serif);line-height:1.5;width:100%;max-width:880px;margin:0 auto;padding-bottom:22px;overflow-wrap:anywhere}}
[data-testid="stChatMessage"]:has(.safety-report){{display:block!important}}
[data-testid="stChatMessage"]:has(.safety-report) > div:first-child{{display:none!important}}
[data-testid="stChatMessage"]:has(.safety-report){{border-color:#E5ECF5!important;background:#FFFFFF!important;box-shadow:0 14px 38px rgba(43,72,116,.075),inset 0 1px 0 #FFFFFF!important;backdrop-filter:none!important}}
.safety-report *{{box-sizing:border-box}}
.sr-head{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:2px 0 11px;border-bottom:1px solid var(--sr-line)}}
.sr-head>div{{min-width:0;flex:1}}
.sr-head h3{{margin:0!important;color:var(--sr-ink);font-size:18px!important;font-weight:650!important;letter-spacing:-.035em!important;line-height:1.4!important;overflow-wrap:anywhere}}
.sr-head p{{margin:2px 0 0!important;color:var(--sr-muted);font-size:12px;line-height:1.45}}
.sr-preview{{flex:none;padding:6px 9px;border-radius:999px;background:#F2F7FF;color:#3478D3;font-size:11px;font-weight:600}}
.sr-preview-today{{background:#EEF8F3;color:#36785A}}
.sr-summary{{margin:11px 0 13px;padding:12px 14px;border:1px solid #E3ECF9;border-radius:12px;background:#F5F8FD;color:#354D6E;font-size:13px;font-weight:550;line-height:1.6;overflow-wrap:anywhere}}
.sr-section{{margin-top:13px}}
.sr-section-head{{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin:0 0 6px}}
.sr-section-head strong{{color:#344256;font-size:13px;font-weight:650}}
.sr-section-head span{{color:#96A1AF;font-size:11px;letter-spacing:.035em}}
.sr-task-list{{border-top:1px solid #EFF2F6}}
.sr-task-card{{border-bottom:1px solid #EFF2F6;transition:background .18s ease,border-color .18s ease}}
.sr-task-card:hover{{background:rgba(241,247,255,.55);border-color:#DDE9F8}}
.sr-task-row{{display:grid;grid-template-columns:112px minmax(0,1fr);align-items:start;gap:12px;padding:10px 8px;border-radius:8px;transition:transform .18s ease}}
.sr-task-card:hover .sr-task-row{{transform:translateX(2px)}}
.sr-task-row time{{color:#6380A5;font:600 11px/1.5 var(--font-mono,monospace);font-variant-numeric:tabular-nums}}
.sr-task-row time small{{display:block;margin-top:3px;color:#8995A5;font:500 11px/1.4 var(--font-ui,"Pretendard",sans-serif)}}
.sr-task-main{{min-width:0}}
.sr-task-main>strong{{display:block;color:#2F3C4E;font-size:14px;font-weight:620;line-height:1.45;overflow-wrap:anywhere}}
.sr-task-guidance{{display:grid;gap:3px;margin-top:4px;color:#637286;font-size:12px;line-height:1.5;overflow-wrap:anywhere}}
.sr-task-guidance b{{margin-right:4px;color:#718198;font-weight:620}}
.sr-context{{display:flex;align-items:center;gap:7px;min-width:0;padding:9px 11px;border:1px solid rgba(226,234,244,.88);border-radius:10px;background:rgba(255,255,255,.68);color:#60738D;font-size:12px;overflow-wrap:anywhere;backdrop-filter:blur(12px);transition:background .18s ease,border-color .18s ease,box-shadow .18s ease}}
.sr-context:hover{{border-color:#C8D9EF;background:rgba(255,255,255,.9);box-shadow:0 5px 14px rgba(44,71,111,.06)}}
.sr-context i{{color:#B6C1CF;font-style:normal}}
.sr-context-note{{margin-top:6px;padding:8px 10px;border-radius:8px;background:#F5F8FD;color:#5E718A;font-size:12px;line-height:1.55;overflow-wrap:anywhere}}
.sr-weather-list{{margin-top:7px}}
.sr-weather-row{{padding:7px 9px;border:1px solid #EEF1F5;border-radius:8px;background:#fff;margin-top:5px}}
.sr-weather-row b,.sr-weather-row span,.sr-weather-row small{{display:block;overflow-wrap:anywhere}}
.sr-weather-row b{{color:#52647B;font-size:11px;font-weight:620}}
.sr-weather-row span{{margin-top:2px;color:#52647B;font-size:12px}}
.sr-weather-row small{{margin-top:2px;color:#72829A;font-size:11px}}
.sr-case-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.sr-case{{min-width:0;padding:10px;border:1px solid rgba(226,234,244,.9);border-radius:12px;background:rgba(255,255,255,.76);backdrop-filter:blur(12px) saturate(1.08);transition:transform .18s ease,border-color .18s ease,background .18s ease,box-shadow .18s ease}}
.sr-case:hover{{transform:translateY(-2px);border-color:#C7D9F1;background:rgba(255,255,255,.9);box-shadow:0 12px 26px rgba(43,72,116,.09),inset 0 1px 0 #FFFFFF}}
.sr-case-title{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:6px}}
.sr-case-title strong{{min-width:0;color:#435670;font-size:12px;font-weight:620;overflow-wrap:anywhere}}
.sr-case-title span{{flex:none;color:#8793A2;font-size:10px}}
.sr-panel{{padding:11px 12px;border:1px solid var(--sr-line);border-radius:11px;background:#fff}}
.sr-chart-title{{min-width:0;margin-bottom:7px;color:#68798F;font-size:12px;overflow-wrap:anywhere}}
.sr-chart-title strong{{color:#435670;font-size:12px;font-weight:620}}
.sr-chart-row{{display:grid;grid-template-columns:82px minmax(0,1fr);align-items:center;gap:9px;min-height:82px}}
.sr-donut-wrap{{width:82px;height:82px}}
.sr-donut{{display:block;width:82px;height:82px;overflow:visible}}
.sr-donut-track,.sr-donut-slice{{fill:none;transform:rotate(-90deg);transform-origin:44px 44px}}
.sr-donut-track{{stroke:#EDF2F8;stroke-width:13}}
.sr-donut-slice{{stroke-width:14;transition:stroke-width .18s ease,filter .18s ease;cursor:pointer}}
.sr-donut-slice:hover{{stroke-width:20;filter:drop-shadow(0 2px 3px rgba(37,91,158,.24))}}
.sr-donut-total{{fill:#27384F;text-anchor:middle;font-size:15px;font-weight:700;letter-spacing:-.03em}}
.sr-donut-caption{{fill:#8995A4;text-anchor:middle;font-size:8px}}
.sr-legend{{display:grid;gap:2px;min-width:0}}
.sr-legend-row{{display:grid;grid-template-columns:8px minmax(0,1fr) auto 28px;align-items:center;gap:5px;min-width:0;padding:3px 4px;border-radius:6px;transition:transform .16s ease,background .16s ease,box-shadow .16s ease}}
.sr-legend-row:hover{{position:relative;z-index:1;transform:scale(1.035);background:#F4F8FE;box-shadow:0 2px 8px rgba(42,78,125,.1)}}
.sr-legend-row>i{{width:7px;height:7px;border-radius:50%;background:var(--sr-swatch)}}
.sr-legend-row>span{{min-width:0;overflow:hidden;color:#6F7D90;font-size:11px;text-overflow:ellipsis;white-space:nowrap}}
.sr-legend-row>b{{color:#52647B;text-align:right;font-size:10px;font-weight:620;white-space:nowrap}}
.sr-legend-row>small{{color:#8B97A7;text-align:right;font-size:9px}}
.sr-case:has(.sr-legend-row[data-index="0"]:hover) .sr-donut-slice[data-index="0"],.sr-case:has(.sr-legend-row[data-index="1"]:hover) .sr-donut-slice[data-index="1"],.sr-case:has(.sr-legend-row[data-index="2"]:hover) .sr-donut-slice[data-index="2"],.sr-case:has(.sr-legend-row[data-index="3"]:hover) .sr-donut-slice[data-index="3"]{{stroke-width:20;filter:drop-shadow(0 2px 3px rgba(37,91,158,.24))}}
.sr-action{{margin:8px 0 0!important;padding:7px 8px;border:1px solid rgba(255,255,255,.75);border-radius:8px;background:rgba(239,246,255,.68);color:#647A98;font-size:11px;line-height:1.5;overflow-wrap:anywhere;backdrop-filter:blur(8px)}}
.sr-action b{{margin-right:5px;color:#4B6688;font-weight:620}}
.sr-foot{{margin:9px 0 14px;color:#8290A0;font-size:10px;line-height:1.6}}
.sr-details{{margin-top:9px;border-top:1px solid #EEF1F5}}
.sr-details summary{{padding:8px 20px 8px 1px;color:#738198;font-size:11px;cursor:pointer;list-style:none;overflow-wrap:anywhere}}
.sr-details summary::-webkit-details-marker{{display:none}}
.sr-details summary::after{{content:"＋";float:right;color:#8B9BB0}}
.sr-details[open] summary::after{{content:"−"}}
.sr-details-body{{min-width:0;padding:0 2px 8px;color:#6D7B8E;font-size:11px;line-height:1.55;overflow-wrap:anywhere}}
.sr-details-body p{{margin:4px 0}}
.sr-detail-title{{margin-top:9px;color:#52647B;font-weight:620}}
.sr-detail-task{{margin-top:5px;padding:7px 8px;border-radius:8px;background:#F7F9FC}}
.sr-detail-task strong{{color:#43546A}}
.sr-detail-task ul{{margin:3px 0 0;padding-left:16px}}
.sr-detail-task li{{margin:2px 0}}
.sr-detail-task b{{color:#718098;font-weight:600}}
.sr-muted,.sr-empty{{color:#8490A0;font-size:11px}}
.sr-empty{{padding:9px 2px}}
.sr-more{{padding:7px 2px;color:#8390A1;font-size:10px}}
@media(max-width:640px){{.sr-head{{align-items:flex-start}}.sr-head h3{{font-size:16px!important}}.sr-preview{{max-width:130px;text-align:center;line-height:1.35;white-space:normal}}.sr-task-row{{grid-template-columns:78px minmax(0,1fr);gap:8px}}.sr-case-grid{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{.safety-report *{{scroll-behavior:auto!important;transition:none!important;animation:none!important}}}}
.safety-report{{--sr-ink:#E8EFEE;--sr-muted:#91A09F;--sr-line:rgba(204,225,224,.11);color:var(--sr-ink)!important;padding:4px 0 24px}}
.sr-head{{border-color:var(--sr-line)!important}}
.sr-head h3{{color:#F0F5F3!important}}
.sr-head p,.sr-section-head span,.sr-foot,.sr-task-row time small,.sr-task-guidance,.sr-muted,.sr-empty,.sr-more{{color:#889896!important}}
.sr-preview{{background:rgba(83,196,157,.1)!important;color:#8DD9BB!important;border:1px solid rgba(83,196,157,.14)}}
.sr-summary{{border-color:rgba(107,172,212,.14)!important;border-radius:14px!important;background:linear-gradient(105deg,rgba(66,125,160,.13),rgba(63,137,125,.08))!important;color:#CFDDDB!important}}
.sr-section-head strong,.sr-task-main>strong,.sr-case-title strong,.sr-chart-title strong,.sr-action b{{color:#DCE7E5!important}}
.sr-task-list,.sr-task-card{{border-color:var(--sr-line)!important}}
.sr-task-card:hover{{background:rgba(95,165,168,.07)!important}}
.sr-task-row time,.sr-task-guidance b{{color:#86A8A8!important}}
.sr-context,.sr-context-note,.sr-weather-row,.sr-case,.sr-panel{{border-color:rgba(204,225,224,.1)!important;background:rgba(225,242,240,.035)!important;color:#AAB9B7!important}}
.sr-context:hover,.sr-case:hover{{border-color:rgba(104,199,177,.32)!important;background:rgba(225,242,240,.07)!important;box-shadow:0 12px 28px rgba(0,0,0,.18),inset 0 1px 0 rgba(255,255,255,.04)!important}}
.sr-weather-row b,.sr-weather-row span,.sr-weather-row small,.sr-chart-title,.sr-case-title span,.sr-legend-row>span,.sr-details summary,.sr-details-body,.sr-detail-task{{color:#91A3A1!important}}
.sr-detail-task{{background:rgba(225,242,240,.045)!important}}
.sr-action{{border-color:rgba(120,200,181,.12)!important;background:rgba(65,160,131,.08)!important;color:#A9C4BB!important}}
.sr-donut-track{{stroke:rgba(215,234,230,.11)!important}}
.sr-donut-total{{fill:#ECF4F2!important}}
.sr-donut-caption{{fill:#8EA09E!important}}
.sr-legend-row>b{{color:#CDD9D7!important}}
.sr-legend-row:hover{{background:rgba(119,184,192,.1)!important;box-shadow:0 2px 12px rgba(0,0,0,.2)!important}}
.sr-details{{border-color:var(--sr-line)!important}}
.sr-details summary::after{{color:#8EA09E!important}}
.sr-foot{{margin:13px 0 20px!important}}
.sr-preview{{background:rgba(72,145,255,.12)!important;color:#A8CEFF!important;border-color:rgba(101,168,255,.2)!important}}
.sr-preview-today{{background:rgba(72,145,255,.12)!important;color:#A8CEFF!important}}
.sr-summary{{border-color:rgba(107,157,231,.18)!important;background:linear-gradient(105deg,rgba(52,105,187,.18),rgba(65,138,193,.09))!important}}
.sr-task-row time,.sr-task-guidance b{{color:#9ABEFF!important}}
.sr-context,.sr-context-note,.sr-weather-row,.sr-case,.sr-panel{{border-color:rgba(164,196,237,.12)!important;background:rgba(201,222,255,.045)!important}}
.sr-context:hover,.sr-case:hover{{border-color:rgba(117,176,255,.36)!important;background:rgba(183,211,255,.085)!important;box-shadow:0 12px 28px rgba(0,0,0,.2),inset 0 1px 0 rgba(255,255,255,.06)!important}}
.sr-action{{border-color:rgba(125,176,245,.2)!important;background:rgba(63,125,220,.13)!important;color:#BAD5FF!important}}
.sr-donut-track{{stroke:rgba(210,229,255,.13)!important}}
.sr-legend-row:hover{{background:rgba(93,151,235,.13)!important}}
.safety-report{{--sr-ink:#203550;--sr-muted:#64768E;--sr-line:#E5ECF5;color:#203550!important;background:transparent!important}}
.sr-head h3,.sr-section-head strong,.sr-task-main>strong,.sr-case-title strong,.sr-chart-title strong{{color:#203550!important}}
.sr-head p,.sr-section-head span,.sr-foot,.sr-task-row time small,.sr-task-guidance,.sr-muted,.sr-empty,.sr-more,.sr-weather-row b,.sr-weather-row span,.sr-weather-row small,.sr-chart-title,.sr-case-title span,.sr-legend-row>span,.sr-details summary,.sr-details-body,.sr-detail-task{{color:#61738A!important}}
.sr-preview,.sr-preview-today{{background:#EAF2FF!important;color:#3975C8!important;border-color:#D9E7FA!important}}
.sr-summary{{border-color:#DCE8F8!important;background:linear-gradient(105deg,#EDF4FF,#F4F8FF)!important;color:#3A5477!important}}
.sr-task-list,.sr-task-card,.sr-details{{border-color:#E8EEF6!important}}
.sr-context,.sr-context-note,.sr-weather-row,.sr-case,.sr-panel{{border-color:#E4EBF4!important;background:rgba(255,255,255,.88)!important;color:#566C89!important;box-shadow:0 4px 16px rgba(41,73,119,.035)!important}}
.sr-context:hover,.sr-case:hover{{border-color:#BED4F3!important;background:#FFFFFF!important;box-shadow:0 12px 28px rgba(48,89,151,.09)!important}}
.sr-action{{border-color:#DCE8F8!important;background:#EFF5FF!important;color:#526F98!important}}
.sr-action b,.sr-task-row time,.sr-task-guidance b{{color:#4B77B5!important}}
.sr-donut-track{{stroke:#E8EEF7!important}}
.sr-donut-total{{fill:#203550!important}}
.sr-donut-caption{{fill:#7789A3!important}}
.sr-legend-row>b{{color:#435A78!important}}
.sr-legend-row:hover{{background:#F0F6FF!important;box-shadow:0 2px 10px rgba(47,89,150,.1)!important}}
.sr-details summary::after{{color:#7A8EAA!important}}
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:has(.safety-report){{color:#203550!important}}
body:has(.chat-conversation-active) [data-testid="stChatMessage"]:has(.safety-report) *{{--sr-ink:#203550}}
@keyframes sr-motion-in{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.safety-report>.sr-head,.safety-report>.sr-summary,.safety-report>.sr-section{{animation:sr-motion-in .58s cubic-bezier(.18,.76,.2,1) both}}
.safety-report>.sr-summary{{animation-delay:.07s}}
.safety-report>.sr-section:nth-of-type(1){{animation-delay:.13s}}
.safety-report>.sr-section:nth-of-type(2){{animation-delay:.2s}}
.safety-report>.sr-section:nth-of-type(3){{animation-delay:.27s}}
@media(prefers-reduced-motion:reduce){{.safety-report>.sr-head,.safety-report>.sr-summary,.safety-report>.sr-section{{animation:none!important}}}}
</style>
<header class="sr-head"><div><h3>{_text(report.get("date"))} {_text(report.get("weekday"))} {scope} 안전 브리핑</h3>
<p>{_text(report.get("site"))} · {_text(report.get("location"), "현장 지역 미입력")}</p></div>{preview_banner}</header>
<div class="sr-summary">{summary}</div>
<section class="sr-section"><div class="sr-section-head"><strong>{scope} 예정 작업</strong><span>{len(tasks)}건</span></div>
<div class="sr-task-list">{"".join(task_rows)}</div></section>
<section class="sr-section"><div class="sr-section-head"><strong>현장 조건</strong></div><div class="sr-context">{_text(weather_brief)} <i>·</i> {_text(season)}철</div>
<div class="sr-context-note">{_text(context_note)}</div>
{"<div class=\"sr-weather-list\">" + "".join(weather_rows) + "</div>" if weather_rows else ""}
{"<details class=\"sr-details\"><summary>추가 시간대 예보 보기</summary><div class=\"sr-details-body\"><ul>" + "".join(extra_weather_rows) + "</ul></div></details>" if extra_weather_rows else ""}
</section>
<section class="sr-section sr-cases"><div class="sr-section-head"><strong>작업별 유사 사고 유형</strong><span>공개 사례</span></div>
<div class="sr-case-grid">{"".join(case_cards)}</div>
<div class="sr-foot">공개 SIF 키워드 사례 빈도이며, 현장 사고율을 뜻하지 않습니다.</div>
{"<details class=\"sr-details\"><summary>추가 작업 사고 통계 보기</summary><div class=\"sr-details-body\"><ul>" + "".join(extra_cases) + "</ul></div></details>" if extra_cases else ""}
</section></section>'''

    if not show_cases:
        html = html[:html.index('<section class="sr-section sr-cases">')] + "</section>"
    return html
