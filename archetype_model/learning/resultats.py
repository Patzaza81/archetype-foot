"""
archetype_model/learning/resultats.py — Vérification autonome des résultats.

Pourquoi ce module existe : archive.py enregistre les pronostics (SELECTED)
et les marchés proches du seuil (COUNTERFACTUAL), mais aucun des deux n'a de
résultat réel tant que ce module n'est pas passé. Sans lui, ni le ROI, ni la
matrice comportementale, ni le contrefactuel du bureau d'étude n'ont quoi
que ce soit à mesurer.

Réutilise le scraping déjà existant et déjà éprouvé en production, à
l'identique de verification_resultats.py (ancien moteur) :
- url_resultat_foot() / fetch_html() / parse_matches() (scraper.py)
- _memes_equipes() (scraper_details.py)
- aujourdhui_france() (run_pipeline.py) -- même définition du "jour" que le
  reste du pipeline, correctif fuseau horaire du 04/09/2026 inclus.

Différence essentielle avec verification_resultats.py : ce module résout
DEUX populations avec la MÊME fonction de règlement (reglement.evaluer_marche)
-- les pronostics SELECTED et les marchés COUNTERFACTUAL proches du seuil.
C'est la correction exigée le 12/09/2026 : sans elle, le mécanisme de test
contrefactuel du bureau d'étude n'aurait jamais eu de résultat réel à
comparer.

Logique d'abandon identique à verification_resultats.py (mêmes règles,
même seuil NB_JOURS_MAX_A_VERIFIER) :
- jour >= aujourd'hui  -> jamais traité, jamais abandonné (pas encore fini) ;
- jour trop ancien (> NB_JOURS_MAX_A_VERIFIER jours) -> marqué
  NON_RESOLU_DEFINITIF sans nouvelle tentative ;
- jour intermédiaire -> une tentative de récupération du score par cycle.

Un marché que reglement.py ne reconnaît pas n'est JAMAIS résolu par défaut
en LOSS : il reste PENDING et une alerte est écrite sur stderr -- c'est un
signal que reglement.py doit être complété, pas une donnée à deviner ici.
"""

from __future__ import annotations

import datetime
import sys
from typing import Any

from scraper import parse_matches, url_resultat_foot, fetch_html
from scraper_details import _memes_equipes
from run_pipeline import aujourdhui_france

from archetype_model.learning import archive
from archetype_model.learning.reglement import evaluer_marche, MARCHE_NON_RECONNU

# Valeur identique à verification_resultats.py -- ne doit jamais diverger
# entre les deux moteurs, sous peine de traiter un même jour différemment
# selon le moteur qui l'a produit.
NB_JOURS_MAX_A_VERIFIER = 10


def _parse_score(score: str) -> tuple[int, int]:
    """\"2-1\" -> (2, 1). Lève une erreur explicite plutôt que de deviner un
    format inattendu."""
    dom, ext = score.split("-")
    return int(dom), int(ext)


def _trouve_score(matchs_page: list[dict[str, Any]], equipe_dom: str, equipe_ext: str) -> str | None:
    """Identique à verification_resultats.trouve_score() : ne renvoie un
    score que si le statut scrapé est exactement \"TER\" (terminé). Un match
    reporté/suspendu, ou sans score encore affiché, reste None -- jamais un
    score partiel écrit comme définitif."""
    for m in matchs_page:
        if _memes_equipes(m["domicile"], equipe_dom) and _memes_equipes(m["exterieur"], equipe_ext):
            if m.get("score") is not None and m.get("heure") == "TER":
                return m["score"]
            return None
    return None


def _fichiers_archive_a_verifier(aujourdhui: datetime.date, repertoire: str = "archive") -> list[str]:
    """Les fichiers archive/YYYY-MM.json susceptibles de contenir un match
    de la fenêtre [aujourd'hui - NB_JOURS_MAX_A_VERIFIER, aujourd'hui - 1]."""
    chemins: list[str] = []
    vus: set[str] = set()
    for delta in range(1, NB_JOURS_MAX_A_VERIFIER + 1):
        jour = aujourdhui - datetime.timedelta(days=delta)
        chemin = str(archive.chemin_archive_mensuelle(jour.isoformat(), repertoire))
        if chemin not in vus:
            vus.add(chemin)
            chemins.append(chemin)
    return chemins


