# -*- coding: utf-8 -*-
"""A5 (24/09/2026) — contrat de transmission des données collectées au moteur d'analyse des marchés.

Le moteur ne lit les données d'équipes QUE par ce module :
    import contrat_moteur as cm
    doc = cm.charge_assemblage()                 # vérifié ; lève ContratRompu si le fichier ne respecte pas le contrat
    equipe = cm.equipe(doc, url_equipe, competition)   # entrée d'une équipe (ou None)

Documentation complète : docs/CONTRAT_MOTEUR.md. Toute modification d'un champ = nouvelle VERSION_CONTRAT + mise à jour
de la documentation + des tests (tests/test_contrat_moteur.py). La collecte ne calcule rien : ce module non plus
(il vérifie la forme des données, jamais leur valeur métier).

Usage en ligne de commande (workflow journal.yml) : python contrat_moteur.py --verifier
  -> code 0 si data/assemblage/equipes.json et data/correspondances/equipes.json respectent le contrat, 1 sinon.
"""
import datetime
import json
import os
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER_ASSEMBLAGE = os.path.join(RACINE, "data", "assemblage", "equipes.json")
FICHIER_CORRESPONDANCES = os.path.join(RACINE, "data", "correspondances", "equipes.json")
VERSION_CONTRAT = 1


class ContratRompu(ValueError):
    """Les données ne respectent pas le contrat : le moteur ne doit pas les utiliser."""


ENTIER = (int,)
NOMBRE = (int, float)
TEXTE = (str,)
BOOLEEN = (bool,)

# Champs d'un match. obligatoire=True : toujours présent et jamais null. Les autres peuvent être null (donnée non publiée
# par la source) : le moteur écarte alors le marché qui en a besoin (règle du 24/09/2026).
CHAMPS_MATCH_COMMUNS = {
    "date": (TEXTE, True), "domicile": (BOOLEEN, True), "adversaire": (TEXTE, False),
    "buts_marques": (ENTIER, True), "buts_encaisses": (ENTIER, True),
    "source": (TEXTE, True), "provisoire": (BOOLEEN, True),
}
CHAMPS_MATCH_FOOTBALL_DATA = {
    "buts_marques_mi_temps": ENTIER, "buts_encaisses_mi_temps": ENTIER, "tirs": ENTIER, "tirs_concedes": ENTIER,
    "tirs_cadres": ENTIER, "tirs_cadres_concedes": ENTIER, "corners": ENTIER, "corners_concedes": ENTIER,
    "cartons_jaunes": ENTIER, "cartons_rouges": ENTIER, "xg": NOMBRE, "xg_concede": NOMBRE, "saison": TEXTE,
}
CHAMPS_MATCH_MATCHENDIRECT = {"url_match": TEXTE}
SOURCES = {"football-data", "matchendirect"}


def _date(texte):
    try:
        return datetime.date.fromisoformat(str(texte))
    except (TypeError, ValueError):
        return None


def _type_ok(valeur, types):
    if isinstance(valeur, bool) and bool not in types:
        return False                       # en Python, True est un int : on refuse un booléen à la place d'un nombre
    return isinstance(valeur, types)


def erreurs_match(m, couverte, ou):
    e = []
    if not isinstance(m, dict):
        return [f"{ou} : match qui n'est pas un objet"]
    for champ, (types, obligatoire) in CHAMPS_MATCH_COMMUNS.items():
        v = m.get(champ)
        if v is None:
            if obligatoire and not (champ == "date" and not couverte):
                e.append(f"{ou} : champ obligatoire « {champ} » absent")
            continue
        if not _type_ok(v, types):
            e.append(f"{ou} : « {champ} » de type {type(v).__name__} au lieu de {types[0].__name__}")
    if m.get("date") is not None and _date(m.get("date")) is None:
        e.append(f"{ou} : date illisible « {m.get('date')} »")
    src = m.get("source")
    if src not in SOURCES:
        e.append(f"{ou} : source inconnue « {src} »")
    extra = CHAMPS_MATCH_FOOTBALL_DATA if src == "football-data" else CHAMPS_MATCH_MATCHENDIRECT
    for champ, types in extra.items():
        v = m.get(champ)
        if v is not None and not _type_ok(v, types):
            e.append(f"{ou} : « {champ} » de type {type(v).__name__} au lieu de {types[0].__name__}")
    if src == "football-data" and m.get("provisoire") is not False:
        e.append(f"{ou} : un match Football-Data n'est jamais provisoire")
    if src == "matchendirect" and m.get("provisoire") is True and not couverte:
        e.append(f"{ou} : un match provisoire n'existe que pour un championnat couvert par Football-Data")
    if src == "matchendirect" and any(k in m for k in CHAMPS_MATCH_FOOTBALL_DATA if k != "saison"):
        e.append(f"{ou} : un match Matchendirect ne porte pas de données Football-Data (mi-temps, corners, xG...)")
    return e


