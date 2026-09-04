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
    passé le filtre EV au moment du run -- l'échantillon exploitable pour
    ce calcul grossit donc bien plus vite que les 63 paris qui plafonnaient
    ce calibrage avant le 04/09/2026 (TOUS_MARCHES_EVALUES n'existe que
    pour les matchs traités APRÈS ce correctif -- l'échantillon met
    plusieurs jours à dépasser l'historique pré-correctif).

    Ne modifie JAMAIS calculs.py automatiquement -- affiche seulement une
    recommandation par palier de volume minimum (n_planchers), à appliquer
    manuellement après relecture (voir règle de Patrick : jamais de
    changement sur les tamis sans repasser par un test complet). Un seul
    pari à faible n peut faire beaucoup varier le "meilleur" réglage --
    lire plusieurs nuits de suite avant de changer quoi que ce soit.
    """
    triplets = []
    for jour in historique:
        for m in jour.get("matchs", []):
            score = parse_score(m.get("score"))
            if score is None:
                continue
            buts_dom, buts_ext = score
            for c in (m.get("TOUS_MARCHES_EVALUES") or []):
                resultat = verifie_pari(c.get("marche"), buts_dom, buts_ext)
                if resultat is None:
                    continue
                proba, cote = c.get("probabilite_modele"), c.get("cote_observee")
                if proba is None or not cote:
                    continue
                triplets.append({"gagne": resultat, "proba": proba, "cote": cote})

    resultats = []
    k = k_min
    while k <= k_max + 1e-9:
        seuil = seuil_min
        while seuil <= seuil_max + 1e-9:
            lignes = [t["gagne"] for t in triplets
                      if 1.25 <= t["cote"] <= 1.69
                      and (t["cote"] * ajuste_p(t["proba"], k) - 1) >= seuil]
            if lignes:
                nb = len(lignes)
                taux = sum(lignes) / nb * 100
                resultats.append({"k": round(k, 2), "seuil_ev": round(seuil, 2), "n": nb, "taux_reussite_pct": round(taux, 1)})
            seuil += seuil_pas
        k += k_pas

    recommandations = {}
    for n_min in n_planchers:
        candidats = [r for r in resultats if r["n"] >= n_min]
        if not candidats:
            recommandations[f"n_min_{n_min}"] = None
            continue
        candidats.sort(key=lambda r: (-r["taux_reussite_pct"], -r["n"]))
        recommandations[f"n_min_{n_min}"] = candidats[0]

    return {
        "nb_triplets_disponibles": len(triplets),
        "note": ("Recommandation par palier de volume minimum -- ne descend jamais "
                 "en dessous d'un seuil sans un n suffisant pour être crédible. "
                 "Ne modifie pas calculs.py automatiquement, à appliquer manuellement."),
        "recommandations_par_palier_n": recommandations,
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
