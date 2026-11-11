"""Suivi de MEGAPOWER. Usage : python -m megapower.suivi [pipeline]

Chaque passage :
  1. relit tous les matchs du flux commun (data/archive_test) et réapprend le modèle sur les matchs joués (rien n'est figé à la main) ;
  2. refait le test « marche avant » : apprendre sur le passé, juger les matchs suivants jamais vus (le seul chiffre honnête avant les résultats réels) ;
  3. gèle AVANT le coup d'envoi le pari retenu de chaque match à venir (journal data/megapower/journal.jsonl, ajout seul) ; « aucun pari » est une réponse valide.
     Seul un pari « prouvé » est proposé ; un pari « sous observation » est gelé et suivi, mais la page dit de ne pas le jouer ;
  4. règle les paris des matchs terminés ;
  5. écrit data/megapower/pronostics.json pour la page (bilan réel = paris gelés avant le coup d'envoi, matchs terminés, rien d'autre).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import verif_pronostic as V
from . import coeur as C, donnees as D, signaux as S, tri_moteurs as TM

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "megapower"
JOURNAL = DOSSIER / "journal.jsonl"
PAGE = DOSSIER / "pronostics.json"
MODELE = DOSSIER / "modele.json"
VERSION = "megapower-1"
JOURS_REGLES_AFFICHES = 7
NOMS_STATUT = {2: "prouvé", 1: "sous observation"}


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


def cote_min() -> float:
    return float(V.config()["cote_min"])


def _resume(T, idx, J=None) -> dict:
    if len(idx) == 0:
        return {"paris": 0}
    g = np.where(T["y"][idx] == 1, T["cote"][idx] - 1, -1.0)
    return {"paris": int(len(idx)), "matchs": int(len(np.unique(T["match"][idx]))), "reussite": round(float(T["y"][idx].mean()), 4), "cote_moyenne": round(float(T["cote"][idx].mean()), 3),
            "rendement": round(float(g.mean()), 4), "marge": round(float(2 * g.std() / np.sqrt(len(g))), 4)}


def marche_avant(T: dict, jours: np.ndarray, cmin: float) -> dict:
    """Exactement ce que fait le moteur chaque nuit, rejoué sur le passé : pour chaque jour de la seconde moitié de la période, apprendre sur tous les jours d'avant,
    puis parier sur les matchs de ce jour, jamais vus. Ce n'est pas un bilan réel (les paris n'étaient pas gelés) : c'est le test le plus honnête possible avant les vrais résultats."""
    from datetime import date
    joue = ~np.isnan(T["y"])
    dj = [str(j) for j in np.unique(jours[joue])]
    vide = {"jours_testes": 0, "sous_observation": {"paris": 0}, "prouves": {"paris": 0}, "periode_testee": None, "par_semaine": []}
    if len(dj) < 4:
        return vide
    d0, d1 = date.fromisoformat(dj[0]), date.fromisoformat(dj[-1])
    milieu = (d0 + (d1 - d0) / 2).isoformat()
    tout, par_jour = {1: [], 2: []}, {}
    testes = [j for j in dj if j >= milieu]
    for j in testes:
        tr, te = joue & (jours < j), joue & (jours == j)
        mod = C.apprendre({k: v[tr] for k, v in T.items()}, jours[tr], cmin)
        Tt = {k: v[te] for k, v in T.items()}
        Jt = C.juger(Tt, mod)
        for s in (1, 2):
            i = np.nonzero(te)[0][C.meilleur_par_match(Tt, Jt, s)] if (Jt["statut"] >= s).any() else np.array([], dtype=int)
            tout[s] += list(i)
            if s == 1:
                par_jour[j] = list(i)
    lundi = lambda j: (date.fromisoformat(j) - timedelta(days=date.fromisoformat(j).weekday())).isoformat()
    semaines = {}
    for j, i in par_jour.items():
        semaines.setdefault(lundi(j), []).extend(i)
    return {"jours_testes": len(testes), "periode_testee": [testes[0], testes[-1]], "sous_observation": _resume(T, np.array(tout[1], dtype=int)), "prouves": _resume(T, np.array(tout[2], dtype=int)),
            "par_semaine": [{"semaine_du": k, **_resume(T, np.array(v, dtype=int))} for k, v in sorted(semaines.items())]}


