"""Justifications publiques du moteur ARCHETYPE.

Ce module intervient APRES la décision du moteur. Il n'effectue aucune
sélection, aucun filtrage et aucun nouveau calcul de probabilité/EDV.

Principe de traçabilité :
- la raison du choix provient des résultats réels de la convergence et de la
  cascade du sélecteur ;
- les preuves historiques proviennent uniquement des fenêtres déjà chargées ;
- une fréquence historique n'est publiée que sur au moins 5 matchs et à 60 %
  ou plus ;
- un échantillon de 1 à 4 matchs n'est jamais présenté comme une preuve ;
- si aucune preuve historique assez large n'est disponible, on explique la
  sélection par les éléments décisionnels réellement disponibles, sans phrase
  générique laissant croire qu'une statistique manque alors que le modèle a
  sélectionné le marché pour d'autres raisons.
"""

from __future__ import annotations

import re
from statistics import mean

MIN_MATCHS_PREUVE = 5
MAX_MATCHS_AFFICHAGE = 8
MIN_H2H_PREUVE = 5
MIN_POURCENTAGE_PREUVE = 60.0


def _propres(matchs):
    out = []
    for m in matchs or []:
        if not isinstance(m, dict):
            continue
        if not isinstance(m.get("buts_marques"), (int, float)):
            continue
        if not isinstance(m.get("buts_encaisses"), (int, float)):
            continue
        out.append(m)
    return out


def _role(matchs, domicile):
    return [m for m in _propres(matchs) if m.get("domicile") is domicile]


def _echantillon(matchs_role, matchs_tous):
    """Privilégie le rôle du match si >=5, sinon l'historique équipe.

    Le fallback est explicitement décrit comme forme récente générale.
    Aucun échantillon <5 n'est publié comme preuve de fréquence.
    """
    role = _propres(matchs_role)
    if len(role) >= MIN_MATCHS_PREUVE:
        return role[-MAX_MATCHS_AFFICHAGE:], True
    tous = _propres(matchs_tous)
    if len(tous) >= MIN_MATCHS_PREUVE:
        return tous[-MAX_MATCHS_AFFICHAGE:], False
    return [], False


def _pct(n, d):
    return round(n * 100.0 / d, 1) if d else None


def _preuve_frequence(titre, matchs, condition, texte):
    matchs = _propres(matchs)
    if len(matchs) < MIN_MATCHS_PREUVE:
        return None
    ok = sum(1 for m in matchs if condition(m))
    pct = _pct(ok, len(matchs))
    if pct is None or pct < MIN_POURCENTAGE_PREUVE:
        return None
    return {
        "titre": titre,
        "texte": f"{ok}/{len(matchs)} {texte} ({pct:.1f} %).",
        "occurrences": ok,
        "total": len(matchs),
        "pourcentage": pct,
        "force": "preuve",
    }


def _preuve_moyenne(titre, texte, matchs, fonction):
    matchs = _propres(matchs)
    if len(matchs) < MIN_MATCHS_PREUVE:
        return None
    valeur = round(mean(fonction(m) for m in matchs), 2)
    return {
        "titre": titre,
        "texte": texte.format(valeur=valeur),
        "moyenne": valeur,
        "total": len(matchs),
        "force": "statistique",
    }


def _h2h_propres(confrontations):
    return [
        x for x in confrontations or []
        if isinstance(x, dict)
        and isinstance(x.get("buts_a"), (int, float))
        and isinstance(x.get("buts_b"), (int, float))
    ]


def _preuve_h2h(confrontations, condition):
    c = _h2h_propres(confrontations)
    if len(c) < MIN_H2H_PREUVE:
        return None
    ok = sum(1 for x in c if condition(x))
    pct = _pct(ok, len(c))
    if pct is None or pct < MIN_POURCENTAGE_PREUVE:
        return None
    return {
        "titre": "Confrontations directes",
        "texte": f"{ok}/{len(c)} confrontations directes confirment cette tendance ({pct:.1f} %).",
        "occurrences": ok,
        "total": len(c),
        "pourcentage": pct,
        "force": "preuve",
    }


def _parse_total(marche):
    # Formats acceptés : total_over_2.5, total_under_3.5,
    # over_under_total_2.5_over/under (compatibilité historique).
    m = re.match(r"^total_(over|under)_(-?\d+(?:\.\d+)?)$", marche or "")
    if m:
        return float(m.group(2)), m.group(1)
    m = re.match(r"^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$", marche or "")
    if m:
        return float(m.group(1)), m.group(2)
    m = re.match(r"^(over|under)_(-?\d+(?:\.\d+)?)$", marche or "")
    if m:
        return float(m.group(2)), m.group(1)
    return None


