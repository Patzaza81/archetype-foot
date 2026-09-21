#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluation_moteur.py -- compare l'analyse FIGÉE du moteur (snapshot) aux résultats réels.

    python evaluation_moteur.py evaluation/snapshot_....json resultats.txt [--json rapport.json] [--liste]

Résultats acceptés, une ligne par match (le score est toujours « buts du premier - buts du second », dans l'ordre écrit) :
    Manta - Orense 2-1          |   Manta 2-1 Orense          |   Manta;Orense;2;1          |   2026-09-20 Manta - Orense 2-1
Règles de sécurité (décidées avant de connaître un seul résultat) :
  - un résultat n'est associé à un match que si LES DEUX équipes correspondent (même date si elle est donnée) ; en cas
    d'ambiguïté ou de doute, la ligne est rejetée et listée avec le meilleur candidat : jamais d'association devinée ;
  - équipes écrites dans l'ordre inverse : détectées, le score est inversé et un avertissement est émis ;
  - le règlement est celui du pipeline (archetype_model.learning.reglement), dont la cohérence avec le moteur est testée ;
  - aucune conclusion sur le ROI sous SEUIL_CONCLUSION_CHOIX choix (ROADMAP : 150 à 200 choix propres).

Ce que mesure le rapport, du plus au moins « ce que le site affiche » :
  choix_publies           les choix P1/P2/P3 affichés sur le site
  value_bets_hors_D       tout ce que le moteur signale comme value bet et n'écarte pas (catégories A, B, C)
  value_bets_D            les value bets écartées par le moteur (catégorie D) : montre si l'écart est justifié
  tous_les_marches        les ~25 marchés cotés de chaque match : mesure de CALIBRATION, la plus riche en observations
Pour chaque groupe : taux de réussite, probabilité moyenne annoncée par le modèle, probabilité juste du marché (cotes sans
marge), Brier et log-loss du modèle et du marché, ROI à mise plate, avec intervalles de confiance (bootstrap PAR MATCH :
les marchés d'un même match ne sont pas indépendants).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
import random
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from archetype_model.learning.reglement import evaluer_marche

SEUIL_CORRESPONDANCE = 0.85          # les DEUX équipes doivent atteindre ce score
MARGE_AMBIGUITE = 0.03               # deux matchs à moins de 0,03 l'un de l'autre : ligne rejetée
SEUIL_CONCLUSION_CHOIX = 150         # sous ce nombre de choix, aucune conclusion sur le ROI
N_BOOTSTRAP = 2000
GRAINE = 20260921
GROUPES = ("choix_publies", "value_bets_hors_D", "value_bets_D", "tous_les_marches")
MOTS_VIDES = {"fc", "cf", "sc", "ac", "afc", "cd", "ca", "sk", "fk", "the", "de", "del", "la", "el", "club", "fbc", "ud", "sd", "as", "ss"}


# ═══════════════════════════ noms d'équipes ═══════════════════════════
def jetons(nom: str) -> List[str]:
    s = unicodedata.normalize("NFD", (nom or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("&", " and ")
    return [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in MOTS_VIDES]


def score_noms(a: str, b: str) -> float:
    """1,0 = mêmes mots ; 0,92 = tous les mots du plus court sont dans le plus long ; sinon ressemblance des lettres."""
    ta, tb = jetons(a), jetons(b)
    if not ta or not tb:
        return 0.0
    if set(ta) == set(tb):
        return 1.0
    sa, sb = set(ta), set(tb)
    if (sa <= sb or sb <= sa) and max(len(t) for t in (sa & sb)) >= 3:
        return 0.92
    return difflib.SequenceMatcher(None, "".join(ta), "".join(tb)).ratio()


# ═══════════════════════════ lecture des résultats ═══════════════════════════
_SCORE = r"(\d{1,2})\s*[-–:]\s*(\d{1,2})"
_RE_A = re.compile(rf"^(?:(\d{{4}}-\d{{2}}-\d{{2}})\s+)?(.+?)\s+[-–—]\s+(.+?)\s+{_SCORE}\s*$")
_RE_B = re.compile(rf"^(?:(\d{{4}}-\d{{2}}-\d{{2}})\s+)?(.+?)\s+{_SCORE}\s+(.+?)\s*$")


def lit_resultats(texte: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """(résultats lus, lignes non comprises). Format libre, voir l'en-tête du module."""
    lus, refusees = [], []
    for brut in (texte or "").splitlines():
        ligne = brut.strip()
        if not ligne or ligne.startswith("#"):
            continue
        r = None
        if ";" in ligne or "\t" in ligne:
            morceaux = [x.strip() for x in re.split(r"[;\t]", ligne)]
            if len(morceaux) >= 4 and morceaux[-1].isdigit() and morceaux[-2].isdigit():
                r = {"date": None, "dom": morceaux[-4], "ext": morceaux[-3], "a": int(morceaux[-2]), "b": int(morceaux[-1])}
                if len(morceaux) >= 5 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", morceaux[0]):
                    r["date"] = morceaux[0]
        if r is None:
            m = _RE_A.match(ligne)
            if m:
                r = {"date": m.group(1), "dom": m.group(2), "ext": m.group(3), "a": int(m.group(4)), "b": int(m.group(5))}
            else:
                m = _RE_B.match(ligne)
                if m:
                    r = {"date": m.group(1), "dom": m.group(2), "ext": m.group(5), "a": int(m.group(3)), "b": int(m.group(4))}
        if r is None or r["a"] > 20 or r["b"] > 20 or not re.search(r"[^\W_]", r["dom"]) or not re.search(r"[^\W_]", r["ext"]):   # un nom d'équipe contient au moins une lettre ou un chiffre
            refusees.append(ligne)
            continue
        r["ligne"] = ligne
        lus.append(r)
    return lus, refusees


# ═══════════════════════════ association résultat -> match ═══════════════════════════
def associe(resultats: List[Dict[str, Any]], matchs: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Retourne ({id_match: {buts_dom, buts_ext, ligne, inverse}}, lignes rejetées avec raison, avertissements)."""
    attribues: Dict[str, Dict[str, Any]] = {}
    rejetees: List[Dict[str, Any]] = []
    avertissements: List[str] = []
    for r in resultats:
        candidats = []
        for m in matchs:
            if r["date"] and r["date"] != m["date"]:
                continue
            direct = min(score_noms(r["dom"], m["domicile"]), score_noms(r["ext"], m["exterieur"]))
            inverse = min(score_noms(r["dom"], m["exterieur"]), score_noms(r["ext"], m["domicile"]))
            if direct >= inverse:
                candidats.append((direct, False, m))
            else:
                candidats.append((inverse, True, m))
        candidats.sort(key=lambda c: -c[0])
        if not candidats or candidats[0][0] < SEUIL_CORRESPONDANCE:
            meilleur = candidats[0] if candidats else None
            rejetees.append({"ligne": r["ligne"], "raison": "aucun match du snapshot ne correspond aux deux équipes",
                             "meilleur_candidat": f"{meilleur[2]['domicile']} - {meilleur[2]['exterieur']} (score {meilleur[0]:.2f})" if meilleur else None})
            continue
        if len(candidats) > 1 and candidats[0][0] - candidats[1][0] < MARGE_AMBIGUITE and candidats[1][0] >= SEUIL_CORRESPONDANCE:
            rejetees.append({"ligne": r["ligne"], "raison": "ambigu : deux matchs correspondent",
                             "meilleur_candidat": f"{candidats[0][2]['domicile']} - {candidats[0][2]['exterieur']} / {candidats[1][2]['domicile']} - {candidats[1][2]['exterieur']}"})
            continue
        score, inverse, m = candidats[0]
        if m["id"] in attribues:
            rejetees.append({"ligne": r["ligne"], "raison": "match déjà renseigné par une ligne précédente", "meilleur_candidat": f"{m['domicile']} - {m['exterieur']}"})
            continue
        bd, be = (r["b"], r["a"]) if inverse else (r["a"], r["b"])
        if inverse:
            avertissements.append(f"équipes écrites dans l'ordre inverse, score inversé : « {r['ligne']} » -> {m['domicile']} {bd}-{be} {m['exterieur']}")
        attribues[m["id"]] = {"buts_dom": bd, "buts_ext": be, "ligne": r["ligne"], "inverse": inverse}
    return attribues, rejetees, avertissements


# ═══════════════════════════ statistiques ═══════════════════════════
def _clamp(p: float) -> float:
    return min(max(p, 1e-6), 1 - 1e-6)


def _stats(lignes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Agrégats d'une liste de lignes {gagne, p, pj, cote}."""
    n = len(lignes)
    if n == 0:
        return None
    g = sum(l["gagne"] for l in lignes)
    p_moy = sum(l["p"] for l in lignes) / n
    out = {"n": n, "gagnes": g, "taux": g / n, "p_modele": p_moy, "ecart_calibration": g / n - p_moy,
           "brier_modele": sum((l["p"] - l["gagne"]) ** 2 for l in lignes) / n,
           "logloss_modele": -sum(l["gagne"] * math.log(_clamp(l["p"])) + (1 - l["gagne"]) * math.log(1 - _clamp(l["p"])) for l in lignes) / n,
           "roi": sum(l["gagne"] * (l["cote"] - 1) - (1 - l["gagne"]) for l in lignes) / n,
           "cote_moyenne": sum(l["cote"] for l in lignes) / n}
    avec_marche = [l for l in lignes if l["pj"] is not None]
    if avec_marche:
        k = len(avec_marche)
        out["p_marche"] = sum(l["pj"] for l in avec_marche) / k
        out["brier_marche"] = sum((l["pj"] - l["gagne"]) ** 2 for l in avec_marche) / k
        out["logloss_marche"] = -sum(l["gagne"] * math.log(_clamp(l["pj"])) + (1 - l["gagne"]) * math.log(1 - _clamp(l["pj"])) for l in avec_marche) / k
        out["brier_modele_meme_lignes"] = sum((l["p"] - l["gagne"]) ** 2 for l in avec_marche) / k
        out["diff_brier"] = out["brier_modele_meme_lignes"] - out["brier_marche"]           # < 0 : le modèle fait mieux que le marché
    return out


def _bootstrap(par_match: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Tuple[float, float]]]:
    """Intervalles à 95 % par rééchantillonnage des MATCHS (les marchés d'un match sont corrélés)."""
    ids = sorted(par_match)
    if len(ids) < 5:
        return None
    rnd = random.Random(GRAINE)
    ech: Dict[str, List[float]] = {"ecart_calibration": [], "roi": [], "diff_brier": [], "taux": []}
    for _ in range(N_BOOTSTRAP):
        tirage = [l for i in (rnd.choice(ids) for _ in ids) for l in par_match[i]]
        s = _stats(tirage)
        if s is None:
            continue
        for k in ech:
            if k in s:
                ech[k].append(s[k])
    out = {}
    for k, v in ech.items():
        if len(v) > 100:
            v.sort()
            out[k] = (v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1])
    return out


def _bins(lignes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.0001)):
        b = [l for l in lignes if lo <= l["p"] < hi]
        if b:
            out.append({"tranche": f"{int(lo*100)}-{min(int(hi*100), 100)} %", "n": len(b), "p_modele": sum(l["p"] for l in b) / len(b), "taux": sum(l["gagne"] for l in b) / len(b)})
    return out


def evalue(snapshot: Dict[str, Any], attribues: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Règle chaque marché de chaque match renseigné et agrège. Les matchs sans résultat sont ignorés (et comptés)."""
    groupes: Dict[str, Dict[str, List[Dict[str, Any]]]] = {g: {} for g in GROUPES}
    detail_choix, erreurs = [], []
    familles: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for m in snapshot["matchs"]:
        res = attribues.get(m["id"])
        if not res:
            continue
        par_marche = {}
        for l in m["inventaire"]:
            if l["marche"] is None or not l["cote"] or l["cote"] <= 1:
                continue
            statut = evaluer_marche(l["marche"], res["buts_dom"], res["buts_ext"]).statut
            if statut not in ("WIN", "LOSS"):
                erreurs.append(f"{m['domicile']} - {m['exterieur']} : {l['marche']} -> {statut}")
                continue
            ligne = {"gagne": 1 if statut == "WIN" else 0, "p": l["probabilite"], "pj": l["p_juste"], "cote": l["cote"], "marche": l["marche"], "famille": l["famille"]}
            par_marche[l["marche"]] = ligne
            groupes["tous_les_marches"].setdefault(m["id"], []).append(ligne)
            if l["is_value"]:
                groupes["value_bets_D" if l["categorie"] == "D" else "value_bets_hors_D"].setdefault(m["id"], []).append(ligne)
        for c in m["choix_publies"]:
            ligne = par_marche.get(c["marche"])
            if ligne is None:
                erreurs.append(f"{m['domicile']} - {m['exterieur']} : choix {c['marche']} introuvable ou non réglable")
                continue
            groupes["choix_publies"].setdefault(m["id"], []).append(dict(ligne, rang=c["rang"], niveau=c["niveau"]))
            familles.setdefault(ligne["famille"], {}).setdefault(m["id"], []).append(ligne)
            detail_choix.append({"match": f"{m['domicile']} - {m['exterieur']}", "score": f"{res['buts_dom']}-{res['buts_ext']}", "rang": c["rang"], "marche": c["marche"],
                                 "cote": c["cote"], "probabilite": c["probabilite"], "resultat": "GAGNÉ" if ligne["gagne"] else "PERDU", "resume": c.get("resume")})
    rapport: Dict[str, Any] = {"groupes": {}, "erreurs_reglement": erreurs, "detail_choix": detail_choix}
    for g, par_match in groupes.items():
        lignes = [l for ls in par_match.values() for l in ls]
        rapport["groupes"][g] = {"stats": _stats(lignes), "n_matchs": len(par_match), "intervalles": _bootstrap(par_match), "tranches": _bins(lignes)}
    rapport["choix_par_famille"] = {f: {"stats": _stats([l for ls in pm.values() for l in ls]), "n_matchs": len(pm)} for f, pm in sorted(familles.items())}
    rapport["choix_par_rang"] = {}
    for rang in ("P1", "P2", "P3"):
        ls = [l for ls in groupes["choix_publies"].values() for l in ls if l["rang"] == rang]
        if ls:
            rapport["choix_par_rang"][rang] = _stats(ls)
    return rapport


# ═══════════════════════════ rapport ═══════════════════════════
def _pct(x: Optional[float]) -> str:
    return "n/d" if x is None else f"{100 * x:.1f} %".replace(".", ",")


def _iv(iv: Optional[Tuple[float, float]], pct: bool = True) -> str:
    if not iv:
        return "intervalle non calculable (moins de 5 matchs)"
    f = (lambda x: f"{100 * x:+.1f} %") if pct else (lambda x: f"{x:+.4f}")
    return f"95 % : [{f(iv[0])} ; {f(iv[1])}]".replace(".", ",")


TITRES = {"choix_publies": "CHOIX PUBLIÉS (ce que le site affiche)", "value_bets_hors_D": "VALUE BETS du moteur, catégories A/B/C",
          "value_bets_D": "VALUE BETS écartées par le moteur (catégorie D)", "tous_les_marches": "TOUS LES MARCHÉS COTÉS (calibration)"}


def rapport_texte(entete: Dict[str, Any], rapport: Dict[str, Any]) -> str:
    L: List[str] = []
    L.append(f"ÉVALUATION DU MOTEUR {entete['moteur']} — {entete['n_avec_resultat']} matchs avec résultat sur {entete['n_snapshot']} figés")
    L.append(f"snapshot : {entete['origine'][:110]}")
    if entete.get("integrite") is not None:
        L.append("intégrité du snapshot : " + ("INTACT (empreinte SHA-256 conforme)" if entete["integrite"] else "MODIFIÉ — évaluation à ne pas prendre en compte"))
    for g in GROUPES:
        d = rapport["groupes"][g]; s = d["stats"]
        L.append("")
        L.append(f"── {TITRES[g]} ──")
        if not s:
            L.append("   aucune ligne")
            continue
        L.append(f"   {s['n']} lignes sur {d['n_matchs']} matchs ; {s['gagnes']} gagnées : taux {_pct(s['taux'])} pour une probabilité annoncée de {_pct(s['p_modele'])}"
                 + (f" (marché sans marge : {_pct(s['p_marche'])})" if "p_marche" in s else ""))
        iv = d["intervalles"] or {}
        L.append(f"   écart de calibration (taux − probabilité annoncée) : {_pct(s['ecart_calibration'])}   {_iv(iv.get('ecart_calibration'))}")
        if "diff_brier" in s:
            verdict = "le modèle fait MIEUX que le marché" if s["diff_brier"] < 0 else "le marché fait mieux que le modèle"
            L.append(f"   Brier : modèle {s['brier_modele_meme_lignes']:.4f} | marché {s['brier_marche']:.4f} | différence {s['diff_brier']:+.4f} ({verdict})   {_iv(iv.get('diff_brier'), False)}")
        L.append(f"   ROI à mise plate : {_pct(s['roi'])}   {_iv(iv.get('roi'))}   (cote moyenne {s['cote_moyenne']:.2f})".replace(".", ","))
        if g == "choix_publies" and s["n"] < SEUIL_CONCLUSION_CHOIX:
            L.append(f"   ⚠ {s['n']} choix < {SEUIL_CONCLUSION_CHOIX} : le ROI n'est PAS concluant (l'intervalle ci-dessus montre l'incertitude).")
        if g in ("tous_les_marches", "value_bets_hors_D") and d["tranches"]:
            L.append("   fiabilité par tranche de probabilité annoncée : " + " | ".join(f"{t['tranche']} : {t['n']} lignes, annoncé {_pct(t['p_modele'])}, réel {_pct(t['taux'])}" for t in d["tranches"]))
    if rapport["choix_par_rang"]:
        L.append("")
        L.append("── choix publiés par rang ──")
        for r, s in rapport["choix_par_rang"].items():
            L.append(f"   {r} : {s['n']} choix, {s['gagnes']} gagnés ({_pct(s['taux'])}) pour {_pct(s['p_modele'])} annoncé, ROI {_pct(s['roi'])}")
    if rapport["choix_par_famille"]:
        L.append("── choix publiés par famille de marché ──")
        for f, d in rapport["choix_par_famille"].items():
            s = d["stats"]; L.append(f"   {f:24s} {s['n']:3d} choix, {s['gagnes']:3d} gagnés ({_pct(s['taux'])}) pour {_pct(s['p_modele'])} annoncé")
    if rapport["detail_choix"]:
        L.append("")
        L.append("── détail des choix publiés ──")
        for c in rapport["detail_choix"]:
            L.append(f"   {c['resultat']:6s} {c['match']} {c['score']} | {c['rang']} {c['marche']} cote {c['cote']:.2f} annoncé {_pct(c['probabilite'])}")
    if rapport["erreurs_reglement"]:
        L.append("")
        L.append(f"⚠ {len(rapport['erreurs_reglement'])} ligne(s) non réglable(s), exclue(s) : " + " ; ".join(rapport["erreurs_reglement"][:5]))
    return "\n".join(L)


def integrite(chemin: str) -> Optional[bool]:
    somme = chemin + ".sha256"
    if not os.path.exists(somme):
        return None
    attendu = open(somme).read().strip()
    return hashlib.sha256(open(chemin, "rb").read()).hexdigest() == attendu


def main(argv: List[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 1 or (len(args) < 2 and "--liste" not in argv):
        print(__doc__)
        return 2
    snapshot = json.load(open(args[0], encoding="utf-8"))
    if "--liste" in argv:
        for m in sorted(snapshot["matchs"], key=lambda x: (x["date"], x["heure"], x["domicile"])):
            print(f"{m['domicile']} - {m['exterieur']}")
        return 0
    lus, refusees = lit_resultats(open(args[1], encoding="utf-8").read())
    attribues, rejetees, avertissements = associe(lus, snapshot["matchs"])
    entete = {"moteur": f"{snapshot['moteur']['nom']} v{snapshot['moteur']['version']}", "origine": snapshot["origine"], "n_snapshot": len(snapshot["matchs"]),
              "n_avec_resultat": len(attribues), "integrite": integrite(args[0])}
    rapport = evalue(snapshot, attribues)
    rapport.update({"entete": entete, "lignes_non_lues": refusees, "lignes_rejetees": rejetees, "avertissements": avertissements})
    print(rapport_texte(entete, rapport))
    if refusees or rejetees or avertissements:
        print("\n── À VÉRIFIER ──")
        for l in refusees:
            print(f"   ligne non comprise : {l}")
        for r in rejetees:
            print(f"   REJETÉE : {r['ligne']} -> {r['raison']}" + (f" (meilleur candidat : {r['meilleur_candidat']})" if r.get("meilleur_candidat") else ""))
        for a in avertissements:
            print(f"   avertissement : {a}")
    sans = [m for m in snapshot["matchs"] if m["id"] not in attribues]
    print(f"\n{len(sans)} match(s) du snapshot sans résultat (ignorés).")
    if "--json" in argv:
        chemin = argv[argv.index("--json") + 1]
        json.dump(rapport, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
