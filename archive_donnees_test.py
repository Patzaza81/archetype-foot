#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archive_donnees_test.py -- ARCHIVE DE TEST : tout ce qu'il faut pour rejouer n'importe quel moteur sur un match passé.

Pourquoi ce module existe (27/09/2026). historique_pronostics.json garde le score, les cotes et les choix des anciens
moteurs, mais PAS les statistiques d'équipe connues avant le match. Constat du 27/09 : sur 1 113 matchs archivés avec
score + cotes, seuls 108 pouvaient être reconstruits pour tester un nouveau moteur. Ce module comble ce trou.

Règles (décision de Patrick du 27/09/2026 : « l'archive doit conserver désormais toutes les données nécessaires pour un
test ») :
  1. Un enregistrement par match, rangé dans le fichier de SA date : archive_test/AAAA-MM-JJ.json.gz.
  2. Contenu = ce que le moteur avait réellement sous les yeux : liste COMPLÈTE des matchs de chaque équipe (saison en
     cours, même compétition, domicile ET extérieur, date/adversaire/buts), cotes BetPawa complètes, choix du moteur.
  3. Anti-fuite : seuls les matchs d'équipe joués STRICTEMENT avant la date du match sont gardés. Un match d'équipe daté
     du jour même ou après est retiré et compté (`matchs_retires_apres_date`).
  4. Figé au coup d'envoi : chaque run remplace l'enregistrement tant que le match n'a pas commencé (on garde donc le
     DERNIER état connu avant le coup d'envoi, comme le protocole d'évaluation du 21/09). Après le coup d'envoi, ou dès
     qu'un score est présent, l'enregistrement n'est plus jamais modifié, sauf pour y écrire le score.
  5. Le score vient de historique_pronostics.json (rempli par enregistre_scores_historique.py), par match_id exact.
     Un score existant n'est jamais modifié.
  6. Aucun calcul de moteur ici : on enregistre, on ne prédit rien. Étape autonome du workflow (continue-on-error) :
     un échec ne fait jamais échouer le run, et precalcul.py n'est pas modifié.
  7. Source des données : ce que precalcul.py vient d'écrire -- precalcul.json (matchs, cotes, choix du moteur) et
     cache_equipes_saison.json (saison en cours, même compétition : exactement ce que lit le moteur). Chaque équipe est
     retrouvée par l'ADRESSE EXACTE du match (« domicile-exterieur » = adresse équipe domicile + « - » + adresse équipe
     extérieur, dans la même compétition), jamais par ressemblance de nom. Pas de correspondance exacte = équipe ABSENTE.

Utilisation :
    python archive_donnees_test.py --run --scores   # run nocturne : avant-match des matchs à venir + scores des matchs joués
    python archive_donnees_test.py --bilan          # nombre de matchs archivés, testables, avec score
