from __future__ import annotations
import argparse, csv, hashlib, json
from urllib.parse import quote
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


def rows(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def dec(value: str) -> Decimal:
    return Decimal(value.strip().replace(',', ''))


def src(filename: str, row: dict) -> str:
    keys=('source_row','industry_major','industry_mid','business_size','year','reference_date')
    return filename+'#'+'&'.join(f'{k}={quote(str(row[k]))}' for k in keys if row.get(k))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True, help='로컬 원천 데이터가 있는 RAG-project 경로')
    parser.add_argument('--output-dir', type=Path, default=Path('data/evaluation'))
    args=parser.parse_args()
    raw=args.source_root/'data/raw/sif_openapi_cases.jsonl'
    processed=args.source_root/'data/processed'
    cases=[json.loads(s) for s in raw.read_text(encoding='utf-8').splitlines() if s.strip()]
    valid=[c for c in cases if c.get('case_id') and all(c.get('fields',{}).get(k) for k in ('situation','disasterFactor','dcrsCntrplnCn'))]
    groups=defaultdict(list)
    for c in valid: groups[c['fields']['situation'].strip()].append(c)
    ranked=sorted(groups.items(),key=lambda x:(-len(x[1]),x[0]))
    situation_group_count=len(groups)
    if len(ranked)<35: raise SystemExit(f'eligible_situations={len(ranked)}; need 35')
    rec=[]
    def tbm(qid, task, situation, members):
        is_tbm=task=='pre_task_tbm'
        q=(f'오늘 {situation} 작업 전 TBM 내용을 만들어줘. 주요 위험요인, 예방수칙, 작업을 멈춰야 할 상황을 포함해줘.' if is_tbm else f'신규 근로자에게 {situation}의 핵심 안전수칙을 쉽게 알려줘. 작업 전 확인사항과 위험할 때의 행동도 포함해줘.')
        status='auto_pass_candidate' if len(members)>=3 else 'human_review_needed'
        rec.append({'question_id':qid,'category':'tbm','task_type':task,'question':q,'constraints':{'work_situation':situation},'evidence_ids':[c['case_id'] for c in members],'expected_points':['위험과 통제는 연결된 사례의 근거 필드에 맞춘다','초보 작업자가 이해할 쉬운 표현을 사용한다','자료에 없는 법적 의무나 작업중지 기준을 단정하지 않는다'],'answer_checks':['evidence_grounding','risk_and_control_present','plain_language','no_unsupported_claims'],'status':status,'issue_code':'LOW_SUPPORT_GROUP' if len(members)<3 else '', 'issue_note':f'동일 작업상황 근거 사례 {len(members)}건' if len(members)<3 else '', 'validation_attempts':0,'review_provenance':'정확한 원천 situation 값으로 그룹화; 사람 확정 라벨 아님','label_scope':'동일한 원천 situation 값의 사례','source_fields':['situation','disasterFactor','dcrsCntrplnCn']})
    for i,(s,cs) in enumerate(ranked[:20],1): tbm(f'TBM-{i:03d}','pre_task_tbm',s,cs)
    for i,(s,cs) in enumerate(ranked[20:35],21): tbm(f'TBM-{i:03d}','new_worker_rules',s,cs)
    # Specific case teaching prompts: context carries the cited record; the query itself stays natural.
    selected=[]; used_situations=set()
    for c in sorted(valid,key=lambda x:x['case_id']):
        s=c['fields']['situation']
        if s not in used_situations:
            selected.append(c); used_situations.add(s)
        if len(selected)==15: break
    if len(selected)<15: raise SystemExit('not enough distinct case situations')
    for i,c in enumerate(selected,36):
        f=c['fields']; s=f['situation']
        rec.append({'question_id':f'TBM-{i:03d}','category':'tbm','task_type':'case_based_training','question':f'이 {s} 사고사례를 작업자 교육용으로 쉽게 설명해줘. 사고가 난 흐름과 재발방지 행동을 짚어줘.','constraints':{'context_case_id':c['case_id']},'evidence_ids':[c['case_id']],'expected_points':['사고개요와 위험요인을 원천에 맞게 설명한다','예방대책을 작업자가 실행할 행동으로 풀어쓴다','사례에 없는 원인·결과를 덧붙이지 않는다'],'answer_checks':['overview_matches_source','factor_matches_source','controls_matches_source','plain_language','no_unsupported_claims'],'status':'auto_pass_candidate','issue_code':'','issue_note':'','validation_attempts':0,'review_provenance':'단일 사고사례 원천 필드 연결; 사람 확정 라벨 아님','source_fields':['disasterOverview','disasterFactor','dcrsCntrplnCn']})
    inj_n='15084672_industry_size_accident_injured_2025_tidy.csv'; fat_n='15084674_industry_size_fatalities_2025_tidy.csv'; rate_n='15064491_industry_size_fatality_rate_2025_tidy.csv'; trend_n='15084663_accident_fatalities_by_size_2004_2025_tidy.csv'
    inj=rows(processed/inj_n); fat=rows(processed/fat_n); rate=rows(processed/rate_n); trend=rows(processed/trend_n)
    industries=sorted({r['industry_major'] for r in fat})
    # 20 direct industry metrics: each observed industry, injured and fatality counts.
    for industry in industries:
        for name,data,file,metric in [('사고재해자 수',inj,inj_n,'accident_injured_count'),('사고사망자 수',fat,fat_n,'accident_fatality_count')]:
            subset=[r for r in data if r['industry_major']==industry]
            value=sum((dec(r['value']) for r in subset),Decimal(0))
            n=1+sum(x['category']=='statistics' for x in rec)
            rec.append({'question_id':f'STAT-{n:03d}','category':'statistics','task_type':'industry_metric_lookup','question':f'2025년 {industry} 전체의 {name}는 몇 명이야?','constraints':{'reference_period':'2025-12-31','industry_major':industry,'metric':metric,'unit':'명','aggregation':'산업중분류와 10개 사업장 규모 합계'},'evidence_ids':[src(file,r) for r in subset],'expected_answer':{'value':str(value),'unit':'명','metric':metric,'reference_period':'2025-12-31'},'expected_points':['정확한 합계와 명 단위를 제시한다','2025-12-31 기준임을 밝힌다','사고유형별 수치로 오해하지 않게 한다'],'answer_checks':['numeric_match','unit_match','period_match','source_match'],'status':'auto_pass_candidate','issue_code':'','issue_note':'','validation_attempts':0,'review_provenance':'원자료 행 합산; 계산 재현 가능, 사람 검증 아님'})
    # 15개 비교 문항: 5개 사업장 규모에서 사망자수·재해자수·사망만인율을 각각 비교한다.
    sizes=sorted({r['business_size'].replace(',','') for r in fat})
    chosen=[s for s in ['5인미만','5인-9인','10인-19인','50인-99인','1000인이상'] if s in sizes]
    if len(chosen)!=5: chosen=sizes[:5]
    for size in chosen:
        for data,file,metric,label,unit,is_rate in [(fat,fat_n,'accident_fatality_count','사고사망자 수','명',False),(inj,inj_n,'accident_injured_count','사고재해자 수','명',False),(rate,rate_n,'fatality_rate_per_10000','사망만인율','사망만인율',True)]:
            subset=[r for r in data if r['business_size'].replace(',','')==size and r.get('value','').strip()]
            groups=defaultdict(list)
            for row in subset: groups[(row['industry_major'],row['industry_mid'])].append(row)
            values={}
            for key,items in groups.items():
                if is_rate:
                    if len(items)!=1: raise SystemExit(f'non-unique rate row: {key}, {size}')
                    values[key]=dec(items[0]['value'])
                else: values[key]=sum((dec(x['value']) for x in items),Decimal(0))
            ordered=sorted(values,key=lambda k:(-values[k],k[0],k[1]))
            threshold=values[ordered[2]]
            top_keys=[k for k in ordered if values[k]>=threshold]
            top_rows=[row for key in top_keys for row in groups[key]]
            answer=[{'industry_major':key[0],'industry_mid':key[1],'value':str(values[key]),'unit':unit} for key in top_keys]
            n=1+sum(x['category']=='statistics' for x in rec)
            rec.append({'question_id':f'STAT-{n:03d}','category':'statistics','task_type':'industry_comparison','question':f'2025년 {size} 규모에서 {label}가 높은 업종중분류 상위 3위까지(동점 포함)는 어디야?','constraints':{'reference_period':'2025-12-31','business_size':size,'metric':metric,'unit':unit,'rank':'업종중분류 내림차순 상위 3위; 3위 동점 포함'},'evidence_ids':[src(file,row) for row in top_rows],'expected_answer':answer,'expected_points':['같은 사업장 규모 안에서 업종중분류를 비교한다','상위 3위까지 동점 업종과 원자료 값을 제시한다','사망자 수와 사망만인율을 혼동하지 않는다'],'answer_checks':['ranking_match','numeric_match','unit_match','period_match','metric_match'],'status':'auto_pass_candidate','issue_code':'','issue_note':'','validation_attempts':0,'review_provenance':'원자료 행 정렬; 재현 가능, 사람 검증 아님'})
    # 10개 장기 추세 문항: 사업장 규모별 2004년과 2025년을 비교한다.
    by_size=defaultdict(dict)
    for r in trend: by_size[r['business_size'].replace(',','')][r['year']]=r
    for size in sizes:
        pair=by_size[size]
        if '2004' not in pair or '2025' not in pair: continue
        a=dec(pair['2004']['value']); b=dec(pair['2025']['value']); delta=b-a
        pct=(delta/a*100) if a else None
        n=1+sum(x['category']=='statistics' for x in rec)
        rec.append({'question_id':f'STAT-{n:03d}','category':'statistics','task_type':'size_trend','question':f'{size} 사업장의 사고사망자 수는 2004년에서 2025년 사이 어떻게 변했어?','constraints':{'start_year':2004,'end_year':2025,'business_size':size,'metric':'accident_fatality_count','unit':'명','industry_breakdown':False},'evidence_ids':[src(trend_n,pair[y]) for y in ('2004','2025')],'expected_answer':{'2004':str(a),'2025':str(b),'change':str(delta),'change_percent':str(pct) if pct is not None else None,'direction':'증가' if delta>0 else '감소' if delta<0 else '변화 없음'},'expected_points':['두 연도 값과 변화 방향을 제시한다','해당 시계열에는 업종 구분이 없음을 설명한다','증감률의 기준값은 2004년 값으로 둔다'],'answer_checks':['source_values_match','delta_match','percent_match','scope_caveat_present'],'status':'auto_pass_candidate','issue_code':'','issue_note':'','validation_attempts':0,'review_provenance':'원자료 두 행에서 산출; 계산 재현 가능, 사람 검증 아님'})
    # Unsupported type-specific questions remain visible as exceptions, with abstention as the expected behavior.
    gaps=[('2025년 건설업에서 추락사고가 전체 사고에서 차지하는 비중은 얼마야?','사고유형별 건수 분자와 전체 사고 분모가 확인된 원천 없음'),('2025년 제조업 끼임사고는 몇 건이고 전체 사고의 몇 퍼센트야?','업종×사고유형 통계와 분모 원천 없음'),('최근 산업재해 사망자 중 추락 사망 비중은 얼마야?','사망자 수의 사고유형별 분류 및 기준기간 원천 없음'),('최근 5년 제조업 끼임사고 추세는 어때?','업종×사고유형×연도 시계열 원천 없음'),('최근 5년 건설업 추락사고는 증가했어, 감소했어?','업종×사고유형×연도 시계열 원천 없음')]
    for q,why in gaps:
        n=1+sum(x['category']=='statistics' for x in rec)
        rec.append({'question_id':f'STAT-{n:03d}','category':'statistics','task_type':'accident_type_statistics','question':q,'constraints':{'reference_period':'미정; 원천 확인 필요'},'evidence_ids':[],'expected_answer':{'behavior':'근거 부족을 알리고 답변 보류'},'expected_points':[],'answer_checks':['must_abstain_without_source'],'status':'source_needed','issue_code':'STAT_TYPE_SOURCE_MISSING','issue_note':why,'validation_attempts':0,'review_provenance':'자동 출처 커버리지 점검'})
    ids=[r['question_id'] for r in rec]; qs=[r['question'] for r in rec]
    assert len(rec)==100, f'total={len(rec)}'
    assert len(set(ids))==100, 'duplicate IDs'
    assert len(set(qs))==100, [q for q,n in Counter(qs).items() if n>1]
    assert Counter(r['category'] for r in rec)=={'tbm':50,'statistics':50}
    assert sum(r['category']=='statistics' and r['status']=='source_needed' for r in rec)==5
    caseids={c['case_id'] for c in cases}
    for r in rec:
        if r['category']=='tbm': assert r['evidence_ids'] and set(r['evidence_ids'])<=caseids
        if r['category']=='statistics' and r['status']=='auto_pass_candidate': assert r['evidence_ids'] and r.get('expected_answer') is not None
    rec.sort(key=lambda r:r['question_id'])
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'golden_set_candidates_v0.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rec),encoding='utf-8')
    exceptions=[r for r in rec if r['status'] in ('human_review_needed','source_needed','deferred')]
    (args.output_dir/'golden_set_exceptions_v0.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in exceptions),encoding='utf-8')
    source_paths=[raw,processed/inj_n,processed/fat_n,processed/rate_n,processed/trend_n]
    source_hashes={str(p.relative_to(args.source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    old_q_file=args.source_root/'data/evaluation/rag_questions_100.jsonl'
    old_qs=[json.loads(line) for line in old_q_file.read_text(encoding='utf-8').splitlines() if line.strip()] if old_q_file.exists() else []
    old_labeled=sum(bool(q.get('expected_case_ids')) for q in old_qs) if old_q_file.exists() else None
    report={'source_sha256':source_hashes,'total':len(rec),'by_category':dict(Counter(r['category'] for r in rec)),'by_status':dict(Counter(r['status'] for r in rec)),'tbm_types':dict(Counter(r['task_type'] for r in rec if r['category']=='tbm')),'statistics_types':dict(Counter(r['task_type'] for r in rec if r['category']=='statistics')),'sif_api_cases':len(cases),'eligible_cases':len(valid),'situation_groups':situation_group_count,'existing_100_question_set_labels':old_labeled,'checks':'PASS: totals, IDs, duplicate question text, case evidence IDs, and numeric expected-answer presence'}
    (args.output_dir/'golden_set_generation_report_v0.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
