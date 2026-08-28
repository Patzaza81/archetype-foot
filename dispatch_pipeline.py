"""
dispatch_pipeline.py — point d'entrée du canal workflow_dispatch.
Reçoit un TABLEAU de matchs (le panier envoyé depuis le site), déjà
formés avec domicile/exterieur/competition/url_match, écrit panier.json
directement, puis appelle run_pipeline.py tel quel.
"""
import json
import os
import sys


def main():
    raw = os.environ.get("INPUT_MATCHS_JSON", "").strip()
    if not raw:
        print("ERREUR : aucun match reçu (matchs_json vide).", file=sys.stderr)
        sys.exit(1)

    try:
        matchs = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERREUR : JSON invalide dans matchs_json : {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(matchs, list) or not matchs:
        print("ERREUR : matchs_json doit être un tableau non vide.", file=sys.stderr)
        sys.exit(1)

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

    with open("panier.json", "w", encoding="utf-8") as f:
        json.dump(panier, f, ensure_ascii=False, indent=2)

    print(f"[dispatch] panier.json écrit : {len(panier)} entrée(s) sur {len(matchs)} reçue(s).")

    import run_pipeline
    run_pipeline.main()


if __name__ == "__main__":
    main()
