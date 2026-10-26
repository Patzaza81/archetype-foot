import json,numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
R=json.load(open('rep1x2_feat.json'));CUT='2026-04-01'
F=['dd','ph','pe','wh','lh','dh','wa','la','gdh','gda']
X=np.array([[r[k] for k in F]+[r['niv']['total'],len(r['hm']),len(r['am'])] for r in R]);d=np.array([r['jour']<CUT for r in R])
days=len({r['jour'] for r in R})
for lab,y in (('DOMICILE','yh'),('EXTÉRIEUR','ya')):
    Y=np.array([r[y] for r in R])
    for nm,mod in (('logistique',LogisticRegression(max_iter=2000,C=1.0)),('boosting',HistGradientBoostingClassifier(max_depth=3,learning_rate=0.05,max_iter=150,min_samples_leaf=80))):
        Xs=(X-X[d].mean(0))/X[d].std(0) if nm=='logistique' else X
        mod.fit(Xs[d],Y[d]);p=mod.predict_proba(Xs[~d])[:,1];yt=Y[~d]
        o=np.argsort(-p);nd=(~d).sum()
        out=[]
        for frac in (0.02,0.05,0.10,0.20,0.30):
            k=int(frac*nd);out.append('top %d%% (%.1f/jour) → %.1f%%'%(100*frac,frac*nd/ (len({r['jour'] for r in R if r['jour']>=CUT})) ,100*yt[o[:k]].mean()))
        print(lab,nm,'| entraîné avant le 01/04, jugé après |',' | '.join(out))
