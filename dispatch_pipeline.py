"""
dispatch_pipeline.py — point d'entrée du canal workflow_dispatch.
Lit les inputs (variables d'environnement), construit panier.json,
puis appelle run_pipeline.py tel quel.
"""
import json
import os
import sys

from payload_builder import build_payload


def main():
    payload = {
        "equipe_dom": os.environ.get("INPUT_EQUIPE_DOM", "").strip(),
        "equipe_ext": os.environ.get("INPUT_EQUIPE_EXT", "").strip(),
        "date": os.environ.get("INPUT_DATE", "").strip(),
        "heure": os.environ.get("INPUT_HEURE", "").strip(),
        "url_matchendirect": os.environ.get("INPUT_URL_MD", "").strip() or None,
    }

    if not all([payload["equipe_dom"], payload["equipe_ext"], payload["date"], payload["heure"]]):
        print("ERREUR : champs obligatoires manquants.", file=sys.stderr)
        sys.exit(1)

    try:
        panier = build_payload(payload)
    except (ValueError, RuntimeError) as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        sys.exit(1)

    with open("panier.json", "w", encoding="utf-8") as f:
        json.dump(panier, f, ensure_ascii=False, indent=2)

    print(f"[dispatch] panier.json écrit : {len(panier)} entrée(s).")

    import run_pipeline
    run_pipeline.main()


if __name__ == "__main__":
    main()
