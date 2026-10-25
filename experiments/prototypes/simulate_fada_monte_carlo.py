#!/usr/bin/env python3
"""Independent Monte Carlo study: FADA versus interleaved dispatch."""
from __future__ import annotations
import argparse, json, math, random, statistics
from collections import defaultdict

MACHINES={'local':(32,1.0),'wsl':(24,.639),'asus':(16,.51),'i5':(4,.934),'acer':(4,.323),'dell':(8,.72),'bot':(12,.80)}
SCENARIOS=[50,100,200,400,800,1600]

def tasks(): return [n for n in SCENARIOS for _ in range(200)]
def duration(n,speed,rng,cv):
    mean=n/50/speed
    return max(.01,rng.lognormvariate(math.log(mean)-.5*math.log(1+cv*cv),math.sqrt(math.log(1+cv*cv))))
def run(policy,seed,epsilon,cv,fail_rate):
    rng=random.Random(seed); q=tasks(); slots=[]
    for machine,(count,speed) in MACHINES.items():
        for k in range(count): slots.append({'m':machine,'speed':speed,'free':0.0,'last':0.0})
    events=[]; order=0
    while q or events:
        free=[s for s in slots if s['free']<= (min((e[0] for e in events),default=0) if not q else min(s['free'] for s in slots))]
        if not q: break
        # advance to next free slot when no slot is immediately available
        t=min(s['free'] for s in slots); free=[s for s in slots if s['free']<=t+1e-12]
        if policy=='interleaved':
            chosen=q.pop(0); s=min(free,key=lambda x:(x['free'],x['m']))
        else:
            # Evaluate candidate scenarios and wait only if the slow tail is better served later.
            candidates=q[:min(60,len(q))]
            s=min(free,key=lambda x:x['free'])
            scored=[]
            for n in candidates:
                p=n/50/s['speed']
                projected=max(max(x['free'] for x in slots),t+p)
                scored.append((projected,p,n))
            scored.sort(); _,_,chosen=min(scored)
            q.remove(chosen)
        p=duration(chosen,s['speed'],rng,cv)
        if rng.random()<fail_rate: p*=2.5
        s['free']=max(s['free'],t)+p; s['last']=s['free']; order+=1
        events.append((s['free'],order))
        events=[e for e in events if e[0]>t]
    return max(s['last'] for s in slots)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--replicates',type=int,default=100); ap.add_argument('--epsilon',type=float,default=.005); ap.add_argument('--cv',type=float,default=.15); ap.add_argument('--fail-rate',type=float,default=.01); ap.add_argument('--output',required=True); a=ap.parse_args()
    fada=[]; inter=[]
    for seed in range(a.replicates):
        fada.append(run('fada',seed,a.epsilon,a.cv,a.fail_rate)); inter.append(run('interleaved',seed,a.epsilon,a.cv,a.fail_rate))
    result={'model':'FADA Monte Carlo','replicates':a.replicates,'machines':MACHINES,'tasks':1200,'cv':a.cv,'fail_rate':a.fail_rate,'epsilon':a.epsilon,'fada_mean':statistics.mean(fada),'interleaved_mean':statistics.mean(inter),'fada_median':statistics.median(fada),'interleaved_median':statistics.median(inter),'mean_gain_fraction':(statistics.mean(inter)-statistics.mean(fada))/statistics.mean(inter),'fada_p95':sorted(fada)[int(.95*len(fada))-1],'interleaved_p95':sorted(inter)[int(.95*len(inter))-1],'note':'simulação independente; não altera campanha ativa'}
    open(a.output,'w',encoding='utf-8').write(json.dumps(result,indent=2,ensure_ascii=False)+'\n'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
