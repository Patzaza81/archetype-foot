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

from . import calibrage as K, definitions as Df, donnees as D, marches as M, poisson as P, suivi as SV

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "gamma"
JOURNAL = DOSSIER / "journal_mixte.jsonl"
PAGE = DOSSIER / "mixte.json"
PARAMS = Path(__file__).with_name("parametres_mixte.json")
HAUT_DE_LISTE = 10                    # nombre de marchés AFFICHÉS par match (affichage seulement : le journal garde tous les marchés)
NB = len(M.CLES)
FAM = [M.famille(c) for c in M.CLES]
AFFICHABLE = np.array([f != "scores exacts" for f in FAM])


def calibrer(log=print) -> dict[str, Any]:
    """MIXTE : matchs avec séquences de 5 matchs au même lieu (525) ; FORCE (repli) : tous les matchs où les forces existent (≈ 1 079). Chaque modèle a SON calibreur."""
    ligues = D.charger_ligues()
    ech, _ = K.echantillon(log)
    ech = sorted(ech, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    brut = P.probabilites(ech, ligues)
    ok = ~np.isnan(brut["MIXTE"][:, 0])
    Y = np.array([x["y"] for x in ech])
    cal_mixte = P.Calibreur(brut["MIXTE"][ok], (Y == 1)[ok], (Y != 2)[ok])
    Pf, Sf, Vf, jours = [], [], [], []
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
        jours.append(m["jour"])
    cal_force = P.Calibreur(np.array(Pf), np.array(Sf), np.array(Vf))
    Sa, Va = np.array(Sf), np.array(Vf)
    base = np.where(Va.sum(0) > 0, (Sa & Va).sum(0) / np.maximum(Va.sum(0), 1), np.nan)      # réussite habituelle de chaque marché sur tous les matchs joués de l'archive
    out = {"version": "mixte-1", "calibre_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "MIXTE": {"table": [round(float(x), 4) for x in cal_mixte.table], "effectifs": cal_mixte.effectifs, "matchs": int(ok.sum())},
           "FORCE": {"table": [round(float(x), 4) for x in cal_force.table], "effectifs": cal_force.effectifs, "matchs": len(Pf), "du": min(jours), "au": max(jours)},
           "taux_base": [None if np.isnan(x) else round(float(x), 4) for x in base], "valides_base": [int(x) for x in Va.sum(0)]}
    PARAMS.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  calibrage mixte : MIXTE {out['MIXTE']['matchs']} matchs, FORCE {out['FORCE']['matchs']} matchs")
    return out


def charger_calibreurs(chemin: Path = PARAMS) -> tuple[dict[str, P.Calibreur], dict[str, Any]] | None:
    if not chemin.exists():
        return None
    d = json.loads(chemin.read_text(encoding="utf-8"))
    cals = {}
    for k in ("MIXTE", "FORCE"):
        c = P.Calibreur.__new__(P.Calibreur)
        c.table, c.effectifs = np.array(d[k]["table"]), d[k]["effectifs"]
        cals[k] = c
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
    return {**base, "modele": r["modele"], "p": [round(float(x), 3) for x in q], "p_brut": [round(float(x), 3) for x in r["brut"]],
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
        nouveaux.append({"type": "pronostic", "match_id": m["id"], "gele_le": maintenant.isoformat(timespec="seconds"), "commit": SV._commit(), "version": "mixte-1", "fiche": f})
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
        v = y != 2
        P_.append(p[v & AFFICHABLE])
        S_.append((y == 1)[v & AFFICHABLE])
        cand = [i for i in np.argsort(-p) if AFFICHABLE[i] and v[i] and 0 < f["p_brut"][i] < 1]
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
    out = []
    for i in np.argsort(-p, kind="stable"):
        if not AFFICHABLE[i] or not 1e-3 < brut[i] < 1 - 1e-3 or f["cotes"][i] is None:
            continue                                              # un marché sans cote BetPawa ne peut pas être joué : il n'est pas proposé (condition d'accès, pas un critère de qualité)
        b = base[i] if base else None
        if b is None or p[i] <= b:
            continue
        c = M.CLES[i]
        out.append({"cle": M.cle_txt(c), "libelle": Df.definition(c[0], c[1])[0], "famille": FAM[i], "p": float(p[i]), "habituel": b, "cote": f["cotes"][i]})
        if len(out) >= k:
            break
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
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "version": "mixte-1", "a_venir": avenir, "sans_pronostic": sans, "bilan": bilan(lignes),
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
