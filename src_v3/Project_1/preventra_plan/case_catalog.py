"""Report-only SIF catalog. No embeddings, LLM rerank, or chat TOP_K."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from hashlib import sha256
from threading import Lock
from time import monotonic
from types import SimpleNamespace

import pandas as pd
import psycopg
import streamlit as st

from preventra_settings import database_settings
from preventra_plan.vendor.case_summary import summarize_cases

CATALOG_SQL = """
SELECT DISTINCT ON (source_id) source_id, ''::text AS content, metadata
FROM rag_day1_documents
WHERE kind = 'sif_case' AND metadata->>'group' = '건설업'
ORDER BY source_id
"""


class CaseCatalog:
    def __init__(self, rows):
        records = []
        for source_id, content, meta in rows:
            if meta.get('group') != '건설업':
                continue
            records.append({
                'record_id': str(source_id), 'industry_major': '건설업',
                'work_name': str(meta.get('작업중분류') or ''),
                'unit_work': str(meta.get('작업소분류') or ''),
                'causal_object': str(meta.get('기인물') or ''),
                'accident_type': str(meta.get('재해종류') or ''),
                'trigger_factor': str(meta.get('재해유발요인') or ''),
                # The existing Preventra report does not treat case measures as official guidance.
                'risk_reduction_measures': '', 'risk_measures_available': False,
                'content': content or '', 'source_file': str(meta.get('source_file') or ''),
                'sheet': str(meta.get('sheet') or ''), 'row_number': str(meta.get('row_number') or ''),
            })
        columns = ['record_id', 'industry_major', 'work_name', 'unit_work', 'causal_object',
                   'accident_type', 'trigger_factor', 'risk_reduction_measures',
                   'risk_measures_available', 'content', 'source_file', 'sheet', 'row_number']
        self.frame = pd.DataFrame(records, columns=columns).drop_duplicates('record_id')
        self.records = self.frame.set_index('record_id').to_dict('index')
        self.summary = lru_cache(maxsize=512)(self._summary)

    def _summary(self, activity, equipment):
        return summarize_cases(SimpleNamespace(activity=activity, equipment=equipment), self.frame)


def load_catalog(dsn):
    """Bounded read-only query; source text stays in server memory, never logged."""
    with psycopg.connect(dsn, connect_timeout=5,
                         options='-c statement_timeout=7000 -c default_transaction_read_only=on') as conn:
        rows = conn.execute(CATALOG_SQL).fetchall()
    return CaseCatalog(rows)


class CatalogCache:
    """Single in-flight fetch per DB. Polling the UI never starts another fetch."""
    def __init__(self, loader=load_catalog, ttl=3600, error_ttl=30):
        self.loader, self.ttl, self.error_ttl = loader, ttl, error_ttl
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='plan-sif-catalog')
        self.lock = Lock()
        self.entries = {}

    def get(self, dsn, *, refresh=False):
        key = sha256(dsn.encode()).hexdigest()
        now = monotonic()
        with self.lock:
            entry = self.entries.get(key)
            if entry:
                started, future = entry
                if not future.done():
                    return future
                ttl = self.error_ttl if future.exception() else self.ttl
                if not refresh and now - started < ttl:
                    return future
            # There is normally one configured DB. Bound cached alternate configurations.
            if key not in self.entries and len(self.entries) >= 4:
                for old_key, (_, old_future) in list(self.entries.items()):
                    if old_future.done():
                        del self.entries[old_key]
                        break
                else:
                    raise RuntimeError('Report catalog busy')
            future = self.executor.submit(self.loader, dsn)
            self.entries[key] = now, future
            return future


@st.cache_resource(show_spinner=False)
def _catalog_cache():
    return CatalogCache()


def catalog_future(*, refresh=False):
    # Resolve settings on the Streamlit thread; workers never access session state or secrets.
    dsn, _, valid, error = database_settings()
    if not valid or error:
        raise RuntimeError('Report catalog configuration unavailable')
    return _catalog_cache().get(dsn, refresh=refresh)


@st.cache_data(ttl=3600, max_entries=128, show_spinner=False)
def _case_text(source_id, database_key, _dsn):
    with psycopg.connect(_dsn, connect_timeout=5,
                         options='-c statement_timeout=7000 -c default_transaction_read_only=on') as conn:
        row = conn.execute("""SELECT content FROM rag_day1_documents
            WHERE source_id=%s AND kind='sif_case' AND metadata->>'group'='건설업' LIMIT 1""",
                           (source_id,)).fetchone()
    return row[0] if row else None


def case_text(source_id):
    dsn, _, valid, error = database_settings()
    if not valid or error:
        raise RuntimeError('Report catalog configuration unavailable')
    return _case_text(source_id, sha256(dsn.encode()).hexdigest(), dsn)
