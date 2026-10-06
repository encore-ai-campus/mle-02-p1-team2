"""Plan parsing, request isolation, citation and real Streamlit lifecycle checks."""
from copy import deepcopy
from datetime import date, timedelta, time
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
from openpyxl import Workbook
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import get_widget_state
from streamlit.proto.WidgetStates_pb2 import WidgetState

from preventra_plan import domain
from preventra_plan.agent import PlanTools, dispatch
from preventra_plan.storage import SavedPlan, PlanConflict
from preventra_ui.gateway import AssistantRequest, AssistantResult, Evidence
from preventra_ui.history import encode_result, decode_result
from preventra_ui_v2.presentation import for_display
from preventra_agent.agent import SafetyAgent
from preventra_fakes import MemoryStore
from test_preventra_agent import Model, call, final

ENTRY = Path(__file__).resolve().parents[1] / 'preventra_plus.py'


def browser_widget_state(node):
    # Streamlit 1.64 AppTest omits stateful tab blocks from browser events.
    # Supply the same string_value the real browser sends, leaving other widgets intact.
    if node.type == 'tab_container' and node.proto.tab_container.id:
        identifier=node.proto.tab_container.id
        return WidgetState(id=identifier, string_value=node.root.session_state[identifier])
    return get_widget_state(node)


def workbook_bytes(extra=False):
    day = domain.today_korea().isoformat()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = '계획'
    sheet.append(['현장명', '검증용 가상 현장'])
    sheet.append(list(domain.HEADERS))
    sheet.append(['A', day, '09:00', '11:00', '1구역', '실내', '운반', '지게차 자재 운반',
                  '지게차', 2, '가상업체', '가상담당', '보행 통로 구분', '작업구역 확인', '', ''])
    sheet.append(['B', day, '10:00', '12:00', '1구역', '', '정리', '자재 정리',
                  '', None, '', '', '', '', '', ''])
    if extra:
        sheet.append(['BAD', day, '12:00', '09:00', '1구역', '', '', '잘못된 시간'])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def context():
    plan = domain.read_work_plan(workbook_bytes())
    return {'work_plan': domain.snapshot(plan, domain.today_korea())}


class MemoryPlans:
    def __init__(self):
        self.rows = {}
        self.fail_load = False
        self.fail_save = False

    def load(self, identifier):
        if self.fail_load:
            raise RuntimeError('private-secret')
        return deepcopy(self.rows.get(identifier, SavedPlan()))

    def save(self, identifier, value, expected_revision):
        if self.fail_save:
            raise RuntimeError('private-secret')
        current = self.load(identifier)
        if current.revision != expected_revision:
            raise PlanConflict('다른 화면에서 변경되었습니다.')
        domain.validate_snapshot(value)
        result = SavedPlan(current.revision + 1, deepcopy(value))
        self.rows[identifier] = result
        return result


