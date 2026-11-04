"""Etape 4b (EXPLORATOIRE): grille (lambda, effectif minimal) appliquee aux regles figees avant chaque saison test.
Les combinaisons sont comparees sur les saisons test elles-memes: c'est une cartographie, pas un resultat valide (le choix valide en marche avant est dans regles_conditions.py)."""
import sys, json, numpy as np
import regles_conditions as rc, pouvoir_predictif_v3 as v3
from multiprocessing import Pool
def un(code):
    PR=rc.preparer(code)
    if PR is None: return code,None
    out={}
    for e in range(7):
        cache={}
        for s in rc.TESTS:
            R=rc.regles_avant(PR,e,s,cache); te=PR["valide"]&(PR["S"]==s); p=PR["P1"][te,e]; y=PR["Y"][te,e]
            for l in (0.1,0.2,0.35,0.5,1.0):
                for f in rc.FMIN:
                    pc,_=rc.ajuster_p(R,PR["X"][te],p,l,f); out.setdefault((e,l,f),[]).append((v3.lb(p,y)-v3.lb(pc,y)))
    return code,{k:np.concatenate(v) for k,v in out.items()}
if __name__=="__main__":
    codes=sorted(json.load(open('data/inventaire/classement_descriptif.json'))["competitions"])
    with Pool(2) as P: R=dict(P.map(un,codes,chunksize=1))
    R={c:v for c,v in R.items() if v}
    sortie = {}
    for e in range(7):
        print(rc.EVT[e])
        for l in (0.1,0.2,0.35,0.5,1.0):
            row=[]
            for f in rc.FMIN:
                g=[v[(e,l,f)].mean() for v in R.values()]; z=[v[(e,l,f)].mean()/(v[(e,l,f)].std(ddof=1)/np.sqrt(len(v[(e,l,f)]))+1e-12) for v in R.values()]
                sortie.setdefault(rc.EVT[e], []).append({'lambda': l, 'fmin': f, 'gain_moyen': round(float(np.mean(g)), 6), 'competitions_gain_positif': int(sum(1 for x in g if x > 0)), 'competitions_z_sup_1_96': int(sum(1 for x in z if x > 1.96)), 'gain_par_competition': {c: round(float(v[(e, l, f)].mean()), 6) for c, v in R.items()}})
                row.append(f"f{f}: {np.mean(g):+.5f} (comp>0 {sum(1 for x in g if x>0)}, z>1.96 {sum(1 for x in z if x>1.96)})")
            print(" lam",l," | ".join(row))
    json.dump({'description': 'Cartographie exploratoire (lambda, effectif minimal) sur 2324-2526; non validee.', 'marches': sortie}, open('data/inventaire/regles_conditions_grille.json', 'w'), ensure_ascii=False, indent=1)