def _lectures(m: dict, k: int, cote: float) -> list[dict]:
    out = []
    for nom, a, b in C.LECTURES:
        v = (m["signaux"][a][k] + m["signaux"][b][k]) / 2
        if not np.isnan(v):
            out.append({"moteur": nom, "lecture": round(float(v), 4), "pour": bool(v > 1 / cote)})
    return out


def fiche(m: dict, T: dict, J: dict, i: int | None) -> dict:
    base = {"match_id": m["id"], "jour": m["jour"], "heure": m.get("heure"), "coup_d_envoi_utc": m.get("ko"), "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"],
            "n_domicile": m["n_dom"], "n_exterieur": m["n_ext"]}
    if i is None:
        return {**base, "pari": None}
    k = int(T["marche"][i]); nom = S.NOMS[k]; cote = float(T["cote"][i])
    return {**base, "pari": {"marche": nom, "libelle": V.libelle(nom, m["domicile"], m["exterieur"]), "famille": C.famille(nom), "cote": cote, "statut": NOMS_STATUT[int(J["statut"][i])],
                             "reussite_apprise": round(float(J["p"][i]), 4), "reussite_pour_rembourser": round(1 / cote, 4), "gain_attendu": round(float(J["gain"][i]), 4),
                             "gain_attendu_bas": round(float(J["gain_bas"][i]), 4), "lectures": _lectures(m, k, cote)}}


