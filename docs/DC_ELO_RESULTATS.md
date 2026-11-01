# Piste B′ (prior Elo) — rapport

> **Rejeu Football-Data (archive), PAS un bilan réel.** Périmètre : E0, SP1, I1, D1, F1 (les seules divisions où l'Elo existe). Source Elo : copie CC BY 4.0 de ClubElo (voir `data/clubelo/SOURCE.md`) ; l'API ClubElo est en panne.

> **Écart au protocole, déclaré avant le résultat :** le test sur 2026-27 est IMPOSSIBLE dans ces divisions (la saison est trop jeune : aucun match ne passe le contrat 1.5, qui exige 4 matchs au lieu). Le test est donc un découpage chronologique de 2025-26 à la date médiane des matchs notés (2026-02-08) : (γ, δ) appris AVANT la coupe, lus APRÈS, puis l'inverse comme contrôle de stabilité.

- 2025-26 : 1352 matchs notés (contrat passé). Test principal : **679 matchs** (2026-02-08 → 2026-05-24). Échantillon petit : le test ne voit que de gros effets.
- (γ, δ) appris sur la 1re moitié : **+0.15 / -0.10** ; appris sur la 2e moitié : **+0.15 / +0.05** (départ (0, 0) = ridge actuel).

## Gain de log-vraisemblance du score par match (Dixon-Coles avec prior Elo − Dixon-Coles pur), apparié

| Lecture | Gain moyen | IC 95 % | MDE recalculé | n | Retenu |
|---|---|---|---|---|---|
| Principale (appris 1re moitié, lu 2e) | +0.00063 | [-0.00737 ; +0.00882] | 0.00787 | 679 | non |
| Principale centrée (niveau de buts égalé, facteur 0.9996) | +0.00062 | [-0.00730 ; +0.00872] | 0.00787 | 679 | non |
| Inverse (appris 2e moitié, lu 1re) | +0.00554 | [-0.00404 ; +0.01500] | 0.00970 | 673 | non |
| Inverse centrée | +0.00554 | [-0.00393 ; +0.01513] | 0.00970 | 673 | non |

Règle : retenu si et seulement si la borne basse de l'IC 95 % est > 0 (comme la piste A).

## Par division, lecture principale (gain moyen, n)

- E0 : -0.00180 sur 132 matchs
- SP1 : -0.01034 sur 158 matchs
- I1 : +0.01105 sur 147 matchs
- D1 : +0.00165 sur 120 matchs
- F1 : +0.00391 sur 122 matchs

## EMAC (103 marchés, lecture principale) : sans Elo 0.005 — avec Elo 0.0058

## Exemple de matrices : fd|2526|D1, 2026-02-08, score réel 5-1

- Dixon-Coles pur : buts attendus 2.57 – 1.43
- Avec prior Elo : buts attendus 2.79 – 1.27
