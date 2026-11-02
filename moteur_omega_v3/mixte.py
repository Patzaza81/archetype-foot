"""Pourcentage officiel MIXTE d'Omega V3 : calibrage, gel, résultats, page (expérimental, 02/11/2026). `python -m moteur_omega_v3.mixte [calibrer|pipeline]`

Journal à part (`data/gamma/journal_mixte.jsonl`, ajout seul) : la production actuelle de la page Gamma (`journal.jsonl`) n'est ni lue ni modifiée.
Chaque match à venir est gelé AVANT le coup d'envoi avec la probabilité calibrée de TOUS ses marchés (pas de sélection, pas de seuil, pas de cote dans le calcul).
Le seul bilan juste d'un modèle de probabilité est la calibration : pour chaque tranche de probabilité annoncée, la réussite réellement observée (matchs terminés, gel avant le coup d'envoi).
Aucun Edge, EV ou « value » : la cote n'est qu'une information affichée à côté.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as K, coeur as C, definitions as Df, donnees as D, marches as M, poisson as P, suivi as SV

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "gamma"
JOURNAL = DOSSIER / "journal_mixte.jsonl"
PAGE = DOSSIER / "mixte.json"
PARAMS = Path(__file__).with_name("parametres_mixte.json")
COTE_MIN = C.PARAMS_DEFAUT["cote_min"]      # 1,26 (Patrick, 02/11/2026) : un marché n'est proposé que s'il a une cote jouable ; le calibrage ne porte QUE sur ces marchés
HAUT_DE_LISTE = 10                    # nombre de marchés AFFICHÉS par match (affichage seulement : le journal garde tous les marchés)
NB = len(M.CLES)
FAM = [M.famille(c) for c in M.CLES]
AFFICHABLE = np.array([f != "scores exacts" for f in FAM])
EVENEMENT = [M.evenement(c) for c in M.CLES]                  # deux marchés de même empreinte sont le MÊME pari : un seul est proposé


def _cotes(m: dict[str, Any]) -> np.ndarray:
    return np.array([C.lire_cote(m.get("cotes"), c) or np.nan for c in M.CLES])


def _validation(mx_P: np.ndarray, S: np.ndarray, V: np.ndarray, cote: np.ndarray, util: np.ndarray, dev: np.ndarray, res: np.ndarray, base: np.ndarray) -> dict[str, Any]:
    """Validation chronologique sur l'archive : calibreur appris sur les matchs anciens (marchés cotés ≥ COTE_MIN seulement), appliqué aux matchs récents jamais vus.
    N'est PAS un bilan de paris gelés : c'est la preuve que le pourcentage affiché correspond à une réussite observée sur des matchs que le calibrage n'a pas vus."""
    play = (cote >= COTE_MIN) & V & util
    cal = P.Calibreur(mx_P[play & dev[:, None]], S[play & dev[:, None]], np.ones(int((play & dev[:, None]).sum()), dtype=bool))
    Q = cal(np.nan_to_num(mx_P))
    r = play & res[:, None]
    tr = []
    for lo in np.arange(0, 1, 0.1):
        m = r & (Q >= lo - 1e-12) & ((Q < lo + 0.1 - 1e-12) if lo < 0.9 else (Q <= 1.0))
        if m.any():
            tr.append({"tranche": f"{lo:.1f}-{lo + 0.1:.1f}", "n": int(m.sum()), "annonce": round(float(Q[m].mean()), 4), "reel": round(float(S[m].mean()), 4)})
    top = {}
    for k in (1, 3):
        n = kk = 0
        an = 0.0
        for t in np.where(res)[0]:
            q = np.where(play[t] & (Q[t] > base), Q[t], -1.0)
            idx = [i for i in np.argsort(-q)[:k] if q[i] >= 0]
            n, kk, an = n + len(idx), kk + int(S[t, idx].sum()), an + float(Q[t, idx].sum())
        top[str(k)] = {"paris": n, "reel": round(kk / n, 4) if n else None, "annonce": round(an / n, 4) if n else None}
    return {"matchs_apprentissage": int(dev.sum()), "matchs_validation": int(res.sum()), "marches_evalues": int(r.sum()), "annonce_moyenne": round(float(Q[r].mean()), 4), "reel": round(float(S[r].mean()), 4),
            "tranches": tr, "meilleurs_marches_du_match": top}


