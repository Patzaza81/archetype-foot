# moteur_v2_6_10 — la v2.6.9 corrigée, même ossature P1 / P2 / P3

**Statut : branché en production comme moteur lissé, calibration inactive tant que son jeu d'apprentissage n'atteint pas les garde-fous.** Le pipeline, le site et les archives utilisent désormais `moteur_v2_6_10`. La base `moteur_v2_6_9.py` reste intacte comme dépendance interne et référence historique.

## Ce qui ne change pas
Tout vient de `moteur_v2_6_9`, importé tel quel : validations V1-V12, Poisson, marchés, edge / EV / seuils, statuts, artefacts
R1-R3, catégories A-D, désignations, verdict. La sélection (`branchement_moteur.selectionne`) lit `inventaire` comme avant :
P1 = probabilité maximale, P2 = meilleur EV restant, P3 = coup de poker (cote ≥ 2,91 et probabilité ≥ 20 %).

## Ce qui change (réponse aux faiblesses mesurées le 21/09/2026)

| Faiblesse mesurée sur 390 matchs | Correction | Module |
|---|---|---|
| Surconfiance : 52,8 % de réussite pour 65,1 % annoncés | Lissage des moyennes de buts vers une référence **par rôle** (domicile 1,50 / extérieur 1,20, K = 4), **fixé à l'avance** | `lissage.py` |
| Aucune calibration (11 % annoncé / 16 % réel, 89 % / 84 %) | Calibration isotone (PAV), **≥ 300 observations ET ≥ 100 matchs**, inventaire complet obligatoire, blocs ≥ 30, correction pondérée n/(n+100), valable seulement pour le modèle et les dates qui l'ont produite ; probabilités rendues cohérentes (`coherence.py`) | `calibration.py`, `coherence.py` |
| Value bets trop fréquentes, écarts au marché de 9 à 19 points | Alertes (écart > 12 pts, buts attendus extrêmes, probabilités non calibrées). **Sans effet sur la sélection.** | `risque.py` |

Structure identique à celle du moteur V3 : un module par responsabilité, un orchestrateur (`core.py`), des paramètres nommés.

## Garde-fous
- Les bornes V5 (moyenne de buts dans [0 ; 10]) sont contrôlées sur les valeurs **brutes** : une donnée aberrante n'est jamais rattrapée par le lissage.
- Sans calibrateur, le moteur le déclare (`calibration.statut = "NON_CALIBRE"`, alerte « Probabilités non calibrées »). Il ne calibre jamais sur trop peu de matchs.
- `analyser_match(..., lisser=False)` redonne exactement les résultats de la v2.6.9 (testé).
- Aucun paramètre n'a été réglé sur les 501 matchs du banc : ils servent uniquement à mesurer. Les références 1,50 / 1,20 sont des ordres de grandeur généraux, pas des mesures sur tes championnats.
- Un calibrateur appris pour un autre modèle, ou sur des matchs non antérieurs au match analysé, est ignoré et signalé (`calibration.statut`).
- R5 (profil asymétrique) reste évalué sur les moyennes brutes.
- Voir `docs/AUDIT_MOTEUR_V2_6_10.md` pour les défauts corrigés et les limites restantes.

## Utilisation
```python
import moteur_v2_6_10 as moteur
res = moteur.analyser_match(match, date_run, maintenant)                       # lissage seul
res = moteur.analyser_match(match, date_run, maintenant, calibrateur=cal)      # lissage + calibration

cal, diag = moteur.apprendre(observations, modele=moteur.signature_modele())
    # observations = [{match_id, marche, proba, gagne, date}] de matchs JOUÉS, TOUS les marchés de l'inventaire (pas seulement
    # les value bets), probabilités brutes du modèle courant ; filtrer d'abord avec moteur.avant(observations, date_du_match)
```

## Mesurer avant d'activer la calibration
```
python -m pytest tests/test_moteur_v2_6_10.py
python evaluation/compare_moteurs_v2.py evaluation/snapshot_historique_moteur_v2_6_9.json evaluation/scores_historique_moteur_v2_6_9.json
python evaluation/compare_moteurs_v2.py SNAPSHOT SCORES --calibration-chrono 0.6
python evaluation/compare_moteurs_v2.py SNAPSHOT SCORES --sensibilite     # lecture seule, ne jamais y choisir un paramètre
```
Le second rejoue la v2.6.9 et la v2.6.10 sur les mêmes matchs et les mêmes scores. Le troisième apprend le calibrateur sur les
60 % de matchs les plus anciens et mesure tout sur les 40 % restants.
Les choix P1/P2/P3 y sont simulés **sans** le filtre de justification (identique pour toutes les variantes).

Critère de bascule proposé : la v2.6.10 réduit l'écart de calibration et la différence de Brier avec le marché, avec des
intervalles qui ne se contredisent pas. Un ROI positif n'est pas exigé ni attendu (non concluant sous 150 à 200 choix).

## État de branchement
1. `branchement_moteur.py`, `pont_moteur.py` et `archetype.js` utilisent désormais `moteur_v2_6_10`.
2. Le lissage par rôle est actif avec les paramètres fixés à l'avance : K=4, référence domicile=1,50 et référence extérieur=1,20.
3. La calibration isotone est volontairement inactive en production jusqu'à constitution d'un inventaire complet et atteinte des garde-fous documentés : au moins 300 observations et 100 matchs, avec antériorité temporelle stricte.
4. `moteur_v2_6_9.py` reste intact comme dépendance interne de v2.6.10 et référence historique ; il n'est plus utilisé comme moteur de décision du pipeline.
5. Le Journal filtre les archives résolues sur `model_version = moteur_v2_6_10` afin de ne pas mélanger les performances des deux générations.

## Limites connues
- Poisson à buts indépendants : inchangé. Ton calibrage v2.7 suggérait que le Poisson n'apporte rien au-delà du marché recalibré ; la v2.6.10 ne prétend pas le contredire.
- Deux références de buts (domicile / extérieur) identiques pour tous les championnats.
- Il y aura moins de value bets et de choix qu'avec la v2.6.9 : les seuils d'EV et de catégorie ont été posés sur des probabilités non corrigées. Le comparateur affiche le nombre de choix.
- **Le marché prédit mieux que le modèle** (Brier 0,1860 contre 0,2004). Lissage et calibration ne rendent pas le modèle plus informatif : si la différence de Brier reste positive après comparaison, la sélection « value » n'a pas de fondement statistique (voir l'audit).
- Pas de contrôle de corrélation entre les trois choix (V3 le fait par probabilités conjointes) : à faire dans `branchement_moteur.selectionne`, pas dans le moteur.
