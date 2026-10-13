# -*- coding: utf-8 -*-
"""Source complémentaire Livescore pour le moteur Europe (13/10/2026). Isolée : aucun scraper existant n'est modifié.

Pourquoi : BeSoccer et Sofascore répondent 403 depuis GitHub Actions (diagnostic du 13/10). Livescore expose un flux
public « tous les matchs d'un jour » (200 depuis Actions). On le lit jour par jour, on garde seulement les matchs
terminés (FT, score réel), et on s'en sert pour COMPLÉTER l'historique des clubs que Matchendirect ne fournit pas.

Règles : NO DATA -> NO GO. Jamais de score deviné ; prolongation/tirs au but écartés (Eps != FT) ; un club n'est rapproché
d'une équipe Livescore que par nom normalisé identique ou alias explicite (data/europe/alias_livescore.json). Un club non
rapproché est listé avec des suggestions, jamais deviné. Les jours passés sont figés dans data/europe/livescore/.

Usage : python source_livescore.py [--jours 75]
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import json
import os
import re
import sys
import time
import unicodedata

URL = "https://prod-public-api.livescore.com/v1/api/app/date/soccer/{jour}/1?MCC=INT&countryCode=CM"
ENTETES = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0 Safari/537.36", "Accept-Language": "en;q=0.9"}
DOSSIER = "data/europe/livescore"
FICHIER_ALIAS = "data/europe/alias_livescore.json"
COMPETITIONS_EUROPE = {"champions league": "ldc", "europa league": "el", "uefa europa league": "el",
                       "conference league": "ecl", "uefa conference league": "ecl"}
MARQUEURS_REFUSES = ("qualification", "qualifying", "preliminary", "youth", "women", "u17", "u18", "u19", "u20", "u21", "u23",
                     "friendl", "cup", "copa", "coupe", "pokal", "supercup", "super cup", "playoff play", "trophy", "reserve")
ZONES_NON_NATIONALES = {"asia", "africa", "europe", "world", "oceania", "north america", "south america", "central america",
                        "international", "concacaf", "caf", "afc", "conmebol", "uefa"}
MOTS_VIDES = {"fc", "cf", "sc", "ac", "as", "afc", "fk", "sk", "bk", "if", "club", "the", "de", "cd", "ud", "sv", "vfb", "vfl", "1"}


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn")


def norm(nom):
    mots = re.findall(r"[a-z0-9]+", _sans_accents(nom).lower())
    return " ".join(m for m in mots if m not in MOTS_VIDES)


def competition_europe(pays, stage, comp=None):
    """'ldc' | 'el' | 'ecl' pour un match de phase de ligue / élimination directe de clubs, sinon None."""
    nom = _sans_accents(pays or "").lower().strip()
    code = COMPETITIONS_EUROPE.get(nom)
    if code is None:
        return None
    texte = _sans_accents(f"{stage or ''}").lower()
    if any(m in texte for m in MARQUEURS_REFUSES):
        return None
    return code


def est_championnat(pays, stage):
    """Rubrique nationale « de championnat » : ni coupe, ni amical, ni jeunes, ni femmes, ni qualification."""
    p, s = _sans_accents(pays or "").lower(), _sans_accents(stage or "").lower()
    if not p or competition_europe(pays, stage) or p in COMPETITIONS_EUROPE or p in ZONES_NON_NATIONALES or p.startswith("uefa"):
        return False
    return not any(m in p + " " + s for m in MARQUEURS_REFUSES)


def compacte(payload):
    """Matchs terminés (FT, score entier) d'un flux journalier -> liste de dicts compacts."""
    out = []
    for st in (payload or {}).get("Stages", []):
        for ev in st.get("Events", []):
            if ev.get("Eps") != "FT":
                continue
            try:
                gd, ge = int(ev["Tr1"]), int(ev["Tr2"])
                dom, ext = ev["T1"][0]["Nm"], ev["T2"][0]["Nm"]
                esd = str(ev["Esd"])
                date = f"{esd[0:4]}-{esd[4:6]}-{esd[6:8]}"
            except (KeyError, ValueError, IndexError, TypeError):
                continue                      # événement incomplet : écarté, jamais reconstitué
            out.append({"date": date, "pays": st.get("Cnm"), "stage": st.get("Snm"), "dom": dom, "ext": ext,
                        "buts_dom": gd, "buts_ext": ge})
    return out


def telecharge_jour(jour, get=None):
    import requests
    get = get or (lambda u: requests.get(u, headers=ENTETES, timeout=30))
    derniere = None
    for essai in range(3):
        try:
            r = get(URL.format(jour=jour.strftime("%Y%m%d")))
            if r.status_code == 200:
                return r.json()
            derniere = f"HTTP {r.status_code}"
        except Exception as e:           # noqa: BLE001
            derniere = f"{type(e).__name__}: {e}"
        time.sleep(2 * (essai + 1))
    raise RuntimeError(f"livescore {jour}: {derniere}")