"""
from __future__ import annotations

import argparse
import datetime
import glob
import gzip
import json
import os
import re
import sys

SCHEMA_VERSION = 1
DOSSIER = "archive_test"
FICHIER_HISTORIQUE = "historique_pronostics.json"
FICHIER_PRECALCUL = "precalcul.json"
FICHIER_CACHE_SAISON = "cache_equipes_saison.json"
DECALAGE_CAMEROUN = datetime.timedelta(hours=1)          # heure_cameroun = UTC+1, sans heure d'été
CLE_BLOC_MOTEUR = "moteur_v2_6_9"
_SCORE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


# ---------------------------------------------------------------------------------------------------------------------
# Règles pures (testées dans tests/test_archive_donnees_test.py)
# ---------------------------------------------------------------------------------------------------------------------

def coup_d_envoi_utc(date_match, heure_cameroun):
    """Coup d'envoi en UTC à partir de la date et de l'heure du Cameroun (« 17:00 »). None si l'une manque ou est
    illisible : on ne devine jamais une heure."""
    if not date_match or not heure_cameroun:
        return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(heure_cameroun))
    if not m:
        return None
    try:
        jour = datetime.date.fromisoformat(str(date_match))
    except ValueError:
        return None
    local = datetime.datetime(jour.year, jour.month, jour.day, int(m.group(1)), int(m.group(2)),
                              tzinfo=datetime.timezone.utc)
    return local - DECALAGE_CAMEROUN


def peut_mettre_a_jour(existant, date_match, coup_envoi, maintenant):
    """True si le run courant a le droit d'écrire l'enregistrement d'avant-match de ce match.
    - aucun enregistrement : oui ;
    - un score est déjà présent : jamais ;
    - coup d'envoi connu : seulement avant le coup d'envoi ;
    - coup d'envoi inconnu : seulement jusqu'au jour du match inclus (date UTC du run <= date du match)."""
    if existant is None:
        return True
    if existant.get("score") is not None:
        return False
    if coup_envoi is not None:
        return maintenant < coup_envoi
    try:
        return maintenant.date() <= datetime.date.fromisoformat(str(date_match))
    except ValueError:
        return False


def _buts_valides(m):
    for k in ("buts_marques", "buts_encaisses"):
        v = m.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            return False
    return True


def matchs_avant(matchs, date_match):
    """Garde les matchs d'équipe joués STRICTEMENT avant date_match, avec une date et des buts valides, triés du plus
    ancien au plus récent. Renvoie (gardés, nb_retirés_après_date, nb_invalides)."""
    gardes, apres, invalides = [], 0, 0
    for m in matchs or []:
        d = m.get("date")
        if not d or not _buts_valides(m):
            invalides += 1
            continue
        if str(d) >= str(date_match):
            apres += 1
            continue
        gardes.append({
            "date": str(d),
            "domicile": bool(m.get("domicile")),
            "adversaire": m.get("adversaire"),
            "buts_marques": m["buts_marques"],
            "buts_encaisses": m["buts_encaisses"],
            "url_match": m.get("url_match"),
        })
    gardes.sort(key=lambda x: x["date"])
    return gardes, apres, invalides


def lit_score(texte):
    """« 2-1 » -> (2, 1). Tout autre format -> None (jamais de score deviné)."""
    if not isinstance(texte, str):
        return None
    m = _SCORE.match(texte)
    return (int(m.group(1)), int(m.group(2))) if m else None


# ---------------------------------------------------------------------------------------------------------------------
# Construction d'un enregistrement
# ---------------------------------------------------------------------------------------------------------------------

def _equipe(nom, competition, stats_equipes, date_match, url_equipe):
    res = stats_equipes.get((nom, competition))
    base = {"nom": nom, "url_equipe": url_equipe, "source": "saison_en_cours_seule"}
    if res is None:
        return dict(base, statut="ABSENTE", matchs=[])
    if "raison_non_traite" in res:
        return dict(base, statut=str(res["raison_non_traite"]), matchs=[])
    tous = list(res.get("matchs_domicile_bruts") or []) + list(res.get("matchs_exterieur_bruts") or [])
    gardes, apres, invalides = matchs_avant(tous, date_match)
    return dict(base, statut="OK", matchs=gardes,
                nb_domicile=sum(1 for m in gardes if m["domicile"]),
                nb_exterieur=sum(1 for m in gardes if not m["domicile"]),
                matchs_retires_apres_date=apres, matchs_invalides=invalides)


def _cotes_observees(s):
    out = {}
    for m in s.get("TOUS_MARCHES_EVALUES") or []:
        c = m.get("cote_observee")
        if m.get("marche") and isinstance(c, (int, float)) and c > 1:
            out[m["marche"]] = c
    return out


def _choix_moteur(s):
    bloc = s.get(CLE_BLOC_MOTEUR) or {}
    sel = bloc.get("selection") or {}
    choix = {}
    if isinstance(sel, dict):
        for role, c in sel.items():
            if isinstance(c, dict):
                choix[role] = {k: c.get(k) for k in ("marche", "marche_moteur", "probabilite", "p_juste", "cote",
                                                     "edge", "edv") if k in c}
    return {"moteur": bloc.get("moteur") or CLE_BLOC_MOTEUR, "version": bloc.get("version_moteur"),
            "statut": bloc.get("statut"), "raison": bloc.get("raison"),
            "lambda_dom": bloc.get("lambda_dom"), "lambda_ext": bloc.get("lambda_ext"), "choix": choix}


def construit_enregistrement(s, stats_equipes, details, maintenant, commit=None):
    date_match = s.get("date")
    d = (details or {}).get(s.get("url_match")) or {}
    dom = _equipe(s.get("domicile"), s.get("competition"), stats_equipes, date_match, d.get("url_equipe_domicile"))
    ext = _equipe(s.get("exterieur"), s.get("competition"), stats_equipes, date_match, d.get("url_equipe_exterieur"))
    cotes_betpawa = s.get("cotes_manuelles") or None
    cotes_obs = _cotes_observees(s)
    coup = coup_d_envoi_utc(date_match, s.get("heure_cameroun"))
    return {
        "schema_version": SCHEMA_VERSION,
        "match_id": s.get("match_id"),
        "date": date_match,
        "heure_cameroun": s.get("heure_cameroun"),
        "coup_d_envoi_utc": coup.strftime("%Y-%m-%dT%H:%M:%SZ") if coup else None,
        "competition": " ".join(str(s.get("competition") or "").split()),
        "competition_brute": s.get("competition"),
        "domicile": s.get("domicile"),
        "exterieur": s.get("exterieur"),
        "url_match": s.get("url_match"),
        "betpawa_url": s.get("betpawa_url"),
        "run": {"pris_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": commit},
        "source_cotes": s.get("source_cotes"),
        "cotes_betpawa": cotes_betpawa,
        "cotes_observees": cotes_obs,
        "equipe_dom": dom,
        "equipe_ext": ext,
        "moteur_en_production": _choix_moteur(s),
        "testable": bool(dom["statut"] == "OK" and ext["statut"] == "OK" and dom["matchs"] and ext["matchs"]
                         and (cotes_betpawa or cotes_obs)),
        "score": None,
    }


# ---------------------------------------------------------------------------------------------------------------------
# Lecture / écriture des fichiers (un fichier gzip par date de match, contenu trié et horodatage gzip fixe : le fichier
# ne change sur GitHub que si son contenu change)
# ---------------------------------------------------------------------------------------------------------------------

def _chemin(dossier, date_match):
    return os.path.join(dossier, f"{date_match}.json.gz")


def charge_fichier(chemin):
    if not os.path.exists(chemin):
        return {}
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        return json.load(f)


def sauve_fichier(chemin, donnees):
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    brut = json.dumps(donnees, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tmp = chemin + ".tmp"
    with open(tmp, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as g:
            g.write(brut)
    os.replace(tmp, chemin)


def _a_des_cotes(s):
    return bool(s.get("cotes_manuelles")) or bool(_cotes_observees(s))


def _plus_recent(existant, maintenant):
    """True si l'enregistrement existant vient de données plus récentes que celles du run courant (ex. precalcul.json
    resté d'hier après un run en échec) : une donnée plus ancienne ne remplace jamais une plus récente."""
    pris = ((existant or {}).get("run") or {}).get("pris_le")
    return bool(pris) and pris > maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")


