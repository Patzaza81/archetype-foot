"""Suivi de MEGAPOWER v2 (sans aucune cote). Usage : python -m megapower.suivi [pipeline]

Chaque passage :
  1. relit tous les matchs du flux commun (data/archive_test) et réapprend les paramètres du modèle de buts sur les matchs joués (modele.ajuster) ;
  2. calcule, pour chaque match, la probabilité de tous les marchés dans trois scénarios (favorable / normal / catastrophe), puis la calibre sur les résultats connus ;
  3. refait le test « marche avant » : apprendre sur le passé, juger les jours suivants jamais vus (le seul chiffre honnête avant les résultats réels) ;
  4. gèle AVANT le coup d'envoi les pronostics retenus de chaque match à venir (journal data/megapower/journal_v2.jsonl, ajout seul) ; « aucun pronostic » est valide ;
  5. règle les matchs terminés et écrit data/megapower/pronostics.json pour la page (bilan réel = gel valide avant le coup d'envoi, match terminé, rien d'autre).
L'ancien journal (data/megapower/journal.jsonl, version 1 fondée sur les cotes) n'est plus alimenté ; il reste en place pour comparer.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import verif_pronostic as V
from . import calibration as C, donnees as D, modele as M

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "megapower"
JOURNAL = DOSSIER / "journal_v2.jsonl"
PAGE = DOSSIER / "pronostics.json"
MODELE = DOSSIER / "modele_v2.json"
CONFIG = ROOT / "config" / "megapower.json"
VERSION = "megapower-2"
COTE_MIN = 1.26                                # règle de Patrick (07/11) : filtre opérationnel, jamais une variable du modèle
JOURS_REGLES_AFFICHES = 7
LISSAGE_NATURE = 100.0                         # matchs « virtuels » du modèle mélangés à la fréquence du championnat (meilleur de 10 / 30 / 100 sur la seconde moitié de l archive : réussite 78,7 % -> 79,3 %)


def fiabilite_demandee() -> float:
    return float(json.loads(CONFIG.read_text(encoding="utf-8"))["fiabilite_demandee"])


def _ko(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _lire(journal: Path) -> list[dict]:
    return [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()] if journal.exists() else []


def _ajouter(journal: Path, lignes: list[dict]) -> None:
    if not lignes:
        return
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")


# ------------------------------------------------------------------------------------------------ prévisions
def prevoir(matchs: list[dict], P: dict) -> dict:
    """Pour chaque match analysable (4 matchs au même lieu au moins pour chaque équipe) : buts attendus et probabilités des trois scénarios."""
    lig = {k: M.Ligue(v) for k, v in M.index_ligues(matchs).items()}
    garde, L = [], []
    for m in matchs:
        c = M.composantes(m, lig[(m["competition"], m["saison"])], P["w_xg"], P["m_equipe"], P["m_ligue"])
        if c is None:
            continue
        garde.append(m)
        L.append((c, *M.lambdas(c, P)))
    la, lb, sa, sb = (np.array([l[i] for l in L]) for i in (1, 2, 3, 4))
    pn, pf, pc = M.scenarios(la, lb, sa, sb) if len(L) else (np.zeros((0, M.NB)),) * 3
    return {"matchs": garde, "comp": [l[0] for l in L], "la": la, "lb": lb, "pn": pn, "pf": pf, "pc": pc, "pl": nature(garde, lig, pn),
            "cote": np.array([[m.get("cotes", {}).get(n, np.nan) for n in M.NOMS] for m in garde]).reshape(len(garde), M.NB)}


def nature(matchs: list[dict], lig: dict, pn: np.ndarray, lissage: float = LISSAGE_NATURE) -> np.ndarray:
    """Nature du championnat (étude du 19/11/2026) : fréquence réelle de chaque marché dans le championnat, sur ses matchs joués strictement avant le match,
    rapprochée de la probabilité du modèle par `lissage` matchs (peu de matchs = on garde le modèle). Aucune cote."""
    out = pn.copy()
    cache = {}
    for t, m in enumerate(matchs):
        k = (m["competition"], m["saison"])
        if k not in cache:
            L = lig[k].matchs
            h = np.array([x["r"]["gf"] if x["r"]["dom"] else x["r"]["ga"] for x in L], int)
            a = np.array([x["r"]["ga"] if x["r"]["dom"] else x["r"]["gf"] for x in L], int)
            O = M.TABLE[np.minimum(h, V.CAP), np.minimum(a, V.CAP)].astype(float) if len(L) else np.zeros((0, M.NB))
            cache[k] = ([x["date"] for x in L], np.vstack([np.zeros((1, M.NB)), np.cumsum(O, axis=0)]))
        dates, cum = cache[k]
        n = int(np.searchsorted(dates, m["jour"], side="left"))
        out[t] = (cum[n] + lissage * pn[t]) / (n + lissage)
    return out


def _resultats(F: dict, sc: dict) -> tuple[np.ndarray, np.ndarray]:
    joue = np.array([m["id"] in sc for m in F["matchs"]], dtype=bool)
    Y = np.full(F["pn"].shape, np.nan)
    for t, m in enumerate(F["matchs"]):
        if joue[t]:
            h, a = sc[m["id"]]
            Y[t] = M.TABLE[min(h, V.CAP), min(a, M.V.CAP)]
    return joue, Y


def _lignes(F, joue, Y, masque_matchs):
    """Lignes (match, marché) des matchs retenus : pn, pc, y, marché, match."""
    N, K = F["pn"].shape
    t = np.repeat(np.arange(N), K)
    mk = np.tile(np.arange(K), N)
    s = masque_matchs[t]
    if F.get("cote") is not None:        # le calibrage ne s'apprend que sur les marchés proposables (cote ≥ 1,26) : la fiabilité annoncée est celle de la population réellement proposée
        s = s & (np.nan_to_num(F["cote"].ravel(), nan=0.0) >= COTE_MIN)
    return F["pn"].ravel()[s], F["pc"].ravel()[s], Y.ravel()[s], mk[s], t[s], (F["pl"].ravel()[s] if F.get("pl") is not None else None)


def retenus(q_bas: np.ndarray, q: np.ndarray, seuil: float, autorisees: set[str] | None = None, cotes: np.ndarray | None = None) -> list[int]:
    """Marchés retenus d'un match : fiabilité calibrée (borne basse) au moins égale à `seuil`, dans une famille autorisée, sans doublon d'événement.
    Si `cotes` est fourni : le marché doit avoir une cote Betpawa au moins égale à COTE_MIN (sans cote = pas proposable)."""
    ok = ~np.isnan(q_bas) & (q_bas >= seuil)
    if cotes is not None:
        ok &= np.nan_to_num(cotes, nan=0.0) >= COTE_MIN
    if autorisees is not None:
        ok &= np.isin(C.FAMILLE, sorted(autorisees))
    return C.choisir(np.nan_to_num(q), ok)


def marche_avant(F: dict, joue: np.ndarray, Y: np.ndarray, seuil: float) -> dict:
    """Chaque jour de la seconde moitié des matchs joués : apprendre le calibrage sur les jours d'avant, juger les pronostics du jour (jamais vus).
    Une famille de marchés est ensuite écartée si sa réussite réelle sur cette période est sous le niveau demandé ; ce choix est vérifié hors échantillon :
    famille choisie sur la première moitié de la période de test, résultat mesuré sur la seconde."""
    jours = np.array([m["jour"] for m in F["matchs"]])
    dj = sorted(set(jours[joue]))
    vide = {"matchs": 0, "pronostics": 0, "familles_autorisees": sorted(C.FAMILLES)}
    if len(dj) < 6:
        return vide
    test = dj[len(dj) // 2:]
    milieu = test[len(test) // 2]
    K = F["pn"].shape[1]
    rec, couv = [], set()                                        # (jour, famille, gagné)
    for d in test:
        cal = C.apprendre(*_lignes(F, joue, Y, joue & (jours < d)))
        for t in np.nonzero(joue & (jours == d))[0]:
            q, bas = C.predire(cal, F["pn"][t], F["pc"][t], np.arange(K), F["pl"][t] if F.get("pl") is not None else None)
            for k in retenus(bas, q, seuil, None, F["cote"][t] if F.get("cote") is not None else None):
                rec.append((d, C.FAMILLE[k], int(Y[t, k]))); couv.add(t)
    if not rec:
        return {**vide, "periode": [test[0], test[-1]], "matchs": int(sum(1 for d in test for _ in np.nonzero(joue & (jours == d))[0]))}

    def taux(R):
        return (round(sum(g for *_, g in R) / len(R), 4) if R else None)

    def par_fam(R):
        out = {}
        for _, f, g in R:
            a = out.setdefault(f, [0, 0]); a[0] += 1; a[1] += g
        return out
    autorisees = {f for f, (n, g) in par_fam(rec).items() if g / n >= seuil}
    A, B = [r for r in rec if r[0] < milieu], [r for r in rec if r[0] >= milieu]
    choix_A = {f for f, (n, g) in par_fam(A).items() if g / n >= seuil}
    B_filtre = [r for r in B if r[1] in choix_A]
    return {"periode": [test[0], test[-1]], "matchs": int(sum(1 for d in test for _ in np.nonzero(joue & (jours == d))[0])), "matchs_avec_pronostic": len(couv),
            "pronostics": len(rec), "reussite": taux(rec), "par_moitie": [{"pronostics": len(A), "reussite": taux(A)}, {"pronostics": len(B), "reussite": taux(B)}],
            "par_famille": {f: {"pronostics": n, "reussite": round(g / n, 4), "autorisee": f in autorisees} for f, (n, g) in sorted(par_fam(rec).items())},
            "familles_autorisees": sorted(autorisees),
            "controle_hors_echantillon": {"familles_choisies_sur": [test[0], milieu], "mesure_sur": [milieu, test[-1]], "pronostics_sans_filtre": len(B), "reussite_sans_filtre": taux(B),
                                          "pronostics_avec_filtre": len(B_filtre), "reussite_avec_filtre": taux(B_filtre)}}


# ------------------------------------------------------------------------------------------------ fiches et journal
def _txt(x: float) -> float:
    return round(float(x), 2)


def fiche(m: dict, t: int, F: dict, cal: dict, seuil: float, autorisees: set[str] | None = None) -> dict:
    K = M.NB
    q, bas = C.predire(cal, F["pn"][t], F["pc"][t], np.arange(K), F["pl"][t] if F.get("pl") is not None else None)
    sel = retenus(bas, q, seuil, autorisees, F["cote"][t] if F.get("cote") is not None else None)
    c = F["comp"][t]
    base = {"match_id": m["id"], "jour": m["jour"], "heure": m.get("heure"), "coup_d_envoi_utc": m.get("ko"), "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"],
            "n_domicile": c["n_dom"], "n_exterieur": c["n_ext"], "buts_attendus": [_txt(F["la"][t]), _txt(F["lb"][t])]}
    paris = [{"marche": M.NOMS[k], "libelle": V.libelle(M.NOMS[k], m["domicile"], m["exterieur"]), "famille": C.FAMILLE[k], "cote": (round(float(F["cote"][t, k]), 2) if F.get("cote") is not None and not np.isnan(F["cote"][t, k]) else None), "fiabilite": round(float(q[k]), 4), "fiabilite_basse": round(float(bas[k]), 4),
              "modele": round(float(F["pn"][t, k]), 4), "catastrophe": round(float(F["pc"][t, k]), 4), "favorable": round(float(F["pf"][t, k]), 4)} for k in sel]
    return {**base, "paris": paris}


def geler(F: dict, cal: dict, sc: dict, maintenant: datetime, seuil: float, autorisees: set[str] | None = None, journal: Path = JOURNAL) -> tuple[int, int]:
    """Gèle les pronostics de chaque match à venir. -> (nouvelles lignes, matchs à venir analysés)."""
    dernier = {}
    for l in _lire(journal):
        if l["type"] == "pronostic":
            dernier[l["match_id"]] = json.dumps([p["marche"] for p in l["fiche"]["paris"]])
    nouveaux, analyses = [], 0
    for t, m in enumerate(F["matchs"]):
        ko = _ko(m.get("ko"))
        if ko is None or ko <= maintenant or m["id"] in sc:
            continue
        analyses += 1
        f = fiche(m, t, F, cal, seuil, autorisees)
        sig = json.dumps([p["marche"] for p in f["paris"]])
        if not f["paris"] and m["id"] not in dernier:
            continue
        if dernier.get(m["id"]) == sig:
            continue
        nouveaux.append({"type": "pronostic", "match_id": m["id"], "gele_le": maintenant.isoformat(timespec="seconds"), "version": VERSION, "fiche": f})
    _ajouter(journal, nouveaux)
    return len(nouveaux), analyses


def gels_valides(lignes: list[dict]) -> dict[str, dict]:
    """Dernier gel de chaque match fait AVANT son coup d'envoi."""
    out = {}
    for l in lignes:
        if l["type"] != "pronostic":
            continue
        ko, g = _ko(l["fiche"].get("coup_d_envoi_utc")), _ko(l["gele_le"])
        if ko and g and g < ko:
            out[l["match_id"]] = l
    return out


