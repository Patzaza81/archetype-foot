import importlib.util, json, sys
s=importlib.util.spec_from_file_location("c","moteur_v_calibre.py"); c=importlib.util.module_from_spec(s); s.loader.exec_module(c)
ids=json.load(open("jeu_reglage_ids.json")); D="/home/claude/patzaza81/archetype-foot/data/archive_test"
# on rejoue UNE fois à seuil bas, puis on filtre (p_cal est par pari ; le meilleur pari par match dépend du seuil -> on rejoue par seuil)
cut="2026-10-10"
def st(r):
    n=len(r)
    if n==0: return None
    w=sum(x["gagne"] for x in r); lo=c.mv.wilson(w,n)[0]
    return n,w/n,sum(x["p_cal"] for x in r)/n,lo,sum((x["cote"]-1) if x["gagne"] else -1 for x in r)/n
for av in (True,False):
    print(f"\n=== verrou d'échantillon : {'oui' if av else 'non'} ===")
    print("seuil | cote max | paris | réussite | annoncé | écart | borne basse | 1ère moitié (n, écart) | 2e moitié (n, écart) | ROI")
    for t in (.66,.68,.70,.72,.74,.76,.78):
        r=c.rejouer(D,ids,t,av,True,True,True)
        a=[x for x in r if x["date"]<=cut]; b=[x for x in r if x["date"]>cut]
        S=st(r); A=st(a); B=st(b)
        print(f"{t:.2f}  | {c.cote_max_pour_seuil(t):.3f}   | {S[0]:>4} | {S[1]:.1%}  | {S[2]:.1%} | {S[1]-S[2]:+.1%} | {S[3]:.1%} | {A[0]:>3}, {A[1]-A[2]:+.1%} | {B[0]:>3}, {B[1]-B[2]:+.1%} | {S[4]:+.1%}")