def verifier_resultats(
    repertoire: str = "archive",
    aujourdhui: datetime.date | None = None,
) -> dict[str, int]:
    """Point d'entrée. Résout tous les enregistrements PENDING (SELECTED et
    COUNTERFACTUAL confondus) dont le jour est strictement passé et dans la
    fenêtre de vérification. Retourne un résumé chiffré -- jamais un
    résultat silencieux."""
    aujourdhui = aujourdhui or aujourdhui_france()
    limite_ancienne = aujourdhui - datetime.timedelta(days=NB_JOURS_MAX_A_VERIFIER)

    total_resolus = 0
    total_non_reconnus = 0
    total_abandonnes = 0
    total_restants = 0

    for chemin in _fichiers_archive_a_verifier(aujourdhui, repertoire):
        records = archive.charger_archive(chemin)

        en_attente_par_date: dict[datetime.date, list[dict[str, Any]]] = {}
        for record in records:
            if record.get("resultat_statut") != archive.STATUT_PENDING:
                continue
            try:
                date_obj = datetime.date.fromisoformat(str(record["date_match"])[:10])
            except (ValueError, TypeError):
                # Date invalide dans l'archive : ne doit jamais faire
                # planter tout le run pour un seul enregistrement suspect.
                continue
            en_attente_par_date.setdefault(date_obj, []).append(record)

        for date_obj, records_du_jour in en_attente_par_date.items():
            if date_obj >= aujourdhui:
                continue  # jour pas encore terminé -- jamais abandonné

            if date_obj < limite_ancienne:
                for record in records_du_jour:
                    archive.marquer_non_resolu_definitif(record["record_id"], chemin=chemin)
                    total_abandonnes += 1
                continue

            try:
                url = url_resultat_foot(date_obj)
                html, _ = fetch_html(url)
            except Exception as exc:
                print(f"[resultats] échec récupération {date_obj} : {exc}", file=sys.stderr)
                total_restants += len(records_du_jour)
                continue

            # max_matchs=2000 : une page résultat contient plusieurs
            # centaines de matchs toutes compétitions confondues -- la
            # valeur par défaut de parse_matches (20) en perdrait la quasi-
            # totalité silencieusement (même raison que dans
            # verification_resultats.py).
            matchs_page = parse_matches(html, max_matchs=2000, date_label=date_obj.isoformat())

            for record in records_du_jour:
                score = _trouve_score(matchs_page, record["equipe_dom"], record["equipe_ext"])
                if score is None:
                    total_restants += 1
                    continue

                buts_dom, buts_ext = _parse_score(score)
                resultat = evaluer_marche(record["marche"], buts_dom, buts_ext)

                if resultat.statut == MARCHE_NON_RECONNU:
                    print(
                        f"[resultats] ALERTE marché non reconnu : {record['marche']!r} "
                        f"(record_id={record['record_id']}) -- laissé PENDING, "
                        "reglement.py doit être complété avant de pouvoir le résoudre.",
                        file=sys.stderr,
                    )
                    total_non_reconnus += 1
                    total_restants += 1
                    continue

                archive.mettre_a_jour_resultat(
                    record["record_id"],
                    buts_marques=buts_dom,
                    buts_encaisses=buts_ext,
                    resultat_marche=resultat.statut,
                    date_resolution=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    chemin=chemin,
                )
                total_resolus += 1

    return {
        "resolus": total_resolus,
        "non_reconnus": total_non_reconnus,
        "abandonnes": total_abandonnes,
        "restants": total_restants,
    }


if __name__ == "__main__":
    resume = verifier_resultats()
    print(
        f"[resultats] {resume['resolus']} résolu(s) -- "
        f"{resume['restants']} encore en attente après ce passage -- "
        f"{resume['abandonnes']} marqué(s) NON_RESOLU_DEFINITIF -- "
        f"{resume['non_reconnus']} marché(s) non reconnu(s) (alerte, voir stderr)."
    )
