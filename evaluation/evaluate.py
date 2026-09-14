"""Synthetic rule-regression smoke test, NOT a legal accuracy benchmark."""
import json
import os
import sys
from pathlib import Path
os.environ['AI_PROVIDER']='demo'
os.environ['EMBEDDING_PROVIDER']='local'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import llm
cases=json.loads(Path(__file__).with_name('clause_cases.json').read_text(encoding='utf-8'))
tp=fp=fn=0
failed=[]
for case in cases:
    result=llm.demo_analysis([{'clause_index':0,'heading':None,'page':1,'text':case['text']}])
    actual={r['title'] for r in result['risky_clauses']}
    expected=set(case['expected'])
    tp+=len(actual&expected);fp+=len(actual-expected);fn+=len(expected-actual)
    if actual!=expected:
        failed.append({'case':case['title'],'expected':sorted(expected),'actual':sorted(actual)})
print(json.dumps({'scope':'14 authored synthetic cases; rule smoke test only, not legal/model accuracy',
    'cases':len(cases),'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/(tp+fn) if tp+fn else 0,
    'false_positives':fp,'false_negatives':fn,'failures':failed},indent=2))
raise SystemExit(1 if failed else 0)
