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


def extrait_resultat_de_ce_panier(matchs_demandes, historique):
    """Le fichier historique_pronostics.json produit par run_pipeline.py reste
    global (utilisé aussi par le pipeline quotidien planifié) -- on y retrouve
    les entrées de CE panier en comparant (domicile, exterieur), pour ne
    renvoyer à l'utilisateur que ce qu'il a lui-même demandé."""
    cles_demandees = {(m["domicile"], m["exterieur"]) for m in matchs_demandes}
    trouves = []
    for jour in historique:
        for m in jour.get("matchs", []):
            if (m.get("domicile"), m.get("exterieur")) in cles_demandees:
                trouves.append(m)
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
        sys.exit(1)

    # run_pipeline.py inchangé : il lit toujours panier.json sur disque et
    # écrit toujours historique_pronostics.json/data.json globalement.
    with open("panier.json", "w", encoding="utf-8") as f:
        json.dump(panier, f, ensure_ascii=False, indent=2)

    print(f"[dispatch] panier.json écrit : {len(panier)} entrée(s) sur {len(matchs)} reçue(s).")

    import run_pipeline
    run_pipeline.main()

    with open("historique_pronostics.json", "r", encoding="utf-8") as f:
        historique = json.load(f)

    resultat = extrait_resultat_de_ce_panier(panier, historique)
    ecrit_resultat(panier_id, ligne_panier["user_id"], resultat)
    print(f"[dispatch] résultat écrit dans Supabase pour panier {panier_id} "
          f"({len(resultat)} match(s) trouvé(s) sur {len(panier)} demandé(s)).")


if __name__ == "__main__":
    main()
