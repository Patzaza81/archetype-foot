"""Preuves historiques destinées à l'affichage public.

Ce module intervient après le calcul du moteur. Il ne choisit pas de marché,
ne modifie aucune sélection et ne recalcule ni probabilité, ni edge, ni EDV.
Il transforme uniquement l'historique déjà chargé en preuves lisibles.

Règle de qualité : une fréquence n'est publiable qu'avec au moins 5 matchs
comparables ET une tendance favorable d'au moins 60 %. Ainsi 4/5 est
parfaitement recevable, tandis que 1/2 ou 1/5 ne peuvent jamais être
présentés comme une justification favorable. Le nombre de matchs utilisé
pour une preuve est toujours indiqué.
"""

import re
from statistics import mean

MIN_MATCHS_PREUVE = 5
MAX_MATCHS_AFFICHAGE = 8
MIN_H2H_PREUVE = 5
MIN_POURCENTAGE_PREUVE = 60.0


def _propres(matchs):
    resultat = []
    for m in matchs or []:
        if not isinstance(m, dict):
            continue
        if not isinstance(m.get("buts_marques"), (int, float)):
            continue
        if not isinstance(m.get("buts_encaisses"), (int, float)):
            continue
        resultat.append(m)
    return resultat


def _derniers(matchs, minimum=MIN_MATCHS_PREUVE):
    """Retourne jusqu'à 8 matchs récents si l'historique est exploitable."""
    propres = _propres(matchs)
    if len(propres) < minimum:
        return []
    return propres[-MAX_MATCHS_AFFICHAGE:]

def _historique_preuve(role_matchs, historique_recent):
    """Choisit le meilleur échantillon public sans confondre les contextes.

    Le rôle (domicile/extérieur) est prioritaire lorsqu'il fournit au moins
    5 matchs. Sinon, on bascule sur les derniers matchs toutes situations.
    Dans ce second cas, le texte doit parler de « forme récente » et jamais
    prétendre qu'il s'agit d'un historique domicile/extérieur.
    """
    role = _derniers(role_matchs)
    if role:
        return role, True
    recent = _derniers(historique_recent)
    if recent:
        return recent, False
    return [], False


def _role(matchs, domicile):
    return [m for m in _propres(matchs) if m.get("domicile") is domicile]


def _pct(n, d):
    return round((n / d) * 100, 1) if d else None


def _freq(matchs, condition):
    if len(matchs) < MIN_MATCHS_PREUVE:
        return None
    ok = sum(1 for m in matchs if condition(m))
    pourcentage = _pct(ok, len(matchs))
    if pourcentage < MIN_POURCENTAGE_PREUVE:
        return None
    return {"occurrences": ok, "total": len(matchs), "pourcentage": pourcentage}


def _moyenne(matchs, fonction):
    if len(matchs) < MIN_MATCHS_PREUVE:
        return None
    return round(mean(fonction(m) for m in matchs), 2)


def _ligne(marche):
    m = re.search(
        r"(?:over_under_total_|buts_equipe_(?:domicile|exterieur)_)(-?\d+(?:\.\d+)?)_(over|under)$",
        marche or "",
    )
    return (float(m.group(1)), m.group(2)) if m else None


def _h2h_propres(confrontations):
    return [
        x for x in confrontations or []
        if isinstance(x, dict)
        and isinstance(x.get("buts_a"), (int, float))
        and isinstance(x.get("buts_b"), (int, float))
    ]


def _h2h_freq(confrontations, condition):
    c = _h2h_propres(confrontations)
    if len(c) < MIN_H2H_PREUVE:
        return None
    ok = sum(1 for x in c if condition(x))
    pourcentage = _pct(ok, len(c))
    if pourcentage < MIN_POURCENTAGE_PREUVE:
        return None
    return {"occurrences": ok, "total": len(c), "pourcentage": pourcentage}


