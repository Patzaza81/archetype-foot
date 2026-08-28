"""
payload_builder.py — construit panier.json à partir des inputs reçus
par workflow_dispatch.

Matching utilisé : Niveau 3 (cherche_url_matchendirect_auto, algorithme
existant, éprouvé) + Niveau 4 (URL matchendirect de secours fournie
manuellement). Pas de Niveau 1 (URL opaque compétition) ni de recherche
Betpawa par nom pour l'instant -- pas encore construits, ne pas prétendre
le contraire. En cas d'échec des deux niveaux : NO MATCH, exception levée,
rien n'est deviné.
"""
import re
from scraper_betpawa import cherche_url_matchendirect_auto, genere_match_id


def _valide_date(d):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        raise ValueError(f"date invalide : {d}")
    return d


def _valide_heure(h):
    if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", h):
        raise ValueError(f"heure invalide : {h}")
    return h


def build_payload(payload):
    date_ok = _valide_date(payload["date"])
    heure_ok = _valide_heure(payload["heure"])
    equipe_dom = payload["equipe_dom"]
    equipe_ext = payload["equipe_ext"]
    url_secours = payload.get("url_matchendirect")

    url_match = cherche_url_matchendirect_auto(equipe_dom, equipe_ext, date_betpawa=date_ok)

    if not url_match and url_secours:
        url_match = url_secours

    if not url_match:
        raise RuntimeError(
            f"NO MATCH pour {equipe_dom} - {equipe_ext} le {date_ok} {heure_ok} : "
            f"aucune correspondance automatique, aucune URL de secours fournie."
        )

    return [{
        "domicile": equipe_dom,
        "exterieur": equipe_ext,
        "competition": "Inconnue",
        "url_match": url_match,
        "match_id": genere_match_id(equipe_dom, equipe_ext),
        "source": "auto_dispatch",
        "cotes_manuelles": None,
    }]
