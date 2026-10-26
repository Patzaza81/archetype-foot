"""Mesure (lecture seule, hors dépôt) des deux niveaux d'indice existants — normal / maximal du « Plus de 1,5 » — généralisés à chaque marché.
Population : pronostics PUBLIÉS par alpha (onglets buts / équipes), rejoués sans fuite. Niveau normal : écart de niveau d'alpha >= T (T choisi sur le réglage seul).
Niveau maximal : niveau normal ET au plus 1 match passé où l'événement a échoué dans les séries appariées des deux équipes (définition gelée du Plus de 1,5)."""
import json, math, pickle, sys
from pathlib import Path
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from alpha_serie import coeur, parametres as P, robustesse as RB, decouverte_marches as V1
from alpha_serie.etude_marches import wilson, rendement

OUT = Path(__file__).resolve().parent
FIN_A, FIN_B, DEBUT_D = "2026-01-01", "2026-04-01", "2026-09-28"
FAIBLES_MAX = 1          # valeur gelée du Plus de 1,5 (matchs_faibles_max)
JOURS_D = 28


def echecs(off, de, pred):
    """Matchs passés où l'événement a échoué : match à domicile de l'équipe qui reçoit = (marqués off[0], encaissés de[1]) ;
    match à l'extérieur de l'adversaire = (encaissés de[0], marqués off[1]). Pour le Plus de 1,5 : identique à tickets.matchs_faibles."""
    if not off or len(off) != len(de):
        return None
    return sum(not pred(o[0], d[1]) for o, d in zip(off, de)) + sum(not pred(d[0], o[1]) for o, d in zip(off, de))


def construire():
    evts = V1.evenements()
    sig2eid = {}
    for eid, e in evts.items():
        sig2eid[tuple(bool(e["pred"](h, a)) for h in range(10) for a in range(10))] = eid
    params = P.charger()
    lignes, vus = [], set()
    for src, ch in (("FD", RB.charger_bloc), ("ARCH", RB.charger_archive_archetype)):
        for m in ch():
            if src == "FD" and m["jour"] >= DEBUT_D:
                continue
            if not isinstance(m.get("h"), int) or not isinstance(m.get("a"), int) or m["id"] in vus:
                continue
            vus.add(m["id"])
            try:
                r = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
            except Exception:
                continue
            if r.get("statut") != "analyse":
                continue
            per = 3 if src == "ARCH" else (0 if m["jour"] < FIN_A else (1 if m["jour"] < FIN_B else 2))
            off, de = r["scenarios_offensifs"], r["scenarios_defensifs"]
            for ong in ("buts", "equipes"):
                for f in r["onglets"][ong]:
                    g, s = f["cle"]
                    pred = coeur.test_du_marche(g, s) if g != "multigoals" else (lambda h, a, lo=int(s.split("-")[0]), hi=int(s.split("-")[1]): lo <= h + a <= hi)
                    eid = sig2eid.get(tuple(bool(pred(h, a)) for h in range(10) for a in range(10)))
                    if eid is None:
                        continue
                    cote = None
                    if src == "ARCH":
                        for cle in evts[eid]["cles"]:
                            cote = coeur.cote_de(m.get("cotes"), cle)
                            if cote:
                                break
                    lignes.append({"eid": eid, "jour": m["jour"], "per": per, "y": bool(pred(m["h"], m["a"])), "ecart": f.get("ecart_niveau"),
                                   "echecs": echecs(off, de, pred), "cote": cote, "total": r["niveaux"]["total"], "match": m["id"]})
    return evts, lignes


def wl(g, n):
    return wilson(g, n)[0] if n else None


def n_requis(p, t):
    """Plus petit nombre de pronostics pour que la borne basse de Wilson 95 % atteigne t si la réussite vaut p (None si p <= t)."""
    if p is None or p <= t:
        return None
    n = 1
    while n < 200000:
        if wilson(round(p * n), n)[0] >= t:
            return n
        n = int(n * 1.05) + 1
    return None


def stats(L):
    n, g = len(L), sum(x["y"] for x in L)
    return {"n": n, "g": g, "taux": g / n if n else None, "w_bas": wl(g, n), "w_haut": wilson(g, n)[1] if n else None}


