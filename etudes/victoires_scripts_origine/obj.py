import json,math,itertools,collections
R=[r for r in json.load(open('replay.json')) if r['pick']]
for r in R:
    n=r['niv'];r['ok']=r['h']+r['a']>=2;r['T']=n['total'];r['mn']=min(n['dom'],n['ext']);r['mx']=max(n['dom'],n['ext']);r['d']=n['d']
CUT='2026-04-01'
def wil(k,n):
    if not n:return 0
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
dev=[r for r in R if r['jour']<CUT];te=[r for r in R if r['jour']>=CUT]
jd=len({r['jour'] for r in R}); print('picks',len(R),'jours',jd,'base %.1f%%'%(100*sum(r['ok'] for r in R)/len(R)))
def st(S):
    n=len(S);k=sum(r['ok'] for r in S);return n,k
feats={'T':[2.5,3.0,3.2,3.4,3.6,3.8,4.0],'mn':[0.8,1.0,1.2,1.4,1.6],'mx':[1.8,2.0,2.2,2.5],'d':[0.5,1.0,1.5],'valeur':[0.8,0.85,0.9,0.95],'off':[0.9],'de':[0.9]}
rules=[]
conds=[(f,c) for f,cs in feats.items() for c in cs]
def apply(S,rule):
    return [r for r in S if all((r[f] is not None and r[f]>=c) for f,c in rule)]
for k in (1,2):
    for rule in itertools.combinations(conds,k):
        if len({f for f,_ in rule})<k: continue
        a=apply(dev,rule);b=apply(te,rule)
        if len(a)<150 or len(b)<150: continue
        na,ka=st(a);nb,kb=st(b)
        rules.append((rule,na,ka/na,wil(ka,na),nb,kb/nb,wil(kb,nb)))
ok=[x for x in rules if x[3]>=0.80 and x[6]>=0.80]
print('règles stables (borne basse>=80% avant ET après):',len(ok),'sur',len(rules))
ok.sort(key=lambda x:-(x[1]+x[4]))
for x in ok[:8]:
    tot=x[1]+x[4]
    print(' ',' & '.join('%s>=%s'%c for c in x[0]),'| avant n=%d %.1f%% | après n=%d %.1f%% | ≈%.1f paris/jour'%(x[1],100*x[2],x[4],100*x[5],tot/jd))
print('-- meilleures réussites (n>=150 des deux côtés)')
rules.sort(key=lambda x:-min(x[2],x[5]))
for x in rules[:8]:
    print(' ',' & '.join('%s>=%s'%c for c in x[0]),'| avant n=%d %.1f%% | après n=%d %.1f%%'%(x[1],100*x[2],x[4],100*x[5]))
# stabilité mensuelle de T>=3.4
S=[r for r in R if r['T']>=3.4];m=collections.defaultdict(lambda:[0,0])
for r in S:
    m[r['jour'][:7]][0]+=1;m[r['jour'][:7]][1]+=r['ok']
print('T>=3.4 par mois:',' '.join('%s %d/%d=%.0f%%'%(k,v[1],v[0],100*v[1]/v[0]) for k,v in sorted(m.items()) if v[0]>=10))