def resultats(sc: dict, journal: Path = JOURNAL) -> int:
    lignes = _lire(journal)
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    nouveaux = []
    for mid, l in gels_valides(lignes).items():
        paris = l["fiche"].get("paris") or []
        if mid in faits or mid not in sc or not paris:
            continue
        h, a = sc[mid]
        nouveaux.append({"type": "resultat", "match_id": mid, "score": [h, a], "regle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "paris": [{"marche": p["marche"], "gagne": bool(M.TABLE[min(h, V.CAP), min(a, V.CAP), V.IDX[p["marche"]]])} for p in paris]})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(lignes: list[dict]) -> dict:
    """Bilan RÉEL : pronostics gelés avant le coup d'envoi, matchs terminés."""
    gels, res = gels_valides(lignes), {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    n = g = 0
    fiab = 0.0
    jours, matchs = [], set()
    fam: dict[str, list[int]] = {}
    for mid, gel in gels.items():
        r = res.get(mid)
        if not r:
            continue
        gagne = {p["marche"]: p["gagne"] for p in r["paris"]}
        for p in gel["fiche"]["paris"]:
            if p["marche"] not in gagne:
                continue
            n += 1; g += gagne[p["marche"]]; fiab += p["fiabilite"]
            a = fam.setdefault(p["famille"], [0, 0]); a[0] += 1; a[1] += gagne[p["marche"]]
        matchs.add(mid); jours.append(gel["fiche"]["jour"])
    if not n:
        return {"pronostics": 0, "matchs": 0}
    return {"pronostics": n, "matchs": len(matchs), "reussite": round(g / n, 4), "fiabilite_annoncee": round(fiab / n, 4), "du": min(jours), "au": max(jours),
            "par_famille": {f: {"pronostics": a, "reussite": round(b / a, 4)} for f, (a, b) in sorted(fam.items())}}


def page(F: dict, R: dict, validation: dict, analyses: int, maintenant: datetime, seuil: float, journal: Path = JOURNAL, sortie: Path = PAGE) -> dict:
    lignes = _lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    derniers = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    valides = gels_valides(lignes)
    avenir, encours, reglees = [], [], []
    limite = (maintenant - timedelta(days=JOURS_REGLES_AFFICHES)).date().isoformat()
    for mid, l in derniers.items():
        f = dict(l["fiche"]); f["gele_le"] = l["gele_le"]
        ko = _ko(f.get("coup_d_envoi_utc"))
        if ko and ko > maintenant:
            if f["paris"]:
                avenir.append(f)
            continue
        v = valides.get(mid)
        if not v or not v["fiche"].get("paris"):
            continue
        f = dict(v["fiche"]); f["gele_le"] = v["gele_le"]
        r = res.get(mid)
        if r:
            if f["jour"] >= limite:
                gagne = {p["marche"]: p["gagne"] for p in r["paris"]}
                f["paris"] = [{**p, "resultat": "WIN" if gagne.get(p["marche"]) else "LOSS"} for p in f["paris"]]
                reglees.append({**f, "score": r["score"]})
        else:
            encours.append(f)
    cle = lambda f: (f.get("coup_d_envoi_utc") or "", f["match_id"])
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "version": VERSION, "fiabilite_demandee": seuil, "matchs_a_venir_analyses": analyses,
           "a_venir": sorted(avenir, key=cle), "en_cours": sorted(encours, key=cle), "reglees": sorted(reglees, key=cle, reverse=True), "bilan": bilan(lignes),
           "modele": {"parametres": R["parametres"], "ablation_seconde_moitie": R["ablation_seconde_moitie"], "classement": R["classement"], "matchs_appris": R["matchs_A"] + R["matchs_B"]},
           "marche_avant": validation}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    maintenant = datetime.now(timezone.utc)
    seuil = fiabilite_demandee()
    matchs, sc = D.lire_flux(), D.scores()
    R = M.ajuster(matchs, sc)
    F = prevoir(matchs, R["parametres"])
    joue, Y = _resultats(F, sc)
    cal = C.apprendre(*_lignes(F, joue, Y, joue))
    DOSSIER.mkdir(parents=True, exist_ok=True)
    MODELE.write_text(json.dumps({"version": VERSION, "appris_le": maintenant.isoformat(timespec="seconds"), "fiabilite_demandee": seuil, "modele": R,
                                  "calibrage": {f: {k: v for k, v in r.items() if k != "cov"} for f, r in cal.items()}}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    validation = marche_avant(F, joue, Y, seuil)
    autorisees = set(validation.get("familles_autorisees") or C.FAMILLES)
    n, analyses = geler(F, cal, sc, maintenant, seuil, autorisees)
    r = resultats(sc)
    p = page(F, R, validation, analyses, maintenant, seuil)
    print(f"megapower v2 : appris sur {int(joue.sum())} matchs joués ; {analyses} match(s) à venir analysés, {len(p['a_venir'])} avec pronostics, {n} gel(s), {r} résultat(s)")
    print(f"  marche avant : {validation.get('matchs')} matchs, {validation.get('pronostics')} pronostics, réussite {validation.get('reussite')}")


if __name__ == "__main__":
    pipeline()