def calibrer(log=print) -> dict[str, Any]:
    """Calibrage sur la population JOUABLE (cote ≥ COTE_MIN) : calibrer sur tous les marchés puis n'afficher que les cotés surestime (biais de sélection mesuré le 02/11/2026).
    MIXTE : matchs avec séquences de 5 matchs au même lieu (525) ; FORCE (repli) : tous les matchs où les forces existent (≈ 1 079). Chaque modèle a SON calibreur."""
    ligues = D.charger_ligues()
    ech, _ = K.echantillon(log)
    ech = sorted(ech, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    brut = P.probabilites(ech, ligues)
    ok = ~np.isnan(brut["MIXTE"][:, 0])
    Y = np.array([x["y"] for x in ech])
    cote = np.array([_cotes(x["m"]) for x in ech])
    S_, V_ = Y == 1, Y != 2
    F = np.array([x["f"] for x in ech])
    util = (np.array(FAM) != "scores exacts")[None, :] & (F > 0) & (F < 1)
    jours = np.array([x["m"]["jour"] for x in ech])
    coupe = jours[int(len(ech) * K.PART_DEV)]
    dev, res = jours < coupe, jours >= coupe
    base_dev = np.array([(S_[:, i] & dev & V_[:, i]).sum() / max(1, (dev & V_[:, i]).sum()) for i in range(NB)])
    validation = _validation(brut["MIXTE"], S_, V_, cote, util, dev & ok, res & ok, base_dev)
    jou = (cote >= COTE_MIN) & V_
    cal_mixte = P.Calibreur(brut["MIXTE"][ok][jou[ok]], S_[ok][jou[ok]], np.ones(int(jou[ok].sum()), dtype=bool))
    Pf, Sf, Vf, Jf, dates = [], [], [], [], []
    for m in D.charger_archive(ligues):
        if m["h"] is None or not ligues.matchs.get(m["ligue"]):
            continue
        try:
            f = P.forces_championnat(ligues.matchs[m["ligue"]], m["eq_dom"], m["eq_ext"], m["jour"])
        except ValueError:
            continue
        y = M.vecteur(m["h"], m["a"])
        Pf.append(P.proba_lambdas(f["lam_dom"], f["lam_ext"]))
        Sf.append(y == 1)
        Vf.append(y != 2)
        Jf.append(_cotes(m) >= COTE_MIN)
        dates.append(m["jour"])
    Pf, Sf, Vf, Jf = np.array(Pf), np.array(Sf), np.array(Vf), np.array(Jf)
    jf = Jf & Vf
    cal_force = P.Calibreur(Pf[jf], Sf[jf], np.ones(int(jf.sum()), dtype=bool))
    base = np.where(Vf.sum(0) > 0, (Sf & Vf).sum(0) / np.maximum(Vf.sum(0), 1), np.nan)      # réussite habituelle de chaque marché sur tous les matchs joués de l'archive
    out = {"version": "mixte-3", "cote_min": COTE_MIN, "calibre_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "MIXTE": {"x": [round(v, 5) for v in cal_mixte.x], "y": [round(v, 5) for v in cal_mixte.y], "effectifs": cal_mixte.effectifs, "matchs": int(ok.sum())},
           "FORCE": {"x": [round(v, 5) for v in cal_force.x], "y": [round(v, 5) for v in cal_force.y], "effectifs": cal_force.effectifs, "matchs": len(Pf), "du": min(dates), "au": max(dates)},
           "taux_base": [None if np.isnan(x) else round(float(x), 4) for x in base], "validation_archive": validation}
    PARAMS.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  calibrage mixte : MIXTE {out['MIXTE']['matchs']} matchs, FORCE {out['FORCE']['matchs']} matchs ; validation : annoncé {validation['annonce_moyenne']} réel {validation['reel']}")
    return out


def charger_calibreurs(chemin: Path = PARAMS) -> tuple[dict[str, P.Calibreur], dict[str, Any]] | None:
    if not chemin.exists():
        return None
    d = json.loads(chemin.read_text(encoding="utf-8"))
    cals = {}
    for k in ("MIXTE", "FORCE"):
        cals[k] = P.Calibreur.depuis(d[k]["x"], d[k]["y"], d[k]["effectifs"])
    return cals, d


def fiche(m: dict[str, Any], liste: list[dict] | None, cals: dict[str, P.Calibreur]) -> dict[str, Any]:
    base = {"match_id": m["id"], "jour": m["jour"], "heure": m.get("heure"), "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"],
            "coup_d_envoi_utc": m.get("coup_d_envoi_utc")}
    if not liste:
        return {**base, "modele": None, "raison": "championnat sans match connu"}
    r = P.proba_officielle(liste, m["eq_dom"], m["eq_ext"], m["jour"], cals)
    if r["modele"] is None:
        return {**base, "modele": None, "raison": r["raison"]}
    q = r["calibre"]
    return {**base, "modele": r["modele"], "p": [round(float(x), 4) for x in q], "p_brut": [round(float(x), 4) for x in r["brut"]],
            "cotes": [(lambda v: v if v is not None else None)(_cote(m, c)) for c in M.CLES]}