def lit_genere_le(texte):
    """« 2026-09-26 21:28 UTC » (champ genere_le de precalcul.json) -> datetime UTC, sinon None."""
    try:
        return datetime.datetime.strptime(str(texte), "%Y-%m-%d %H:%M UTC").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def archive_run(signaux, stats_equipes, details, dossier=DOSSIER, maintenant=None, commit=None):
    """Enregistre l'avant-match de chaque match qui a des cotes. Renvoie le bilan du run."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    commit = commit if commit is not None else (os.environ.get("GITHUB_SHA") or "")[:7] or None
    par_date = {}
    for s in signaux:
        if s.get("match_id") and s.get("date") and _a_des_cotes(s):
            par_date.setdefault(s["date"], []).append(s)
    bilan = {"ecrits": 0, "testables": 0, "figes_non_modifies": 0, "fichiers": 0}
    for date_match, liste in sorted(par_date.items()):
        chemin = _chemin(dossier, date_match)
        donnees = charge_fichier(chemin)
        change = False
        for s in liste:
            existant = donnees.get(s["match_id"])
            coup = coup_d_envoi_utc(date_match, s.get("heure_cameroun"))
            if not peut_mettre_a_jour(existant, date_match, coup, maintenant) or _plus_recent(existant, maintenant):
                bilan["figes_non_modifies"] += 1
                continue
            e = construit_enregistrement(s, stats_equipes, details, maintenant, commit)
            donnees[s["match_id"]] = e
            bilan["ecrits"] += 1
            bilan["testables"] += int(e["testable"])
            change = True
        if change:
            sauve_fichier(chemin, donnees)
            bilan["fichiers"] += 1
    return bilan


def scores_de_l_historique(fichier_historique=FICHIER_HISTORIQUE):
    """{match_id: (buts_dom, buts_ext)} pour les matchs dont historique_pronostics.json a un score lisible."""
    if not os.path.exists(fichier_historique):
        return {}
    with open(fichier_historique, encoding="utf-8") as f:
        hist = json.load(f)
    out = {}
    for bloc in hist if isinstance(hist, list) else []:
        for m in bloc.get("matchs") or []:
            sc = lit_score(m.get("score"))
            if sc and m.get("match_id"):
                out[m["match_id"]] = sc
    return out


def complete_scores(dossier=DOSSIER, fichier_historique=FICHIER_HISTORIQUE, maintenant=None):
    """Écrit le score des matchs joués. Un score existant n'est jamais modifié ; seulement après le coup d'envoi."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    scores = scores_de_l_historique(fichier_historique)
    bilan = {"scores_ecrits": 0, "deja_presents": 0, "sans_score": 0}
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        donnees = charge_fichier(chemin)
        change = False
        for mid, e in donnees.items():
            if e.get("score") is not None:
                bilan["deja_presents"] += 1
                continue
            coup = coup_d_envoi_utc(e.get("date"), e.get("heure_cameroun"))
            joue = (maintenant > coup) if coup else (maintenant.date() > datetime.date.fromisoformat(e["date"]))
            sc = scores.get(mid) if joue else None
            if sc is None:
                bilan["sans_score"] += 1
                continue
            e["score"] = {"buts_dom": sc[0], "buts_ext": sc[1], "source": FICHIER_HISTORIQUE,
                          "ecrit_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")}
            bilan["scores_ecrits"] += 1
            change = True
        if change:
            sauve_fichier(chemin, donnees)
    return bilan