def _preuve_frequence(titre, matchs, condition, texte):
    f = _freq(matchs, condition)
    if not f:
        return None
    return {
        "titre": titre,
        "texte": f"{f['occurrences']}/{f['total']} {texte}",
        "occurrences": f["occurrences"],
        "total": f["total"],
        "pourcentage": f["pourcentage"],
    }


def _preuve_moyenne(titre, texte, matchs, fonction):
    valeur = _moyenne(matchs, fonction)
    if valeur is None:
        return None
    return {"titre": titre, "texte": texte.format(valeur=valeur), "moyenne": valeur}


def _ajoute(preuves, preuve):
    if preuve:
        preuves.append(preuve)


def _sujet_role(role, domicile, exterieur):
    return domicile if role == "domicile" else exterieur


def construit_justification(marche, matchs_a, matchs_b, h2h=None,
                             nom_domicile="", nom_exterieur=""):
    """Construit des preuves descriptives pour un marché déjà sélectionné.

    Les historiques sont ceux déjà chargés par le moteur. Les marchés
    dépendant du rôle utilisent domicile pour l'équipe A et extérieur pour
    l'équipe B. Pour les marchés de match (total/BTTS/parité), on décrit les
    tendances observées dans les matchs comparables de chaque équipe, sans
    prétendre qu'il s'agit d'un historique du futur match lui-même.
    """
    a = _propres(matchs_a)
    b = _propres(matchs_b)
    a_dom, a_role = _historique_preuve(_role(a, True), a)
    b_ext, b_role = _historique_preuve(_role(b, False), b)
    h2h_retenu = _h2h_propres(h2h)

    preuves = []
    resume = None
    h2h_condition = None

    if marche == "over_2_5" or marche.startswith("over_under_total_"):
        ligne, sens = _ligne(marche) or (2.5, "over")
        ligne_txt = str(ligne).replace(".", ",")
        if sens == "under":
            resume = f"Ce match devrait rester relativement fermé et ne devrait pas dépasser {ligne_txt} buts."
            condition = lambda m, l=ligne: m["buts_marques"] + m["buts_encaisses"] < l
            description = f"derniers matchs sous {ligne_txt} buts"
        else:
            resume = "Les deux équipes ont montré une belle capacité à trouver le chemin des filets ces derniers temps."
            condition = lambda m, l=ligne: m["buts_marques"] + m["buts_encaisses"] > l
            description = f"derniers matchs au-dessus de {ligne_txt} buts"

        lib_a = (nom_domicile or "Équipe à domicile") if a_role else "Forme récente"
        lib_b = (nom_exterieur or "Équipe à l'extérieur") if b_role else "Forme récente"
        desc_a = description + (" à domicile" if a_role else "")
        desc_b = description + (" à l'extérieur" if b_role else "")
        _ajoute(preuves, _preuve_frequence(lib_a, a_dom, condition, desc_a))
        _ajoute(preuves, _preuve_frequence(lib_b, b_ext, condition, desc_b))
        _ajoute(preuves, _preuve_moyenne(
            "Statistique clé",
            "Moyenne de {valeur:.2f} buts par match sur cet échantillon.",
            a_dom + b_ext,
            lambda m: m["buts_marques"] + m["buts_encaisses"],
        ))
        h2h_condition = lambda x, l=ligne, s=sens: (
            x["buts_a"] + x["buts_b"] < l if s == "under" else x["buts_a"] + x["buts_b"] > l
        )

    elif marche in ("btts_oui", "btts_non"):
        oui = marche == "btts_oui"
        resume = (
            "Les deux équipes ont montré une belle capacité à trouver le chemin des filets ces derniers temps."
            if oui else
            "Les dernières rencontres montrent régulièrement qu'au moins une des deux équipes reste muette."
        )
        condition = lambda m, o=oui: (
            (m["buts_marques"] > 0 and m["buts_encaisses"] > 0)
            if o else not (m["buts_marques"] > 0 and m["buts_encaisses"] > 0)
        )
        description = "derniers matchs avec les deux équipes qui marquent" if oui else "derniers matchs sans les deux équipes qui marquent"
        _ajoute(preuves, _preuve_frequence(nom_domicile or "Équipe à domicile", a_dom, condition, description))
        _ajoute(preuves, _preuve_frequence(nom_exterieur or "Équipe à l'extérieur", b_ext, condition, description))
        h2h_condition = lambda x, o=oui: (
            (x["buts_a"] > 0 and x["buts_b"] > 0)
            if o else not (x["buts_a"] > 0 and x["buts_b"] > 0)
        )

    elif marche in ("double_chance_1X", "1x2_domicile"):
        equipe = nom_domicile or "L'équipe à domicile"
        condition = lambda m: m["buts_marques"] >= m["buts_encaisses"]
        resume = f"{equipe} présente un profil solide à domicile sur les résultats récents."
        desc = "derniers matchs à domicile sans défaite" if a_role else "derniers matchs sans défaite"
        _ajoute(preuves, _preuve_frequence("Forme récente", a_dom, condition, desc))
        h2h_condition = lambda x: x["buts_a"] >= x["buts_b"]

    elif marche in ("double_chance_X2", "1x2_exterieur"):
        equipe = nom_exterieur or "L'équipe à l'extérieur"
        condition = lambda m: m["buts_marques"] >= m["buts_encaisses"]
        resume = f"{equipe} présente un profil solide à l'extérieur sur les résultats récents."
        desc = "derniers matchs à l'extérieur sans défaite" if b_role else "derniers matchs sans défaite"
        _ajoute(preuves, _preuve_frequence("Forme récente", b_ext, condition, desc))
        h2h_condition = lambda x: x["buts_a"] <= x["buts_b"]

    elif marche == "double_chance_12":
        condition = lambda m: m["buts_marques"] != m["buts_encaisses"]
        resume = "Les résultats récents montrent une tendance nette vers une issue avec un vainqueur."
        _ajoute(preuves, _preuve_frequence("Forme récente", a_dom + b_ext, condition, "matchs comparables avec un vainqueur"))
        h2h_condition = lambda x: x["buts_a"] != x["buts_b"]

    elif marche.startswith("buts_equipe_domicile_") or marche.startswith("buts_equipe_exterieur_"):
        info = _ligne(marche)
        if info:
            ligne, sens = info
            role = "domicile" if "domicile" in marche else "exterieur"
            equipe = _sujet_role(role, nom_domicile or "Équipe à domicile", nom_exterieur or "Équipe à l'extérieur")
            matchs = a_dom if role == "domicile" else b_ext
            condition = lambda m, l=ligne, s=sens: m["buts_marques"] > l if s == "over" else m["buts_marques"] < l
            ligne_txt = str(ligne).replace(".", ",")
            resume = f"{equipe} montre une tendance régulière à marquer {('plus de' if sens == 'over' else 'moins de')} {ligne_txt} but(s)."
            contexte = " à domicile" if role == "domicile" and a_role else " à l'extérieur" if role == "exterieur" and b_role else ""
            _ajoute(preuves, _preuve_frequence("Forme récente", matchs, condition, f"derniers matchs{contexte} avec {('plus de' if sens == 'over' else 'moins de')} {ligne_txt} but(s) marqué(s)"))
            _ajoute(preuves, _preuve_moyenne("Statistique clé", f"{equipe} marque en moyenne {{valeur:.2f}} but par match sur cet échantillon.", matchs, lambda m: m["buts_marques"]))

    elif marche.startswith("cage_inviolee_"):
        role = "domicile" if marche.endswith("domicile") else "exterieur"
        equipe = _sujet_role(role, nom_domicile or "Équipe à domicile", nom_exterieur or "Équipe à l'extérieur")
        matchs = a_dom if role == "domicile" else b_ext
        resume = f"{equipe} présente une tendance régulière à préserver sa cage sur ses matchs comparables récents."
        _ajoute(preuves, _preuve_frequence("Forme récente", matchs, lambda m: m["buts_encaisses"] == 0, "derniers matchs avec une cage inviolée"))

    elif marche.startswith("encaisse_"):
        role = "domicile" if marche.endswith("domicile") else "exterieur"
        equipe = _sujet_role(role, nom_domicile or "Équipe à domicile", nom_exterieur or "Équipe à l'extérieur")
        matchs = a_dom if role == "domicile" else b_ext
        resume = f"{equipe} encaisse régulièrement au moins un but sur ses matchs comparables récents."
        _ajoute(preuves, _preuve_frequence("Forme récente", matchs, lambda m: m["buts_encaisses"] > 0, "derniers matchs en encaissant au moins un but"))

    elif marche in ("parite_pair", "parite_impair"):
        pair = marche == "parite_pair"
        condition = lambda m, p=pair: (((m["buts_marques"] + m["buts_encaisses"]) % 2 == 0) == p)
        resume = "Les résultats récents présentent une tendance autour de la parité du nombre de buts."
        _ajoute(preuves, _preuve_frequence("Forme récente", a_dom + b_ext, condition, "matchs comparables avec un nombre de buts pair" if pair else "matchs comparables avec un nombre de buts impair"))
        h2h_condition = lambda x, p=pair: (((x["buts_a"] + x["buts_b"]) % 2 == 0) == p)

    elif marche.startswith("handicap_"):
        m = re.match(r"^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$", marche)
        if m:
            role, ligne = m.group(1), float(m.group(2))
            equipe = _sujet_role(role, nom_domicile or "Équipe à domicile", nom_exterieur or "Équipe à l'extérieur")
            matchs = a_dom if role == "domicile" else b_ext
            condition = lambda x, l=ligne: x["buts_marques"] + l > x["buts_encaisses"]
            ligne_txt = str(ligne).replace(".", ",")
            resume = f"{equipe} présente un profil récent cohérent avec un handicap de {ligne_txt}."
            _ajoute(preuves, _preuve_frequence("Forme récente", matchs, condition, f"derniers matchs couvrant ce handicap de {ligne_txt}"))

    # Le H2H est une preuve séparée : le palier technique seul ne suffit pas.
    # On exige un historique direct réellement disponible et >= 5 rencontres.
    if h2h_condition:
        hf = _h2h_freq(h2h_retenu, h2h_condition)
        if hf:
            preuves.append({
                "titre": "Confrontations directes",
                "texte": f"{hf['occurrences']}/{hf['total']} confrontations directes confirment cette tendance ({hf['pourcentage']} %).",
                "occurrences": hf["occurrences"],
                "total": hf["total"],
                "pourcentage": hf["pourcentage"],
            })

    # Au maximum trois preuves : deux tendances de forme + une H2H/moyenne.
    # On privilégie H2H si disponible, puis les fréquences, puis la moyenne.
    h2h = [p for p in preuves if p.get("titre") == "Confrontations directes"]
    autres = [p for p in preuves if p.get("titre") != "Confrontations directes"]
    frequences = [p for p in autres if "occurrences" in p]
    moyennes = [p for p in autres if "moyenne" in p]
    ordonnees = frequences[:2] + moyennes[:1]
    if h2h:
        ordonnees = frequences[:1] + h2h[:1] + (moyennes[:1] if len(ordonnees) < 2 else [])
    return {
        "resume": resume,
        "preuves": ordonnees[:3],
        "donnees_suffisantes": bool(ordonnees),
    }


def confirmation_historique(marche, matchs_a, matchs_b):
    """Compatibilité avec le moteur : renvoie la première preuve >= 5."""
    resultat = construit_justification(marche, matchs_a, matchs_b)
    for preuve in resultat["preuves"]:
        if "occurrences" in preuve and "total" in preuve:
            return {
                "nb_confirmant": preuve["occurrences"],
                "nb_echantillon": preuve["total"],
                "pourcentage": preuve["pourcentage"],
            }
    return None
