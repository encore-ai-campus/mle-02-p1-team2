"""Automatic multi-task report using the teammate's keyword summaries and cards."""
from base64 import b64encode
from hashlib import sha256
import re
from math import ceil

import streamlit as st

from preventra_plan.case_catalog import catalog_future, case_text
from preventra_plan.vendor.briefing_report import safety_briefing_html


def _case_cards_html(cases):
    markup = safety_briefing_html({'cases': cases})
    style = markup[markup.index('<style>'):markup.index('</style>') + 8]
    section = markup[markup.index('<section class="sr-section sr-cases">'):]
    # Streamlit removes inline SVG tags in HTML/Markdown. Preserve the teammate's
    # generated SVG as an image with self-contained styling instead.
    def svg_image(match):
        svg = match.group(0).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
        svg_style = """<style>
        .sr-donut-track,.sr-donut-slice{fill:none;transform:rotate(-90deg);transform-origin:44px 44px}
        .sr-donut-track{stroke:#E8EEF7;stroke-width:13}
        .sr-donut-slice{stroke-width:14}
        .sr-donut-total{fill:#203550;text-anchor:middle;font:700 15px sans-serif}
        .sr-donut-caption{fill:#7789A3;text-anchor:middle;font:8px sans-serif}
        </style>"""
        svg = svg.replace('>', '>' + svg_style, 1)
        encoded = b64encode(svg.encode()).decode()
        return f'<img class="sr-donut" alt="사고 유형 비율 그래프" width="82" height="82" src="data:image/svg+xml;base64,{encoded}">'
    section = re.sub(r'<svg class="sr-donut".*?</svg>', svg_image, section, flags=re.DOTALL)
    return '<section class="safety-report">' + style + section


def warm_case_catalog():
    """Prepare the shared report data while a manager chooses an upload."""
    try:
        catalog_future()
    except Exception:
        # Render the connection explanation only when there is an actual report.
        pass


def render_case_report(items, *, key):
    if not items:
        return
    st.markdown('#### 작업별 사고사례 보고서')
    try:
        future = catalog_future()
    except Exception:
        st.info('사고사례 자료에 연결하지 못했습니다. 계획 보고서와 질문은 계속 이용할 수 있습니다.')
        return
    if not future.done():
        # Render the plan and question widgets immediately. Stop timed reruns after completion.
        @st.fragment(run_every=1)
        def pending_catalog():
            if future.done():
                st.rerun()
            st.caption('계획 보고서는 준비됐습니다. 작업별 사고사례를 자동으로 연결하고 있습니다…')
        pending_catalog()
        return
    try:
        catalog = future.result()
    except Exception:
        st.info('사고사례 자료를 불러오지 못했습니다. 계획 보고서와 질문은 계속 이용할 수 있습니다.')
        if st.button('사고사례 연결 다시 시도', key=key + '_retry'):
            try:
                catalog_future(refresh=True)
            except Exception:
                pass
            st.rerun()
        return
    if catalog.frame.empty:
        st.info('연결된 자료에 건설업 사고사례가 없습니다.')
        return

    # Identical task/equipment pairs share a report, retaining every plan work ID.
    groups = {}
    for item in items:
        groups.setdefault((item.activity, item.equipment), []).append(item)
    jobs = list(groups)
    st.caption(f'연결된 건설업 SIF {len(catalog.frame):,}건에서 작업명·단위작업, 이어서 장비 키워드를 확인합니다. '
               '작업마다 같은 키워드가 5건 이상 나타나는 경우 집계합니다. 현장 사고율이나 위험 예측은 아닙니다.')
    page = 0
    if len(jobs) > 4:
        page = st.selectbox('보고서 작업 묶음', list(range(ceil(len(jobs) / 4))),
                            format_func=lambda n: f'{n * 4 + 1}–{min((n + 1) * 4, len(jobs))} / {len(jobs)}개 작업',
                            key=key + '_tasks')
    visible = jobs[page * 4:(page + 1) * 4]
    matches, cards = [], []
    for activity, equipment in visible:
        summary = catalog.summary(activity, equipment)
        if summary is None:
            st.caption(f'{activity}: 5건 이상 일치하는 작업·장비 키워드가 없습니다. 사고가 없거나 안전하다는 뜻은 아닙니다.')
            continue
        matches.append(((activity, equipment), summary))
        cards.append({'activity': activity, 'total': summary.total,
                      'counts': [{'name': name, 'count': count} for name, count in summary.counts],
                      'controls': []})
    if cards:
        # Keep the teammate's card layout with sanitized SVG images.
        # Dynamic text is escaped by safety_briefing_html before this point.
        st.markdown(_case_cards_html(cards), unsafe_allow_html=True)
    for job, summary in matches:
        activity, equipment = job
        job_key = sha256((activity + '\0' + equipment + '\0' + summary.keyword + '\0' + summary.field).encode()).hexdigest()[:16]
        st.caption(f'{activity} · {summary.field}의 “{summary.keyword}” 일치 {summary.total:,}건 · '
                   '계획 작업 ' + ', '.join(item.work_id for item in groups[job]))
        with st.expander(f'{activity} · 일치 사례 {summary.total:,}건 · 원문·출처'):
            pages = ceil(summary.total / 10)
            selected_page = st.selectbox('사례 페이지', list(range(pages)),
                                        format_func=lambda n: f'{n + 1} / {pages}',
                                        key=f'{key}_{job_key}_page') if pages > 1 else 0
            start = selected_page * 10
            st.caption(f'{start + 1}–{min(start + 10, summary.total)} / {summary.total:,}건 · 원본 ID 순서')
            for identifier in summary.record_ids[start:start + 10]:
                record = catalog.records[identifier]
                st.markdown('**' + (record['accident_type'] or '미분류') + ' · ' + record['work_name'] + '**')
                # Plain text avoids treating source documents as HTML or instructions.
                st.text(record['trigger_factor'] or '재해유발요인 미기재')
                st.caption(f"출처: {record['source_file']} · {record['sheet']} · 연번 {record['row_number']} · {identifier}")
                detail = st.expander('사례 원문 보기 · ' + identifier,
                                     key=f'{key}_{job_key}_{identifier}_detail', on_change='rerun')
                if detail.open:
                    with detail:
                        try:
                            text = case_text(identifier)
                        except Exception:
                            st.info('원문을 불러오지 못했습니다. 위의 출처로 원자료를 확인해 주세요.')
                        else:
                            st.text(text or '연결된 원문이 없습니다.')
            st.link_button('SIF 원자료 안내', 'https://www.data.go.kr/data/15140383/fileData.do')
    st.caption('키워드 일치 사례는 개별 작업의 적합성을 검증한 검색 순위가 아닙니다. 정확한 작업 조건·안전기준은 후속 질문에서 확인하세요.')
