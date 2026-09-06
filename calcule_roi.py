"""
calcule_roi.py -- (03/09/2026) ferme la boucle laissée ouverte par
verification_resultats.py : ce dernier remplit le score final des matchs
archivés, mais rien ne calculait ensuite si le pari recommandé (LISTE_B)
avait réellement gagné, ni le ROI qui en découle. Fait à la main une
première fois pour répondre à Patrick (29 matchs GO avec score connu, 39
paris, 43,6% de réussite, ROI -35,8%) -- ce script automatise exactement
ce calcul pour qu'il n'ait plus à être refait manuellement.

Conçu pour tourner chaque nuit via GitHub Actions, juste après
verification_resultats.py (voir pipeline.yml) -- pure relecture de
historique_pronostics.json, aucun scraping, donc sans risque et rejouable
autant de fois que nécessaire (recalcul complet à chaque fois, pas d'état
à faire évoluer entre deux runs).

Les règles de chaque marché (fonctions "condition" ci-dessous) sont copiées
EXACTEMENT depuis construit_candidats() dans run_pipeline.py -- même
définition de victoire/défaite que celle utilisée par le moteur au moment
de recommander le pari, pas une réinterprétation a posteriori. Si
run_pipeline.py gagne un nouveau type de marché un jour, ce fichier devra
être mis à jour en miroir (aucun moyen de le faire automatiquement sans
sérialiser les lambdas elles-mêmes, ce que JSON ne permet pas).

Usage : python calcule_roi.py
Sortie : roi_dashboard.json (résumé + détail de chaque pari évalué)
"""
import json
import re
import sys

FICHIER_HISTORIQUE = "historique_pronostics.json"
FICHIER_SORTIE = "roi_dashboard.json"


def parse_score(score_str):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", score_str or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


# Chaque entrée : (regex sur le libellé "marche", fonction(x, y, *groupes_regex) -> bool)
# x = buts domicile, y = buts extérieur. Testées dans l'ordre -- les plus
# spécifiques (avec suffixe " - Domicile"/" - Extérieur") AVANT les
# génériques, sinon "Plus de 1.5 buts - Domicile" matcherait le motif
# générique "Plus de N buts" en coupant le suffixe.
_REGLES = [
    (r"^1X2 - 1$", lambda x, y: x > y),
    (r"^1X2 - X$", lambda x, y: x == y),
    (r"^1X2 - 2$", lambda x, y: x < y),
    (r"^Double chance - 1X$", lambda x, y: x >= y),
    (r"^Double chance - 12$", lambda x, y: x != y),
    (r"^Double chance - X2$", lambda x, y: x <= y),
    (r"^BTTS - oui$", lambda x, y: x > 0 and y > 0),
    (r"^BTTS - non$", lambda x, y: x == 0 or y == 0),
    (r"^Handicap (-?\d+(?:\.\d+)?) - Domicile$", lambda x, y, l: (x + float(l)) > y),
    (r"^Handicap (-?\d+(?:\.\d+)?) - Extérieur$", lambda x, y, l: (x + float(l)) < y),
    (r"^Plus de (\d+(?:\.\d+)?) buts - Domicile$", lambda x, y, l: x > float(l)),
    (r"^Moins de (\d+(?:\.\d+)?) buts - Domicile$", lambda x, y, l: not (x > float(l))),
    (r"^Plus de (\d+(?:\.\d+)?) buts - Extérieur$", lambda x, y, l: y > float(l)),
    (r"^Moins de (\d+(?:\.\d+)?) buts - Extérieur$", lambda x, y, l: not (y > float(l))),
    (r"^Plus de (\d+(?:\.\d+)?) buts$", lambda x, y, l: (x + y) > float(l)),
    (r"^Moins de (\d+(?:\.\d+)?) buts$", lambda x, y, l: (x + y) < float(l)),
    (r"^Total buts - pair$", lambda x, y: (x + y) % 2 == 0),
    (r"^Total buts - impair$", lambda x, y: (x + y) % 2 == 1),
    (r"^Cage inviolée - Domicile$", lambda x, y: y == 0),
    (r"^Cage inviolée - Extérieur$", lambda x, y: x == 0),
    (r"^Encaisse au moins 1 but - Domicile$", lambda x, y: y != 0),
    (r"^Encaisse au moins 1 but - Extérieur$", lambda x, y: x != 0),
    (r"^Score exact (\d+)-(\d+)$", lambda x, y, hc, ac: x == int(hc) and y == int(ac)),
    (r"^Nombre exact de buts 6\+$", lambda x, y: (x + y) >= 6),
    (r"^Nombre exact de buts (\d+)$", lambda x, y, n: (x + y) == int(n)),
]
_REGLES_COMPILEES = [(re.compile(motif), fn) for motif, fn in _REGLES]


