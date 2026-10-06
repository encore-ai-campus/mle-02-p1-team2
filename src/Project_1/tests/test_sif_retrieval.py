"""Synthetic regressions for SIF candidate recall; no network or model calls."""
import unittest
from unittest.mock import Mock, patch

import numpy as np
from langchain_core.documents import Document

from services.query_analysis import analyze_query
from services.safety_rag import SafetyRAGService, RerankBatch, CandidateJudgment
from services.sif_retrieval import KEYWORD_SQL, embedding_query, fuse_candidates, search_terms


def doc(identifier, body="테스트 공정 사고", **metadata):
    return Document(page_content=body, metadata={"source_id": identifier, "distance": .3, **metadata})


class QueryTests(unittest.TestCase):
    def test_agent_boilerplate_does_not_become_subject(self):
        q="제지 작업 중 발생한 산업재해 사고사례, 사고 경위와 원인"
        self.assertEqual(search_terms(q), ("제지",))
        self.assertEqual(embedding_query(q), "제지")

    def test_unknown_subjects_are_not_allowlisted(self):
        for term in ("제지", "인쇄", "혼합기", "섬유", "도금", "가상신설설비"):
            self.assertIn(term, search_terms(f"{term} 작업 사고사례 알려줘"))

    def test_subject_after_six_tokens_is_kept(self):
        self.assertIn("제지", search_terms("하나둘 셋넷 다섯 여섯 일곱 여덟 아홉 제지 사고사례"))

    def test_particles_do_not_destroy_short_material_name(self):
        self.assertEqual(search_terms("종이를 제조하는 작업 사고사례"), ("종이", "제조하"))
        self.assertEqual(search_terms("제지공장에서 발생한 사고"), ("제지공장",))

    def test_hazards_still_contribute_relevance(self):
        self.assertEqual(search_terms("제지 작업 끼임 사고사례 알려줘"), ("제지", "끼임"))

    def test_semantic_query_is_not_padded_with_generic_words(self):
        self.assertEqual(analyze_query("제지 작업 사고사례 알려줘").sif_query, "제지")

    def test_kosha_query_and_categories_are_unchanged(self):
        ctx=analyze_query("절단기 작업 전 점검")
        self.assertEqual(ctx.kosha_category, "용접·용단")
        self.assertEqual(ctx.kosha_query, "절단기 작업 전 점검 작업 전 점검사항 안전장치 확인 사전조사")
        self.assertEqual(ctx.search_terms, ("절단기",))

    def test_lexical_sql_excludes_provenance_and_uses_frequency(self):
        for field in ("source_file", "sheet", "row_number", "metadata::text"):
            self.assertNotIn(field, KEYWORD_SQL)
        self.assertIn("metadata->>'소분류'", KEYWORD_SQL)
        self.assertIn("f.df", KEYWORD_SQL)
        self.assertIn("strpos(d.search_text, t.term)", KEYWORD_SQL)


class FusionTests(unittest.TestCase):
    def test_both_full_channels_survive(self):
        fused=fuse_candidates([doc(f"k{i}") for i in range(10)], [doc(f"v{i}") for i in range(10)])
        self.assertEqual(len(fused),20)
        self.assertEqual({d.metadata['source_id'] for d in fused}, {f"{p}{i}" for p in 'kv' for i in range(10)})

    def test_overlap_deduplicated_and_boosted(self):
        original=doc("both", lexical_score=7, matched_terms=["제지"])
        fused=fuse_candidates([doc("k"), original], [doc("v"),doc("both")])
        self.assertEqual(len(fused),3)
        self.assertEqual(fused[0].metadata['source_id'],"both")
        self.assertEqual(fused[0].metadata['retrieval_channels'],['keyword','vector'])
        self.assertEqual(fused[0].metadata['lexical_score'],7)
        self.assertNotIn('fusion_score',original.metadata)

    def test_duplicate_within_channel_not_double_counted(self):
        fused=fuse_candidates([doc("a"),doc("a")],[])
        self.assertEqual(len(fused),1)
        self.assertEqual(fused[0].metadata['retrieval_channels'],['keyword'])

    def test_empty_lexical_still_searches_semantically(self):
        self.assertEqual(len(fuse_candidates([], [doc('v')])),1)


