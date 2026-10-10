"""journal_indice.py -- ajoute l'indice de performance (moteur_v3/performance.py) aux équipes suivies par le Journal.

Pour chaque ligne « équipe x marché » du Journal qui a un prochain match, on retrouve ce match dans l'archive, on traduit
le marché du Journal en marché V3 (selon que l'équipe joue à domicile ou à l'extérieur) et on calcule l'indice sur les
matchs au même lieu, avec la logique figée (voir docs/CLAUDE_SELECTION.md). Information seulement : le Journal, ses
fréquences, ses ROI et ses statuts ne changent pas. Lecture seule de l'archive ; écrit seulement journal.json.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping, Sequence

from equipe_betpawa import memes_equipes
from moteur_v3.model import _latest
from moteur_v3.performance import indice_performance

FICHIER_JOURNAL = "journal.json"

# libellé du Journal -> (marché V3 si l'équipe joue à domicile, marché V3 si elle joue à l'extérieur)
MARCHES = {
    "Match à moins de 3,5 buts": ("under_3_5", "under_3_5"),
    "Match à moins de 2,5 buts": ("under_2_5", "under_2_5"),
    "Match à plus de 2,5 buts": ("over_2_5", "over_2_5"),
    "Match à plus de 3,5 buts": ("over_3_5", "over_3_5"),
    "Les deux équipes marquent": ("btts_yes", "btts_yes"),
    "Au moins une équipe ne marque pas": ("btts_no", "btts_no"),
    "Ne perd pas (victoire ou nul)": ("dc_1X", "dc_X2"),
    "Victoire": ("1x2_1", "1x2_2"),
    "Marque 2 buts ou plus": ("home_over_1_5", "away_over_1_5"),
    "Garde sa cage inviolée": ("clean_home", "clean_away"),
    "Gagne par 2 buts ou plus": ("handicap_1.5_1", "handicap_-1.5_2"),
}


def marche_moteur(libelle: str, domicile: bool) -> str | None:
    paire = MARCHES.get(libelle)
    return None if paire is None else paire[0 if domicile else 1]


def trouve_match(enregs: Sequence[Mapping[str, Any]], equipe: str, adversaire: str, date: str, domicile: bool):
    """Le match de l'archive : même date, l'équipe suivie du bon côté, l'adversaire en face. None sinon."""
    for e in enregs:
        if e.get("date") != date:
            continue
        nom_eq, nom_adv = (e.get("domicile"), e.get("exterieur")) if domicile else (e.get("exterieur"), e.get("domicile"))
        if memes_equipes(equipe, nom_eq) and memes_equipes(adversaire, nom_adv):
            return e
    return None


def indice_pour_ligne(ligne: Mapping[str, Any], enregs: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    pm = ligne.get("prochain_match") or {}
    lieu = str(pm.get("lieu") or "").lower()
    if lieu not in ("domicile", "extérieur", "exterieur") or not pm.get("date") or not pm.get("adversaire"):
        return None
    domicile = lieu == "domicile"
    mk = marche_moteur(str(ligne.get("marche") or ""), domicile)
    if mk is None:
        return None
    e = trouve_match(enregs, str(ligne.get("equipe") or ""), str(pm["adversaire"]), str(pm["date"]), domicile)
    if e is None:
        return None
    dom = _latest((e.get("equipe_dom") or {}).get("matchs") or [], True)
    ext = _latest((e.get("equipe_ext") or {}).get("matchs") or [], False)
    p = indice_performance(mk, dom, ext)
    if p is None:
        return None
    return {"indice": p["indice"], "sur": p["sur"], "niveau": p["niveau"], "libelle": p["libelle"], "phrase": p["phrase"],
            "marche_moteur": mk, "n_domicile": len(dom), "n_exterieur": len(ext)}


def ajoute_indices(journal: dict[str, Any], enregs: Sequence[Mapping[str, Any]]) -> int:
    n = 0
    for cle in ("equipes_a_suivre", "opportunites_futures"):
        for ligne in journal.get(cle) or []:
            p = indice_pour_ligne(ligne, enregs)
            if p is None:
                ligne.pop("indice_performance", None)
            else:
                ligne["indice_performance"] = p
                n += 1
    return n


def main(chemin: str = FICHIER_JOURNAL) -> None:
    import datetime
    import moteur_v3_pipeline as mp
    enregs = mp.lit_archive(mp.DOSSIER_ARCHIVE)
    limite = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    enregs = [e for e in enregs if str(e.get("date") or "") >= limite]   # seuls les matchs récents ou à venir servent
    with open(chemin, encoding="utf-8") as f:
        journal = json.load(f)
    n = ajoute_indices(journal, enregs)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=2)
    print(f"[journal indice] {n} ligne(s) du Journal avec indice de performance.")


if __name__ == "__main__":
    main(*sys.argv[1:2])