class PlanDomainTests(unittest.TestCase):
    def test_real_excel_validation_roundtrip_and_coordination(self):
        plan = domain.read_work_plan(workbook_bytes(extra=True))
        self.assertEqual(len(plan.items), 2)
        self.assertEqual(len(plan.issues), 1)
        self.assertEqual(domain.decode_plan(domain.encode_plan(plan)), plan)
        self.assertEqual(len(domain.coordination_candidates(plan.items, domain.today_korea())), 1)
        self.assertIn('투입 인원', domain.missing_work_fields(plan.items[1]))
        with self.assertRaises(ValueError):
            domain.read_work_plan(b'not an Excel file')
        with self.assertRaises(ValueError):
            domain.read_work_plan(domain.blank_template())

    def test_plan_tool_no_date_substitution_and_no_person_fields(self):
        backend = PlanTools(context())
        result = backend.plan_result(None, None)
        self.assertEqual(result.data['work_count'], 2)
        self.assertNotIn('가상담당', str(result.model_payload()))
        self.assertNotIn('가상업체', str(result.model_payload()))
        tomorrow = (domain.today_korea() + timedelta(days=1)).isoformat()
        self.assertEqual(backend.plan_result(tomorrow, None).status, 'empty')
        self.assertEqual(backend.plan_result(None, 'missing').status, 'empty')
        self.assertEqual(PlanTools({}).plan_result(None, None).status, 'empty')
        self.assertEqual(len(backend.build()), 5)

    def test_plan_citation_and_gateway_preserve_separate_sources(self):
        backend = PlanTools(context())
        model = Model(call('get_work_plan', {'day': None, 'work_id': 'A', 'period': None}),
                      final('계획에는 통로 구분이 적혀 있습니다. [PLAN-1]', ['PLAN-1']))
        request = AssistantRequest('req', 'session', '오늘 작업', context=context())
        with patch('preventra_plan.agent.SafetyAgent', return_value=SafetyAgent(model, backend)), \
             patch('preventra_agent.observability.get_tracing_client', return_value=None):
            result = dispatch(request)
        self.assertEqual(result.status, 'ready')
        self.assertEqual(len(result.plan_sources), 1)
        self.assertEqual(result.guides, [])
        self.assertEqual(decode_result(encode_result(result), '').plan_sources, result.plan_sources)
        self.assertNotIn('[PLAN-1]', for_display(result).answer)
        self.assertIn('[PLAN-1]', result.answer)
        with patch('preventra_agent.observability.get_tracing_client', return_value=None):
            bad = SafetyAgent(Model(final('가짜 [PLAN-99]', ['PLAN-99'])), PlanTools(context())).run('작업')
        self.assertEqual(bad.status, 'error')

    def test_without_plan_uses_existing_gateway(self):
        with patch('preventra_ui.gateway.dispatch', return_value=AssistantResult(answer='기존')) as original:
            result = dispatch(AssistantRequest('r', 's', '통계'))
        self.assertEqual(result.answer, '기존')
        original.assert_called_once()

    def test_relative_days_follow_selected_plan_date_and_explicit_date_wins(self):
        plan = domain.read_work_plan(workbook_bytes())
        day = domain.today_korea() + timedelta(days=6)
        plan = replace(plan, items=tuple(replace(i, day=day) for i in plan.items))
        backend = PlanTools({'work_plan': domain.snapshot(plan, day, 'A')})
        self.assertEqual(backend.plan_result('today', None, 'morning').data['day'], day.isoformat())
        self.assertEqual(backend.plan_result(None, None).data['work_count'], 1)
        self.assertEqual(backend.plan_result(None, '*').data['work_count'], 2)
        self.assertEqual(backend.plan_result('tomorrow', None).data['day'], (day + timedelta(days=1)).isoformat())
        self.assertEqual(backend.plan_result('calendar_today', None).status, 'empty')
        self.assertEqual(backend.plan_result(domain.today_korea().isoformat(), None).status, 'empty')

    def test_morning_and_afternoon_include_only_overlapping_work(self):
        plan = domain.read_work_plan(workbook_bytes())
        items = (replace(plan.items[0], start=time(8), end=time(12)),
                 replace(plan.items[1], start=time(12), end=time(17)),
                 replace(plan.items[1], work_id='C', start=time(11), end=time(13)))
        backend = PlanTools({'work_plan': domain.snapshot(replace(plan, items=items), domain.today_korea())})
        self.assertEqual([r['work_id'] for r in backend.plan_result(None, '*', 'morning').data['items']], ['A', 'C'])
        self.assertEqual([r['work_id'] for r in backend.plan_result(None, '*', 'afternoon').data['items']], ['B', 'C'])

    def test_selected_date_prompt_and_followup_history_reach_model(self):
        from preventra_ui.gateway import ConversationTurn
        ctx=context()
        ctx['work_plan']['day']='2026-10-12'
        req=AssistantRequest('r', 's', '그중 지게차 작업은?',
                             history=(ConversationTurn('오늘 오전 작업', '지게차와 자재 정리 작업입니다.'),), context=ctx)
        with patch('preventra_plan.agent.SafetyAgent') as factory, \
             patch('preventra_ui.gateway.dispatch') as gateway:
            dispatch(req)
        self.assertIn('계획 기준일은 2026-10-12', factory.call_args.kwargs['system_prompt'])
        self.assertIs(gateway.call_args.args[0], req)


