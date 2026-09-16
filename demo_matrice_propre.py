"""
demo_matrice_propre.py -- refait la demonstration Atl. Madrid vs Osasuna
avec des donnees GARANTIES saison en cours uniquement, via le VRAI
chemin de production (data.loader + data.validation), jamais via
cache_equipes.json (qui melange les saisons, deja identifie comme
probleme par Patrick le 16/09/2026).

A executer depuis la racine du repo, LA OU matchendirect.fr est
accessible (pas dans le bac a sable Claude) :

    python3 demo_matrice_propre.py

Affiche les profils domicile/exterieur reels + les signaux de la
matrice de croisement, avec le nombre de matchs REELLEMENT disponibles
cette saison (probablement INSUFFISANT vu qu'on n'en est qu'a la
4e-5e journee de LaLiga 2026-27 -- c'est attendu, pas une erreur).
"""

import sys
sys.path.insert(0, ".")

from archetype_model.data import loader, validation
from archetype_model.statistics import profil_equipe
from archetype_model.signals import matrice_croisement

URL_DOMICILE = "https://www.matchendirect.fr/equipe/atl-madrid_4ku8o6uf87yd8iecdalipo6wd.html"
NOM_DOMICILE = "Atl. Madrid"
URL_EXTERIEUR = "https://www.matchendirect.fr/equipe/osasuna_2l0ldgiwsgb8d6y3z0sfgjzyj.html"
NOM_EXTERIEUR = "Osasuna"
COMPETITION = "espagne : laliga"


def main():
    print(f"Recuperation de l'historique SAISON EN COURS UNIQUEMENT (aucun repli)...")

    historique_domicile = loader.recupere_historique_saison_courante(URL_DOMICILE, COMPETITION, NOM_DOMICILE)
    historique_exterieur = loader.recupere_historique_saison_courante(URL_EXTERIEUR, COMPETITION, NOM_EXTERIEUR)

    fenetre_dom = validation.classifie_fenetre(historique_domicile)
    fenetre_ext = validation.classifie_fenetre(historique_exterieur)

    print(f"\n{NOM_DOMICILE} : {fenetre_dom['n_brut']} match(s) total cette saison "
          f"dans cette competition -- statut {fenetre_dom['statut']}")
    print(f"{NOM_EXTERIEUR} : {fenetre_ext['n_brut']} match(s) total cette saison "
          f"dans cette competition -- statut {fenetre_ext['statut']}")

    if fenetre_dom["statut"] != validation.STATUT_UTILISABLE or fenetre_ext["statut"] != validation.STATUT_UTILISABLE:
        print("\n-> Au moins une des deux equipes est INSUFFISANT (moins de "
              f"{validation.N_MIN_UTILISABLE} matchs cette saison). C'est attendu "
              "en debut de saison -- PAS une erreur du script. Le match ne peut "
              "pas etre analyse tant que les deux equipes n'ont pas atteint ce seuil.")
        return

    matchs_dom_domicile, _ = loader.separe_domicile_exterieur(fenetre_dom["matchs_retenus"])
    _, matchs_ext_exterieur = loader.separe_domicile_exterieur(fenetre_ext["matchs_retenus"])

    print(f"\n{NOM_DOMICILE} a domicile cette saison : {len(matchs_dom_domicile)} match(s)")
    for i, m in enumerate(matchs_dom_domicile, 1):
        print(f"  match {i}: {m['buts_marques']}-{m['buts_encaisses']}")

    print(f"\n{NOM_EXTERIEUR} a l'exterieur cette saison : {len(matchs_ext_exterieur)} match(s)")
    for i, m in enumerate(matchs_ext_exterieur, 1):
        print(f"  match {i}: {m['buts_marques']}-{m['buts_encaisses']}")

    p_dom = profil_equipe.construit_profil(matchs_dom_domicile)
    p_ext = profil_equipe.construit_profil(matchs_ext_exterieur)

    print(f"\nProfil {NOM_DOMICILE} (domicile) -- fiabilite: {p_dom['statut_fiabilite']} "
          f"(poids {p_dom['poids_fiabilite']})")
    print(f"  Attaque: moyenne={p_dom['attaque']['moyenne']}, musique={p_dom['attaque']['musique']}")
    print(f"  Defense: moyenne={p_dom['defense']['moyenne']}, musique={p_dom['defense']['musique']}")

    print(f"\nProfil {NOM_EXTERIEUR} (exterieur) -- fiabilite: {p_ext['statut_fiabilite']} "
          f"(poids {p_ext['poids_fiabilite']})")
    print(f"  Attaque: moyenne={p_ext['attaque']['moyenne']}, musique={p_ext['attaque']['musique']}")
    print(f"  Defense: moyenne={p_ext['defense']['moyenne']}, musique={p_ext['defense']['musique']}")

    signaux = matrice_croisement.croise_profils(p_dom, p_ext)
    print(f"\n--> {len(signaux)} signal(aux) de la matrice de croisement :")
    if not signaux:
        print("    (aucune tendance nette avec les donnees actuelles)")
    for s in signaux:
        dims_txt = ", ".join(f"{d['nom']}={d['valeur']}" for d in s["dimensions"])
        print(f"    {s['marche']} | {s['nb_dimensions_convergentes']} dimensions | fiabilite={s['fiabilite']}")
        print(f"      -> {dims_txt}")


if __name__ == "__main__":
    main()
