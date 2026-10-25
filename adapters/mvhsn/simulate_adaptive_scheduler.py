#!/usr/bin/env python3
"""Offline, read-only comparison of adaptive scheduling and interleaved order."""
from __future__ import annotations
import argparse, json, math, sqlite3, statistics
from collections import defaultdict
from pathlib import Path

def load(db: Path):
    con=sqlite3.connect(db); con.row_factory=sqlite3.Row
    samples=defaultdict(list); pending=[]; leased=[]
    for r in con.execute("select * from tasks"):
        d=json.loads(r['payload_json']); n=int(d.get('n',0)); machine=r['completed_by']
        if r['status']=='complete' and machine and r['task_elapsed_seconds']:
            samples[(machine,n)].append(float(r['task_elapsed_seconds']))
        elif r['status']=='pending': pending.append(n)
        elif r['status']=='leased': leased.append((r['leased_by'],n))
    workers={r['completed_by']:0 for r in con.execute("select distinct completed_by from tasks where completed_by is not null")}
    for machine in ['local','asus','wsl','i5','acer','dell','bot']:
        workers.setdefault(machine, {'local':32,'asus':16,'wsl':24,'i5':4,'acer':4,'dell':8,'bot':12}[machine])
    return samples,pending,leased,workers

def estimate(samples, machine, n):
    values=samples.get((machine,n),[])
    if values: return statistics.median(values)
    # fallback: nearest observed scenario on this worker, then global n median
    nearest=[v for (m,k),vs in samples.items() if m==machine for v in vs]
    if nearest: return statistics.median(nearest)*(n/100)**1.35
    global_values=[v for (m,k),vs in samples.items() if k==n for v in vs]
    return (statistics.median(global_values) if global_values else 3600.0)*(n/100)**0.25

def simulate(samples,pending,leased,workers):
    load={m:0.0 for m in workers}
    for m,n in leased: load[m]+=estimate(samples,m,n)
    # LPT-like rolling horizon: each task goes to the worker slot with the earliest finish.
    slots=[]
    for m,count in workers.items():
        base=load[m]/max(1,count)
        slots += [[base,m] for _ in range(count)]
    for n in sorted(pending,key=lambda x: estimate(samples,'local',x),reverse=True):
        slot=min(slots,key=lambda x:x[0]); slot[0]+=estimate(samples,slot[1],n)
    return max(x[0] for x in slots)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--database',required=True); p.add_argument('--output')
    a=p.parse_args(); samples,pending,leased,workers=load(Path(a.database))
    adaptive=simulate(samples,pending,leased,workers)
    result={'model':'adaptive_worker_scenario_lpt','read_only':True,'pending':len(pending),'leased':len(leased),'adaptive_eta_seconds':adaptive,'adaptive_eta_hours':adaptive/3600,'samples':{f'{m}:n{n}':len(v) for (m,n),v in samples.items()},'note':'estimativa offline; nao altera a fila ativa'}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'; print(text,end='')
    if a.output: Path(a.output).write_text(text,encoding='utf-8')
if __name__=='__main__': main()