class PlusUITests(unittest.TestCase):
    def setUp(self):
        self.store, self.plans = MemoryStore(), MemoryPlans()
        patch('streamlit.testing.v1.element_tree.get_widget_state', side_effect=browser_widget_state).start()
        patch('preventra_ui.state.get_store', return_value=self.store).start()
        patch('preventra_plan.ui.get_plan_store', return_value=self.plans).start()
        self.dispatch = patch('preventra_plan.agent.dispatch', return_value=AssistantResult(answer='검증 답변')).start()
        self.stats = patch('preventra_ui.statistics_view.get_statistics', side_effect=AssertionError('home must not load stats')).start()
        self.addCleanup(patch.stopall)

    def app(self, role='작업자'):
        app = AppTest.from_file(str(ENTRY), default_timeout=20)
        app.session_state['plus_home_tabs'] = role
        app.run()
        self.assertFalse(app.exception)
        return app

    def click(self, app, key):
        app.button(key).click().run()
        self.assertFalse(app.exception)

    def apply(self, app, plan=None):
        if app.session_state['preventra_page'] == '홈':
            app.session_state['plus_home_tabs'] = '관리자'
        app.session_state['plus_candidate'] = plan or domain.read_work_plan(workbook_bytes())
        app.run()
        self.click(app, 'plus_apply')

    def test_home_is_simple_and_actual_upload_preview_requires_apply(self):
        with patch('streamlit.file_uploader', return_value=BytesIO(workbook_bytes())):
            app = self.app('관리자')
        self.assertIsNotNone(app.session_state['plus_candidate'])
        self.assertEqual(len(self.store.rows), 0)
        self.assertEqual(len(app.metric), 0)
        self.stats.assert_not_called()
        self.click(app, 'plus_apply')
        self.assertIsNotNone(app.session_state['plus_saved'].snapshot)

    def test_apply_ask_rerun_restore_and_conversation_isolation(self):
        app = self.app()
        self.apply(app)
        identifier = app.session_state['preventra_conversation_id']
        app.selectbox('plus_work').set_value('A').run()
        self.click(app, 'plus_ask')
        app.run().run()
        self.dispatch.assert_called_once()
        request = self.dispatch.call_args.args[0]
        self.assertEqual(request.context['work_plan']['work_id'], 'A')
        self.assertEqual(len(self.store.load(identifier)), 1)
        self.click(app, 'preventra_new_chat')
        self.assertEqual(app.session_state['plus_saved'], SavedPlan())
        self.assertIsNone(app.session_state['plus_candidate'])
        restored = self.app()
        self.click(restored, 'preventra_conversation_' + identifier)
        self.assertIsNotNone(restored.session_state['plus_saved'].snapshot)
        self.assertEqual(len(restored.chat_message), 2)
        self.dispatch.assert_called_once()

    def test_replacement_and_detach_preserve_old_answer_snapshot(self):
        app = self.app()
        self.apply(app)
        self.click(app, 'plus_ask')
        identifier = app.session_state['preventra_conversation_id']
        before = deepcopy(self.store.load(identifier)[0]['request'].context)
        self.apply(app)
        self.click(app, 'plus_detach')
        self.assertIsNone(app.session_state['plus_saved'].snapshot)
        self.assertEqual(self.store.load(identifier)[0]['request'].context, before)
        app.chat_input[0].set_value('안녕').run()
        self.assertEqual(self.dispatch.call_args.args[0].context, {})

    def test_plan_save_failure_preserves_current_plan(self):
        app = self.app()
        self.apply(app)
        previous = deepcopy(app.session_state['plus_saved'])
        self.plans.fail_save = True
        self.apply(app)
        self.assertEqual(app.session_state['plus_saved'], previous)
        self.assertTrue(any('저장하지 못했습니다' in w.value for w in app.warning))
        self.assertFalse(any('private-secret' in w.value for w in app.warning))

    def test_answer_save_retry_keeps_context_without_agent_rerun(self):
        app = self.app()
        self.apply(app)
        self.store.fail_save = True
        self.click(app, 'plus_ask')
        self.assertTrue(app.chat_input[0].disabled)
        self.assertTrue(app.button('plus_detach').disabled)
        self.store.fail_save = False
        self.click(app, 'preventra_retry_save')
        self.dispatch.assert_called_once()
        identifier = app.session_state['preventra_conversation_id']
        self.assertIn('work_plan', self.store.load(identifier)[0]['request'].context)

    def test_load_failure_clears_context_and_blocks_new_questions(self):
        app = self.app()
        self.apply(app)
        identifier = app.session_state['preventra_conversation_id']
        self.click(app, 'preventra_new_chat')
        self.plans.fail_load = True
        self.click(app, 'preventra_conversation_' + identifier)
        self.assertTrue(app.chat_input[0].disabled)
        self.assertIsNone(app.session_state['plus_saved'].snapshot)
        self.dispatch.assert_not_called()

    def test_no_work_date_is_not_shifted_to_another_day(self):
        app = self.app()
        self.apply(app)
        day = domain.today_korea() + timedelta(days=1)
        app.date_input('plus_day').set_value(day).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('등록된 작업이 없습니다' in i.value for i in app.info))
        self.assertEqual(app.session_state['plus_day'], day)

    def test_concurrent_plan_revision_is_not_overwritten(self):
        app = self.app()
        self.apply(app)
        identifier = app.session_state['preventra_conversation_id']
        self.plans.save(identifier, None, 1)
        self.apply(app)
        self.assertEqual(self.plans.load(identifier).revision, 2)
        self.assertIsNone(self.plans.load(identifier).snapshot)

    def test_worker_home_and_new_chat_have_no_plan_uploader(self):
        app = self.app()
        self.assertEqual([tab.label for tab in app.tabs], ['작업자', '관리자'])
        self.assertEqual(len(app.get('file_uploader')), 0)
        self.apply(app)
        self.click(app, 'preventra_new_chat')
        self.assertEqual(len(app.get('file_uploader')), 0)
        app.chat_input[0].set_value('지게차 사고사례 알려줘').run()
        self.assertEqual(self.dispatch.call_args.args[0].context, {})

    def test_followups_keep_selected_date_work_and_history_after_restore(self):
        app = self.app()
        plan = domain.read_work_plan(workbook_bytes())
        future = domain.today_korea() + timedelta(days=6)
        plan = replace(plan, items=tuple(replace(i, day=future) for i in plan.items))
        self.apply(app, plan)
        identifier=app.session_state['preventra_conversation_id']
        app.date_input('plus_day').set_value(future).run()
        app.selectbox('plus_work').set_value('A').run()
        questions=['오늘 오전 작업에서 주의사항 알려줘', '그 작업의 계획된 안전조치는?', '이 작업과 비슷한 사고는?']
        for index, question in enumerate(questions):
            app.chat_input[0].set_value(question).run()
            self.assertFalse(app.exception)
            request=self.dispatch.call_args.args[0]
            self.assertEqual(request.context['work_plan']['day'], future.isoformat())
            self.assertEqual(request.context['work_plan']['work_id'], 'A')
            self.assertEqual([turn.question for turn in request.history], questions[:index])
        self.assertEqual(self.dispatch.call_count, 3)
        self.click(app, 'preventra_new_chat')
        self.click(app, 'preventra_conversation_' + identifier)
        self.assertEqual(app.date_input('plus_day').value, future)
        self.assertEqual(app.selectbox('plus_work').value, 'A')
        app.chat_input[0].set_value('앞에서 말한 내용 더 짧게 정리해 줘').run()
        self.assertEqual(len(self.dispatch.call_args.args[0].history), 3)

    def test_home_tab_switch_keeps_manager_selection_and_worker_starts_clean(self):
        app=self.app()
        self.apply(app)
        app.selectbox('plus_work').set_value('A').run()
        identifier=app.session_state['preventra_conversation_id']
        self.click(app, 'preventra_sidebar_home')
        app.session_state['plus_home_tabs']='작업자'
        app.run()
        self.assertEqual(len(app.get('file_uploader')), 0)
        app.session_state['plus_home_tabs']='관리자'
        app.run()
        self.assertEqual(app.selectbox('plus_work').value, 'A')
        self.assertEqual(app.session_state['preventra_conversation_id'], identifier)
        self.click(app,'plus_resume')
        self.assertEqual(app.selectbox('plus_work').value,'A')
        self.click(app, 'preventra_sidebar_home')
        app.session_state['plus_home_tabs']='작업자'
        app.run()
        self.click(app,'pv2_example_지게차 사고사례')
        self.assertNotEqual(app.session_state['preventra_conversation_id'],identifier)
        self.assertEqual(self.dispatch.call_args.args[0].context,{})


if __name__ == '__main__':
    unittest.main()