def met_a_jour(jours, aujourdhui=None, dossier=DOSSIER, get=None, pause=0.7):
    """Télécharge les jours passés absents du dossier (un fichier par jour, figé). Aujourd'hui n'est jamais figé."""
    aujourdhui = aujourdhui or datetime.date.today()
    os.makedirs(dossier, exist_ok=True)
    bilan = {"telecharges": 0, "deja_presents": 0, "echecs": []}
    for i in range(jours, 0, -1):
        j = aujourdhui - datetime.timedelta(days=i)
        chemin = os.path.join(dossier, j.isoformat() + ".json")
        if os.path.exists(chemin):
            bilan["deja_presents"] += 1
            continue
        try:
            matchs = compacte(telecharge_jour(j, get))
        except RuntimeError as e:
            bilan["echecs"].append(str(e)[:120])
            continue
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(matchs, f, ensure_ascii=False, separators=(",", ":"))
        bilan["telecharges"] += 1
        time.sleep(pause)
    return bilan


def charge_index(dossier=DOSSIER):
    """{nom normalisé: {"noms": {noms Livescore}, "lignes": [lignes du point de vue du club]}}."""
    idx = {}
    if not os.path.isdir(dossier):
        return idx
    for nom_f in sorted(os.listdir(dossier)):
        if not nom_f.endswith(".json"):
            continue
        with open(os.path.join(dossier, nom_f), encoding="utf-8") as f:
            for m in json.load(f):
                for cote, equipe, adv in (("dom", m["dom"], m["ext"]), ("ext", m["ext"], m["dom"])):
                    e = idx.setdefault(norm(equipe), {"noms": set(), "lignes": []})
                    e["noms"].add(equipe)
                    d = cote == "dom"
                    e["lignes"].append({"date": m["date"], "domicile": d, "buts_marques": m["buts_dom"] if d else m["buts_ext"],
                                        "buts_encaisses": m["buts_ext"] if d else m["buts_dom"], "adversaire": adv,
                                        "url_match": None, "source": "livescore", "pays": m["pays"], "stage": m["stage"]})
    return idx


def lit_alias(chemin=FICHIER_ALIAS):
    if not chemin or not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        brut = json.load(f)
    return {str(k).strip(): ([v] if isinstance(v, str) else list(v)) for k, v in brut.items() if not str(k).startswith("_")}


def apparie(nom, index, alias=None):
    """Clé de l'index pour un nom d'équipe Matchendirect : alias explicite d'abord, sinon nom normalisé identique."""
    for a in (alias or {}).get(str(nom or "").strip(), []):
        if norm(a) in index:
            return norm(a)
    cle = norm(nom)
    return cle if cle in index else None


def suggestions(nom, index, n=3):
    return difflib.get_close_matches(norm(nom), list(index), n=n, cutoff=0.6)


def _proche(date, dates):
    d = datetime.date.fromisoformat(date)
    return any(abs((d - datetime.date.fromisoformat(x)).days) <= 1 for x in dates)


def historique_club(cle, index):
    """{"europe": [...], "championnat": [...]} d'un club apparié. Championnat = rubrique nationale qui a le plus de matchs
    (égalité en tête -> aucune donnée)."""
    europe, par_rubrique = [], {}
    for l in index[cle]["lignes"]:
        code = competition_europe(l["pays"], l["stage"])
        if code:
            europe.append({**l, "competition": code})
        elif est_championnat(l["pays"], l["stage"]):
            par_rubrique.setdefault((l["pays"], l["stage"]), []).append({**l, "competition": "championnat"})
    tri = sorted(par_rubrique.items(), key=lambda kv: len(kv[1]), reverse=True)
    champ = [] if not tri or (len(tri) > 1 and len(tri[0][1]) == len(tri[1][1])) else tri[0][1]
    return {"europe": europe, "championnat": champ}


def complete(donnees, nom, index, alias=None):
    """Ajoute à `donnees` ({"europe","championnat","meta"}) les matchs Livescore absents (même club à ±1 jour = même match).
    Renvoie (donnees, info). Ne retire ni ne modifie jamais une ligne Matchendirect."""
    cle = apparie(nom, index, alias)
    if cle is None:
        return donnees, {"statut": "NON_APPARIE", "suggestions": [sorted(index[c]["noms"])[0] for c in suggestions(nom, index)]}
    h = historique_club(cle, index)
    ajouts = {"europe": 0, "championnat": 0}
    for genre in ("europe", "championnat"):
        dates = [m["date"] for m in donnees.get(genre, [])]
        for l in h[genre]:
            if not _proche(l["date"], dates):
                donnees.setdefault(genre, []).append(l)
                dates.append(l["date"])
                ajouts[genre] += 1
        donnees[genre] = sorted(donnees.get(genre, []), key=lambda m: (m["date"], m["adversaire"]))
    return donnees, {"statut": "OK", "equipe_livescore": sorted(index[cle]["noms"])[0], "ajouts": ajouts}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jours", type=int, default=75)
    a = p.parse_args()
    print(json.dumps(met_a_jour(a.jours), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
