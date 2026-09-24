# -*- coding: utf-8 -*-
"""A3 + A4 bis (24/09/2026) — correspondance des noms d'équipes et assemblage Football-Data / Matchendirect.

Collecte pure : aucun calcul de marché. Deux sorties, entièrement RECONSTRUITES à chaque run (jamais cumulées) :

1. data/correspondances/equipes.json — A3
   Relie chaque équipe Football-Data (division + nom) à son nom Matchendirect. Matchendirect sert de pivot : les noms
   BetPawa sont déjà reliés aux noms Matchendirect par le pipeline existant (resolution_betpawa_precalcul.py).
   Méthode (preuves, jamais une simple ressemblance) : un match Football-Data et un match Matchendirect sont le même
   match s'ils ont le même score, une date à ± 1 jour, et au moins une des deux équipes au nom clairement semblable.
   Chaque tel match est une preuve pour les DEUX équipes. Une correspondance est acceptée si elle a au moins 2 preuves
   et au moins deux fois plus que toute autre candidate, ou 1 preuve avec des noms presque identiques. Deux équipes qui
   revendiquent le même nom sont rejetées toutes les deux (« ambiguës »). Les non résolues sont listées.

2. data/assemblage/equipes.json — A4 bis (règle d'assemblage de CLAUDE.md)
   Pour chaque équipe de cache_equipes_saison.json (les équipes des matchs à venir) :
   - championnat couvert : matchs Football-Data en base (source « football-data ») ; un match Matchendirect n'est
     ajouté que si l'équipe n'a AUCUN match Football-Data à ± 1 jour (une équipe ne joue jamais deux fois en 48 h) ;
     il porte alors « provisoire : true » et disparaît au run suivant dès que Football-Data le publie ;
   - championnat non couvert : matchs Matchendirect seuls (« provisoire : false », source unique) ;
   - un match Matchendirect sans date lisible n'est jamais ajouté à une équipe couverte (dates non vérifiables).

Bibliothèque standard uniquement. Usage : python assemblage_equipes.py
"""
import datetime
import difflib
import glob
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
FD_NORMALISE = os.path.join(RACINE, "data", "football_data", "normalized")
FICHIER_CACHE = os.path.join(RACINE, "cache_equipes_saison.json")
FICHIER_ECHANTILLON = os.path.join(RACINE, "data", "echantillon_betpawa_501.json")
FICHIER_HISTORIQUE = os.path.join(RACINE, "historique_pronostics.json")
SORTIE_CORRESPONDANCES = os.path.join(RACINE, "data", "correspondances", "equipes.json")
SORTIE_ASSEMBLAGE = os.path.join(RACINE, "data", "assemblage", "equipes.json")
VERSION = "1.0.0"

TOLERANCE_JOURS = 1
SIMILARITE_PREUVE = 0.6       # au moins une équipe du match doit avoir un nom clairement semblable
SIMILARITE_UNE_PREUVE = 0.85  # une seule preuve n'est acceptée qu'avec des noms presque identiques
MOTS_VIDES = {"fc", "cf", "afc", "sc", "ac", "as", "cd", "ud", "sd", "club", "de", "del", "the", "fk", "sk", "if", "bk",
              "calcio", "football", "futbol", "united", "utd", "city", "town"}


