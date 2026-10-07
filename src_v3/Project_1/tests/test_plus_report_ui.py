"""Offline regression tests: upload -> report -> saved plan -> follow-up."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from streamlit.testing.v1 import AppTest
from preventra_plan import domain, report
from preventra_plan.storage import SavedPlan
from preventra_ui.gateway import AssistantResult, Evidence
from preventra_ui.history import Conversation, encode_result, decode_result
from preventra_plan.vendor.briefing_report import safety_briefing_html

ENTRY = Path(__file__).resolve().parents[1] / 'preventra_plus.py'
DAY = date(2026, 10, 12)


def sample_bytes():
    book = Workbook()
    ws = book.active
    ws.title = '검증 계획'
    ws.append(['현장명', '회귀 검증 현장'])
    ws.append(list(domain.HEADERS))
    for ident, day, start, end, activity in (
        ('A', '2026-10-12', '08:00', '11:00', '비계 해체'),
        ('B', '2026-10-12', '13:00', '17:00', '자재 운반'),
        ('C', '2026-10-13', '09:00', '12:00', '후속일 작업'),
    ):
        ws.append([ident, day, start, end, 'B동', '외벽', '건축', activity,
                   '작업대', 2, '검증업체', '검증담당', '출입 통제', '발판 점검', '', ''])
    data = BytesIO()
    book.save(data)
    return data.getvalue()


class MemoryHistory:
    def __init__(self):
        self.rows = {}

    def create(self):
        key = str(uuid4())
        now = datetime.now(timezone.utc)
        self.rows[key] = [Conversation(key, '새 대화', now, now), []]
        return key

    def list_recent(self):
        return [row[0] for row in reversed(list(self.rows.values()))]

    def find_work_by_title(self, title):
        return next((k for k, (c, _) in self.rows.items() if c.title == title and c.record_type == 'work'), None)

    def set_work_title(self, key, title, days):
        self.rows[key][0] = replace(self.rows[key][0], title=title, record_type='work', work_days=tuple(days))

    def load(self, key, touch=False):
        return deepcopy(self.rows[key][1])

    def save_turn(self, request, result):
        row = self.rows[request.session_id]
        if any(t['request'].request_id == request.request_id for t in row[1]):
            return False
        row[1].append({'request': request, 'result': decode_result(encode_result(result), '')})
        row[0] = replace(row[0], has_messages=True)
        return True


class MemoryPlans:
    def __init__(self):
        self.rows = {}

    def load(self, key):
        return deepcopy(self.rows.get(key, SavedPlan()))

    def save(self, key, snapshot, revision):
        self.rows[key] = SavedPlan(snapshot=snapshot, revision=revision + 1)
        return self.load(key)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.history, self.plans = MemoryHistory(), MemoryPlans()
        self.stack.enter_context(patch('preventra_runtime.require_configuration'))
        self.stack.enter_context(patch('preventra_ui.state.get_store', return_value=self.history))
        self.stack.enter_context(patch('preventra_plan.ui.get_store', return_value=self.history))
        self.stack.enter_context(patch('preventra_plan.ui.get_plan_store', return_value=self.plans))
        self.weather = self.stack.enter_context(patch('preventra_plan.report.weather_for_day', return_value={'status': 'unavailable'}))
        self.search = self.stack.enter_context(patch('preventra_agent.tools.SafetyTools.search', side_effect=RuntimeError('offline')))
        self.dispatch = self.stack.enter_context(patch('preventra_plan.agent.dispatch', return_value=AssistantResult(answer='검증 답변 [PLAN-1]')))

    def app(self):
        at = AppTest.from_file(str(ENTRY), default_timeout=15).run()
        self.assertFalse(at.exception)
        return at

    def apply_plan(self, at):
        at.session_state.plus_candidate = domain.read_work_plan(sample_bytes())
        at.session_state.plus_candidate_token = 'fixture'
        at.session_state.plus_home_upload_open = True
        at.run()
        at.button(key='plus_apply').click().run()
        self.assertFalse(at.exception)

    def send(self, at, text):
        at.text_input(key='plus_manager_home_question').set_value(text)
        next(b for b in at.button if b.label == '↑').click().run()
        self.assertFalse(at.exception)

    def test_upload_preview_and_applied_report_do_not_call_external_services(self):
        at = self.app()
        at.button(key='plus_home_upload_toggle').click().run()
        with patch('streamlit.file_uploader', return_value=BytesIO(sample_bytes())):
            at.run()
        self.assertFalse(at.exception)
        self.assertTrue(at.get('plotly_chart'))
        self.assertEqual(len(self.plans.rows), 0)
        at.button(key='plus_apply').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(self.plans.rows), 1)
        self.assertTrue(at.get('plotly_chart'))
        self.weather.assert_not_called()
        self.search.assert_not_called()
        self.dispatch.assert_not_called()

    def test_followup_date_restore_and_failed_enrichment(self):
        at = self.app()
        self.apply_plan(at)
        ident = at.session_state.preventra_conversation_id
        at.button(key='plus_load_weather').click().run()
        at.button(key='plus_load_cases').click().run()
        self.assertFalse(at.exception)
        self.send(at, '오전 작업 알려줘')
        self.send(at, '그 작업의 확인사항은?')
        request = self.dispatch.call_args.args[0]
        self.assertEqual(request.context['work_plan']['day'], '2026-10-12')
        self.assertEqual(len(request.history), 1)
        self.assertEqual(len(self.history.load(ident)), 2)
        at.button(key=f'preventra_workday_{ident}_2026-10-13').click().run()
        self.send(at, '이 날짜 작업 알려줘')
        request = self.dispatch.call_args.args[0]
        self.assertEqual(request.context['work_plan']['day'], '2026-10-13')
        self.assertEqual(len(request.history), 0)
        at.button(key=f'preventra_workday_{ident}_2026-10-12').click().run()
        self.assertEqual(len(at.chat_message), 4)
        self.assertEqual(self.dispatch.call_count, 3)
        self.assertEqual(self.weather.call_count, 1)
        self.assertEqual(self.search.call_count, 1)

    def test_worker_question_is_not_given_manager_plan(self):
        at = self.app()
        self.apply_plan(at)
        at.button(key='plus_role_worker').click().run()
        at.text_area(key='preventra_home_question').set_value('지게차 작업 질문')
        next(b for b in at.button if b.label == '질문 보내기').click().run()
        self.assertFalse(at.exception)
        self.assertFalse(self.dispatch.call_args.args[0].context.get('work_plan'))

    def test_plan_cards_escape_inputs_and_timeline_uses_actual_schedule(self):
        plan = domain.read_work_plan(sample_bytes())
        items = domain.daily_rows(plan, DAY)
        figure = report.plan_timeline(items, DAY)
        self.assertEqual(list(figure.data[0].x), [3 * 3600000, 4 * 3600000])
        self.assertEqual(figure.data[0].base[1].hour, 13)
        payload = report.plan_brief_payload(plan, DAY, items, '하루 전체')
        payload['site'] = '<script>alert(1)</script>'
        markup = safety_briefing_html(payload, show_cases=False)
        self.assertIn('&lt;script&gt;', markup)
        self.assertNotIn('<script>', markup)
        self.assertIn('검증 계획 3행', markup)
        self.assertIn('하루 전체 예정 작업', markup)
        self.assertNotIn('오전 안전교육', markup)

    def test_case_chart_is_opt_in_keeps_source_and_reuses_cached_result(self):
        self.search.side_effect = None
        self.search.return_value = SimpleNamespace(evidence=[SimpleNamespace(
            title='검증용 사례', excerpt='검증용 사고 내용',
            source={'재해종류': '떨어짐', 'doc_id': 'fixture-case', 'source': '검증 자료', 'sheet': '사례', 'row_number': '2'},
        )])
        at = self.app()
        self.apply_plan(at)
        at.button(key='plus_load_cases').click().run()
        self.assertFalse(at.exception)
        markup = '\n'.join(str(e.proto) for e in at.get('html'))
        self.assertIn('sr-donut', markup)
        self.assertIn('떨어짐', markup)
        self.assertTrue(any('fixture-case' in m.value for m in at.markdown))
        at.run()
        self.assertEqual(self.search.call_count, 1)

    def test_display_hides_internal_tokens_but_saved_evidence_survives(self):
        self.dispatch.return_value = AssistantResult(
            answer='검증 답변 [SIF-1]',
            cases=[Evidence('검증 사고사례', 'case-id', '검증 본문', reference='SIF-1', source={'doc_id': 'case-id'})],
        )
        at = self.app()
        self.apply_plan(at)
        self.send(at, '관련 사고사례는?')
        saved = self.history.load(at.session_state.preventra_conversation_id)[0]['result']
        self.assertIn('[SIF-1]', saved.answer)
        self.assertEqual(saved.cases[0].reference, 'SIF-1')
        displayed = '\n'.join(m.value for m in at.markdown)
        self.assertNotIn('[SIF-1]', displayed)
        self.assertIn('검증 사고사례', displayed)
        self.assertIn('case-id', displayed)


if __name__ == '__main__':
    unittest.main()
