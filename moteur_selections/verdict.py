"""Verdict d'un pari sur un match de sélections nationales, avec la méthode d'Analyse Verdict (verif_pronostic.py), mêmes primitives en lecture seule :
  1. cote >= cote minimale (config/selections.json, 1,26 : règle de l'utilisateur) et au moins NMIN matchs AU MEME LIEU pour chaque équipe (domicile pour l'une, extérieur pour l'autre) ;
  2. combien de fois le pari serait passé dans chaque échantillon : plus souvent passé que raté des DEUX côtés -> TIENT ; d'un seul côté -> TIENT AVEC RÉSERVE ; sinon NE TIENT PAS ;
  3. buts attendus = moyenne de ce que l'attaque marque et de ce que la défense adverse encaisse (avantage du terrain des qualifications remis) ;
  4. si l'attaque contre la défense confirme alors que les fréquences disent non, le verdict remonte d'un cran.
Pas de xG pour les sélections : la lecture xG reste « indisponible », sans effet. Terrain neutre : non évaluable (pas de domicile ni d'extérieur).
Aucune constante inventée : cote minimale et NMIN viennent de l'utilisateur, la fenêtre et le périmètre des matchs viennent de l'étude sur les données (etude_parametres.py)."""
import json, os

import verif_pronostic as V          # primitives d'Analyse Verdict (catalogue des marchés, lecture des lignes, ajustement), lues sans être modifiées
from moteur_selections import donnees

CONFIG = os.path.join(donnees.RACINE, "config", "selections.json")
ORDRE = V.ORDRE


def config(chemin=CONFIG):
    with open(chemin, encoding="utf-8") as f: return json.load(f)


def _moy(S):
    n = len(S)
    return {"n": n, "buts_marques": sum(m for m, _ in S) / n if n else None, "buts_encaisses": sum(e for _, e in S) / n if n else None}


def _reussis(S, dom, k):
    """Nombre de matchs de l'échantillon où le pari (indice k du catalogue) serait passé. Orientation (domicile, extérieur) : l'équipe qui se déplace marque en 2e position."""
    return sum(1 for m, e in S if V.TABLE[min(m if dom else e, V.CAP), min(e if dom else m, V.CAP), k])


def constat(hist, match, marche, cote=None, cfg=None):
    """match : {date, domicile, exterieur, neutre}. -> dict (verdict, force, libelle, cote, phrase, A, B, buts_attendus)."""
    cfg = cfg or config(); nmin = cfg["nmin"]; d, e = match["domicile"], match["exterieur"]
    if cote is not None and cote < cfg["cote_min"]: return {"verdict": "REFUSÉ", "phrase": f"Cote {cote} sous le minimum {cfg['cote_min']}."}
    if match.get("neutre"): return {"verdict": "NON ÉVALUABLE", "phrase": "Terrain neutre : pas de domicile ni d'extérieur, la méthode du même lieu ne s'applique pas."}
    SA = hist.meme_lieu(d, "dom", match["date"], cfg["fenetre_jours"], cfg["officiels_seulement"])
    SB = hist.meme_lieu(e, "ext", match["date"], cfg["fenetre_jours"], cfg["officiels_seulement"])
    if len(SA) < nmin or len(SB) < nmin:
        return {"verdict": "NON ÉVALUABLE", "phrase": f"Rejeté : moins de {nmin} matchs au même lieu ({d} à domicile {len(SA)}, {e} à l'extérieur {len(SB)})."}
    k = V.IDX[marche]; A, B = _moy(SA), _moy(SB)
    A["reussi"], B["reussi"] = _reussis(SA, True, k), _reussis(SB, False, k)
    pa, pb = A["reussi"] / A["n"] > 0.5, B["reussi"] / B["n"] > 0.5
    verdict = "TIENT" if pa and pb else "TIENT AVEC RÉSERVE" if pa or pb else "NE TIENT PAS"
    bm = V._attendus(A, B, ("buts_marques", "buts_encaisses"), ("buts_marques", "buts_encaisses"))
    lect = V._lecture(marche, *bm, hist.avantage(match["date"], cfg["fenetre_jours"]))
    verdict = V._ajuster(verdict, lect, None)
    f = lambda v: "?" if v is None else f"{v:.1f}"
    phrase = (f"{d} à domicile : {f(A['buts_marques'])} buts marqués, {f(A['buts_encaisses'])} encaissés, pari passé {A['reussi']} fois sur {A['n']}. "
              f"{e} à l'extérieur : {f(B['buts_marques'])} marqués, {f(B['buts_encaisses'])} encaissés, pari passé {B['reussi']} fois sur {B['n']}.")
    return {"verdict": verdict, "force": (A["reussi"] / A["n"] + B["reussi"] / B["n"]) / 2, "libelle": V.libelle(marche, d, e), "cote": cote,
            "phrase": phrase, "A": A, "B": B, "buts_attendus": bm, "lecture_buts": lect}


def paris(hist, match, cotes=None, cfg=None):
    """Tous les paris du match qui tiennent (TIENT puis TIENT AVEC RÉSERVE), du plus fiable au moins fiable.
    `cotes` : cotes Betpawa du match (format du flux commun) -> seuls les marchés cotés >= cote minimale. Sans cotes : tous les marchés du catalogue, cote None (« cote à vérifier »), aucune sélection jouable."""
    cfg = cfg or config(); R = []
    C = V.cotes_betpawa(cotes) if cotes else None
    for m in (C if C is not None else V.NOMS):
        r = constat(hist, match, m, C[m] if C else None, cfg)
        if r["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE"): R.append({"marche": m, **r})
    R.sort(key=lambda r: (ORDRE.index(r["verdict"]), -r["force"]))
    return R
