# -*- coding: utf-8 -*-
"""Contrôle des données de saison (AJOUT 24/09/2026) — LECTURE SEULE.

Problème constaté le 24/09/2026 : `cache_equipes_saison.json` contient parfois les matchs d'une AUTRE compétition que
celle demandée. Exemple : The New Saints, « Pays de Galles : Cymru Premier » -> 1 match, 1-1 à l'extérieur, qui est en
réalité le match AMICAL Glentoran 1-1 The New Saints (24/06), premier tableau de la page matchendirect de l'équipe.
Cause : `scraper_details._extrait_historique_competition` prend le premier tableau de matchs qui suit un texte
« ressemblant » au nom de la compétition, sans vérifier que ce tableau est bien celui de la compétition.

Principe du contrôle : le pipeline connaît des scores réels par une AUTRE voie (les pages de match : échantillon figé
+ historique_pronostics.json). Pour chaque équipe du cache, chaque match connu par cette autre voie, joué dans la même
compétition et AVANT la date d'enregistrement du cache, doit se retrouver dans la saison enregistrée (même lieu,
mêmes buts marqués / encaissés). Sinon, la saison enregistrée est fausse.

Statuts par équipe :
  COHERENTE        : tous les matchs connus sont présents ;
  INCOHERENTE      : au moins un match connu manque (la saison enregistrée contredit un résultat réel) ;
  NON_VERIFIABLE   : aucun match connu par l'autre voie (équipe non retrouvée, ou aucun match antérieur) ;
  SANS_DONNEES     : rien d'enregistré pour l'équipe (le moteur la refuse déjà) : pas une donnée fausse.

Ce script n'écrit que controle_saisons.json. Il ne modifie ni le cache, ni le moteur.
Bibliothèque standard uniquement. Usage : python controle_saisons.py
"""
import datetime
import json
import os
import re
import unicodedata
from collections import Counter

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER_CACHE = os.path.join(RACINE, "cache_equipes_saison.json")
FICHIER_ECHANTILLON = os.path.join(RACINE, "data", "echantillon_betpawa_501.json")
FICHIER_HISTORIQUE = os.path.join(RACINE, "historique_pronostics.json")
FICHIER_SORTIE = os.path.join(RACINE, "controle_saisons.json")
VERSION = "1.0.0"


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def normalise(texte):
    """minuscules, sans accents, tirets et ponctuation remplacés par des espaces."""
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def partie_competition(nom):
    """« Pays de Galles : Cymru Premier » -> « cymru premier »."""
    return normalise(str(nom or "").split(":", 1)[-1])


def slug_equipe(url):
    """URL matchendirect de l'équipe -> nom lisible : .../the-new-saints_85l2...html -> « the new saints »."""
    fin = str(url or "").rsplit("/", 1)[-1]
    return normalise(fin.split("_")[0].replace(".html", ""))


def _score(s):
    r = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", str(s or ""))
    return (int(r[1]), int(r[2])) if r else None


def resultats_connus(fichier_echantillon=FICHIER_ECHANTILLON, fichier_historique=FICHIER_HISTORIQUE):
    """Matchs terminés connus par les pages de match. Renvoie {nom_normalisé: [match vu du côté de l'équipe]}."""
    matchs = {}
    for m in (_lire(fichier_echantillon, {}) or {}).get("matchs", []):
        if _score(m.get("score")):
            matchs[m["match_id"]] = m
    for jour in _lire(fichier_historique, []) or []:
        for m in jour.get("matchs", []) or []:
            if m.get("match_id") and m["match_id"] not in matchs and _score(m.get("score")):
                matchs[m["match_id"]] = m
    connus = {}
    for m in matchs.values():
        h, a = _score(m["score"])
        comp = partie_competition(m.get("competition"))
        date = str(m.get("date") or "")[:10]
        connus.setdefault(normalise(m.get("domicile")), []).append(
            {"domicile": True, "marques": h, "encaisses": a, "date": date, "adversaire": m.get("exterieur"), "competition": comp})
        connus.setdefault(normalise(m.get("exterieur")), []).append(
            {"domicile": False, "marques": a, "encaisses": h, "date": date, "adversaire": m.get("domicile"), "competition": comp})
    return connus