class RetrievalTests(unittest.TestCase):
    def service(self, keyword, semantic, scores=None):
        service=object.__new__(SafetyRAGService)
        service.sif_count=100
        service.sif_keyword_search=Mock(return_value=keyword)
        service.sif_search=Mock(return_value=semantic)
        ids=dict.fromkeys(d.metadata['source_id'] for d in keyword+semantic)
        service.rerank_llm=Mock(invoke=Mock(return_value=RerankBatch(rankings=[
            CandidateJudgment(doc_id=i,score=(scores or {}).get(i,90),reason="synthetic") for i in ids])))
        return service

    def test_hazard_does_not_filter_out_actual_accident(self):
        relevant=doc('paper', '제지공장 리와인더에 끼임', 재해유발요인='설비를 정지하지 않음')
        rag=self.service([relevant],[doc('other')],{'other':10})
        result=rag.retrieve_sif(np.ones(1536),analyze_query('제지 작업 끼임 사고사례'))
        self.assertEqual([d.metadata['source_id'] for d in result],['paper'])
        self.assertEqual(rag.sif_search.call_args.args[1],{})
        self.assertEqual(rag.sif_keyword_search.call_args.args[1],('제지','끼임'))

    def test_full_union_reaches_reranker_before_top_three(self):
        rag=self.service([doc(f'k{i}') for i in range(10)],[doc(f'v{i}') for i in range(10)],{'v9':100})
        result=rag.retrieve_sif(np.ones(1536),analyze_query('지게차 충돌 사고사례'))
        prompt=rag.rerank_llm.invoke.call_args.args[0].to_string()
        for p in 'kv':
            for i in range(10): self.assertIn(f'doc_id={p}{i}',prompt)
        self.assertEqual(result[0].metadata['source_id'],'v9')
        self.assertEqual(len(result),3)
        self.assertEqual(rag.sif_search.call_args.args[1],{})

    def test_unlisted_subject_uses_all_tokens_not_legacy_first_six(self):
        rag=self.service([],[])
        q='하나둘 셋넷 다섯 여섯 일곱 여덟 아홉 제지 사고사례'
        self.assertNotIn('제지',analyze_query(q).search_terms)
        rag.retrieve_sif(np.ones(1536),analyze_query(q))
        self.assertIn('제지',rag.sif_keyword_search.call_args.args[1])

    def test_small_pool_is_still_checked_for_relevance(self):
        rag=self.service([doc('unrelated')],[],{'unrelated':5})
        self.assertEqual(rag.retrieve_sif(np.ones(1536),analyze_query('제지 사례')),[])
        rag.rerank_llm.invoke.assert_called_once()

    def test_no_matches_skips_reranker(self):
        rag=self.service([],[])
        self.assertEqual(rag.retrieve_sif(np.ones(1536),analyze_query('제지 사례')),[])
        rag.rerank_llm.invoke.assert_not_called()

    def test_rerank_failure_uses_fused_candidates(self):
        rag=self.service([doc('k')],[doc('v')])
        rag.rerank_llm.invoke.side_effect=RuntimeError('synthetic')
        result=rag.retrieve_sif(np.ones(1536),analyze_query('제지 사례'))
        self.assertEqual({d.metadata['source_id'] for d in result},{'k','v'})
        self.assertTrue(all('통합 순위' in d.metadata['rerank_reason'] for d in result))

    def test_keyword_sql_parameters_are_bound_and_generic_terms_removed(self):
        rag=object.__new__(SafetyRAGService)
        with patch('services.safety_rag.psycopg.connect') as connect, patch('services.safety_rag.register_vector'):
            connection=connect.return_value.__enter__.return_value
            connection.execute.return_value.fetchall.return_value=[('test','본문',{},.2,3.5,['제지'])]
            result=rag.sif_keyword_search(np.ones(1536),('제지','산업재해'),10)
            sql,params=connection.execute.call_args.args
            self.assertEqual(sql,KEYWORD_SQL)
            self.assertEqual(params[2],['제지'])
            self.assertEqual(result[0].metadata['lexical_score'],3.5)


if __name__=='__main__':
    unittest.main()