def verifie_pari(marche, buts_domicile, buts_exterieur):
    """Renvoie True/False si le marché est reconnu, None sinon (marché
    inconnu -- on ne devine jamais, on l'exclut proprement du calcul)."""
    for motif, fn in _REGLES_COMPILEES:
        m = motif.match(marche or "")
        if m:
            return fn(buts_domicile, buts_exterieur, *m.groups())
    return None


def categorie_marche(marche):
    """Regroupement large pour le tableau de bord (ex. 'Plus de 2.5 buts'
    et 'Plus de 3.5 buts' comptent ensemble sous 'Plus de'), sans mélanger
    des familles différentes.

    CORRECTIF (immédiat, avant livraison) : un remplacement aveugle des
    chiffres par "N" transformait "1X2" en "NXN" (les caractères "1" et "2"
    du libellé lui-même, pas une ligne numérique). Les familles sans ligne
    variable (1X2, Double chance, BTTS, Total buts pair/impair, Cage
    inviolée, Encaisse au moins 1 but) gardent donc leur libellé exact ;
    seules celles qui ont vraiment un nombre variable dans le libellé
    (Plus/Moins de, Handicap, Score exact, Nombre exact de buts) sont
    généralisées."""
    if not marche:
        return "inconnu"
    prefixe = marche.split(" - ")[0]
    if prefixe in ("1X2", "Double chance", "BTTS", "Total buts",
                   "Cage inviolée", "Encaisse au moins 1 but"):
        return prefixe
    return re.sub(r"\d+(\.\d+)?", "N", prefixe).strip()


def calcule_dashboard(historique):
    detail = []
    for jour in historique:
        for m in jour.get("matchs", []):
            if m.get("verdict_global") != "GO":
                continue
            score = parse_score(m.get("score"))
            if score is None:
                continue
            buts_dom, buts_ext = score
            for p in (m.get("LISTE_B_liste_finale_apres_correlation") or []):
                resultat = verifie_pari(p.get("marche"), buts_dom, buts_ext)
                if resultat is None:
                    continue
                mise = p.get("mise_pct_bankroll") or 0
                cote = p.get("cote_observee") or 0
                # AJOUT (04/09/2026 soir) -- probabilite_modele est déjà
                # présente dans LISTE_B depuis toujours ; elle n'était juste
                # jamais recopiée ici. Nécessaire pour calcule_calibrage()
                # ci-dessous (mesurer l'écart réussite réelle/probabilité
                # annoncée -- sinon impossible de recalculer K_SHRINKAGE).
                proba = p.get("probabilite_modele")
                gain = mise * (cote - 1) if resultat else -mise
                detail.append({
                    "date": m.get("date"), "domicile": m.get("domicile"),
                    "exterieur": m.get("exterieur"), "competition": m.get("competition"),
                    "score": m.get("score"), "marche": p.get("marche"),
                    "cote_observee": cote, "probabilite_modele": proba, "mise_pct_bankroll": mise,
                    "confiance": m.get("confiance"), "gagne": resultat, "gain_pct_bankroll": gain,
                })

    def resume(lignes):
        nb = len(lignes)
        gagnes = sum(1 for l in lignes if l["gagne"])
        mise_totale = sum(l["mise_pct_bankroll"] for l in lignes)
        gain_net = sum(l["gain_pct_bankroll"] for l in lignes)
        return {
            "nb_paris": nb,
            "nb_gagnes": gagnes,
            "taux_reussite_pct": round(gagnes / nb * 100, 1) if nb else None,
            "mise_totale_pct_bankroll": round(mise_totale, 2),
            "gain_net_pct_bankroll": round(gain_net, 2),
            "roi_pct": round(gain_net / mise_totale * 100, 1) if mise_totale else None,
        }

    par_marche = {}
    for cat in sorted({categorie_marche(l["marche"]) for l in detail}):
        par_marche[cat] = resume([l for l in detail if categorie_marche(l["marche"]) == cat])

    par_confiance = {}
    for conf in sorted({l["confiance"] for l in detail if l["confiance"]}):
        par_confiance[conf] = resume([l for l in detail if l["confiance"] == conf])

    return {
        "global": resume(detail),
        "par_marche": par_marche,
        "par_confiance": par_confiance,
        "detail": detail,
    }


def ajuste_p(p, k):
    return 0.5 + k * (p - 0.5)