def controle_equipe(cle_cache, entree, connus):
    """Contrôle d'une entrée du cache. Renvoie un dict (statut, détails)."""
    url, _, competition = cle_cache.partition("||")
    res = (entree or {}).get("resultat") or {}
    horodatage = str((entree or {}).get("horodatage") or "")[:10]
    enregistres = Counter()
    for m in res.get("matchs_domicile_bruts") or []:
        enregistres[(True, m.get("buts_marques"), m.get("buts_encaisses"))] += 1
    for m in res.get("matchs_exterieur_bruts") or []:
        enregistres[(False, m.get("buts_marques"), m.get("buts_encaisses"))] += 1
    comp = partie_competition(competition)
    equipe = slug_equipe(url)
    candidats = [k for k in connus.get(equipe, []) if k["date"] and horodatage and k["date"] < horodatage and k["competition"] == comp]
    ligne = {"equipe": equipe, "competition": competition, "url": url, "enregistre_le": horodatage,
             "matchs_enregistres": sum(enregistres.values()), "matchs_connus": len(candidats), "manquants": []}
    if not candidats:
        ligne["statut"] = "NON_VERIFIABLE"
        return ligne
    if not enregistres:
        # aucune donnée enregistrée : le moteur refuse déjà l'équipe (NO DATA -> NO GO), ce n'est pas une donnée fausse
        ligne["statut"] = "SANS_DONNEES"
        return ligne
    reste = Counter(enregistres)
    for k in sorted(candidats, key=lambda x: x["date"]):
        cle = (k["domicile"], k["marques"], k["encaisses"])
        if reste[cle] > 0:
            reste[cle] -= 1
        else:
            ligne["manquants"].append({"date": k["date"], "adversaire": k["adversaire"],
                                       "lieu": "domicile" if k["domicile"] else "extérieur",
                                       "score_equipe": f"{k['marques']}-{k['encaisses']}"})
    ligne["statut"] = "INCOHERENTE" if ligne["manquants"] else "COHERENTE"
    return ligne


def controle(fichier_cache=FICHIER_CACHE, connus=None):
    cache = _lire(fichier_cache, {}) or {}
    connus = resultats_connus() if connus is None else connus
    lignes = [controle_equipe(k, v, connus) for k, v in cache.items()]
    compte = Counter(l["statut"] for l in lignes)
    verifiables = compte["COHERENTE"] + compte["INCOHERENTE"]
    incoherentes = sorted([l for l in lignes if l["statut"] == "INCOHERENTE"],
                          key=lambda l: (-len(l["manquants"]), l["competition"], l["equipe"]))
    return {
        "version": VERSION,
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "resume": {"equipes_en_cache": len(lignes), "verifiables": verifiables, "coherentes": compte["COHERENTE"],
                   "incoherentes": compte["INCOHERENTE"], "non_verifiables": compte["NON_VERIFIABLE"],
                   "sans_donnees": compte["SANS_DONNEES"],
                   "taux_incoherence": round(compte["INCOHERENTE"] / verifiables, 4) if verifiables else None},
        "methode": "Chaque match connu par les pages de match (même compétition, joué avant l'enregistrement) doit figurer "
                   "dans la saison enregistrée de l'équipe (même lieu, mêmes buts). Sinon : INCOHERENTE.",
        "incoherentes": incoherentes,
    }


def main():
    rapport = controle()
    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    r = rapport["resume"]
    taux = f"{r['taux_incoherence']:.0%}" if r["taux_incoherence"] is not None else "n/a"
    print(f"[controle_saisons] {r['equipes_en_cache']} équipes en cache, {r['verifiables']} vérifiables : "
          f"{r['coherentes']} cohérentes, {r['incoherentes']} INCOHÉRENTES ({taux}).")


if __name__ == "__main__":
    main()