def slug_adresse(url):
    """Dernier segment d'une adresse Matchendirect sans l'identifiant final :
    « .../equipe/rsb-berkane_8q9....html » -> « rsb-berkane » ; « .../live-score/moghreb-rsb-berkane_8zg....html » ->
    « moghreb-rsb-berkane ». None si l'adresse n'a pas ce format."""
    if not url:
        return None
    dernier = str(url).rstrip("/").rsplit("/", 1)[-1]
    m = re.match(r"^([a-z0-9-]+)_[a-z0-9]+\.html$", dernier)
    return m.group(1) if m else None


def _comp_cle(c):
    return " ".join((c or "").split()).lower()


def index_cache_saison(cache):
    """{competition normalisée: {slug équipe: (url_equipe, resultat)}} depuis cache_equipes_saison.json."""
    idx = {}
    for cle, entree in (cache or {}).items():
        if "||" not in cle or not isinstance(entree, dict):
            continue
        url, comp = cle.split("||", 1)
        slug = slug_adresse(url)
        if slug and isinstance(entree.get("resultat"), dict):
            idx.setdefault(_comp_cle(comp), {})[slug] = (url, entree["resultat"])
    return idx


def equipes_du_match(url_match, competition, index):
    """((url_dom, res_dom), (url_ext, res_ext)) si l'adresse du match se décompose EXACTEMENT en deux équipes de la même
    compétition présentes dans le cache ; sinon None. Si plusieurs découpages sont possibles, aucun n'est choisi."""
    slug_match = slug_adresse(url_match)
    equipes = index.get(_comp_cle(competition)) or {}
    if not slug_match or not equipes:
        return None
    trouves = []
    for slug_dom in equipes:
        if slug_match.startswith(slug_dom + "-"):
            slug_ext = slug_match[len(slug_dom) + 1:]
            if slug_ext in equipes and slug_ext != slug_dom:
                trouves.append((equipes[slug_dom], equipes[slug_ext]))
    return trouves[0] if len(trouves) == 1 else None


