import gzip,json,csv,collections
from pathlib import Path
import numpy as np
DOSSIER=Path(__file__).resolve().parent
d=json.load(gzip.open(DOSSIER.parents[1]/'data'/'bloc_saisons'/'bloc_2526_2627.json.gz'))
L=[x for x in d['liste'] if isinstance(x.get('buts_dom'),int) and isinstance(x.get('buts_ext'),int)]
L.sort(key=lambda x:(x['date'],x['id']))
print(len(d['liste']),len(L))
H=collections.defaultdict(list); A=collections.defaultdict(list)   # (div,saison,équipe) -> [(date,gf,ga)] à domicile / à l'extérieur
lig=collections.defaultdict(lambda:[0,0])
rows=[]
byday=collections.defaultdict(list)
for x in L: byday[x['date']].append(x)
def moy(rec,n=None):
    r=rec[-n:] if n else rec
    return np.mean([g for g,c in r]),np.mean([c for g,c in r])
for day in sorted(byday):
    for x in byday[day]:
        kh=(x['division'],x['saison'],x['domicile']); ka=(x['division'],x['saison'],x['exterieur'])
        h,a=H[kh],A[ka]
        if len(h)>=4 and len(a)>=4:
            bm_d,be_d=moy(h); bm_e,be_e=moy(a); bm_d6,be_d6=moy(h,6); bm_e6,be_e6=moy(a,6)
            s=lig[(x['division'],x['saison'])]
            c=x['cotes'].get('plus_moins_2_5_cloture') or {}
            rows.append(dict(id=x['id'],date=day,saison=x['saison'],division=x['division'],domicile=x['domicile'],exterieur=x['exterieur'],
              buts_dom=x['buts_dom'],buts_ext=x['buts_ext'],total=x['buts_dom']+x['buts_ext'],
              n_dom=len(h),n_ext=len(a),BM_dom=round(bm_d,4),BE_dom=round(be_d,4),BM_ext=round(bm_e,4),BE_ext=round(be_e,4),
              BM_dom_6=round(bm_d6,4),BE_dom_6=round(be_d6,4),BM_ext_6=round(bm_e6,4),BE_ext_6=round(be_e6,4),
              V=round(bm_d+be_d+bm_e+be_e,4),V_6=round(bm_d6+be_d6+bm_e6+be_e6,4),
              total_moyen_championnat=round(s[0]/s[1],4) if s[1]>=30 else '',n_championnat=s[1]))
    for x in byday[day]:       # les matchs du jour n'entrent dans l'historique qu'après le jour
        H[(x['division'],x['saison'],x['domicile'])].append((x['buts_dom'],x['buts_ext']))
        A[(x['division'],x['saison'],x['exterieur'])].append((x['buts_ext'],x['buts_dom']))
        s=lig[(x['division'],x['saison'])]; s[0]+=x['buts_dom']+x['buts_ext']; s[1]+=1
print(len(rows), rows[0]['date'], rows[-1]['date'])
with open(DOSSIER/'etude_V_matchs.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