def _cote(m: dict[str, Any], c: M.Cle) -> float | None:
    from . import coeur as C
    return C.lire_cote(m.get("cotes"), c)


def _signature(f: dict[str, Any]) -> str:
    return json.dumps([f.get("modele"), f.get("p"), f.get("cotes")], separators=(",", ":"))


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, ligues: D.Ligues | None = None, matchs: list[dict] | None = None,
          cals: dict[str, P.Calibreur] | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    if cals is None:
        ch = charger_calibreurs()
        if ch is None:
            return 0
        cals = ch[0]
    ligues = ligues or D.charger_ligues()
    matchs = matchs if matchs is not None else D.charger_archive(ligues)
    dernier = {l["match_id"]: _signature(l["fiche"]) for l in SV._lire(journal) if l["type"] == "pronostic"}
    nouveaux = []
    for m in matchs:
        ko = SV._ko(m.get("coup_d_envoi_utc"))
        if ko is None or ko <= maintenant or m.get("h") is not None:
            continue
        f = fiche(m, ligues.matchs.get(m["ligue"]) or [], cals)
        if dernier.get(m["id"]) == _signature(f):
            continue
        nouveaux.append({"type": "pronostic", "match_id": m["id"], "gele_le": maintenant.isoformat(timespec="seconds"), "commit": SV._commit(), "version": "mixte-3", "fiche": f})
    SV._ajouter(journal, nouveaux)
    return len(nouveaux)