def archive_depuis_fichiers(fichier_precalcul=FICHIER_PRECALCUL, fichier_cache=FICHIER_CACHE_SAISON,
                            dossier=DOSSIER, maintenant=None, commit=None):
    """Étape nocturne : relit ce que precalcul.py vient d'écrire et enregistre l'avant-match. L'heure de référence est
    celle où precalcul.json a été généré (genere_le), pas l'heure de cette étape : c'est l'heure réelle des données."""
    with open(fichier_precalcul, encoding="utf-8") as f:
        pre = json.load(f)
    signaux = pre.get("signaux") or []
    if maintenant is None:
        maintenant = lit_genere_le(pre.get("genere_le"))
        if maintenant is None:
            raise ValueError(f"genere_le illisible dans {fichier_precalcul} : {pre.get('genere_le')!r}")
    cache = {}
    if os.path.exists(fichier_cache):
        with open(fichier_cache, encoding="utf-8") as f:
            cache = json.load(f)
    index = index_cache_saison(cache)
    stats, details = {}, {}
    for s in signaux:
        paire = equipes_du_match(s.get("url_match"), s.get("competition"), index)
        if paire is None:
            continue
        (url_dom, res_dom), (url_ext, res_ext) = paire
        stats[(s.get("domicile"), s.get("competition"))] = res_dom
        stats[(s.get("exterieur"), s.get("competition"))] = res_ext
        details[s.get("url_match")] = {"url_equipe_domicile": url_dom, "url_equipe_exterieur": url_ext}
    return archive_run(signaux, stats, details, dossier=dossier, maintenant=maintenant, commit=commit)


def bilan_archive(dossier=DOSSIER):
    total = testables = avec_score = testables_avec_score = 0
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        for e in charge_fichier(chemin).values():
            total += 1
            testables += int(bool(e.get("testable")))
            avec_score += int(e.get("score") is not None)
            testables_avec_score += int(bool(e.get("testable")) and e.get("score") is not None)
    return {"matchs": total, "testables": testables, "avec_score": avec_score,
            "testables_avec_score": testables_avec_score}


def main(argv=None):
    p = argparse.ArgumentParser(description="Archive de test (avant-match complet + score).")
    p.add_argument("--run", action="store_true", help="enregistrer l'avant-match depuis precalcul.json (après precalcul.py)")
    p.add_argument("--scores", action="store_true", help="remplir les scores des matchs joués")
    p.add_argument("--bilan", action="store_true", help="afficher le bilan de l'archive")
    a = p.parse_args(argv)
    if a.run:
        print(f"archive de test -- avant-match : {archive_depuis_fichiers()}")
    if a.scores:
        print(f"archive de test -- scores : {complete_scores()}")
    print(f"archive de test -- bilan : {bilan_archive()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
