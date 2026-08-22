"""
run_pipeline.py — Orchestrateur quotidien. TOUT À LA RACINE DU DÉPÔT,
volontairement — aucun dossier pipeline/ nécessaire. Seule contrainte réelle
de GitHub : .github/workflows/pipeline.yml doit rester à cet emplacement
précis, ça ne se discute pas. Tout le reste vit à côté de index.html, comme
les fichiers déjà uploadés avec succès.

Écrit data.json à la racine — lu directement par index.html/script.js.
"""

import json

from scraper import scrape_programme_du_jour
import calculs


def construit_signaux(matchs_bruts):
    resultats = []
    for m in matchs_bruts:
        # TODO : remplacer par les vraies stats GF/GA dom/ext du match
        # (scraper_besoccer.py fait ce travail, reste à le brancher ici
        # match par match une fois la Phase 2 validée par le diagnostic CI).
        gf_home = m.get("gf_home_domicile")
        ga_home = m.get("ga_home_domicile")
        gf_away = m.get("gf_away_exterieur")
        ga_away = m.get("ga_away_exterieur")
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