def resultats(journal: Path = JOURNAL, matchs: list[dict] | None = None, ligues: D.Ligues | None = None) -> int:
    lignes = SV._lire(journal)
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    matchs = matchs if matchs is not None else D.charger_archive(ligues or D.charger_ligues())
    scores = {m["id"]: (m["h"], m["a"]) for m in matchs if m.get("h") is not None}
    nouveaux = []
    for mid, l in SV.derniers_pronostics(lignes).items():
        if mid in faits or mid not in scores or not l["fiche"].get("p"):
            continue
        h, a = scores[mid]
        nouveaux.append({"type": "resultat", "match_id": mid, "score": [h, a], "regle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "y": [int(v) for v in M.vecteur(h, a)]})
    SV._ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(lignes: list[dict[str, Any]]) -> dict[str, Any]:
    """Calibration sur les matchs terminés dont le gel précède le coup d'envoi : par tranche de probabilité annoncée, réussite réelle et effectif. Remboursés exclus."""
    gels = SV.derniers_pronostics(lignes)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    P_, S_ = [], []
    top1 = []
    n_matchs = 0
    for mid, g in gels.items():
        r, f = res.get(mid), g["fiche"]
        if not r or not f.get("p"):
            continue
        n_matchs += 1
        p, y = np.array(f["p"]), np.array(r["y"])
        cotes = np.array([c if c is not None else 0.0 for c in f["cotes"]])
        v = (y != 2) & (cotes >= COTE_MIN)
        P_.append(p[v & AFFICHABLE])
        S_.append((y == 1)[v & AFFICHABLE])
        cand = [i for i in np.argsort(-p) if AFFICHABLE[i] and v[i] and 1e-3 < f["p_brut"][i] < 1 - 1e-3]
        if cand:
            top1.append((float(p[cand[0]]), bool(y[cand[0]] == 1)))
    if not P_:
        return {"matchs": 0}
    p, s = np.concatenate(P_), np.concatenate(S_)
    tranches = []
    for lo in np.arange(0, 1, 0.1):
        m = (p >= lo - 1e-12) & ((p < lo + 0.1 - 1e-12) if lo < 0.9 else (p <= 1.0))
        if m.any():
            tranches.append({"tranche": f"{lo:.1f}-{lo + 0.1:.1f}", "n": int(m.sum()), "annonce": round(float(p[m].mean()), 4), "reel": round(float(s[m].mean()), 4)})
    return {"matchs": n_matchs, "marches_evalues": int(len(p)), "annonce_moyenne": round(float(p.mean()), 4), "reel": round(float(s.mean()), 4), "tranches": tranches,
            "meilleur_marche_du_match": {"n": len(top1), "annonce": round(float(np.mean([a for a, _ in top1])), 4) if top1 else None, "reel": round(float(np.mean([b for _, b in top1])), 4) if top1 else None}}


def haut_de_liste(f: dict[str, Any], k: int = HAUT_DE_LISTE, base: list | None = None) -> list[dict[str, Any]]:
    """Les k marchés les plus probables du match parmi ceux que CE match rend plus probables que d'habitude (probabilité calibrée au-dessus de la réussite habituelle du marché
    sur l'archive : un marché vrai à 99 % partout, comme « moins de 9 buts », ne dit rien de ce match). Hors scores exacts. Seuls les marchés réellement cotés sont proposés (accès) ; la cote est affichée à côté, jamais dans le calcul."""
    p = np.array(f["p"])
    brut = np.array(f["p_brut"])
    out: list[dict[str, Any]] = []
    index: dict[bytes, dict[str, Any]] = {}
    for i in np.lexsort((-brut, -p)):                                # pourcentage calibré décroissant ; à égalité (plateau du calibrage), probabilité brute du modèle décroissante
        if not AFFICHABLE[i] or not 1e-3 < brut[i] < 1 - 1e-3 or f["cotes"][i] is None or f["cotes"][i] < COTE_MIN:
            continue                                              # cote absente ou < COTE_MIN : marché non jouable, jamais proposé (condition d'accès, pas un critère de qualité)
        b = base[i] if base else None
        if b is None or p[i] <= b:
            continue
        c = M.CLES[i]
        libelle = Df.definition(c[0], c[1])[0]
        deja = index.get(EVENEMENT[i])
        if deja is not None:                                      # même événement, autre intitulé (ex. « nul ou extérieur gagne » = « extérieur +0,5 ») : on garde la meilleure cote
            deja.setdefault("aussi", []).append({"libelle": libelle, "cote": f["cotes"][i]})
            if f["cotes"][i] > deja["cote"]:
                deja["aussi"][-1], deja["libelle"], deja["cote"], deja["cle"] = {"libelle": deja["libelle"], "cote": deja["cote"]}, libelle, f["cotes"][i], M.cle_txt(c)
            continue
        e = {"cle": M.cle_txt(c), "libelle": libelle, "famille": FAM[i], "p": float(p[i]), "habituel": b, "cote": f["cotes"][i]}
        index[EVENEMENT[i]] = e
        out.append(e)
    out = out[:k]
    return out


def page(maintenant: datetime | None = None, journal: Path = JOURNAL, sortie: Path = PAGE) -> dict[str, Any]:
    maintenant = maintenant or datetime.now(timezone.utc)
    lignes = SV._lire(journal)
    ch = charger_calibreurs()
    base = ch[1].get("taux_base") if ch else None
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    avenir, sans = [], []
    for mid, g in SV.derniers_pronostics(lignes).items():
        f = g["fiche"]
        ko = SV._ko(f.get("coup_d_envoi_utc"))
        if mid in res or ko is None or ko <= maintenant:
            continue
        if not f.get("p"):
            sans.append({"match": f"{f['domicile']} – {f['exterieur']}", "raison": f.get("raison")})
            continue
        avenir.append({**{k: f[k] for k in ("match_id", "jour", "heure", "competition", "domicile", "exterieur", "coup_d_envoi_utc", "modele")}, "gele_le": g["gele_le"], "marches": haut_de_liste(f, base=base)})
    avenir.sort(key=lambda x: (x["coup_d_envoi_utc"] or "", x["match_id"]))
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "version": "mixte-3", "cote_min": COTE_MIN, "validation_archive": (ch[1].get("validation_archive") if ch else None), "a_venir": avenir, "sans_pronostic": sans, "bilan": bilan(lignes),
           "avertissement": "Pourcentage calibré sur l'historique du moteur : réussite réellement observée à ce niveau, pas une certitude. La cote n'est qu'une information d'accès."}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    debut = datetime.now(timezone.utc)
    ligues = D.charger_ligues()
    matchs = D.charger_archive(ligues)
    n = geler(maintenant=debut, ligues=ligues, matchs=matchs)
    r = resultats(matchs=matchs)
    p = page(debut)
    print(f"mixte : {n} gel(s), {r} résultat(s), {len(p['a_venir'])} match(s) à venir, {len(p['sans_pronostic'])} sans pronostic")


if __name__ == "__main__":
    import sys
    {"calibrer": calibrer, "pipeline": pipeline}.get(sys.argv[1] if len(sys.argv) > 1 else "pipeline", pipeline)()
