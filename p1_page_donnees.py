"""Donnees de la page « P1 - Analyse statistique » (data/calibration_p1/page_p1.json).
Lecture seule des sorties reelles: journal gele (integration_calibration.py) + scores deja ecrits par le flux (data/archive_test). AUCUN calcul de probabilite ici, aucune valeur inventee:
une donnee absente reste null. Les performances ne portent que sur des matchs termines dont la prediction a ete gelee AVANT le coup d'envoi (verifie par integration_calibration.verifier_journal)."""
import datetime, glob, gzip, json, math, os
import integration_calibration as ic
import p1_paris
import apprentissage_p1 as ap

SORTIE = os.path.join(ic.RACINE, "data", "calibration_p1", "page_p1.json")
MARCHES = ic.MARCHES
BIN = ("o15", "o25", "o35", "btts")

def scores(flux=ic.FLUX):
    """match_id -> score reel, dernier fichier du flux qui le porte."""
    res = {}
    for f in sorted(glob.glob(os.path.join(flux, "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            s = x.get("score")
            if s and s.get("buts_dom") is not None and s.get("buts_ext") is not None: res[x["match_id"]] = {"buts_dom": int(s["buts_dom"]), "buts_ext": int(s["buts_ext"]), "source": s.get("source")}
    return res

def realise(sc):
    d, e = sc["buts_dom"], sc["buts_ext"]; t = d + e
    return {"dom": d > e, "nul": d == e, "ext": d < e, "o15": t >= 2, "o25": t >= 3, "o35": t >= 4, "btts": d > 0 and e > 0}

def evaluer(rec, sc):
    """Evaluation d'un match termine pour P1 original et P1 calibre. Sorties: issue 1X2, log-loss 1X2, Brier 1X2, evenement realise par marche, Brier par marche."""
    o = realise(sc); out = {"realise": o}
    for nom, p in (("original", rec["p1_original"]), ("calibre", rec["p1_calibre"])):
        issue = "dom" if o["dom"] else "nul" if o["nul"] else "ext"
        out[nom] = {"issue_1x2": issue, "p_issue": p[issue], "logloss_1x2": -math.log(p[issue]), "brier_1x2": sum((p[k] - float(o[k])) ** 2 for k in ("dom", "nul", "ext")),
                    "favori": max(("dom", "nul", "ext"), key=lambda k: p[k]), "brier": {k: (p[k] - float(o[k])) ** 2 for k in BIN}}
    return out

def performance(termines):
    n = len(termines)
    if not n: return {"matchs_termines": 0, "periode": None, "note": "Aucun match termine avec prediction gelee : aucune performance mesurable."}
    res = {"matchs_termines": n, "periode": [min(r["date"] for r in termines), max(r["date"] for r in termines)], "par_version": {}}
    for v in ("original", "calibre"):
        E = [r["evaluation"][v] for r in termines]; fav = [e["favori"] == e["issue_1x2"] for e in E]
        d = {"logloss_1x2": sum(e["logloss_1x2"] for e in E) / n, "brier_1x2": sum(e["brier_1x2"] for e in E) / n, "favori_correct": sum(fav), "favori_taux": sum(fav) / n,
             "favori_erreur_type": math.sqrt(max(sum(fav) / n * (1 - sum(fav) / n), 0) / n), "marches": {}}
        for k in BIN:
            y = [float(r["evaluation"]["realise"][k]) for r in termines]; p = [r["p1_original" if v == "original" else "p1_calibre"][k] for r in termines]
            d["marches"][k] = {"n": n, "frequence_reelle": sum(y) / n, "probabilite_moyenne": sum(p) / n, "brier": sum((a - b) ** 2 for a, b in zip(p, y)) / n}
        res["par_version"][v] = d
    return res

def performance_paris(termines):
    """Paris retenus par P1 sur matchs termines (mise unitaire). n_matchs_sans_pari = matchs termines ou P1 n'avait retenu aucun marche."""
    P = [m["evaluation"]["pari"] for m in termines if m["evaluation"].get("pari")]; n = len(P)
    res = {"matchs_termines": len(termines), "paris": n, "matchs_sans_pari": len(termines) - n}
    if not n: return {**res, "note": "Aucun pari retenu et termine : aucun taux ni rendement mesurable."}
    w = sum(p["gagne"] for p in P); g = [p["gain"] for p in P]; moy = sum(g) / n; var = sum((x - moy) ** 2 for x in g) / max(n - 1, 1); t = w / n
    return {**res, "gagnes": w, "taux": t, "taux_erreur_type": math.sqrt(max(t * (1 - t), 0) / n), "rendement_moyen": moy, "rendement_erreur_type": math.sqrt(var / n)}

N_H2H = 10     # règle de Patrick (06/11/2026) : au plus les 10 dernières confrontations directes, pas de minimum

def derniers_matchs(hist, fd_dom, fd_ext, jour):
    """Matchs REELS (archive + saison courante, strictement avant le match), du PLUS RECENT au plus ancien.
    dom = TOUS les matchs de la saison en cours de l'equipe qui recoit, a domicile ; ext = ceux de l'equipe qui se deplace, a l'exterieur ;
    dom_ext / ext_dom = l'autre lieu de chacune (meme saison) ; saison en cours = la plus recente de l'historique ;
    h2h = au plus les N_H2H dernieres confrontations directes, toutes saisons, du point de vue de l'equipe qui recoit (domicile = elle recevait ce jour-la)."""
    saison = max((h[1] for h in hist), default=None)
    def f(equipe, domicile):
        L = [h for h in hist if h[0] < jour and h[1] == saison and h[2 if domicile else 3] == equipe][::-1]
        return [{"date": datetime.date.fromordinal(h[0]).isoformat(), "adversaire": h[3] if domicile else h[2], "marques": h[4] if domicile else h[5], "encaisses": h[5] if domicile else h[4]} for h in L]
    confront = [h for h in hist if h[0] < jour and fd_dom != fd_ext and {h[2], h[3]} == {fd_dom, fd_ext}][-N_H2H:][::-1]
    return {"dom": f(fd_dom, True), "ext": f(fd_ext, False), "dom_ext": f(fd_dom, False), "ext_dom": f(fd_ext, True),
            "h2h": [{"date": datetime.date.fromordinal(h[0]).isoformat(), "domicile": h[2] == fd_dom, "marques": h[4] if h[2] == fd_dom else h[5], "encaisses": h[5] if h[2] == fd_dom else h[4]} for h in confront]}

def construire(maintenant=None, dossier=ic.DOSSIER, flux=ic.FLUX, config=None, etat=None):
    import calibration_p1 as cp
    etat = etat if etat is not None else ap.charger_etat()
    config = config or cp.charger(); maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    import pouvoir_predictif as pp
    J = ic.lire_journal(dossier); S = scores(flux); matchs, termines = [], []; H = {}
    for r in J:
        sc = S.get(r["match_id"]); st = "a_venir" if r["coup_d_envoi_utc"] > maintenant else ("termine" if sc else "en_cours_ou_resultat_attendu")
        m = {k: r.get(k) for k in ("match_id", "date", "coup_d_envoi_utc", "competition", "division", "domicile", "exterieur", "p1_original", "p1_calibre", "methode", "detail", "gele_le", "empreinte", "mode", "n_historique_competition", "pari", "cotes_au_gel")}
        d = r.get("detail") or {}; code = r.get("division")
        if code not in H: H[code] = ic.historique(code)
        m["derniers_matchs"] = derniers_matchs(H[code], d.get("fd_dom"), d.get("fd_ext"), pp._date(r["date"])) if d.get("fd_dom") else None
        m.update(statut=st, resultat=sc if st == "termine" else None, evaluation=evaluer(r, sc) if st == "termine" else None)
        if st == "termine" and (r.get("pari") or {}).get("retenu"):
            pr = r["pari"]["retenu"]; g = p1_paris.gagne(pr["cle"], sc["buts_dom"], sc["buts_ext"]); m["evaluation"]["pari"] = {"cle": pr["cle"], "gagne": g, "gain": pr["cote"] - 1 if g else -1.0}
        if st == "a_venir" and etat and etat.get("corrections_validees"): m["p1_appris"] = ap.corriger(etat, r["p1_calibre"])
        matchs.append(m); termines += [m] if st == "termine" else []
    matchs.sort(key=lambda m: (m["coup_d_envoi_utc"], m["competition"], m["domicile"]))
    valides = [(c, mk) for c, v in config["competitions"].items() for mk in MARCHES if v[mk]["statut"] == "CORRECTION VALIDEE"]
    return {"genere_le": maintenant, "source": "journal gele data/calibration_p1/parallele/journal.jsonl + scores data/archive_test", "mode": ic.mode(),
            "calibration": {"couples_valides": len(valides), "couples_total": sum(len(MARCHES) for _ in config["competitions"]), "competitions": len(config["competitions"]),
                            "texte": "Aucune correction validee : P1 calibre = P1 original." if not valides else "Corrections validees (voir methode par marche) : " + ", ".join(f"{c}/{m}" for c, m in valides)},
            "journal": {"lignes": len(J), "anomalies": ic.verifier_journal(dossier), "derniere_empreinte": J[-1]["empreinte"] if J else None},
            "apprentissage": None if not etat else {k: etat.get(k) for k in ("matchs_termines", "periode", "corrections_validees", "texte")},
            "performance": performance(termines), "performance_paris": performance_paris(termines), "matchs": matchs}

def ecrire(donnees=None, chemin=None):
    d = donnees or construire(); json.dump(d, open(chemin or SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return d

if __name__ == "__main__":
    d = ecrire(); print(json.dumps({"matchs": len(d["matchs"]), "termines": d["performance"]["matchs_termines"], "anomalies": d["journal"]["anomalies"]}))
