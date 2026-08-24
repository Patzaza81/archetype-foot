"""
run_pipeline.py — Orchestrateur quotidien. TOUT À LA RACINE DU DÉPÔT,
volontairement — aucun dossier pipeline/ nécessaire. Seule contrainte réelle
de GitHub : .github/workflows/pipeline.yml doit rester à cet emplacement
précis, ça ne se discute pas. Tout le reste vit à côté de index.html, comme
les fichiers déjà uploadés avec succès.
Écrit data.json à la racine — lu directement par index.html/script.js.

BRANCHEMENT GF/GA (25/08) : utilise recupere_classement_du_match, universel
pour tous les championnats (voir scraper_details.py). Classement Saison
Régulière combiné, pas de split domicile/extérieur — approximation V1
assumée, à ajuster si les résultats le justifient. Un fetch réseau
supplémentaire par match (l'onglet ?p=classement de son URL).
"""
import json
from scraper import scrape_programme_du_jour
from scraper_details import recupere_classement_du_match, trouve_equipe_dans_classement
import calculs


def construit_signaux(matchs_bruts):
    resultats = []
    # Cache par compétition (pas par match — l'URL de match est unique à
    # chaque match, indexer dessus n'apporterait aucune réutilisation).
    # Plusieurs matchs de la même compétition le même jour partagent le
    # même classement -> un seul fetch au lieu d'un par match.
    cache_classement = {}

    for m in matchs_bruts:
        url_match = m.get("url_match")
        nom_domicile = m.get("domicile")
        nom_exterieur = m.get("exterieur")
        competition = m.get("competition")

        gf_home = ga_home = gf_away = ga_away = None

        if url_match and nom_domicile and nom_exterieur:
            try:
                cle_cache = competition or url_match  # repli si compétition absente
                if cle_cache not in cache_classement:
                    cache_classement[cle_cache] = recupere_classement_du_match(url_match)
                classement = cache_classement[cle_cache]

                ligne_domicile = trouve_equipe_dans_classement(classement, nom_domicile)
                ligne_exterieur = trouve_equipe_dans_classement(classement, nom_exterieur)

                # j == 0 (aucun match joué) -> pas de moyenne calculable, on
                # laisse None plutôt que de diviser par zéro ou d'inventer
                # une valeur par défaut.
                if ligne_domicile and ligne_domicile["j"] > 0:
                    gf_home = ligne_domicile["bp"] / ligne_domicile["j"]
                    ga_home = ligne_domicile["bc"] / ligne_domicile["j"]
                if ligne_exterieur and ligne_exterieur["j"] > 0:
                    gf_away = ligne_exterieur["bp"] / ligne_exterieur["j"]
                    ga_away = ligne_exterieur["bc"] / ligne_exterieur["j"]
            except Exception as e:
                # Best-effort assumé : un échec sur un match ne doit jamais
                # faire planter tout le pipeline. On garde traite=False et
                # on note l'erreur pour diagnostic, sans deviner de valeur.
                m["erreur_classement"] = str(e)

        cote_1 = m.get("cote_1")
        signal = {**m, "traite": False}

        if None not in (gf_home, ga_home, gf_away, ga_away):
            lam = calculs.calcule_lambda(gf_home, ga_home, gf_away, ga_away)
            matrice = calculs.matrice_poisson_dixon_coles(lam["lambda_home"], lam["lambda_away"])
            proba_1 = calculs.probabilite_marche(matrice, lambda x, y: x > y)
            signal["lambda"] = lam
            signal["probabilite_victoire_domicile"] = proba_1
            signal["traite"] = True
            if cote_1:
                signal["ev_victoire_domicile"] = calculs.calcule_ev(proba_1, cote_1)
                signal["mise_kelly_victoire_domicile"] = calculs.kelly_stake(proba_1, cote_1)
                signal["standout"] = calculs.est_standout(proba_1, cote_1)
            signal["marches"] = calculs.construit_probabilites_marches(matrice)

        resultats.append(signal)
    return resultats


def main():
    matchs = scrape_programme_du_jour(max_matchs=20)
    signaux = construit_signaux(matchs)
    sortie = {
        "genere_le": None,
        "nb_matchs": len(signaux),
        "matchs": signaux,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, indent=2, ensure_ascii=False)
    print(f"Pipeline terminé : {len(signaux)} matchs -> data.json")


if __name__ == "__main__":
    main()
