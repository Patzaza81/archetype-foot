import pandas as pd, numpy as np, warnings
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')
d=pd.read_csv(Path(__file__).resolve().parent/'etude_V_matchs.csv'); d['Lg']=d.total_moyen_championnat.fillna(d.total.mean())
tr=((d.date>='2025-09-01')&(d.date<='2026-04-12')); C=d.date>'2026-04-12'
M={"+1.5":lambda t:t>=2,"+2.5":lambda t:t>=3,"+3.5":lambda t:t>=4,"-2.5":lambda t:t<=2,"-3.5":lambda t:t<=3,"-4.5":lambda t:t<=4}
sets={"V":['V'],"4 composantes + championnat":['BM_dom','BE_dom','BM_ext','BE_ext','Lg']}
print("Réussite sur C des X % de matchs où le modèle est le plus confiant (modèle appris sur A+B) — base C entre parenthèses")
for mk,f in M.items():
    y=d.total.map(lambda t:int(f(t))).values
    line=f"{mk} (base {y[C].mean():.1%}, {C.sum()} matchs):"
    for nom,cols in sets.items():
        X=StandardScaler().fit(d.loc[tr,cols]).transform(d[cols]); p=LogisticRegression(C=1e6,max_iter=1000).fit(X[tr],y[tr]).predict_proba(X)[:,1]
        pc=p[C]; yc=y[C]; o=np.argsort(-pc)
        line+=f" | {nom}: "+", ".join(f"top{q}% {yc[o[:int(len(o)*q/100)]].mean():.1%}" for q in (50,20,10))
    print(line)