def erreurs_assemblage(doc):
    e = []
    if not isinstance(doc, dict):
        return ["document qui n'est pas un objet"]
    if doc.get("version_contrat") != VERSION_CONTRAT:
        e.append(f"version_contrat {doc.get('version_contrat')!r} au lieu de {VERSION_CONTRAT}")
    if not isinstance(doc.get("equipes"), list):
        return e + ["« equipes » absent ou n'est pas une liste"]
    cles = set()
    for i, eq in enumerate(doc["equipes"]):
        ou = f"équipe {i} ({eq.get('cle_cache') if isinstance(eq, dict) else '?'})"
        if not isinstance(eq, dict):
            e.append(f"{ou} : n'est pas un objet")
            continue
        for champ, types in (("cle_cache", TEXTE), ("competition", TEXTE), ("couverte_par_football_data", BOOLEEN),
                             ("matchs", (list,))):
            if not _type_ok(eq.get(champ), types):
                e.append(f"{ou} : « {champ} » absent ou de mauvais type")
        if eq.get("cle_cache") in cles:
            e.append(f"{ou} : équipe présente deux fois")
        cles.add(eq.get("cle_cache"))
        couverte = eq.get("couverte_par_football_data") is True
        if couverte:
            for champ in ("division_football_data", "nom_football_data", "nom_matchendirect"):
                if not _type_ok(eq.get(champ), TEXTE):
                    e.append(f"{ou} : « {champ} » obligatoire pour une équipe couverte")
        elif not _type_ok(eq.get("raison"), TEXTE):
            e.append(f"{ou} : « raison » obligatoire pour une équipe sans Football-Data")
        matchs = eq.get("matchs") if isinstance(eq.get("matchs"), list) else []
        for j, m in enumerate(matchs):
            e.extend(erreurs_match(m, couverte, f"{ou}, match {j}"))
        # jamais deux fois le même match : une équipe ne joue pas deux fois à ± 1 jour (équipes couvertes, dates vérifiées)
        if couverte:
            dates = sorted(d for d in (_date(m.get("date")) for m in matchs if isinstance(m, dict)) if d)
            for a, b in zip(dates, dates[1:]):
                if (b - a).days <= 1:
                    e.append(f"{ou} : deux matchs à ± 1 jour ({a} et {b}) : doublon probable")
            if [m.get("date") for m in matchs if isinstance(m, dict)] != sorted(m.get("date") for m in matchs if isinstance(m, dict)):
                e.append(f"{ou} : matchs non triés par date")
    return e


def erreurs_correspondances(doc):
    e = []
    if not isinstance(doc, dict) or not isinstance(doc.get("divisions"), dict):
        return ["« divisions » absent ou n'est pas un objet"]
    vus = {}
    for div, info in doc["divisions"].items():
        if not isinstance(info, dict) or not isinstance(info.get("equipes"), dict):
            e.append(f"division {div} : « equipes » absent")
            continue
        for nom_fd, v in info["equipes"].items():
            if not isinstance(v, dict) or not _type_ok(v.get("matchendirect"), TEXTE) or not _type_ok(v.get("preuves"), ENTIER):
                e.append(f"{div} / {nom_fd} : « matchendirect » ou « preuves » absent")
                continue
            cle = (div, v["matchendirect"])
            if cle in vus:
                e.append(f"{div} : « {v['matchendirect']} » relié à deux équipes ({vus[cle]} et {nom_fd})")
            vus[cle] = nom_fd
    return e


def _charge(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def charge_assemblage(chemin=FICHIER_ASSEMBLAGE):
    """Seul point d'entrée du moteur. Lève ContratRompu si le fichier ne respecte pas le contrat."""
    doc = _charge(chemin)
    e = erreurs_assemblage(doc)
    if e:
        raise ContratRompu(f"{len(e)} écart(s) au contrat, ex. : {e[:3]}")
    return doc


def equipe(doc, url_equipe, competition):
    """Entrée de l'équipe (clé du cache : « url||compétition en minuscules »), ou None."""
    cle = f"{url_equipe}||{str(competition).lower()}"
    for eq in doc.get("equipes", []):
        if eq.get("cle_cache") == cle:
            return eq
    return None


def main():
    if "--verifier" not in sys.argv:
        print(__doc__)
        return 0
    code = 0
    for nom, chemin, fn in (("assemblage", FICHIER_ASSEMBLAGE, erreurs_assemblage),
                            ("correspondances", FICHIER_CORRESPONDANCES, erreurs_correspondances)):
        try:
            e = fn(_charge(chemin))
        except (OSError, ValueError) as exc:
            e = [f"fichier illisible : {exc}"]
        print(f"[A5] {nom} : {'CONFORME' if not e else f'{len(e)} écart(s)'}")
        for x in e[:20]:
            print("   -", x)
        code = code or (1 if e else 0)
    return code


if __name__ == "__main__":
    sys.exit(main())