def geler(matchs: list[dict], T: dict, J: dict, sc: dict, maintenant: datetime, journal: Path = JOURNAL) -> tuple[int, int]:
    """Gèle le pari retenu de chaque match à venir. -> (nouvelles lignes, matchs à venir analysés)."""
    choisi = {int(T["match"][i]): int(i) for i in C.meilleur_par_match(T, J, 1)} if (J["statut"] >= 1).any() else {}
    dernier = {}
    for l in _lire(journal):
        if l["type"] == "pronostic":
            dernier[l["match_id"]] = json.dumps(l["fiche"].get("pari"), sort_keys=True)
    nouveaux, analyses = [], 0
    for t, m in enumerate(matchs):
        ko = _ko(m.get("ko"))
        if ko is None or ko <= maintenant or m["id"] in sc:
            continue
        analyses += 1
        f = fiche(m, T, J, choisi.get(t))
        sig = json.dumps(f["pari"], sort_keys=True)
        if f["pari"] is None and m["id"] not in dernier:
            continue                                            # rien à geler : pas de pari, et aucun pari annoncé avant
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
        p = l["fiche"].get("pari")
        if mid in faits or mid not in sc or not p:
            continue
        h, a = sc[mid]
        nouveaux.append({"type": "resultat", "match_id": mid, "score": [h, a], "regle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "marche": p["marche"], "cote": p["cote"], "gagne": bool(S.TABLE[min(h, S.CAP), min(a, S.CAP), V.IDX[p["marche"]]])})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(lignes: list[dict]) -> dict:
    """Bilan RÉEL : paris gelés avant le coup d'envoi, matchs terminés."""
    gels, res = gels_valides(lignes), {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    out = {}
    for s in NOMS_STATUT.values():
        P = [(r["cote"], r["gagne"], g["fiche"]["jour"]) for mid, g in gels.items() if (r := res.get(mid)) and (g["fiche"].get("pari") or {}).get("statut") == s and g["fiche"]["pari"]["marche"] == r["marche"]]
        if not P:
            out[s] = {"paris": 0}
            continue
        gains = [(c - 1) if g else -1.0 for c, g, _ in P]
        out[s] = {"paris": len(P), "reussite": round(sum(g for _, g, _ in P) / len(P), 4), "cote_moyenne": round(sum(c for c, _, _ in P) / len(P), 3),
                  "rendement": round(sum(gains) / len(P), 4), "du": min(j for *_, j in P), "au": max(j for *_, j in P)}
    return out


def _modele_public(mod: dict) -> dict:
    fam = {}
    for f, r in mod["familles"].items():
        fam[f] = {"paris": r["paris"], "matchs": r["matchs"], "reussite": round(r["reussite"], 4), "rendement_de_tout_jouer": round(r["rendement_de_tout_jouer"], 4),
                  "accord_garde": r["avec_accord"], "poids_accord": round(r["w"][2], 4) if r["avec_accord"] else None}
    return {"du": mod["du"], "au": mod["au"], "matchs": mod["matchs"], "paris": mod["paris"], "cote_min": mod["cote_min"], "familles": fam}


def page(matchs: list[dict], mod: dict, validation: dict, analyses: int, maintenant: datetime, journal: Path = JOURNAL, sortie: Path = PAGE) -> dict:
    lignes = _lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    avenir, observation, encours, reglees = [], [], [], []
    limite = (maintenant - timedelta(days=JOURS_REGLES_AFFICHES)).date().isoformat()
    derniers = {}
    for l in lignes:
        if l["type"] == "pronostic":
            derniers[l["match_id"]] = l
    valides = gels_valides(lignes)
    for mid, l in derniers.items():
        f = dict(l["fiche"]); f["gele_le"] = l["gele_le"]
        ko = _ko(f.get("coup_d_envoi_utc"))
        if ko and ko > maintenant:
            if f.get("pari"):
                (avenir if f["pari"]["statut"] == "prouvé" else observation).append(f)
            continue
        v = valides.get(mid)
        if not v or not v["fiche"].get("pari"):
            continue
        f = dict(v["fiche"]); f["gele_le"] = v["gele_le"]
        r = res.get(mid)
        if r:
            if f["jour"] >= limite:
                reglees.append({**f, "score": r["score"], "resultat": "WIN" if r["gagne"] else "LOSS"})
        else:
            encours.append(f)
    cle = lambda f: (f.get("coup_d_envoi_utc") or "", f["match_id"])
    try:
        tri = TM.mesures()
    except Exception as e:                                      # noqa: BLE001 : le tri des autres moteurs ne bloque jamais MEGAPOWER
        tri = [{"moteur": f"tri indisponible ({type(e).__name__})", "paris": 0}]
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "version": VERSION, "matchs_a_venir_analyses": analyses, "a_venir": sorted(avenir, key=cle), "sous_observation": sorted(observation, key=cle), "en_cours": sorted(encours, key=cle),
           "reglees": sorted(reglees, key=cle, reverse=True), "bilan": bilan(lignes), "modele": _modele_public(mod), "marche_avant": validation, "tri_moteurs": tri}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    maintenant = datetime.now(timezone.utc)
    cmin = cote_min()
    matchs = D.lire_flux()
    sc = D.scores()
    T = D.tableau(matchs, sc)
    jours = np.array([m["jour"] for m in matchs])[T["match"]] if len(matchs) else np.array([])
    joue = ~np.isnan(T["y"])
    mod = C.apprendre({k: v[joue] for k, v in T.items()}, jours[joue], cmin)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    MODELE.write_text(json.dumps({"version": VERSION, "appris_le": maintenant.isoformat(timespec="seconds"), **mod}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    validation = marche_avant(T, jours, cmin)
    J = C.juger(T, mod)
    n, analyses = geler(matchs, T, J, sc, maintenant)
    r = resultats(sc)
    p = page(matchs, mod, validation, analyses, maintenant)
    print(f"megapower : appris sur {mod['matchs']} matchs joués ({mod['du']} → {mod['au']}) ; {analyses} match(s) à venir analysés, {len(p['a_venir'])} pari(s) prouvé(s), {len(p['sous_observation'])} sous observation, {n} gel(s), {r} résultat(s)")
    so = validation["sous_observation"]
    print(f"  marche avant : sous observation {so.get('paris', 0)} paris, rendement {so.get('rendement')} ; prouvés {validation['prouves'].get('paris', 0)} paris")


if __name__ == "__main__":
    pipeline()
