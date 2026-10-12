"""parse_corners_cartons_betpawa.py -- relève les cotes CORNERS / CARTONS d'une page BetPawa (12/10/2026).

Module SÉPARÉ de parse_betpawa_playwright.py : le résultat n'entre jamais dans `cotes_manuelles`, donc V2, V3, leur
couverture (`issues_betpawa`, `groupes_non_lus`) et le journal ne voient aucun changement. Le résultat est rangé dans
`cotes_corners_cartons` du match (resolution_betpawa_precalcul.py) et lu uniquement par corners_cartons.py.

Format lu : celui du navigateur automatisé (titres en anglais, étiquette puis valeur sur deux lignes), identique à
parse_betpawa_playwright.py. Titres BetPawa relevés le 12/10/2026 sur une page réelle :
  « Total Corners Over/Under | Full Time »      Over 9.5 / 1.85 / Under 9.5 / 1.85 ...
  « Total Bookings Over/Under | Full Time »     Over 3.5 / 1.61 / Under 3.5 / 2.09 ...
  « Total Corners <équipe> | Full Time »        0-2 / 3-4 / 5-6 / 7+   (tranches, pas de lignes plus/moins)
  « Total Bookings <équipe> | Full Time »       0-1 / 2 / 3 / 4+       (tranches)
  « Player Sent Off | Full Time »               Yes / No               (= carton rouge dans le match)

Seules les cotes qui valent EXACTEMENT un marché du modèle sont gardées (jamais de cote reconstituée) :
  - total corners / total « bookings » : Plus de L et Moins de L, pour chaque ligne publiée ;
  - corners d'une équipe : « 7+ » = Plus de 6,5 ;
  - cartons d'une équipe : « 0-1 » = Moins de 1,5 ;
  - carton rouge : « Player Sent Off » Oui / Non.
Une tranche qui ne correspond à aucune ligne du modèle (« 3-4 », « 5-6 », « 2 »...) est ignorée.

LIMITE À CONNAÎTRE : « Bookings » est le mot de BetPawa. Sa règle de comptage (un rouge = 1 carton, ou 2 selon les
points de réservation) n'est pas vérifiée ici ; le modèle compte jaunes + rouges (un rouge = un carton).

Clés produites (dicts plats, valeurs > 1.0, comme les autres parseurs) :
  corners_total_9.5 {plus, moins} · cartons_total_3.5 {plus, moins}
  corners_domicile_6.5 {plus} · corners_exterieur_6.5 {plus}
  cartons_domicile_1.5 {moins} · cartons_exterieur_1.5 {moins}
  rouge_match {oui, non}
"""
import re

from equipe_betpawa import cote_de_l_equipe
from parse_betpawa_playwright import _lignes_non_vides, _paires, _paires_jusqua_rupture

RE_OU = r"^(Over|Under) \d+(\.\d+)?$"
RE_TRANCHE = r"^\d+(-\d+|\+)?$"
RE_EQUIPE_CORNERS = re.compile(r"^Total Corners (.+) \| Full Time$")
RE_EQUIPE_CARTONS = re.compile(r"^Total Bookings (.+) \| Full Time$")


def _valide(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1.0


def _plus_moins(paires, prefixe, cotes):
    for label, valeur in paires.items():
        m = re.match(r"^(Over|Under) (\d+\.5)$", label)      # lignes en demi-unités seulement (aucun remboursement)
        if not m or not _valide(valeur):
            continue
        cle = "plus" if m.group(1) == "Over" else "moins"
        cotes.setdefault(f"{prefixe}_{m.group(2)}", {})[cle] = valeur


def parse_corners_cartons_betpawa(texte, nom_domicile, nom_exterieur):
    lignes = _lignes_non_vides(texte)
    cotes = {}
    i = 0
    while i < len(lignes):
        titre = lignes[i]

        if titre == "Total Corners Over/Under | Full Time":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, RE_OU)
            _plus_moins(paires, "corners_total", cotes)
            continue

        if titre == "Total Bookings Over/Under | Full Time":
            paires, i = _paires_jusqua_rupture(lignes, i + 1, RE_OU)
            _plus_moins(paires, "cartons_total", cotes)
            continue

        if titre == "Player Sent Off | Full Time":
            paires, i = _paires(lignes, i + 1, 2)
            oui, non = paires.get("Yes"), paires.get("No")
            if _valide(oui) and _valide(non):
                cotes["rouge_match"] = {"oui": oui, "non": non}
            continue

        m = RE_EQUIPE_CORNERS.match(titre)
        if m and m.group(1) != "Over/Under":
            cote_equipe = cote_de_l_equipe(m.group(1), nom_domicile, nom_exterieur)
            paires, i = _paires_jusqua_rupture(lignes, i + 1, RE_TRANCHE)
            if cote_equipe in ("domicile", "exterieur") and _valide(paires.get("7+")):
                cotes[f"corners_{cote_equipe}_6.5"] = {"plus": paires["7+"]}
            continue

        m = RE_EQUIPE_CARTONS.match(titre)
        if m and m.group(1) != "Over/Under":
            cote_equipe = cote_de_l_equipe(m.group(1), nom_domicile, nom_exterieur)
            paires, i = _paires_jusqua_rupture(lignes, i + 1, RE_TRANCHE)
            if cote_equipe in ("domicile", "exterieur") and _valide(paires.get("0-1")):
                cotes[f"cartons_{cote_equipe}_1.5"] = {"moins": paires["0-1"]}
            continue

        i += 1   # section non reconnue : ignorée sans message, comme dans les autres parseurs

    return cotes
