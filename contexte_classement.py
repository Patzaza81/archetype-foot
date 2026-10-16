"""Extraction prudente des zones de classement depuis les pages Matchendirect.

Ce module reste indépendant des moteurs : il ne calcule aucune probabilité.
Une zone n'est associée à des rangs que si la couleur/classe du marqueur de
légende peut être reliée sans ambiguïté aux lignes du tableau.
"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup

MOTS_ZONES = {
    "ligue des champions": "qualification_ligue_champions",
    "champions league": "qualification_ligue_champions",
    "europa league": "qualification_europa_league",
    "ligue europa": "qualification_europa_league",
    "conference league": "qualification_conference_league",
    "ligue europa conference": "qualification_conference_league",
    "relégation": "relegation",
    "relegation": "relegation",
    "barrage": "barrage",
    "maintien": "maintien",
    "championnat": "groupe_championnat",
    "groupe championnat": "groupe_championnat",
    "tour de relégation": "groupe_relegation",
}


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip().lower()


def _couleur(tag):
    """Retourne une couleur explicite dans style ou une classe CSS de couleur."""
    style = tag.get("style", "") if tag else ""
    m = re.search(r"(?:background(?:-color)?|color)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|[a-zA-Z]+)", style)
    if m:
        return m.group(1).lower()
    classes = tag.get("class", []) if tag else []
    # Les pages peuvent nommer une même zone sur la légende et la ligne
    # (ex. "legend-zone europe" / "europe"). On compare les classes utiles,
    # en ignorant les marqueurs structurels génériques.
    generiques = {"legend", "legend-zone", "zone-legend", "classement", "row", "table-row"}
    candidats = [c.lower() for c in classes if c.lower() not in generiques]
    return "|".join(candidats) or None


def _type_zone(texte: str):
    t = _normalise(texte)
    # Les libellés peuvent contenir un nom de zone plus long.
    for motif, type_zone in MOTS_ZONES.items():
        if motif in t:
            return type_zone
    if "qualifi" in t and ("europe" in t or "uefa" in t):
        return "qualification_europeenne"
    if "relégu" in t or "relegu" in t:
        return "relegation"
    return None


def extraire_zones_classement(html: str) -> dict:
    """Renvoie les légendes reconnues et les rangs uniquement si liaison sûre.

    Schéma:
      statut: "identifie" ou "indetermine"
      zones: [{type, libelle, rangs: [int, ...]}]
      source: "matchendirect"
    """
    soup = BeautifulSoup(html or "", "html.parser")
    zones = []
    legend_candidates = []

    # La légende est recherchée dans les petits éléments, pas dans le texte
    # global de la page qui pourrait mélanger plusieurs compétitions.
    for tag in soup.find_all(["li", "span", "div", "p", "td", "label"]):
        label = tag.get_text(" ", strip=True)
        type_zone = _type_zone(label)
        if not type_zone or len(label) > 180:
            continue
        color = _couleur(tag)
        parent_color = _couleur(tag.parent) if tag.parent else None
        legend_candidates.append((type_zone, label, color or parent_color))

    # Dédupliquer les libellés tout en gardant le marqueur de couleur.
    seen = set()
    for type_zone, label, color in legend_candidates:
        key = (type_zone, _normalise(label), color)
        if key not in seen:
            seen.add(key)
            zones.append({"type": type_zone, "libelle": label, "rangs": [], "_couleur": color})

    # Associer une zone aux rangs uniquement quand le même marqueur est trouvé
    # sur les lignes du tableau. Le rang doit être le premier nombre de cellule.
    if zones:
        tables = soup.find_all("table")
        for table in tables:
            for tr in table.find_all("tr"):
                cells = tr.find_all(["td", "th"], recursive=False)
                if len(cells) < 2:
                    continue
                row_color = _couleur(tr)
                if not row_color:
                    row_color = next((_couleur(c) for c in cells if _couleur(c)), None)
                if not row_color:
                    continue
                rang = None
                for cell in cells:
                    texte = cell.get_text(" ", strip=True)
                    if re.fullmatch(r"\d{1,2}", texte):
                        rang = int(texte)
                        break
                if rang is None:
                    continue
                for zone in zones:
                    if zone["_couleur"] and zone["_couleur"] == row_color:
                        zone["rangs"].append(rang)

    # Une couleur/classe n'est exploitable que si elle relie au moins un rang.
    zones_finales = []
    for zone in zones:
        rangs = sorted(set(zone["rangs"]))
        zones_finales.append({
            "type": zone["type"],
            "libelle": zone["libelle"],
            "rangs": rangs,
        })

    identifie = bool(zones_finales) and any(z["rangs"] for z in zones_finales)
    return {
        "statut": "identifie" if identifie else "indetermine",
        "zones": zones_finales,
        "source": "matchendirect",
    }


def enjeu_equipe(classement: dict, rang_equipe: int | None) -> dict:
    """Retourne l'enjeu connu d'une équipe, sans inférer les zones manquantes."""
    if not isinstance(classement, dict) or classement.get("statut") != "identifie" or not rang_equipe:
        return {"statut": "indetermine", "zones": []}
    zones = [
        {"type": z["type"], "libelle": z["libelle"]}
        for z in classement.get("zones", [])
        if rang_equipe in z.get("rangs", [])
    ]
    return {"statut": "identifie" if zones else "indetermine", "zones": zones}
