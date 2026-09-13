"""
notifie_constat_majeur.py -- (13/09/2026) transforme les événements
notables accumulés cette nuit (archetype_model.learning.constat_majeur)
en UNE SEULE Issue GitHub, s'il y en a. Doit tourner en DERNIER dans le
pipeline, après tous les scripts susceptibles d'avoir signalé quelque
chose (calibre_archetype_model.py, genere_tickets_reels_archetype_model.py).

Un seul événement de temps en temps devient une notification GitHub que
Patrick verra sur son téléphone (app GitHub déjà installée) -- jamais un
mail ou un service tiers à configurer. Une nuit sans événement notable
n'ouvre aucune Issue -- silence normal, pas une absence de fonctionnement.

N'utilise jamais l'API GitHub directement -- passe par la CLI `gh`, déjà
installée sur les runners GitHub Actions, authentifiée via la variable
d'environnement GH_TOKEN (voir .github/workflows/pipeline.yml, qui doit
fournir GITHUB_TOKEN avec la permission "issues: write").

Usage : python notifie_constat_majeur.py
"""

from __future__ import annotations

import subprocess
import sys

from archetype_model.learning import constat_majeur


def construit_corps_issue(evenements: list[dict[str, str]]) -> str:
    sections = [f"### {e['titre']}\n\n{e['details']}" for e in evenements]
    return "\n\n---\n\n".join(sections)


def main() -> int:
    evenements = constat_majeur.charger_et_vider()
    if not evenements:
        print("[constat majeur] rien à signaler cette nuit.")
        return 0

    titre = f"Constat majeur -- {len(evenements)} événement(s) cette nuit"
    corps = construit_corps_issue(evenements)

    try:
        resultat = subprocess.run(
            ["gh", "issue", "create", "--title", titre, "--body", corps],
            capture_output=True, text=True,
        )
    except Exception as exc:
        # Un échec de notification (gh absent, non authentifié, réseau...)
        # n'est jamais une raison d'interrompre le pipeline -- les
        # événements sont déjà journalisés ailleurs (journal_promotion.jsonl,
        # vrais_tickets/) même si l'Issue échoue.
        print(f"[constat majeur] échec de création de l'issue : {exc}", file=sys.stderr)
        return 0

    if resultat.returncode != 0:
        print(f"[constat majeur] échec de création de l'issue : {resultat.stderr}", file=sys.stderr)
        return 0

    print(f"[constat majeur] issue créée : {resultat.stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