def calcule_calibrage(historique, k_min=0.10, k_max=1.00, k_pas=0.02,
                       seuil_min=0.02, seuil_max=0.20, seuil_pas=0.01,
                       n_planchers=(10, 20, 30, 50)):
    """AJOUT (04/09/2026 soir) -- recherche de grille (K_SHRINKAGE, SEUIL_EV_MIN)
    sur TOUS_MARCHES_EVALUES (voir run_pipeline.py), pas seulement les paris
    qui ont déjà été recommandés. Contrairement à calcule_dashboard() ci-
    dessus (qui mesure la performance de CE QUI A ÉTÉ JOUÉ), ceci rejoue
    TOUS les marchés évalués avec une cote réelle, qu'ils aient ou non
    passé le filtre EV au moment du run.

    CORRECTIF 06/09/2026 (Groupe 4, bug #13 -- décision Patrick) --
    PSEUDO-RÉPLICATION : un même match produit couramment 6 à 48 lignes
    dans TOUS_MARCHES_EVALUES (mesuré : moyenne 28 sur les données réelles
    du 06/09). Compter ces lignes comme des observations indépendantes
    gonflait artificiellement la taille d'échantillon apparente d'un
    facteur ~28x -- 2 matchs à 28 marchés chacun (56 lignes) ne sont PAS
    56 observations indépendantes, ce sont 2 événements indépendants.
    Chaque triplet porte désormais le match_id de son match d'origine
    (déjà présent dans historique_pronostics.json, simplement jamais
    recopié ici) pour compter les MATCHS DISTINCTS séparément des
    marchés. Les paliers n_planchers (10/20/30/50, INCHANGÉS -- décision
    explicite de ne pas ajouter de palier plus bas malgré la reconstruction
    de l'historique après la casse de #1) s'appliquent maintenant à
    n_matchs_distincts, jamais à n (nombre de marchés). En dessous de 10
    matchs distincts : aucun calibrage n'est considéré crédible, la
    recommandation du palier est None -- PAS un repli sur un palier
    inférieur, jamais de substitution silencieuse entre niveaux de
    confiance.

    CRITÈRE DE TRI CHANGÉ -- l'ancien tri par taux_reussite_pct seul
    récompensait un réglage qui a simplement eu de la chance sur
    l'échantillon, sans jamais pénaliser une probabilité annoncée trop
    confiante. Le score de Brier (moyenne((probabilité_ajustée-résultat)²),
    plus bas = mieux calibré) devient le premier critère de tri --
    taux_reussite_pct reste calculé et affiché, à titre descriptif
    seulement, plus comme critère de sélection.

    CONTRÔLE TEMPOREL HORS-ÉCHANTILLON -- l'historique est trié par date
    et coupé 70% (le plus ancien, "train") / 30% (le plus récent, "test").
    La recherche de grille ne tourne que sur "train". Le couple (k, seuil)
    ainsi choisi est ensuite REJOUÉ tel quel sur "test" (jamais pour en
    choisir un autre -- ça reviendrait à évaluer sur les mêmes données que
    l'entraînement) uniquement pour affichage informatif. Avec le faible
    volume actuel, ce contrôle sera d'abord peu puissant -- affiché comme
    None ("pas assez de données") tant qu'il n'atteint pas lui-même 10
    matchs distincts, jamais une valeur fabriquée sur un échantillon trop
    petit pour être lue.

    Ne modifie JAMAIS calculs.py automatiquement -- affiche seulement une
    recommandation par palier de volume minimum, à appliquer manuellement
    après relecture (K_SHRINKAGE=0.48 reste la valeur en production tant
    qu'aucun recalibrage n'est validé et appliqué à la main -- voir
    calculs.py, jamais changé par ce script)."""

    def _extrait_triplets(jours):
        triplets = []
        nb_non_resolus_definitif = 0
        for jour in jours:
            for m in jour.get("matchs", []):
                if m.get("score_statut") == "non_resolu_definitif":
                    nb_non_resolus_definitif += 1
                    continue
                score = parse_score(m.get("score"))
                if score is None:
                    continue
                buts_dom, buts_ext = score
                match_id = m.get("match_id") or f"{m.get('domicile')}||{m.get('exterieur')}||{m.get('date')}"
                for c in (m.get("TOUS_MARCHES_EVALUES") or []):
                    resultat = verifie_pari(c.get("marche"), buts_dom, buts_ext)
                    if resultat is None:
                        continue
                    proba, cote = c.get("probabilite_modele"), c.get("cote_observee")
                    if proba is None or not cote:
                        continue
                    triplets.append({"gagne": resultat, "proba": proba, "cote": cote, "match_id": match_id})
        return triplets, nb_non_resolus_definitif

    def _grille(triplets):
        resultats = []
        k = k_min
        while k <= k_max + 1e-9:
            seuil = seuil_min
            while seuil <= seuil_max + 1e-9:
                lignes = [t for t in triplets
                          if 1.25 <= t["cote"] <= 1.69
                          and (t["cote"] * ajuste_p(t["proba"], k) - 1) >= seuil]
                if lignes:
                    nb = len(lignes)
                    nb_matchs_distincts = len({t["match_id"] for t in lignes})
                    taux = sum(t["gagne"] for t in lignes) / nb * 100
                    brier = sum((ajuste_p(t["proba"], k) - (1 if t["gagne"] else 0)) ** 2 for t in lignes) / nb
                    resultats.append({
                        "k": round(k, 2), "seuil_ev": round(seuil, 2),
                        "n": nb, "n_matchs_distincts": nb_matchs_distincts,
                        "taux_reussite_pct": round(taux, 1), "brier_score": round(brier, 4),
                    })
                seuil += seuil_pas
            k += k_pas
        return resultats

    def _meilleur_par_palier(resultats, n_planchers):
        recommandations = {}
        for n_min in n_planchers:
            candidats = [r for r in resultats if r["n_matchs_distincts"] >= n_min]
            if not candidats:
                recommandations[f"n_min_{n_min}"] = None
                continue
            # Tri par score de Brier croissant (mieux calibré en premier),
            # puis par nb de matchs distincts décroissant à égalité de Brier.
            candidats.sort(key=lambda r: (r["brier_score"], -r["n_matchs_distincts"]))
            recommandations[f"n_min_{n_min}"] = candidats[0]
        return recommandations

    jours_tries = sorted(historique, key=lambda j: j.get("date") or "")
    coupure = int(len(jours_tries) * 0.7)
    jours_train, jours_test = jours_tries[:coupure], jours_tries[coupure:]

    triplets_train, nb_non_resolus_train = _extrait_triplets(jours_train)
    triplets_test, nb_non_resolus_test = _extrait_triplets(jours_test)

    resultats_train = _grille(triplets_train)
    recommandations = _meilleur_par_palier(resultats_train, n_planchers)

    # Contrôle hors-échantillon : rejoue le (k, seuil) choisi sur "test",
    # jamais pour en choisir un autre. Affiché seulement si "test" atteint
    # lui-même 10 matchs distincts pour ce (k, seuil) précis -- sinon None.
    controle_hors_echantillon = {}
    for cle, choix in recommandations.items():
        if choix is None:
            controle_hors_echantillon[cle] = None
            continue
        k, seuil = choix["k"], choix["seuil_ev"]
        lignes_test = [t for t in triplets_test
                       if 1.25 <= t["cote"] <= 1.69
                       and (t["cote"] * ajuste_p(t["proba"], k) - 1) >= seuil]
        nb_matchs_test = len({t["match_id"] for t in lignes_test})
        if nb_matchs_test < 10:
            controle_hors_echantillon[cle] = None
            continue
        nb = len(lignes_test)
        taux = sum(t["gagne"] for t in lignes_test) / nb * 100
        brier = sum((ajuste_p(t["proba"], k) - (1 if t["gagne"] else 0)) ** 2 for t in lignes_test) / nb
        controle_hors_echantillon[cle] = {
            "n": nb, "n_matchs_distincts": nb_matchs_test,
            "taux_reussite_pct": round(taux, 1), "brier_score": round(brier, 4),
        }

    return {
        "nb_triplets_disponibles": len(triplets_train) + len(triplets_test),
        "nb_matchs_distincts_train": len({t["match_id"] for t in triplets_train}),
        "nb_matchs_distincts_test": len({t["match_id"] for t in triplets_test}),
        "nb_matchs_non_resolus_definitif": nb_non_resolus_train + nb_non_resolus_test,
        "note": ("Recommandation par palier de volume minimum de MATCHS DISTINCTS "
                 "(pas de marchés) -- en dessous de 10, aucun calibrage n'est "
                 "considéré crédible (None), jamais un repli sur un palier "
                 "inférieur. Tri par score de Brier (calibration), pas par taux "
                 "de réussite brut. Ne modifie pas calculs.py automatiquement, "
                 "à appliquer manuellement."),
        "recommandations_par_palier_n": recommandations,
        "controle_hors_echantillon_par_palier_n": controle_hors_echantillon,
    }


def main():
    try:
        with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
            historique = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERREUR : {FICHIER_HISTORIQUE} illisible ({e}).", file=sys.stderr)
        sys.exit(1)

    dashboard = calcule_dashboard(historique)
    dashboard["calibrage_k_shrinkage"] = calcule_calibrage(historique)
    dashboard["genere_le"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    g = dashboard["global"]
    print(f"{FICHIER_SORTIE} écrit : {g['nb_paris']} pari(s) évalué(s), "
          f"{g['nb_gagnes']} gagné(s) ({g['taux_reussite_pct']}%), "
          f"ROI {g['roi_pct']}%.")


if __name__ == "__main__":
    main()
