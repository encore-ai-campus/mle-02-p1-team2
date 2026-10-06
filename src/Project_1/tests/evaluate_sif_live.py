"""Opt-in real Supabase/OpenAI evaluation through Preventra's UI gateway.

Run from the repository root with PYTHONPATH=src/Project_1. This does not save
conversations or modify source data. The existing Langfuse integration applies.
Output contains source excerpts and must stay outside version control.
This is a diagnostic set, not an exhaustively labelled recall benchmark.
"""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4

QUERIES = (
    "제지 작업 사고사례 알려줘",
    "제지 작업 끼임 사고사례 알려줘",
    "제지공장 롤러 끼임 사고사례 알려줘",
    "종이 제조 작업 사고사례 알려줘",
    "인쇄기 작업 중 끼임 사고사례 알려줘",
    "혼합기 사고사례 알려줘",
    "섬유공장 설비에 말려드는 사고사례 알려줘",
    "도금 작업 사고사례 알려줘",
    "지게차 충돌 사고사례 알려줘",
    "굴착기 후진 중 충돌 사고사례 알려줘",
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly permit billable model calls with retrieved evidence')
    parser.add_argument('--output',required=True,type=Path,help='Private local JSONL, outside the repository')
    args=parser.parse_args()
    if not args.live:
        parser.error('--live is required; this sends queries/evidence to configured model and tracing services')
    root=Path(__file__).resolve().parents[3]
    output=args.output.resolve()
    if output.is_relative_to(root):
        parser.error('Keep evaluation output outside the repository')
    if output.exists():
        parser.error('Choose a new output path; existing evaluation records are preserved')
    output.parent.mkdir(parents=True,exist_ok=True)
    from preventra_runtime import require_database
    from preventra_ui.gateway import AssistantRequest, dispatch
    from preventra_agent.models import ConversationTurn
    from services.safety_rag import get_service
    from services.sif_retrieval import search_terms
    require_database()
    rag=get_service()
    calls=[]
    keyword,vector,retrieve=rag.sif_keyword_search,rag.sif_search,rag.retrieve_sif

    def brief(doc):
        return {'doc_id':doc.metadata['source_id'],
                'equipment':doc.metadata.get('기인물'),
                'industry':doc.metadata.get('중분류'),'subindustry':doc.metadata.get('소분류'),
                'distance':doc.metadata.get('distance'),
                'lexical_score':doc.metadata.get('lexical_score'),
                'matched_terms':doc.metadata.get('matched_terms'),
                'channels':doc.metadata.get('retrieval_channels'),
                'rerank_score':doc.metadata.get('rerank_score'),
                'rerank_reason':doc.metadata.get('rerank_reason')}

    def keyword_record(v,terms,k):
        docs=keyword(v,terms,k)
        calls.append({'stage':'keyword','terms':terms,'documents':[brief(d) for d in docs]})
        return docs

    def vector_record(v,conditions,k):
        docs=vector(v,conditions,k)
        calls.append({'stage':'vector','conditions':conditions,'documents':[brief(d) for d in docs]})
        return docs

    def retrieve_record(v,context):
        calls.append({'stage':'query','tool_query':context.resolved_question,
                      'embedding_query':context.sif_query,'subject_terms':search_terms(context.resolved_question)})
        docs=retrieve(v,context)
        calls.append({'stage':'reranked','documents':[brief(d) for d in docs]})
        return docs

    rag.sif_keyword_search=keyword_record
    rag.sif_search=vector_record
    rag.retrieve_sif=retrieve_record
    failures=0
    with output.open('x',encoding='utf-8') as sink:
        def run(question,history=(),conversation_id=None):
            nonlocal failures
            calls.clear()
            started=time.monotonic()
            result=dispatch(AssistantRequest(str(uuid4()),conversation_id or str(uuid4()),question,history=tuple(history)))
            row={'question':question,'history_turns':len(history),'status':result.status,
                 'used_tools':result.used_tools,'trace':result.trace,'stages':list(calls),
                 'answer':result.answer,'cases':[{'id':e.source_id,'excerpt':e.excerpt,'source':e.source} for e in result.cases],
                 'guide_count':len(result.guides),'seconds':round(time.monotonic()-started,2)}
            sink.write(json.dumps(row,ensure_ascii=False)+'\n')
            sink.flush()
            print(json.dumps({'question':question,'status':result.status,'tools':result.used_tools,
                              'case_count':len(result.cases),'seconds':row['seconds']},ensure_ascii=False),flush=True)
            failures+=result.status!='ready'
            return result

        for question in QUERIES:
            run(question)
        conversation_id=str(uuid4())
        question='제지공장에서 리와인더 작업을 하고 있어'
        first=run(question,conversation_id=conversation_id)
        run('이 작업의 실제 사고사례 알려줘',
            [ConversationTurn(question,first.answer)],conversation_id)
    if failures:
        raise SystemExit(f'{failures} execution failures; inspect the private output')


if __name__=='__main__':
    main()
