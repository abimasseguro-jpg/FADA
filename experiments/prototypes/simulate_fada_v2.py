#!/usr/bin/env python3
"""FADA v2: full makespan look-ahead, scenario candidates and uncertainty."""
from __future__ import annotations
import argparse,json,math,random,statistics
M={'local':(32,1.0),'wsl':(24,.639),'asus':(16,.51),'i5':(4,.934),'acer':(4,.323),'dell':(8,.72),'bot':(12,.80)}
N=[50,100,200,400,800,1600]
def mean(n,s): return n/50/s
def sample(n,s,rng,cv): return max(.01,rng.lognormvariate(math.log(mean(n,s)-0.5*math.log(1+cv*cv)),math.sqrt(math.log(1+cv*cv))))
def forecast(loads,counts,chosen,slot,epsilon,cv):
    x=list(loads); x[slot]+=mean(chosen,M[list(M)[0]][1]) # replaced below by caller's slot speed
    return max(x)
def simulate(policy,seed,eps,cv,fail):
    rng=random.Random(seed); counts={n:200 for n in N}; slots=[]
    for name,(k,speed) in M.items():
        slots += [{'m':name,'s':speed,'free':0.0} for _ in range(k)]
    while sum(counts.values()):
        t=min(x['free'] for x in slots); free=[i for i,x in enumerate(slots) if x['free']<=t+1e-9]
        for i in free:
            if not sum(counts.values()): break
            if policy=='interleaved': chosen=next(n for n in N if counts[n]);
            else:
                candidates=[n for n in N if counts[n]]
                scores=[]
                for n in candidates:
                    loads=[x['free'] for x in slots]; loads[i]=t+mean(n,slots[i]['s'])
                    remaining=counts.copy(); remaining[n]-=1
                    # Heterogeneous LPT completion forecast for the entire remaining queue.
                    for k in sorted((k for k,v in remaining.items() for _ in range(v)),key=lambda z:z,reverse=True):
                        j=min(range(len(loads)),key=lambda q:loads[q]); loads[j]+=mean(k,slots[j]['s'])
                    uncertainty=cv*mean(n,slots[i]['s'])
                    scores.append((max(loads)+eps*max(loads)+uncertainty,n))
                chosen=min(scores)[1]
            counts[chosen]-=1; p=sample(chosen,slots[i]['s'],rng,cv)
            if rng.random()<fail: p*=2.5
            slots[i]['free']=t+p
    return max(x['free'] for x in slots)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--replicates',type=int,default=20); ap.add_argument('--epsilon',type=float,default=.005); ap.add_argument('--cv',type=float,default=.15); ap.add_argument('--fail-rate',type=float,default=.01); ap.add_argument('--output',required=True); a=ap.parse_args()
    f=[simulate('fada',i,a.epsilon,a.cv,a.fail_rate) for i in range(a.replicates)]; b=[simulate('interleaved',i,a.epsilon,a.cv,a.fail_rate) for i in range(a.replicates)]
    r={'model':'FADA v2','replicates':a.replicates,'epsilon':a.epsilon,'cv':a.cv,'fail_rate':a.fail_rate,'fada_mean':statistics.mean(f),'interleaved_mean':statistics.mean(b),'gain_fraction':(statistics.mean(b)-statistics.mean(f))/statistics.mean(b),'fada_p95':sorted(f)[max(0,int(.95*len(f))-1)],'interleaved_p95':sorted(b)[max(0,int(.95*len(b))-1)],'read_only':True}
    open(a.output,'w').write(json.dumps(r,indent=2)+'\n'); print(json.dumps(r,indent=2))
if __name__=='__main__': main()
