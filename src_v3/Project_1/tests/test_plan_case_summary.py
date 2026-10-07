"""Report counts use full literal keyword matches, independent of chat TOP_K."""
from base64 import b64decode
from concurrent.futures import Future
import re
from datetime import date
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from preventra_plan.case_catalog import CaseCatalog, CatalogCache, load_catalog
from preventra_plan.case_report import render_case_report, _case_cards_html
from test_plus_report_ui import fixture_catalog, ready_future


class CatalogTests(unittest.TestCase):
    def test_full_counts_keep_all_ids_and_do_not_depend_on_chat_topk(self):
        catalog = fixture_catalog()
        summary = catalog.summary('비계 해체', '작업대')
        self.assertEqual(summary.total, 12)
        self.assertEqual(len(summary.record_ids), 12)
        self.assertEqual(summary.counts, (('떨어짐', 7), ('맞음', 5)))
        self.assertEqual(summary.keyword, '비계')

    def test_original_keyword_precedence_threshold_and_empty_dataset(self):
        catalog = fixture_catalog()
        summary = catalog.summary('없는작업', '작업대')
        self.assertEqual(summary.field, '기인물')
        self.assertEqual(summary.total, 12)
        self.assertIsNone(catalog.summary('없는작업', '없는장비'))
        small = CaseCatalog([('one', '', {'group': '건설업', '작업중분류': '비계'})])
        self.assertIsNone(small.summary('비계', ''))
        self.assertIsNone(CaseCatalog([]).summary('비계', ''))

    def test_nonconstruction_and_duplicate_ids_do_not_inflate_denominator(self):
        rows = [('one', '', {'group': '건설업'}), ('one', '', {'group': '건설업'}), ('two', '', {'group': '제조업등'})]
        self.assertEqual(len(CaseCatalog(rows).frame), 1)

    def test_one_background_read_is_shared_and_failures_can_be_retried(self):
        started, release = Event(), Event()
        calls = []
        def loader(dsn):
            calls.append(dsn)
            started.set()
            release.wait(3)
            return fixture_catalog()
        cache = CatalogCache(loader)
        try:
            first = cache.get('fake-test-dsn')
            self.assertTrue(started.wait(1))
            self.assertFalse(first.done())
            self.assertIs(first, cache.get('fake-test-dsn', refresh=True))
            release.set()
            first.result(timeout=3)
            self.assertIs(first, cache.get('fake-test-dsn'))
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            cache.executor.shutdown(wait=True)
        cache = CatalogCache(Mock(side_effect=[RuntimeError('offline'), fixture_catalog()]))
        try:
            failed = cache.get('fake-test-dsn')
            with self.assertRaises(RuntimeError):
                failed.result(timeout=3)
            self.assertIs(failed, cache.get('fake-test-dsn'))
            self.assertEqual(len(cache.get('fake-test-dsn', refresh=True).result(timeout=3).frame), 12)
        finally:
            cache.executor.shutdown(wait=True)

    def test_database_read_is_bounded_readonly_and_does_not_download_embeddings_or_content(self):
        with patch('preventra_plan.case_catalog.psycopg.connect') as connect:
            connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
            load_catalog('fake-test-dsn')
            args = connect.call_args.kwargs
            self.assertEqual(args['connect_timeout'], 5)
            self.assertIn('default_transaction_read_only=on', args['options'])
            sql = connect.return_value.__enter__.return_value.execute.call_args.args[0]
            self.assertNotIn('embedding', sql)
            self.assertIn("''::text AS content", sql)

    def test_donut_is_preserved_as_svg_image_and_dynamic_labels_are_escaped(self):
        markup = _case_cards_html([{'activity': '<script>bad()</script>', 'total': 12,
                                  'counts': [{'name': '떨어짐', 'count': 7}, {'name': '맞음', 'count': 5}]}])
        self.assertNotIn('<script>', markup)
        self.assertIn('&lt;script&gt;', markup)
        encoded = re.search(r'data:image/svg\+xml;base64,([^" ]+)', markup).group(1)
        svg = b64decode(encoded).decode()
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn('떨어짐 7건', svg)
        self.assertIn('>12</text>', svg)

    def test_pending_catalog_does_not_block_plan_or_question_widgets(self):
        app = '''
import streamlit as st
from types import SimpleNamespace
from preventra_plan.case_report import render_case_report, _case_cards_html
st.markdown('계획 보고서 표시')
render_case_report([SimpleNamespace(activity='비계', equipment='작업대', work_id='A')], key='pending_test')
st.text_input('후속 질문')
'''
        future = Future()
        with patch('preventra_plan.case_report.catalog_future', return_value=future):
            at = AppTest.from_string(app).run()
            self.assertFalse(at.exception)
            self.assertEqual(at.text_input[0].label, '후속 질문')
            self.assertTrue(any('자동으로 연결' in c.value for c in at.caption))
            future.set_result(fixture_catalog())
            at.run()
            self.assertFalse(at.exception)
            self.assertTrue(any('12건' in e.label for e in at.expander))


if __name__ == '__main__':
    unittest.main()
