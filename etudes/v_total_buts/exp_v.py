import pandas as pd, numpy as np, warnings
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')
d=pd.read_csv(Path(__file__).resolve().parent/'etude_V_matchs.csv')
d['Lg']=d.total_moyen_championnat.fillna(d.total.mean())
A=(d.date>='2025-09-01')&(d.date<='2026-01-31'); B=(d.date>'2026-01-31')&(d.date<='2026-04-12'); C=d.date>'2026-04-12'
print("A,B,C =",A.sum(),B.sum(),C.sum())
d['lh']=(d.BM_dom+d.BE_ext)/2; d['la']=(d.BM_ext+d.BE_dom)/2
d['x1']=d.BM_dom*d.BE_ext; d['x2']=d.BM_ext*d.BE_dom
F={"V brut":['V'],"V/2 (identique à V en logistique)":['V'],
   "4 composantes":['BM_dom','BE_dom','BM_ext','BE_ext'],
   "2 intensités (dom / ext)":['lh','la'],
   "interactions (+ composantes)":['BM_dom','BE_dom','BM_ext','BE_ext','x1','x2'],
   "V + nature du championnat":['V','Lg'],
   "4 composantes + championnat":['BM_dom','BE_dom','BM_ext','BE_ext','Lg']}
M={"+0.5":lambda t:t>=1,"+1.5":lambda t:t>=2,"+2.5":lambda t:t>=3,"+3.5":lambda t:t>=4,"-1.5":lambda t:t<=1,"-2.5":lambda t:t<=2,"-3.5":lambda t:t<=3,"-4.5":lambda t:t<=4}
def ll(y,p): p=np.clip(p,1e-6,1-1e-6); return -(y*np.log(p)+(1-y)*np.log(1-p))
tr=A|B  # apprentissage A+B, test C ; seuil de probabilité choisi sur B (modèle appris sur A)
res=[]
print("\nGAIN de log-loss sur C vs taux de base (×1e-4, ± erreur-type) ; réussite des picks p≥seuil (seuil appris sur B, modèle appris sur A)")
for mk,f in M.items():
    y=d.total.map(lambda t:int(f(t))).values
    base=y[tr].mean()
    out=[]
    for nom,cols in F.items():
        sc=StandardScaler().fit(d.loc[tr,cols]); X=sc.transform(d[cols])
        m=LogisticRegression(C=1e6,max_iter=1000).fit(X[tr],y[tr]); p=m.predict_proba(X)[:,1]
        diff=ll(y[C],base)-ll(y[C],p[C]); g=diff.mean()*1e4; se=diff.std()/np.sqrt(C.sum())*1e4
        # sélection
        sa=StandardScaler().fit(d.loc[A,cols]); XA=sa.transform(d[cols]); ma=LogisticRegression(C=1e6,max_iter=1000).fit(XA[A],y[A]); pa=ma.predict_proba(XA)[:,1]
        seuil=None
        for s in np.arange(0.5,0.99,0.01):
            k=B&(pa>=s)
            if k.sum()>=100 and y[k].mean()>=0.72: seuil=s;break
        if seuil is None: sel="aucun seuil ≥72 % sur B"
        else:
            k=C&(pa>=seuil); sel=f"p≥{seuil:.2f}: {k.sum()} matchs, {y[k].mean():.1%}" if k.sum() else f"p≥{seuil:.2f}: 0"
        out.append((nom,g,se,sel))
    print(f"\n{mk} | base A+B {base:.1%} | C réel {y[C].mean():.1%}")
    for nom,g,se,sel in out: print(f"  {nom:36s} {g:+6.1f} ±{se:4.1f} | {sel}")
# total moyen: erreur
print("\nPrévision du total (C) : MAE / corr")
T=d.total.values
for nom,cols in (("V/2 brut",None),("V brut",None)):
    p=d.V/2 if nom=="V/2 brut" else d.V
    print(nom, round(np.abs(T[C]-p[C]).mean(),3), round(np.corrcoef(p[C],T[C])[0,1],3))
X=np.c_[np.ones(len(d)),d.V/2,d.Lg]; c=np.linalg.lstsq(X[tr],T[tr],rcond=None)[0]; p=X@c
print("OLS a+b·V/2+c·champ.",c.round(3),round(np.abs(T[C]-p[C]).mean(),3),round(np.corrcoef(p[C],T[C])[0,1],3))
X=np.c_[np.ones(len(d)),d.Lg]; c=np.linalg.lstsq(X[tr],T[tr],rcond=None)[0]; p=X@c
print("championnat seul",round(np.abs(T[C]-p[C]).mean(),3),round(np.corrcoef(p[C],T[C])[0,1],3))
