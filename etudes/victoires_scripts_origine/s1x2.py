import json,math,itertools,collections
R=json.load(open('rep1x2_feat.json'))
CUT='2026-04-01'
def wil(k,n):
    if not n:return 0
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
days=len({r['jour'] for r in R})
dev=[r for r in R if r['jour']<CUT];te=[r for r in R if r['jour']>=CUT]
def run(lab,y,feats):
    # feats: dict nom -> (thresholds, sens) ; condition = valeur >= seuil (sens=1) ou <= seuil (sens=-1)
    conds=[(k,t,s) for k,(ts,s) in feats.items() for t in ts]
    ok=lambda r,c:(r[c[0]]>=c[1]-1e-9) if c[2]==1 else (r[c[0]]<=c[1]+1e-9)
    # pré-calcul des masques
    mk={c:[ok(r,c) for r in R] for c in conds}
    idx_dev=[i for i,r in enumerate(R) if r['jour']<CUT];idx_te=[i for i,r in enumerate(R) if r['jour']>=CUT]
    Y=[r[y] for r in R]
    def stat(mask,idx):
        n=k=0
        for i in idx:
            if mask[i]: n+=1;k+=Y[i]
        return n,k
    res=[]
    for L in (1,2,3):
        for combo in itertools.combinations(conds,L):
            if len({c[0] for c in combo})<L: continue
            mask=[all(mk[c][i] for c in combo) for i in range(len(R))]
            nd,kd=stat(mask,idx_dev);nt,kt=stat(mask,idx_te)
            if nd<120 or nt<120: continue
            res.append((combo,nd,kd/nd,wil(kd,nd),nt,kt/nt,wil(kt,nt)))
    print('\n######',lab,'— base',round(100*sum(Y)/len(Y),1),'% | règles testées',len(res))
    for niveau in (0.60,0.65,0.70,0.75,0.80):
        ok_=[x for x in res if x[3]>=niveau and x[6]>=niveau]   # borne basse de Wilson >= niveau aux DEUX périodes
        ok_.sort(key=lambda x:-(x[1]+x[4]))
        if not ok_: print('  borne basse >= %d%% aux deux périodes : aucune règle'%(100*niveau));continue
        x=ok_[0]
        print('  borne basse >= %d%% : %s | avant n=%d %.1f%% | après n=%d %.1f%% | %.2f paris/jour'%(100*niveau,' & '.join('%s%s%.2f'%(c[0],'>=' if c[2]==1 else '<=',c[1]) for c in x[0]),x[1],100*x[2],x[4],100*x[5],(x[1]+x[4])/days))
    return res
qs=lambda lo,hi,n:[round(lo+(hi-lo)*i/n,2) for i in range(n+1)]
home={'dd':(qs(0,2.0,8),1),'ph':(qs(0.4,1.0,6),1),'wh':(qs(0.4,1.0,6),1),'la':(qs(0.2,1.0,8),1),'lh':([0,0.15,0.25],-1),'gdh':(qs(0,2,8),1),'gda':(qs(-2,0,4),-1),'wa':([0.0,0.15,0.25,0.35],-1)}
away={'dd':(qs(-2.0,0,8),-1),'pe':(qs(0.4,1.0,6),1),'wa':(qs(0.4,1.0,6),1),'lh':(qs(0.2,1.0,8),1),'la':([0,0.15,0.25],-1),'gda':(qs(0,2,8),1),'gdh':(qs(-2,0,4),-1),'wh':([0.0,0.15,0.25,0.35],-1)}
rh=run('VICTOIRE DOMICILE','yh',home)
ra=run('VICTOIRE EXTÉRIEUR','ya',away)

def pareto(lab,res,key,levels,minn):
    print('\n--',lab,'(réussite mesurée >= niveau aux DEUX périodes, n>=%d chacune)'%minn)
    for lv in levels:
        ok_=[x for x in res if x[2]>=lv and x[5]>=lv and x[1]>=minn and x[4]>=minn]
        ok_.sort(key=lambda x:-(x[1]+x[4]))
        if not ok_: print('  >=%d%% : aucune règle'%(100*lv));continue
        x=ok_[0]
        print('  >=%d%% : %s | avant n=%d %.1f%% (bas %.1f) | après n=%d %.1f%% (bas %.1f) | %.2f/jour'%(100*lv,' & '.join('%s%s%.2f'%(c[0],'>=' if c[2]==1 else '<=',c[1]) for c in x[0]),x[1],100*x[2],100*x[3],x[4],100*x[5],100*x[6],(x[1]+x[4])/days))
pareto('DOMICILE',rh,'yh',(0.65,0.70,0.75,0.80),100)
pareto('EXTÉRIEUR',ra,'ya',(0.45,0.50,0.55,0.60,0.65),100)
