# Source des données Elo (31/10/2026 → 01/11/2026)

L'API api.clubelo.com était en panne (HTTP 502 depuis le 31/10/2026, voir `diagnostic.txt`) et clubelo.com bloque les robots (Cloudflare). Les données viennent donc d'une copie publique :

- Dépôt : https://github.com/Hicruben/theopenmodel — `data/elo-history/*.csv` (105 clubs, 5 grands championnats, séries du 02/01/2020 au 31/12/2026 pour la valeur courante) et `data/clubelo-latest.csv` (instantané du 31/08/2026, 594 clubs).
- Licence des données de ce dépôt : CC BY 4.0. Source de fond : **ClubElo (http://clubelo.com)**, à citer.
- Dernier commit lu : 09/09/2026 ("daily snapshot & results 2026-09-09").
- Intégrité non vérifiable auprès de ClubElo (API indisponible) : contrôles de cohérence dans `docs/DC_ELO_COUVERTURE.md`.
- Couverture limitée : Angleterre, Espagne, France, Allemagne, Italie. Les autres compétitions n'ont aucun Elo (Elo manquant = 0 = ridge simple, protocole B′).