def seuil_T(R, t):
    """Plus petit seuil d'écart de niveau (donc le plus de pronostics) dont la borne basse de Wilson atteint t sur le RÉGLAGE seul."""
    ec = sorted({x["ecart"] for x in R if x["ecart"] is not None})
    if not ec:
        return None, "pas d'écart de niveau pour ce marché : niveau normal = pronostic publié"
    cand = sorted(set(np.round(np.quantile(ec, np.arange(0, 40) / 40), 3).tolist()))
    for T in cand:
        s = stats([x for x in R if x["ecart"] is not None and x["ecart"] >= T - 1e-9])
        if s["n"] and s["w_bas"] >= t:
            return T, None
    return "aucun", "aucun seuil n'atteint la cible sur le réglage"


def niveau(L, T, maximal):
    out = []
    for x in L:
        if T is not None and T != "aucun" and (x["ecart"] is None or x["ecart"] < T - 1e-9):
            continue
        est_max = x["echecs"] is not None and x["echecs"] <= FAIBLES_MAX
        if maximal == est_max:
            out.append(x)
    return out


def evaluer(evts, lignes, t):
    par = defaultdict(list)
    for x in lignes:
        par[x["eid"]].append(x)
    res = {}
    for eid in evts:
        L = par.get(eid, [])
        R = [x for x in L if x["per"] in (0, 1)]
        T, note = seuil_T(R, t)
        r = {"nom": evts[eid]["nom"], "publies": {k: stats([x for x in L if x["per"] in v]) for k, v in (("reglage", (0, 1)), ("controle", (2,)), ("D", (3,)))}, "T": T, "note": note}
        for lev, mx in (("normal", False), ("maximal", True)):
            sel = niveau(L, T if T != "aucun" else None, mx) if T != "aucun" else []
            st = {k: stats([x for x in sel if x["per"] in v]) for k, v in (("A", (0,)), ("B", (1,)), ("reglage", (0, 1)), ("controle", (2,)), ("D", (3,)))}
            D = [x for x in sel if x["per"] == 3]
            jou = [(x["y"], x["cote"]) for x in D if x["cote"] and x["cote"] >= 1.25]
            st["D_par_jour"] = len(D) / JOURS_D
            st["D_jouables"] = len(jou)
            st["D_jouables_par_jour"] = len(jou) / JOURS_D
            st["D_jouables_taux"] = (sum(w for w, _ in jou) / len(jou)) if jou else None
            st["rendement_D"] = rendement(jou)
            nr = n_requis(st["reglage"]["taux"], t)
            st["n_requis"] = nr
            st["requis_par_jour"] = nr / JOURS_D if nr else None
            r[lev] = st
        res[eid] = r
    return res


if __name__ == "__main__":
    cache = OUT / "niveaux_lignes.pkl"
    if cache.exists():
        evts, lignes = pickle.load(open(cache, "rb"))
        evts = V1.evenements()
    else:
        evts, lignes = construire()
        pickle.dump((None, lignes), open(cache, "wb"))
    # contrôle de reproduction : indice maximal gelé du Plus de 1,5 (total >= 3,4, au plus 1 match faible) = 1 027 paris, 86,3 %
    p15 = [x for x in lignes if x["eid"] == "over_under_1.5|plus"]
    ok = lambda x: x["total"] >= 3.4 - 1e-9
    mxm = lambda x: x["echecs"] is not None and x["echecs"] <= 1
    mx = [x for x in p15 if ok(x) and mxm(x)]
    nm = [x for x in p15 if ok(x) and not mxm(x)]
    print("REPRO maximal reglage", stats([x for x in mx if x["per"] < 2]), "apres", stats([x for x in mx if x["per"] >= 2]))
    print("REPRODUCTION Plus 1,5 maximal:", stats(mx), "normal:", stats(nm), "publiés:", len(p15))
    out = {"lignes": len(lignes), "par_periode": {p: sum(1 for x in lignes if x["per"] == p) for p in range(4)}}
    for t in (0.70, 0.80):
        out[f"cible_{int(t*100)}"] = evaluer(evts, lignes, t)
    (OUT / "niveaux_resultats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print("ok", out["lignes"], out["par_periode"])