# ------------------------------------------------------------------------------------------------------------------
# Outils
# ------------------------------------------------------------------------------------------------------------------
def _lire(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def normalise(nom):
    t = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _mots(nom):
    return [m for m in normalise(nom).split() if m not in MOTS_VIDES] or normalise(nom).split()


def similarite(a, b):
    """0..1 : noms identiques, l'un contenu dans l'autre, mots communs, ou ressemblance de caractères."""
    na, nb = " ".join(_mots(a)), " ".join(_mots(b))
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ma, mb = set(na.split()), set(nb.split())
    if ma <= mb or mb <= ma:
        return 0.9
    commun = len(ma & mb) / len(ma | mb)
    return max(commun, difflib.SequenceMatcher(None, na, nb).ratio())


def _date(iso):
    try:
        return datetime.date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return None


def _score(s):
    r = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", str(s or ""))
    return (int(r[1]), int(r[2])) if r else None


def _competition(nom):
    return " ".join(str(nom or "").split())


# ------------------------------------------------------------------------------------------------------------------
# Chargement
# ------------------------------------------------------------------------------------------------------------------
def charge_football_data(dossier=FD_NORMALISE):
    """Matchs Football-Data normalisés (toutes saisons présentes dans normalized/)."""
    out = []
    for f in sorted(glob.glob(os.path.join(dossier, "*", "*.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for ligne in fh:
                if not ligne.strip():
                    continue
                m = json.loads(ligne)
                if m.get("home_team") and m.get("away_team") and _date(m.get("date")) \
                        and m.get("full_time_home_goals") is not None and m.get("full_time_away_goals") is not None:
                    out.append(m)
    return out


def charge_matchendirect_resultats(fichier_echantillon=FICHIER_ECHANTILLON, fichier_historique=FICHIER_HISTORIQUE):
    """Matchs terminés Matchendirect (pages de match) : date, équipes, compétition, score."""
    matchs = {}
    for m in (_lire(fichier_echantillon, {}) or {}).get("matchs", []):
        if _score(m.get("score")) and m.get("match_id"):
            matchs[m["match_id"]] = m
    for jour in _lire(fichier_historique, []) or []:
        for m in jour.get("matchs", []) or []:
            if m.get("match_id") and m["match_id"] not in matchs and _score(m.get("score")):
                matchs[m["match_id"]] = m
    out = []
    for m in matchs.values():
        d = _date(m.get("date"))
        if d and m.get("domicile") and m.get("exterieur"):
            h, a = _score(m["score"])
            out.append({"date": d, "domicile": m["domicile"], "exterieur": m["exterieur"],
                        "competition": _competition(m.get("competition")), "buts": (h, a)})
    return out


# ------------------------------------------------------------------------------------------------------------------
# A3 — correspondance des noms
# ------------------------------------------------------------------------------------------------------------------
def construit_correspondances(fd, med):
    par_date = defaultdict(list)
    for n in med:
        par_date[n["date"]].append(n)
    votes = defaultdict(Counter)            # (division, nom_fd) -> Counter(nom_med)
    sim_max = defaultdict(float)            # ((division, nom_fd), nom_med) -> meilleure similarité vue
    competitions = defaultdict(Counter)     # division -> Counter(competition matchendirect)
    for m in fd:
        d = _date(m["date"])
        score = (m["full_time_home_goals"], m["full_time_away_goals"])
        div = m.get("competition_code")
        for decalage in range(-TOLERANCE_JOURS, TOLERANCE_JOURS + 1):
            for n in par_date.get(d + datetime.timedelta(days=decalage), []):
                if n["buts"] != score:
                    continue
                sh, sa = similarite(m["home_team"], n["domicile"]), similarite(m["away_team"], n["exterieur"])
                if max(sh, sa) < SIMILARITE_PREUVE:
                    continue
                for nom_fd, nom_med, sim in ((m["home_team"], n["domicile"], sh), (m["away_team"], n["exterieur"], sa)):
                    votes[(div, nom_fd)][nom_med] += 1
                    cle = ((div, nom_fd), nom_med)
                    sim_max[cle] = max(sim_max[cle], sim)
                competitions[div][n["competition"]] += 1

    retenus, ambigus, non_resolus = {}, [], []
    for cle, c in votes.items():
        (meilleur, n1), *reste = c.most_common()
        n2 = reste[0][1] if reste else 0
        if (n1 >= 2 and n1 >= 2 * n2) or (n1 == 1 and n2 == 0 and sim_max[(cle, meilleur)] >= SIMILARITE_UNE_PREUVE):
            retenus[cle] = (meilleur, n1)
        else:
            non_resolus.append({"division": cle[0], "football_data": cle[1], "candidats": dict(c.most_common(3))})
    # unicité : un nom Matchendirect ne peut appartenir qu'à une équipe Football-Data par division
    revendications = defaultdict(list)
    for (div, nom_fd), (nom_med, n) in retenus.items():
        revendications[(div, normalise(nom_med))].append(nom_fd)
    correspondances = defaultdict(dict)
    for (div, nom_fd), (nom_med, n) in sorted(retenus.items()):
        if len(revendications[(div, normalise(nom_med))]) > 1:
            ambigus.append({"division": div, "football_data": nom_fd, "matchendirect": nom_med,
                            "concurrents": revendications[(div, normalise(nom_med))]})
            continue
        correspondances[div][nom_fd] = {"matchendirect": nom_med, "preuves": n,
                                        "similarite_nom": round(sim_max[((div, nom_fd), nom_med)], 3)}
    divisions = {}
    for div, equipes in correspondances.items():
        comp = competitions[div].most_common(1)[0][0] if competitions[div] else None
        divisions[div] = {"competition_matchendirect": comp, "equipes": equipes}
    return divisions, sorted(ambigus, key=lambda x: (x["division"], x["football_data"])), \
        sorted(non_resolus, key=lambda x: (x["division"], x["football_data"]))


# ------------------------------------------------------------------------------------------------------------------
# A4 bis — assemblage par équipe (reconstruit à chaque run)
# ------------------------------------------------------------------------------------------------------------------
def _slug(url):
    return normalise(str(url or "").rsplit("/", 1)[-1].split("_")[0])


def _equipe_du_cache(cle, divisions):
    """(division, nom_fd, nom_med) si l'équipe du cache appartient à un championnat couvert et relié, sinon None."""
    url, _, competition = cle.partition("||")
    comp = normalise(competition.split(":", 1)[-1])
    slug = _slug(url)
    for div, info in divisions.items():
        cm = normalise(str(info.get("competition_matchendirect") or "").split(":", 1)[-1])
        if not cm or cm != comp:
            continue
        candidats = [(similarite(slug, v["matchendirect"]), nom_fd, v["matchendirect"]) for nom_fd, v in info["equipes"].items()]
        candidats = [c for c in candidats if c[0] >= SIMILARITE_UNE_PREUVE]
        if len(candidats) == 1 or (candidats and sorted(candidats)[-1][0] > sorted(candidats)[-2][0]):
            _, nom_fd, nom_med = max(candidats)
            return div, nom_fd, nom_med
    return None


def _match_fd_vu_equipe(m, nom_fd):
    dom = m["home_team"] == nom_fd
    g = lambda cle_dom, cle_ext: m.get(cle_dom if dom else cle_ext)
    return {"date": m["date"], "domicile": dom, "adversaire": m["away_team"] if dom else m["home_team"],
            "buts_marques": g("full_time_home_goals", "full_time_away_goals"),
            "buts_encaisses": g("full_time_away_goals", "full_time_home_goals"),
            "buts_marques_mi_temps": g("half_time_home_goals", "half_time_away_goals"),
            "buts_encaisses_mi_temps": g("half_time_away_goals", "half_time_home_goals"),
            "tirs": g("home_shots", "away_shots"), "tirs_concedes": g("away_shots", "home_shots"),
            "tirs_cadres": g("home_shots_on_target", "away_shots_on_target"),
            "tirs_cadres_concedes": g("away_shots_on_target", "home_shots_on_target"),
            "corners": g("home_corners", "away_corners"), "corners_concedes": g("away_corners", "home_corners"),
            "cartons_jaunes": g("home_yellow_cards", "away_yellow_cards"), "cartons_rouges": g("home_red_cards", "away_red_cards"),
            "xg": g("home_xg", "away_xg"), "xg_concede": g("away_xg", "home_xg"),
            "source": "football-data", "provisoire": False, "saison": m.get("season")}


def _matchs_cache(entree):
    res = (entree or {}).get("resultat") or {}
    return list(res.get("matchs_domicile_bruts") or []) + list(res.get("matchs_exterieur_bruts") or [])


def assemble(cache, fd, divisions, saison_fd=None):
    equipes, bilan = [], Counter()
    fd_par_equipe = defaultdict(list)
    for m in fd:
        if saison_fd and m.get("season") != saison_fd:
            continue
        fd_par_equipe[(m.get("competition_code"), m["home_team"])].append(m)
        fd_par_equipe[(m.get("competition_code"), m["away_team"])].append(m)
    for cle, entree in sorted(cache.items()):
        url, _, competition = cle.partition("||")
        med = _matchs_cache(entree)
        lien = _equipe_du_cache(cle, divisions)
        if lien:
            div, nom_fd, nom_med = lien
            base = [_match_fd_vu_equipe(m, nom_fd) for m in fd_par_equipe.get((div, nom_fd), [])]
            dates_fd = [_date(x["date"]) for x in base]
            ajout, sans_date = [], 0
            for x in med:
                d = _date(x.get("date"))
                if d is None:
                    sans_date += 1
                    continue
                if any(abs((d - df).days) <= TOLERANCE_JOURS for df in dates_fd if df):
                    bilan["doublons_evites"] += 1
                    continue
                ajout.append({"date": d.isoformat(), "domicile": x.get("domicile"), "adversaire": x.get("adversaire"),
                              "buts_marques": x.get("buts_marques"), "buts_encaisses": x.get("buts_encaisses"),
                              "url_match": x.get("url_match"), "source": "matchendirect", "provisoire": True})
            matchs = sorted(base + ajout, key=lambda x: x["date"])
            bilan["equipes_couvertes"] += 1
            bilan["matchs_football_data"] += len(base)
            bilan["matchs_provisoires"] += len(ajout)
            bilan["matchs_sans_date_ignores"] += sans_date
            equipes.append({"cle_cache": cle, "competition": competition, "couverte_par_football_data": True,
                            "division_football_data": div, "nom_football_data": nom_fd, "nom_matchendirect": nom_med,
                            "matchs_sans_date_ignores": sans_date, "matchs": matchs})
        else:
            couvert = any(normalise(str(i.get("competition_matchendirect") or "").split(":", 1)[-1])
                          == normalise(competition.split(":", 1)[-1]) for i in divisions.values())
            if couvert:
                bilan["equipes_couvertes_non_reliees"] += 1
            matchs = sorted(({"date": x.get("date"), "domicile": x.get("domicile"), "adversaire": x.get("adversaire"),
                              "buts_marques": x.get("buts_marques"), "buts_encaisses": x.get("buts_encaisses"),
                              "url_match": x.get("url_match"), "source": "matchendirect", "provisoire": False}
                             for x in med), key=lambda x: str(x["date"]))
            bilan["equipes_matchendirect_seul"] += 1
            bilan["matchs_matchendirect_seul"] += len(matchs)
            equipes.append({"cle_cache": cle, "competition": competition, "couverte_par_football_data": False,
                            "raison": ("championnat couvert par Football-Data mais équipe pas encore reliée (A3)"
                                       if couvert else "championnat non couvert par Football-Data"),
                            "matchs": matchs})
    return equipes, dict(bilan)


# ------------------------------------------------------------------------------------------------------------------
def main():
    fd = charge_football_data()
    med = charge_matchendirect_resultats()
    divisions, ambigus, non_resolus = construit_correspondances(fd, med)
    maintenant = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    nb = sum(len(v["equipes"]) for v in divisions.values())
    corr = {"version": VERSION, "genere_le": maintenant, "pivot": "matchendirect",
            "methode": "même score, date à ± 1 jour, au moins un nom clairement semblable ; ≥ 2 preuves et 2× la "
                       "suivante, ou 1 preuve avec noms presque identiques ; noms revendiqués deux fois rejetés",
            "bilan": {"equipes_reliees": nb, "divisions_reliees": len(divisions), "ambigues": len(ambigus),
                      "non_resolues": len(non_resolus)},
            "divisions": divisions, "ambigues": ambigus, "non_resolues": non_resolus}
    os.makedirs(os.path.dirname(SORTIE_CORRESPONDANCES), exist_ok=True)
    with open(SORTIE_CORRESPONDANCES, "w", encoding="utf-8") as f:
        json.dump(corr, f, ensure_ascii=False, indent=1)
    saisons = sorted({m.get("season") for m in fd if m.get("season")})
    equipes, bilan = assemble(_lire(FICHIER_CACHE, {}) or {}, fd, divisions, saison_fd=saisons[-1] if saisons else None)
    doc = {"version": VERSION, "version_contrat": 1, "genere_le": maintenant, "saison_football_data": saisons[-1] if saisons else None,
           "regle": "Football-Data en base ; jours manquants complétés par Matchendirect (provisoire) ; même équipe "
                    "à ± 1 jour = même match ; reconstruit à chaque run, jamais cumulé",
           "bilan": bilan, "equipes": equipes}
    os.makedirs(os.path.dirname(SORTIE_ASSEMBLAGE), exist_ok=True)
    with open(SORTIE_ASSEMBLAGE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"[A3] {nb} équipes reliées dans {len(divisions)} divisions ; {len(ambigus)} ambiguës, {len(non_resolus)} non résolues.")
    print(f"[A4 bis] {bilan}")


if __name__ == "__main__":
    main()
