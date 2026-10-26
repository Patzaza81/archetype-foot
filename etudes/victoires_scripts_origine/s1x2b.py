import json,math,itertools
R=json.load(open('rep1x2_feat.json'))
for r in R:
    hm,hc,am,ac=r['hm'],r['hc'],r['am'],r['ac'];nh,na=len(hm),len(am)
    r['csh']=sum(c==0 for c in hc)/nh; r['ftsa']=sum(a==0 for a in am)/na      # dom garde sa cage ; ext muet
    r['w2h']=sum(a-c>=2 for a,c in zip(hm,hc))/nh; r['l2a']=sum(c-a>=2 for a,c in zip(am,ac))/na
    r['ptsh']=sum(3*(a>c)+(a==c) for a,c in zip(hm,hc))/nh; r['ptsa']=sum(3*(a>c)+(a==c) for a,c in zip(am,ac))/na
    r['w2a']=sum(a-c>=2 for a,c in zip(am,ac))/na; r['l2h']=sum(c-a>=2 for a,c in zip(hm,hc))/nh
    r['ncsa']=1-sum(c==0 for c in ac)/na
CUT='2026-04-01';MID='2026-01-01'
def wil(k,n):
    if not n:return 0
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
days=len({r['jour'] for r in R})
per=lambda r:0 if r['jour']<MID else (1 if r['jour']<CUT else 2)   # 0: réglage A, 1: réglage B, 2: contrôle réservé
P=[per(r) for r in R]
qs=lambda lo,hi,n:[round(lo+(hi-lo)*i/n,2) for i in range(n+1)]
def run(lab,y,feats,minn=60,target=0.70):
    conds=[(k,t,s) for k,(ts,s) in feats.items() for t in ts]
    okf=lambda r,c:(r[c[0]]>=c[1]-1e-9) if c[2]==1 else (r[c[0]]<=c[1]+1e-9)
    mk={c:[okf(r,c) for r in R] for c in conds};Y=[r[y] for r in R]
    res=[]
    for L in (1,2,3):
        for combo in itertools.combinations(conds,L):
            if len({c[0] for c in combo})<L: continue
            n=[0,0,0];k=[0,0,0]
            for i in range(len(R)):
                if all(mk[c][i] for c in combo): n[P[i]]+=1;k[P[i]]+=Y[i]
            if n[0]<minn or n[1]<minn or n[2]<minn: continue
            res.append((combo,n,k))
    print('\n######',lab,'| règles testées',len(res))
    for L in (2,3):
        # choisie sur A et B seulement (taux >= cible dans chacune), classée par fréquence ; jugée UNE fois sur la période réservée
        cand=[x for x in res if len(x[0])<=L and x[2][0]/x[1][0]>=target and x[2][1]/x[1][1]>=target]
        cand.sort(key=lambda x:-(x[1][0]+x[1][1]))
        print(' -- au plus %d conditions, choisies sur 2025 puis janv–mars 2026 (>= %d%% dans chacune), jugées sur la période réservée (depuis 01/04/2026)'%(L,100*target))
        if not cand: print('    aucune règle');continue
        for x in cand[:3]:
            n,k=x[1],x[2]
            print('    %s | réglage A %.1f%% (%d) | B %.1f%% (%d) | RÉSERVÉE %.1f%% (%d, bas %.1f) | %.2f paris/jour'%(' & '.join('%s%s%.2f'%(c[0],'>=' if c[2]==1 else '<=',c[1]) for c in x[0]),100*k[0]/n[0],n[0],100*k[1]/n[1],n[1],100*k[2]/n[2],n[2],100*wil(k[2],n[2]),sum(n)/days))
    return res
home={'dd':(qs(0,2.0,8),1),'ph':(qs(0.4,1.0,6),1),'wh':(qs(0.4,1.0,6),1),'la':(qs(0.2,1.0,8),1),'lh':([0,0.15,0.25],-1),'gdh':(qs(0,2,8),1),'gda':(qs(-2,0,4),-1),'wa':([0.0,0.15,0.25,0.35],-1),'csh':([0.25,0.4,0.5,0.6],1),'ftsa':([0.25,0.4,0.5],1),'w2h':([0.25,0.4,0.5],1),'l2a':([0.25,0.4,0.5],1),'ptsh':([2.0,2.25,2.5],1),'ptsa':([0.5,0.75,1.0],-1)}
away={'dd':(qs(-2.0,0,8),-1),'pe':(qs(0.4,1.0,6),1),'wa':(qs(0.4,1.0,6),1),'lh':(qs(0.2,1.0,8),1),'la':([0,0.15,0.25],-1),'gda':(qs(0,2,8),1),'gdh':(qs(-2,0,4),-1),'wh':([0.0,0.15,0.25,0.35],-1),'w2a':([0.25,0.4,0.5],1),'l2h':([0.25,0.4,0.5],1),'ptsa':([1.75,2.0,2.25],1),'ptsh':([0.75,1.0,1.25],-1),'ncsa':([0.5,0.75],1)}
run('VICTOIRE DOMICILE','yh',home)
run('VICTOIRE EXTÉRIEUR','ya',away,target=0.55)
