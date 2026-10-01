# moteur_v2_6_10 — la v2.6.9 corrigée, même ossature P1 / P2 / P3

**Statut : candidat, NON branché.** Rien dans le pipeline, le site ni les archives ne l'appelle. `moteur_v2_6_9.py` reste le
moteur de production, intact (aucune ligne modifiée).

## Ce qui ne change pas
Tout vient de `moteur_v2_6_9`, importé tel quel : validations V1-V12, Poisson, marchés, edge / EV / seuils, statuts, artefacts
R1-R3, catégories A-D, désignations, verdict. La sélection (`branchement_moteur.selectionne`) lit `inventaire` comme avant :
P1 = probabilité maximale, P2 = meilleur EV restant, P3 = coup de poker (cote ≥ 2,91 et probabilité ≥ 20 %).

## Ce qui change (réponse aux faiblesses mesurées le 21/09/2026)

| Faiblesse mesurée sur 390 matchs | Correction | Module |
|---|---|---|
| Surconfiance : 52,8 % de réussite pour 65,1 % annoncés | Lissage des moyennes de buts vers 1,35 (K = 4), **fixé à l'avance** | `lissage.py` |
| Aucune calibration (11 % annoncé / 16 % réel, 89 % / 84 %) | Calibration isotone (PAV), apprise sur matchs déjà joués, **≥ 300 observations ET ≥ 50 matchs**, marchés équivalents comptés une fois, sortie bornée à [1 % ; 99 %] | `calibration.py` |
| Value bets trop fréquentes, écarts au marché de 9 à 19 points | Alertes (écart > 12 pts, buts attendus extrêmes, probabilités non calibrées). **Sans effet sur la sélection.** | `risque.py` |

Structure identique à celle du moteur V3 : un module par responsabilité, un orchestrateur (`core.py`), des paramètres nommés.

## Garde-fous
- Les bornes V5 (moyenne de buts dans [0 ; 10]) sont contrôlées sur les valeurs **brutes** : une donnée aberrante n'est jamais rattrapée par le lissage.
- Sans calibrateur, le moteur le déclare (`calibration.statut = "NON_CALIBRE"`, alerte « Probabilités non calibrées »). Il ne calibre jamais sur trop peu de matchs.
- `analyser_match(..., lisser=False)` redonne exactement les résultats de la v2.6.9 (testé).
- Aucun paramètre n'a été réglé sur les 501 matchs du banc : ils servent uniquement à mesurer.

## Utilisation
```python
import moteur_v2_6_10 as moteur
res = moteur.analyser_match(match, date_run, maintenant)                       # lissage seul
res = moteur.analyser_match(match, date_run, maintenant, calibrateur=cal)      # lissage + calibration

cal, diag = moteur.apprendre(observations)   # observations = [{match_id, marche, proba, gagne, date}] de matchs JOUÉS
                                             # filtrer d'abord avec moteur.avant(observations, date_du_match)
```

## Mesurer avant de brancher
```
python -m pytest tests/test_moteur_v2_6_10.py
python evaluation/compare_moteurs_v2.py evaluation/snapshot_historique_moteur_v2_6_9.json evaluation/scores_historique_moteur_v2_6_9.json
python evaluation/compare_moteurs_v2.py SNAPSHOT SCORES --calibration-chrono 0.6
```
Le second rejoue la v2.6.9 et la v2.6.10 sur les mêmes matchs et les mêmes scores. Le troisième apprend le calibrateur sur les
60 % de matchs les plus anciens et mesure tout sur les 40 % restants.
Les choix P1/P2/P3 y sont simulés **sans** le filtre de justification (identique pour toutes les variantes).

Critère de bascule proposé : la v2.6.10 réduit l'écart de calibration et la différence de Brier avec le marché, avec des
intervalles qui ne se contredisent pas. Un ROI positif n'est pas exigé ni attendu (non concluant sous 150 à 200 choix).

## Brancher (une fois la mesure faite, décision du propriétaire)
1. `branchement_moteur.py` : `import moteur_v2_6_10 as moteur` ; `NOM_MOTEUR`, `VERSION_MOTEUR`, `CONFIG_VERSION`.
2. Site (`archetype.js`) : `CLE_MOTEUR` doit suivre `NOM_MOTEUR` (un test de contrat le vérifie).
3. Étape nocturne qui apprend le calibrateur sur l'archive des matchs joués (`calibration.avant`) et le passe à `analyser_match`.
4. Mettre à jour README, ROADMAP et CLAUDE.md.

## Limites connues
- Poisson à buts indépendants : inchangé. Ton calibrage v2.7 suggérait que le Poisson n'apporte rien au-delà du marché recalibré ; la v2.6.10 ne prétend pas le contredire.
- Une seule référence de buts (1,35) pour tous les championnats.
- Les probabilités calibrées de marchés complémentaires ne somment pas exactement à 1.
- Pas de contrôle de corrélation entre les trois choix (V3 le fait par probabilités conjointes) : à faire dans `branchement_moteur.selectionne`, pas dans le moteur.
