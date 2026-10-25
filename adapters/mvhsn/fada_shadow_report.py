#!/usr/bin/env python3
"""Read-only FADA shadow analysis for an active MVHSN queue."""
from __future__ import annotations
import argparse, csv, hashlib, json, sqlite3, statistics
from collections import defaultdict
from pathlib import Path

WORKERS = {'local':32,'asus':16,'wsl':24,'i5':4,'acer':4,'dell':8,'bot':12}


def load_workers(path: str | None):
    if path is None:
        return dict(WORKERS), {}, "legacy_builtin"
    workers = {}
    backends = {}
    with open(path, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("enabled", "true").strip().lower() != "true":
                continue
            machine = row.get("machine", "").strip()
            if not machine:
                raise ValueError("worker configuration contains an empty machine")
            slots = int(row.get("task_slots", "0"))
            if slots < 1 or machine in workers:
                raise ValueError(f"invalid or duplicate worker capacity: {machine}")
            workers[machine] = slots
            backends[machine] = row.get("gpu_backend", "").strip() or "unknown"
    if not workers:
        raise ValueError("worker configuration has no enabled workers")
    return workers, backends, hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--database',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--gpu-workers-csv')
    ap.add_argument('--required-execution-class', default='gpu')
    ap.add_argument('--required-requires-gpu', default='true', choices=('true', 'false'))
    a=ap.parse_args()
    workers, worker_backends, worker_source = load_workers(a.gpu_workers_csv)
    database = Path(a.database).resolve()
    c=sqlite3.connect(f"file:{database}?mode=ro", uri=True); c.row_factory=sqlite3.Row
    samples=defaultdict(list); pending=defaultdict(int); active=defaultdict(int); completed=defaultdict(int)
    execution_classes=set(); requires_gpu=set()
    for r in c.execute('select * from tasks'):
        p=json.loads(r['payload_json']); n=int(p.get('n',0)); key=(r['completed_by'],n)
        execution_classes.add(str(p.get('execution_class', 'unknown')))
        requires_gpu.add(str(p.get('requires_gpu', 'unknown')).lower())
        if r['status']=='complete' and r['completed_by'] and r['task_elapsed_seconds']:
            samples[key].append(float(r['task_elapsed_seconds'])); completed[key]+=1
        elif r['status']=='pending': pending[n]+=1
        elif r['status']=='leased': active[r['leased_by']]+=1
    global_by_n=defaultdict(list)
    for (_,n),vs in samples.items(): global_by_n[n]+=vs
    def pred(m,n):
        if samples[(m,n)]: return statistics.median(samples[(m,n)])
        if global_by_n[n]: return statistics.median(global_by_n[n])
        nearest=sorted(global_by_n, key=lambda x:abs(x-n))
        return statistics.median(global_by_n[nearest[0]])*(n/nearest[0])**1.2 if nearest else 3600.0
    recommendations=[]
    eligibility_verified = (
        bool(worker_backends)
        and execution_classes == {a.required_execution_class}
        and requires_gpu == {a.required_requires_gpu}
    )
    for m in workers:
        if not eligibility_verified or active[m] >= workers[m]: continue
        candidates=[]
        for n,count in pending.items():
            if count: candidates.append((pred(m,n),n))
        if candidates:
            # FADA recommends the task with the smallest predicted campaign impact,
            # preserving long tasks for workers where their relative cost is lower.
            candidates.sort()
            recommendations.append({'machine':m,'recommended_n':candidates[0][1],'predicted_seconds':candidates[0][0],'alternatives':[(n,round(t,1)) for t,n in candidates]})
    result={'mode':'FADA-shadow','read_only':True,'database_open_mode':'mode=ro','database_sha256':hashlib.sha256(database.read_bytes()).hexdigest(),'worker_capacities':workers,'worker_backends':worker_backends,'worker_configuration_sha256':worker_source,'campaign_execution_classes':sorted(execution_classes),'campaign_requires_gpu':sorted(requires_gpu),'eligibility_verified':eligibility_verified,'blocked_reason':None if eligibility_verified else 'backend_eligibility_not_verified','active_workers':dict(active),'pending_by_n':dict(pending),'completed_samples':{f'{m}:n{n}':len(v) for (m,n),v in samples.items()},'recommendations':recommendations,'warning':'recomendacoes nao alteram a fila ativa'}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'; Path(a.output).write_text(text,encoding='utf-8'); print(text,end=''); return 0
if __name__=='__main__': raise SystemExit(main())
