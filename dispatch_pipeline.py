"""
dispatch_pipeline.py — point d'entrée du canal workflow_dispatch.

(29/08/2026 -- Supabase) Ne reçoit plus le panier en clair (INPUT_MATCHS_JSON) --
reçoit un panier_id (INPUT_PANIER_ID), va chercher le panier correspondant
dans Supabase avec la clé service_role (qui contourne RLS -- normal, c'est
le pipeline serveur, pas une requête utilisateur), écrit panier.json
localement à l'identique d'avant pour que run_pipeline.py n'ait RIEN à
changer, puis relit le résultat produit et l'écrit dans la table
`resultats_pipeline`, rattaché au user_id du panier -- c'est ce qui isole
le résultat de cette personne de celui de n'importe qui d'autre.

Variables d'environnement requises (secrets GitHub Actions) :
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import sys
import requests


def _config_supabase():
    url = os.environ.get("SUPABASE_URL", "").strip()
    cle = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not cle:
        print("ERREUR : SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant.", file=sys.stderr)
        sys.exit(1)
    return url, {
        "apikey": cle,
        "Authorization": f"Bearer {cle}",
        "Content-Type": "application/json",
    }


def recupere_panier(panier_id):
    url, headers = _config_supabase()
    r = requests.get(
        f"{url}/rest/v1/paniers",
        params={"id": f"eq.{panier_id}", "select": "id,user_id,matchs"},
        headers=headers, timeout=30,
    )
    r.raise_for_status()
    lignes = r.json()
    if not lignes:
        print(f"ERREUR : panier {panier_id} introuvable dans Supabase.", file=sys.stderr)
        sys.exit(1)
    return lignes[0]


def marque_panier_en_cours(panier_id):
    url, headers = _config_supabase()
    requests.patch(
        f"{url}/rest/v1/paniers", params={"id": f"eq.{panier_id}"},
        headers=headers, json={"statut": "en_cours"}, timeout=30,
    )


def ecrit_resultat(panier_id, user_id, data):
    url, headers = _config_supabase()
    headers = {**headers, "Prefer": "return=minimal"}
    r = requests.post(
        f"{url}/rest/v1/resultats_pipeline", headers=headers,
        json={"panier_id": panier_id, "user_id": user_id, "data": data}, timeout=30,
    )
    r.raise_for_status()
    requests.patch(
        f"{url.rstrip('/')}/rest/v1/paniers", params={"id": f"eq.{panier_id}"},
        headers={k: v for k, v in headers.items() if k != "Prefer"},
        json={"statut": "termine"}, timeout=30,
    )


def _cle_match(m):
    """Identité canonique d'un match. match_id (identifiant matchendirect réel,
    présent sur 100% des entrées depuis le retrait de la saisie manuelle --
    06/09/2026) prioritaire ; repli (domicile, exterieur) seulement pour une
    entrée dégradée qui n'en aurait pas, même convention que la déduplication
    déjà en place dans run_pipeline.py."""
    return m.get("match_id") or (m.get("domicile"), m.get("exterieur"))


def marque_panier_echec(panier_id):
    """CORRECTIF 06/09/2026 (Groupe 2, bug #11) -- avant, une exception
    n'importe où entre marque_panier_en_cours() et la fin de main() laissait
    le panier bloqué "en_cours" indéfiniment côté Supabase, sans jamais
    d'erreur visible pour l'utilisateur. Écrit seulement "statut": "echec"
    -- colonne déjà existante et déjà utilisée pour "en_cours"/"termine",
    aucune nouvelle colonne Supabase supposée (schéma non vérifiable depuis
    ce dépôt). Le détail de l'exception reste dans les logs GitHub Actions
    (voir main()), pas persisté ici."""
    url, headers = _config_supabase()
    requests.patch(
        f"{url}/rest/v1/paniers", params={"id": f"eq.{panier_id}"},
        headers=headers, json={"statut": "echec"}, timeout=30,
    )


def extrait_resultat_de_ce_panier(matchs_demandes, historique):
    """Le fichier historique_pronostics.json produit par run_pipeline.py reste
    global (utilisé aussi par le pipeline quotidien planifié) -- on y retrouve
    les entrées de CE panier par match_id (CORRECTIF 06/09/2026, bug #8 --
    (domicile, exterieur) seul pouvait faire retourner le résultat d'une
    AUTRE rencontre entre les deux mêmes équipes, ex. aller-retour ou
    championnat vs coupe), pour ne renvoyer à l'utilisateur que ce qu'il a
    lui-même demandé."""
    cles_demandees = {_cle_match(m) for m in matchs_demandes}
    trouves = []
    for jour in historique:
        for m in jour.get("matchs", []):
            if _cle_match(m) in cles_demandees:
                trouves.append(m)
    return trouves


# AJOUT 03/09/2026 -- demande explicite de Patrick : un match du panier déjà
# analysé (par le moteur automatique J0/J+1/J+2/J+3, OU archivé lors d'un
# panier précédent) ne doit PAS redéclencher un scraping complet -- son
# résultat existant est réutilisé tel quel. Deux sources sont regardées,
# dans cet ordre :
#   1. precalcul.json (moteur automatique) -- couvre les matchs actuellement
#      dans la fenêtre J0-J+3, MÊME s'ils n'ont pas encore été archivés cette
#      nuit (l'archivage ne se fait qu'à J0/J+1, voir precalcul.py).
#   2. historique_pronostics.json -- couvre ce qui est sorti de la fenêtre
#      automatique (matchs plus anciens) ou déjà analysé via un panier
#      précédent.
# CORRECTIF 06/09/2026 (bug #7) : comparaison désormais par match_id (voir
# _cle_match ci-dessus), plus par (domicile, exterieur) -- deux rencontres
# différentes entre les deux mêmes équipes ne se substituent plus l'une à
# l'autre. On ne renvoie toujours JAMAIS que les matchs explicitement
# demandés -- jamais "tout ce qui traîne" dans ces fichiers.
def cherche_deja_analyses(matchs_demandes, precalcul_signaux, historique):
    cles_demandees = {_cle_match(m) for m in matchs_demandes}
    trouves = {}

    for s in precalcul_signaux:
        cle = _cle_match(s)
        if cle in cles_demandees and s.get("traite") and s.get("verdict_global"):
            trouves[cle] = s

    for jour in historique:
        for m in jour.get("matchs", []):
            cle = _cle_match(m)
            if cle in cles_demandees and cle not in trouves:
                trouves[cle] = m

    return trouves


def main():
    panier_id = os.environ.get("INPUT_PANIER_ID", "").strip()
    if not panier_id:
        print("ERREUR : aucun panier_id reçu (INPUT_PANIER_ID vide).", file=sys.stderr)
        sys.exit(1)

    ligne_panier = recupere_panier(panier_id)
    matchs = ligne_panier.get("matchs") or []
    if not isinstance(matchs, list) or not matchs:
        print("ERREUR : panier vide côté Supabase -- rien à traiter.", file=sys.stderr)
        sys.exit(1)

    marque_panier_en_cours(panier_id)

    # CORRECTIF 06/09/2026 (Groupe 2, bug #11) -- tout ce qui suit était
    # jusqu'ici sans filet : une exception n'importe où (parsing, run_pipeline,
    # écriture du résultat...) laissait le panier bloqué "en_cours" pour
    # toujours côté Supabase, sans jamais d'erreur visible pour l'utilisateur.
    # Le détail de l'exception va dans les logs GitHub Actions (déjà
    # consultables) ; seul "statut": "echec" est persisté (voir
    # marque_panier_echec ci-dessus -- aucune nouvelle colonne supposée).
    try:
        panier = []
        for i, m in enumerate(matchs):
            if not isinstance(m, dict) or not m.get("domicile") or not m.get("exterieur") or not m.get("competition"):
                print(f"AVERTISSEMENT : entrée {i} ignorée (domicile/exterieur/competition manquant).", file=sys.stderr)
                continue
            panier.append({
                "domicile": m["domicile"],
                "exterieur": m["exterieur"],
                "competition": m["competition"],
                "url_match": m.get("url_match"),
                "match_id": m.get("match_id"),
                "source": m.get("source", "panier_web"),
                "cotes_manuelles": m.get("cotes_manuelles"),
            })

        if not panier:
            print("ERREUR : aucune entrée valide après filtrage -- rien à traiter.", file=sys.stderr)
            marque_panier_echec(panier_id)
            sys.exit(1)

        # AJOUT 03/09/2026 -- voir cherche_deja_analyses() ci-dessus : on
        # regarde d'abord ce qui est déjà disponible avant de lancer quoi
        # que ce soit.
        precalcul_signaux = []
        if os.path.exists("precalcul.json"):
            with open("precalcul.json", "r", encoding="utf-8") as f:
                precalcul_signaux = json.load(f).get("signaux", [])

        historique_existant = []
        if os.path.exists("historique_pronostics.json"):
            with open("historique_pronostics.json", "r", encoding="utf-8") as f:
                historique_existant = json.load(f)

        deja_analyses = cherche_deja_analyses(panier, precalcul_signaux, historique_existant)
        manquants = [m for m in panier if _cle_match(m) not in deja_analyses]

        if not manquants:
            print(f"[dispatch] les {len(panier)} match(s) du panier sont déjà "
                  f"analysés -- aucun scraping déclenché, résultats existants "
                  f"réutilisés tels quels.")
            resultat = [deja_analyses[_cle_match(m)] for m in panier]
            ecrit_resultat(panier_id, ligne_panier["user_id"], resultat)
            print(f"[dispatch] résultat écrit dans Supabase pour panier {panier_id} "
                  f"({len(resultat)} match(s), 100% déjà disponibles).")
            return

        # run_pipeline.py inchangé : il lit toujours panier.json sur disque et
        # écrit toujours historique_pronostics.json/data.json globalement.
        # Seuls les matchs MANQUANTS sont écrits ici -- ceux déjà analysés ne
        # sont pas repassés dans le scraping.
        with open("panier.json", "w", encoding="utf-8") as f:
            json.dump(manquants, f, ensure_ascii=False, indent=2)

        print(f"[dispatch] panier.json écrit : {len(manquants)} entrée(s) à "
              f"analyser sur {len(matchs)} reçue(s) ({len(deja_analyses)} "
              f"déjà disponibles, non re-scrapées).")

        import run_pipeline
        run_pipeline.main()

        with open("historique_pronostics.json", "r", encoding="utf-8") as f:
            historique = json.load(f)

        resultat_nouveaux = extrait_resultat_de_ce_panier(manquants, historique)
        resultat_par_cle = dict(deja_analyses)
        for r in resultat_nouveaux:
            resultat_par_cle[_cle_match(r)] = r

        # RÈGLE STRICTE : ordre et contenu = exactement le panier demandé, ni
        # plus ni moins -- un match qu'on n'a réussi à retrouver ni déjà
        # analysé ni tout juste calculé est simplement absent du résultat
        # renvoyé (pas de placeholder inventé).
        resultat = [resultat_par_cle[_cle_match(m)]
                    for m in panier if _cle_match(m) in resultat_par_cle]

        ecrit_resultat(panier_id, ligne_panier["user_id"], resultat)
        print(f"[dispatch] résultat écrit dans Supabase pour panier {panier_id} "
              f"({len(resultat)} match(s) trouvé(s) sur {len(panier)} demandé(s), "
              f"dont {len(deja_analyses)} réutilisé(s) sans nouveau scraping).")

    except SystemExit:
        raise
    except Exception as e:
        print(f"ERREUR dispatch_pipeline : {e}", file=sys.stderr)
        marque_panier_echec(panier_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