def _parse_team_goals(marche):
    m = re.match(
        r"^buts_equipe_(domicile|exterieur)_(over|under)_(-?\d+(?:\.\d+)?)$",
        marche or "",
    )
    if not m:
        return None
    return m.group(1), m.group(2), float(m.group(3))


def _parse_handicap(marche):
    m = re.match(r"^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$", marche or "")
    if not m:
        return None
    return m.group(1), float(m.group(2))


def construit_justification(marche, matchs_a, matchs_b, h2h=None,
                             nom_domicile="", nom_exterieur="",
                             contexte_selection=None):
    """Produit le résumé et les preuves publiques d'un marché DÉJÀ sélectionné."""
    a = _propres(matchs_a)
    b = _propres(matchs_b)
    a_role, a_est_role = _echantillon(_role(a, True), a)
    b_role, b_est_role = _echantillon(_role(b, False), b)
    h2h = _h2h_propres(h2h)

    preuves = []
    resume = None
    h2h_condition = None

    total = _parse_total(marche)
    if total:
        ligne, sens = total
        txt = str(ligne).replace(".", ",")
        if sens == "under":
            resume = f"Ce match devrait rester relativement fermé et ne devrait pas dépasser {txt} buts."
            condition = lambda m, l=ligne: m["buts_marques"] + m["buts_encaisses"] < l
            desc = f"derniers matchs sous {txt} buts"
        else:
            resume = "Les deux équipes ont montré une belle capacité à trouver le chemin des filets ces derniers temps."
            condition = lambda m, l=ligne: m["buts_marques"] + m["buts_encaisses"] > l
            desc = f"derniers matchs au-dessus de {txt} buts"
        _ajoute_preuve_total(preuves, nom_domicile, a_role, a_est_role, condition, desc, "à domicile")
        _ajoute_preuve_total(preuves, nom_exterieur, b_role, b_est_role, condition, desc, "à l'extérieur")
        echantillon_total = a_role + b_role
        if len(echantillon_total) >= MIN_MATCHS_PREUVE:
            moyenne_total = mean(m["buts_marques"] + m["buts_encaisses"] for m in echantillon_total)
            moyenne_coherente = moyenne_total < ligne if sens == "under" else moyenne_total > ligne
            if moyenne_coherente:
                _ajoute(preuves, _preuve_moyenne(
                    "Statistiques clés",
                    "Ces matchs produisent en moyenne {valeur:.2f} buts.",
                    echantillon_total,
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
        condition = lambda m, o=oui: ((m["buts_marques"] > 0 and m["buts_encaisses"] > 0) if o else not (m["buts_marques"] > 0 and m["buts_encaisses"] > 0))
        desc = "derniers matchs avec les deux équipes qui marquent" if oui else "derniers matchs sans les deux équipes qui marquent"
        _ajoute(preuves, _preuve_frequence("Équipes en forme", a_role, condition, desc + (" à domicile" if a_est_role else "")))
        _ajoute(preuves, _preuve_frequence("Équipes en forme", b_role, condition, desc + (" à l'extérieur" if b_est_role else "")))
        h2h_condition = lambda x, o=oui: ((x["buts_a"] > 0 and x["buts_b"] > 0) if o else not (x["buts_a"] > 0 and x["buts_b"] > 0))

    elif marche in ("double_chance_1X", "1x2_domicile"):
        equipe = nom_domicile or "L'équipe à domicile"
        condition = lambda m: m["buts_marques"] >= m["buts_encaisses"]
        resume = f"{equipe} présente un profil solide sur ses résultats récents."
        _ajoute(preuves, _preuve_frequence("Équipes en forme", a_role, condition, "derniers matchs sans défaite" + (" à domicile" if a_est_role else "")))
        h2h_condition = lambda x: x["buts_a"] >= x["buts_b"]

    elif marche in ("double_chance_X2", "1x2_exterieur"):
        equipe = nom_exterieur or "L'équipe à l'extérieur"
        condition = lambda m: m["buts_marques"] >= m["buts_encaisses"]
        resume = f"{equipe} présente un profil solide sur ses résultats récents."
        _ajoute(preuves, _preuve_frequence("Équipes en forme", b_role, condition, "derniers matchs sans défaite" + (" à l'extérieur" if b_est_role else "")))
        h2h_condition = lambda x: x["buts_a"] <= x["buts_b"]

    elif marche == "double_chance_12":
        condition = lambda m: m["buts_marques"] != m["buts_encaisses"]
        resume = "Les résultats récents présentent une tendance vers une issue avec un vainqueur."
        _ajoute(preuves, _preuve_frequence("Équipes en forme", a_role + b_role, condition, "matchs comparables avec un vainqueur"))
        h2h_condition = lambda x: x["buts_a"] != x["buts_b"]

    elif marche.startswith("1x2_nul"):
        condition = lambda m: m["buts_marques"] == m["buts_encaisses"]
        resume = "Les résultats récents montrent la fréquence des matchs nuls observés dans les historiques disponibles."
        _ajoute(preuves, _preuve_frequence("Équipes en forme", a_role + b_role, condition, "matchs comparables terminés à égalité"))
        h2h_condition = lambda x: x["buts_a"] == x["buts_b"]

    else:
        team = _parse_team_goals(marche)
        if team:
            role, sens, ligne = team
            equipe = nom_domicile if role == "domicile" else nom_exterieur
            equipe = equipe or ("L'équipe à domicile" if role == "domicile" else "L'équipe à l'extérieur")
            matchs = a_role if role == "domicile" else b_role
            role_ok = a_est_role if role == "domicile" else b_est_role
            comparatif = "plus de" if sens == "over" else "moins de"
            txt = str(ligne).replace(".", ",")
            condition = lambda m, l=ligne, s=sens: m["buts_marques"] > l if s == "over" else m["buts_marques"] < l
            resume = f"{equipe} montre une tendance récente à marquer {comparatif} {txt} but(s)."
            contexte = " à domicile" if role == "domicile" and role_ok else " à l'extérieur" if role == "exterieur" and role_ok else ""
            _ajoute(preuves, _preuve_frequence("Équipes en forme", matchs, condition, f"derniers matchs{contexte} avec {comparatif} {txt} but(s) marqué(s)"))
            _ajoute(preuves, _preuve_moyenne("Statistiques clés", f"{equipe} marque en moyenne {{valeur:.2f}} but par match sur cet échantillon.", matchs, lambda m: m["buts_marques"]))

        elif marche.startswith("cage_inviolee_"):
            role = "domicile" if marche.endswith("domicile") else "exterieur"
            equipe = nom_domicile if role == "domicile" else nom_exterieur
            matchs = a_role if role == "domicile" else b_role
            resume = f"{equipe or 'L’équipe'} présente une tendance récente à préserver sa cage."
            _ajoute(preuves, _preuve_frequence("Équipes en forme", matchs, lambda m: m["buts_encaisses"] == 0, "derniers matchs avec une cage inviolée"))

        elif marche.startswith("encaisse_"):
            role = "domicile" if marche.endswith("domicile") else "exterieur"
            equipe = nom_domicile if role == "domicile" else nom_exterieur
            matchs = a_role if role == "domicile" else b_role
            resume = f"{equipe or 'L’équipe'} encaisse régulièrement au moins un but sur ses matchs récents."
            _ajoute(preuves, _preuve_frequence("Équipes en forme", matchs, lambda m: m["buts_encaisses"] > 0, "derniers matchs en encaissant au moins un but"))

        elif marche in ("parite_pair", "parite_impair"):
            pair = marche == "parite_pair"
            condition = lambda m, p=pair: (((m["buts_marques"] + m["buts_encaisses"]) % 2 == 0) == p)
            resume = "Les résultats récents présentent une tendance autour de la parité du nombre de buts."
            texte = "matchs comparables avec un nombre de buts pair" if pair else "matchs comparables avec un nombre de buts impair"
            _ajoute(preuves, _preuve_frequence("Équipes en forme", a_role + b_role, condition, texte))
            h2h_condition = lambda x, p=pair: (((x["buts_a"] + x["buts_b"]) % 2 == 0) == p)

        else:
            handicap = _parse_handicap(marche)
            if handicap:
                role, ligne = handicap
                equipe = nom_domicile if role == "domicile" else nom_exterieur
                matchs = a_role if role == "domicile" else b_role
                role_ok = a_est_role if role == "domicile" else b_est_role
                condition = lambda x, l=ligne: x["buts_marques"] + l > x["buts_encaisses"]
                txt = str(ligne).replace(".", ",")
                resume = f"{equipe or 'L’équipe'} présente un profil récent cohérent avec un handicap de {txt}."
                if ligne == -0.5:
                    desc = "derniers matchs avec une victoire"
                elif ligne == 0.5:
                    desc = "derniers matchs sans défaite"
                elif ligne < 0:
                    marge = int(abs(ligne) + 0.5)
                    desc = f"derniers matchs gagnés avec au moins {marge} buts d'écart"
                else:
                    marge = int(ligne + 0.5)
                    desc = f"derniers matchs compatibles avec un avantage de {txt} but(s)"
                if role_ok:
                    desc += " à domicile" if role == "domicile" else " à l'extérieur"
                _ajoute(preuves, _preuve_frequence("Équipes en forme", matchs, condition, desc))
                _ajoute(preuves, _preuve_moyenne("Statistiques clés", f"{equipe or 'Cette équipe'} marque en moyenne {{valeur:.2f}} but par match sur cet échantillon.", matchs, lambda m: m["buts_marques"]))
                h2h_condition = lambda x, l=ligne: x["buts_a"] + l > x["buts_b"]

    if h2h_condition:
        _ajoute(preuves, _preuve_h2h(h2h, h2h_condition))

    # Ordre public proche du prototype : forme -> H2H -> statistique clé.
    h2h_p = [p for p in preuves if p.get("titre") == "Confrontations directes"]
    forme = [p for p in preuves if p.get("titre") == "Équipes en forme"]
    stats = [p for p in preuves if p.get("titre") == "Statistiques clés"]
    ordonnees = (forme[:2] + h2h_p[:1] + stats[:1])[:3]
    if h2h_p:
        ordonnees = (forme[:1] + h2h_p[:1] + stats[:1])[:3]

    return {
        "resume": resume,
        "preuves": ordonnees,
        "donnees_suffisantes": bool(ordonnees),
    }


def _ajoute(preuves, preuve):
    if preuve:
        preuves.append(preuve)


def _ajoute_preuve_total(preuves, nom, matchs, role_ok, condition, desc, contexte):
    if not matchs:
        return
    texte = desc + (contexte if role_ok else "")
    _ajoute(preuves, _preuve_frequence("Équipes en forme", matchs, condition, texte))


def construit_raison_selection(candidat, rang, candidats, diagnostic):
    """Explique la décision avec les résultats réels déjà calculés.

    Aucun nouveau classement n'est effectué ici. Les phrases sont construites
    à partir de la trace du filtre et des attributs du candidat déjà sélectionné.
    """
    if not isinstance(candidat, dict):
        return None

    filtre = (diagnostic or {}).get("filtre") or {}
    par_scenario = filtre.get("resultats_par_scenario") or {}
    valeurs = []
    for nom in ("offensif", "defensif", "contextuel", "global"):
        r = par_scenario.get(nom) or {}
        p = r.get("probabilite_centrale")
        if isinstance(p, (int, float)):
            valeurs.append(float(p))

    morceaux = []
    if len(valeurs) == 4:
        mini, maxi = min(valeurs), max(valeurs)
        morceaux.append(
            f"Les quatre scénarios du modèle convergent vers ce marché, avec des estimations comprises entre {mini * 100:.0f} % et {maxi * 100:.0f} %."
        )
    elif valeurs:
        morceaux.append(
            f"Les scénarios disponibles du modèle convergent vers ce marché, avec des estimations comprises entre {min(valeurs) * 100:.0f} % et {max(valeurs) * 100:.0f} %."
        )
    else:
        morceaux.append("Le marché a été retenu sur la base des contrôles décisionnels réellement disponibles.")

    if candidat.get("robustesse") == "STABLE":
        morceaux.append("La dispersion entre les scénarios reste dans la zone de stabilité du modèle.")

    niveau = candidat.get("niveau")
    lib_niveau = {
        "PREMIUM": "le niveau d'éligibilité le plus élevé",
        "TRES_FORT": "un niveau d'éligibilité très fort",
        "FORT": "un niveau d'éligibilité fort",
        "ELIGIBLE": "un niveau d'éligibilité éligible",
        "ELIGIBLE_PLUS": "un niveau d'éligibilité suffisant",
    }.get(niveau)
    if lib_niveau:
        morceaux.append(f"Le marché atteint {lib_niveau}.")

    # Pour P2/P3, la diversification est une raison réelle de rang.
    if rang == "P2":
        morceaux.append("Il constitue ensuite la meilleure option restante après la diversification imposée entre familles et groupes d'exposition.")
    elif rang == "P3":
        morceaux.append("Il complète les deux premières sélections avec une famille et une exposition distinctes, tout en restant éligible.")
    elif rang == "P1":
        autres = [c for c in (candidats or []) if c is not candidat and c.get("marche") != candidat.get("marche")]
        if not autres:
            morceaux.append("Aucun autre marché éligible ne devait être départagé sur ce match.")
        else:
            # Reproduit la cascade existante uniquement pour identifier le premier
            # critère qui distingue le candidat ; cela n'altère aucune décision.
            try:
                from archetype_model.signals import selector as sel
                criteres = [
                    ("niveau", lambda c: sel.ORDRE_NIVEAU.get(c.get("niveau"), -1)),
                    ("robustesse", lambda c: sel.ORDRE_ROBUSTESSE.get(c.get("robustesse"), 0)),
                    ("signal", lambda c: (sel.ORDRE_DIRECTION_SIGNAL.get(c.get("signal_direction"), -1), c.get("signal_frequence") if c.get("signal_frequence") is not None else float("-inf"))),
                    ("H2H", lambda c: sel.ORDRE_PALIER_H2H.get(c.get("h2h_palier"), 0)),
                    ("EDV", lambda c: c.get("edv") if isinstance(c.get("edv"), (int, float)) else float("-inf")),
                ]
                for nom, fn in criteres:
                    valeur = fn(candidat)
                    autres_valeurs = [fn(c) for c in autres]
                    if autres_valeurs and valeur > max(autres_valeurs):
                        if nom == "niveau":
                            morceaux.append("Son niveau d'éligibilité supérieur l'a placé devant les autres marchés.")
                        elif nom == "robustesse":
                            morceaux.append("Sa stabilité l'a départagé à ce stade de la sélection.")
                        elif nom == "signal":
                            morceaux.append("Son signal statistique l'a départagé à ce stade de la sélection.")
                        elif nom == "H2H":
                            morceaux.append("La qualité des confrontations directes l'a départagé à ce stade de la sélection.")
                        elif nom == "EDV":
                            morceaux.append("À critères précédents équivalents, son gain potentiel supérieur l'a départagé.")
                        break
            except Exception:
                # La justification ne doit jamais bloquer le moteur si un module
                # d'affichage technique devient indisponible.
                pass

    return {
        "texte": " ".join(morceaux),
        "scenarios_valides": len(valeurs),
        "scenarios_total": 4,
        "probabilite_min": min(valeurs) if valeurs else None,
        "probabilite_max": max(valeurs) if valeurs else None,
    }


def enrichit_selection(resultat, nom_domicile="", nom_exterieur="", h2h=None):
    """Ajoute les justifications aux P1/P2/P3 après la sélection.

    Fonction appelée par le pipeline après `selector.selectionner()`.
    La structure et le contenu décisionnels du résultat restent inchangés.
    """
    if not isinstance(resultat, dict) or resultat.get("statut") != "OK":
        return resultat

    selection = resultat.get("selection") or {}
    candidats = resultat.get("candidats_dedupliques") or []
    diagnostics = {
        d.get("marche"): d for d in (resultat.get("diagnostics") or []) if d.get("marche")
    }
    fenetres = resultat.get("fenetres") or {}
    matchs_a = (fenetres.get("A") or {}).get("matchs_retenus") or []
    matchs_b = (fenetres.get("B") or {}).get("matchs_retenus") or []
    h2h = _h2h_propres(h2h)

    for rang in ("P1", "P2", "P3"):
        candidat = selection.get(rang)
        if not isinstance(candidat, dict):
            continue
        marche = candidat.get("marche")
        diagnostic = diagnostics.get(marche, {})
        candidat["justification_selection"] = construit_raison_selection(
            candidat, rang, candidats, diagnostic
        )
        candidat["justification"] = construit_justification(
            marche,
            matchs_a,
            matchs_b,
            h2h=h2h,
            nom_domicile=nom_domicile,
            nom_exterieur=nom_exterieur,
        )

    return resultat


def confirmation_historique(marche, matchs_a, matchs_b):
    """Compatibilité avec les appels historiques du projet."""
    resultat = construit_justification(marche, matchs_a, matchs_b)
    for preuve in resultat.get("preuves", []):
        if "occurrences" in preuve and "total" in preuve:
            return {
                "nb_confirmant": preuve["occurrences"],
                "nb_echantillon": preuve["total"],
                "pourcentage": preuve.get("pourcentage"),
            }
    return None
