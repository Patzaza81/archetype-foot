# Audit d'Omega V3 — PR #143, branche `moteur-gamma-omega-v3` (02/11/2026)

Rien n'est fusionné, `main` n'est pas touché, rien n'est déployé, aucun journal gelé n'est modifié. Source de tous les chiffres : `python -m moteur_omega_v3.audit` → `docs/omega_v3_audit.json` (graine 20261102, 2 000 rééchantillonnages par match). Étiquettes : **[V]** vérifié · **[H]** hypothèse · **[E]** résultat expérimental · **[?]** non vérifié.

## 0. Ce qu'il faut retenir
1. **[V] Les défenses n'ont aucun effet sur la fréquence brute ni sur la fréquence robuste g.** Le score d'un scénario est (attaque A, attaque B) ; chaque couple est répété 25 fois, une fois par couple de défenses. Les 625 scénarios n'apportent donc pas plus d'information que les 25 couples (attA, attB). Les défenses ne servent qu'aux paliers de compatibilité, qui ne participent pas à la décision.
2. **[V] L'écart de 7,3 points vient d'un biais de sélection, pas du bruit ni de la réserve.** Le calibrage ignorait la cote ; or le moteur ne parie que si la cote est ≥ 1,26, c'est-à-dire là où le bookmaker voit moins de chances. Sur le développement lui-même : toutes les cellules « g ≥ seuil » = 92,3 % annoncé / 92,3 % réel ; cote ≥ 1,26 = 76,9 % / 69,3 % ; cote < 1,26 = 84,3 % / 85,2 %.
3. **[V] Correction apportée** : calibrage sur la seule population jouable (cote connue ≥ 1,26). Écart en échantillon : 0,1 point. Mais **13 marchés sur 383 seulement** ont ensuite un seuil, les seuils sont instables, et sur la réserve l'écart reste de 4,0 points (IC 95 % −0,9 à +10,0).
4. **[E] Aucun signe que le moteur bat le bookmaker.** Réserve, 269 paris : réussite 71,8 %, probabilité implicite moyenne des cotes 74,7 %, rendement à mise plate −4,1 % (information, pas un bilan).
5. **[V] Une fuite trouvée et corrigée** : Coritiba – Grêmio figurait dans son propre historique (daté la veille par la source). 1 match sur 525 concerné.
6. **[V] Marchés oubliés trouvés et ajoutés** : 174 → 383 (nombre exact de buts, handicaps à trois issues, lignes hautes, les deux marquent × total).
7. **Aucune validation n'est annoncée.** Le moteur reste en observation ; seuls les paris gelés réels trancheront.

## 1. Fichiers
Modifiés : `moteur_omega_v3/{marches,donnees,coeur,calibrage,suivi}.py`, `parametres.json`, `archetype_gamma.js`, `pronostics_gamma.html`, `.github/workflows/pipeline.yml`, `CLAUDE.md`, `docs/MOTEUR_OMEGA_V3.md`, `docs/omega_v3_validation.json`, tests.
Ajoutés : `moteur_omega_v3/{definitions,variantes,audit}.py`, `archetype_dc.js` + `pronostics_dc.html` (ancienne page DC, copie exacte de `main`), `tests/test_dc_js.py`, `docs/omega_v3_audit.json`, `docs/omega_v3_marches_exemple.csv` (383 marchés), `docs/omega_v3_audit_par_marche.csv`.
Intacts : `moteur_dc/`, `data/dc/`, `tests/test_moteur_dc.py`, `main`.

## 2. Matrice des 625 scénarios (§1 de tes directives)
- **[V]** Séquences : `donnees.sequences` prend les 5 derniers matchs de A à domicile et de B à l'extérieur, strictement avant le jour. Attaque A = buts de A, défense A = buts encaissés par A (à domicile) ; attaque B = buts de B, défense B = buts encaissés par B (à l'extérieur). Test d'orientation ajouté.
- **[V]** 625 combinaisons, 625 identifiants uniques `i-l-k-j`, chacune garde ses quatre observations d'origine. Écarts : A = |attA − défB|, B = |attB − défA|.
- **[V]** 73 scénarios incompatibles sur 625 restent dans l'exploration brute (exemple de l'énoncé) ; les paliers ne s'appliquent qu'après le brut.
- **[V]** Dénominateur = nombre de scénarios (625) ; chaque palier a son propre dénominateur.
- **[V] Pondération marginale** : f(marché) = Σ P(attA=x)·P(attB=y) sur les couples gagnants ; écart avec l'énumération des 625 = 0 (exemple de l'énoncé et tests). Pas de pondération supplémentaire ni de double comptage.
- **[V] Mais** : retirer une observation de défense ne change f d'aucun marché (écart 0 sur 10 retraits). La « robustesse » ne teste donc en pratique que 10 retraits sur 20.
- Exemple détaillé : `docs/omega_v3_audit.json` → `matrice.scenarios_detailles`.

## 3. Score du scénario : trois variantes (§2)
Formules et hypothèses : `moteur_omega_v3/variantes.py`. Absence de double comptage prouvée par tests (factorisation = énumération scénario par scénario, chaque scénario pèse 1/625).
- **A (production)** : W = pmf(attA) ⊗ pmf(attB).
- **B** : W = (½ pmf(attA) + ½ pmf(défB)) ⊗ (½ pmf(attB) + ½ pmf(défA)) — chaque scénario donne 4 scores de poids ¼.
- **C** : λA = (attA+défB)/2, λB = (attB+défA)/2, deux lois de Poisson indépendantes, moyenne des 625 scénarios. C'est un **modèle** (hypothèses : Poisson, indépendance, poids égaux), pas une fréquence.

Réserve chronologique (171 matchs du 28/10 au 01/11, seuils appris avant), **aucune variante choisie** :

| | Marchés avec seuil | Paris | Réussite | Annoncé | Écart | Brier groupé calibré, 174 marchés initiaux |
|---|---|---|---|---|---|---|
| A | 11 | 269 | 71,8 % | 75,7 % | +4,0 | 0,1445 |
| B | 12 | 384 | 66,9 % | 74,1 % | +7,2 | 0,1331 |
| C | 11 | 270 | 71,9 % | 75,3 % | +3,4 | 0,1318 |

**[E]** B et C ont un meilleur Brier groupé que A (information défensive utile pour une probabilité lissée). Sur les paris retenus, les intervalles se recouvrent (A : 66,3–76,8 % ; B : 61,4–72,7 % ; C : 66,7–76,6 %). **Aucune supériorité démontrée.** Le Brier groupé est dominé par des marchés quasi certains : il ne prouve aucune capacité à battre un bookmaker.
Contrôle de cohérence **[V]** : sur les 174 marchés initiaux, la variante A reproduit exactement la première validation (Brier 0,1531 / 0,1445, log loss 0,6655 / 0,4541).

## 4. Les marchés (§3)
- **[V]** 383 marchés (avant : 174), tous générés par règle à partir des scores. Chaque marché est comparé à une **définition indépendante** (`definitions.py`, relue depuis la clé) sur 196 scores : 0 écart. Tableau complet (définition, formule, k, n, f brute, par palier, g, statut) : `docs/omega_v3_marches_exemple.csv`.
- **Trouvé** : lignes plafonnées (6,5 total ; 4,5 par équipe ; ±3,5) alors que l'historique contient 9 buts pour une équipe, 10 au total, 9 d'écart ; et deux marchés cotés par la source jamais générés (`nombre_exact_buts`, `handicap_3issues_*`) + « les deux marquent × total ». **Corrigé.** Lignes désormais fixées sur les maxima observés ; un test échoue si l'historique les dépasse.
- Sens du handicap à trois issues vérifié sur les cotes : cote(« 1 » | −1) ≈ 1,86 × cote 1X2, cote(« 1 » | +1) ≈ 0,61 × **[V]**.
- Relations vérifiées par test : plus + moins = 100 % (lignes demi-buts), gagné + perdu + remboursé = 100 % (lignes entières), 1X2 ⇒ double chance, trois issues = 100 %, nombre exact = 100 %.
- **Non calculables** (jamais présentés comme calculés) : mi-temps, premier buteur, corners, cartons ; pair/impair exclu par ta décision.
- **Calculables mais non générés [?]** : marge de victoire, buts exacts par équipe, lignes asiatiques en quarts. Pas de cote dans la source ; à décider.

## 5. Écart annoncé / observé (§4)
Mesure : « annoncé » = réussite lissée de la tranche de g (`coeur.p_calibree`), « réel » = résultat, remboursés exclus.

| Étape (développement, seuils appris dessus) | Cellules | Annoncé | Réel |
|---|---|---|---|
| toutes les cellules g ≥ seuil | 26 104 | 92,3 % | 92,3 % |
| cote connue | 4 699 | 81,9 % | 80,0 % |
| sans cote (injouables) | 21 405 | 94,6 % | 95,0 % |
| **cote ≥ 1,26 (jouable)** | 1 552 | **76,9 %** | **69,3 %** |
| cote < 1,26 | 3 147 | 84,3 % | 85,2 % |

Réserve, même lecture : jouable 801 cellules, 77,0 % annoncé / 68,3 % réel. **[V]** Le biais est présent en échantillon et hors échantillon ; ce n'est ni la fuite, ni la taille de la réserve.
Autres pistes testées **[V]** : marche avant interne au développement (seuils sur les 60 % anciens, test sur les 40 % récents, réserve intouchée) : écart 6,8 points ; doublons d'événement : déjà éliminés par `decider` ; dépendance entre paris d'un même match : 3,15 paris par match, corrélation intra-match 0,08, 6,6 % des paris impliqués par un autre — cela élargit les intervalles (IC 95 % par match : écart +2,8 à +11,9) mais ne crée pas l'écart.
Variations **[E]** (calibrage corrigé, réserve) : par jour 62 % à 74 % (8 à 158 paris), par famille résultat 69,2 % (156 paris), buts d'une équipe 64,7 % (34), buts du match 78,4 % (74), par championnat 14 à 30 paris chacun : trop peu de données pour conclure.
Ventilation par marché : `docs/omega_v3_audit_par_marche.csv` (paris, annoncé, réussites, taux, écart, Brier, log loss, Wilson 95 %). Avec le calibrage corrigé, seuls 10 marchés ont des paris sur la réserve, de 15 à 110 paris chacun : **aucun taux par marché n'est concluant** (ex. `double_chance|1N` 53,3 % sur 15 paris, annoncé 76,4 %).

Après correction **[V/E]** : en échantillon 75,5 % réel / 75,6 % annoncé ; réserve 269 paris, 71,8 % / 75,7 %, écart +4,0 (IC −0,9 à +10,0). Seuils : 1 marché sur 11 garde un seuil dans les deux moitiés du développement (instables). Je n'ai pas abaissé de seuil.
Pas de lecture du calibrage sur la réserve pour l'apprendre : tout est appris sur le développement.

## 6. Couverture (§5)
Source : `audit_couverture`, 1 191 matchs joués de l'archive.
- Analysables 525, exclus 666 (659 données insuffisantes + 7 championnat sans match connu).
- Causes : 528 « les deux équipes < 5 matchs au lieu », 64 domicile seul, 67 extérieur seul. Manque : 1 match pour 523 équipes-matchs, 2 pour 371, 3 pour 168, 4 pour 92, 5 pour 33.
- Cause racine **[V]** : la source donne peu de profondeur (médiane ≈ 8 matchs par équipe), pas un défaut du moteur. Championnats les plus touchés : Série C Girone A (30 exclus / 50), Grèce Super Ligue (25 / 25), Série B (24 / 24), Serie A (20 / 20), Eredivisie (19 / 22). Équipes : Crystal Palace, Arsenal, Aston Villa, Twente, Aris (5 à 7 matchs exclus chacune).
- Si le minimum était 3 / 4 / 5 / 6 / 8 / 10 : 1 004 / 797 / 525 / 333 / 275 / 259 matchs.
- **[E]** Variantes (même protocole, calibrage jouable, réserve lue une fois) : production 269 paris, 71,8 % ; fenêtre 8 → 197 paris, 69,5 % ; fenêtre 10 → 295 paris, 68,1 % ; minimum 4 → 353 paris, 71,7 % ; minimum 3 → 424 paris, 73,4 %. Par taille d'échantillon (minimum 3) : 3 matchs → 42 paris (73,8 %), 4 → 108 (70,4 %), 5 → 274 (74,5 %). Écarts non distincts du bruit (annoncé 74,9 à 77,8 %). **Je n'ai pas réduit le minimum de 5.**
- 36 matchs analysés sur 525 (7 %) contiennent une observation d'avant juillet 2026 (autre saison pour l'Europe) ; ancienneté médiane de la plus vieille observation : 75 jours, max 183 **[V]**. Sur la réserve, 3 matchs seulement : non concluant.

## 7. Données et fuites (§6)
- **[V]** Archive : 4 285 enregistrements bruts → 1 557 matchs (301 `match_id` en double dédoublonnés) ; 97 matchs joués écartés car cotes prises après le coup d'envoi, 233 sans horodatage.
- **[V]** Aucune séquence ne contient une date ≥ au jour du match (0 sur 525).
- **[V] Fuite corrigée** : le match lui-même, daté la veille par la source (fuseaux : la page date en heure du Cameroun, l'historique en heure locale) : 1 cas (Coritiba – Grêmio, 27/10). Désormais écarté (même affiche à ± 1 jour). Le compte affiché de matchs disponibles l'excluait aussi mal : corrigé.
- **[V]** 78 matchs ont un jour différent de la date UTC du coup d'envoi (fuseau). 99 matchs figurent dans l'historique daté le lendemain : jamais utilisés (`date < jour`).
- **[V]** Doublons exacts dans l'historique : 0 ; domicile = extérieur : 0 ; 67 matchs à 8 buts ou plus (réels ou erreurs de source : [?]).
- **[?] Non vérifiable ici** : matchs reportés ou annulés (aucun champ de statut ; un match sans score est ignoré, un score partiel d'abandon ne se détecte pas), résultats révisés après coup (l'historique est un instantané actuel), cotes historiques au-delà de leur horodatage de prise (`run.pris_le` n'est contrôlé que pour les matchs joués).

## 8. Intégration Gamma / Omega (§7)
- **[V]** Entrée pipeline : `python -m moteur_omega_v3.suivi pipeline` ; fonctions : `geler`, `resultats`, `page`. Format page : `data/gamma/pronostics.json` ; champs lus par `archetype_gamma.js` vérifiés par les tests JS et un rendu navigateur mobile (390 px) sur 68 matchs : aucune erreur JS, pas de débordement horizontal.
- **Trouvé et corrigé** : (1) l'ancien moteur DC n'était plus lancé par le pipeline : son journal gelé s'arrêtait, plus de comparaison réelle possible → étape DC **rétablie** ; (2) l'ancienne page DC n'était plus accessible → copie exacte conservée (`pronostics_dc.html`, `archetype_dc.js`, tests) ; (3) les matchs non analysés (données insuffisantes) étaient comptés « analysés sans pari » → séparés ; (4) la conclusion et les raisons « à surveiller » affichaient des clés techniques (`handicap_-2.5 – exterieur`) et listaient en tête des marchés vrais à 100 % → phrases en clair, marchés certains écartés.
- **[V]** `bilan_reel.py` lit le journal Gamma (gel avant le coup d'envoi, matchs terminés, remboursements exclus) : test ajouté. Identifiants de pronostic = `match_id` de l'archive, comme le DC.
- **[V]** Aucun journal existant réécrit : `data/gamma/journal.jsonl` n'existe pas encore sur `main` ; `data/dc/` est identique à `main` (test).
- **[?] Compatibilité** : changer l'ordre ou le nombre de marchés change `ordre_marches` ; une fiche gelée avec un autre ordre s'affiche sans le tableau « tous les marchés » (testé côté JS). Poids : 165 gels = 1,85 Mo de journal, page 1,56 Mo (avant : 1,4 / 1,3 Mo).

## 9. Textes et interface (§8)
- Mot « BetPawa » absent des textes affichés ; libellés sans clé technique ; l'introduction dit désormais : fréquences de scénarios ≠ probabilités, seuil expérimental ≠ garantie, cote jouable ≠ opportunité rentable. « Réussite observée sur l'archive à ce niveau, parmi les paris jouables ».
- Cas affichés : aucun pari (ligne « analysés sans pari »), données insuffisantes (ligne « non analysés » avec raison), sans cote (« à surveiller : aucune cote disponible »), contradictions (« Contradictions entre le brut et un palier défensif »), palier peu représenté (« trop peu représenté »).
- **[?]** Je n'ai pas testé de contradiction réelle forte ni de fiche sans aucune donnée d'affichage sur un vrai téléphone.

## 10. Tests (§9)
- Avant : 3 059 réussis, 0 échoué. Après correction : **3 118 réussis, 0 échoué** (`python -m pytest tests`, 107 s).
- Ajoutés : orientation, quatre observations conservées, brut intact, défenses sans effet sur f/g, pondération marginale, 383 marchés vs définitions indépendantes, clés inconnues refusées, lignes ≥ maxima de l'historique, marchés ajoutés, auto-référence ± 1 jour (3 cas qui passent / 3 qui échouent), ordre des données, variantes (somme 1, pas de double comptage), calibrage jouable, conclusion sans clé, page (exclus vs sans pari), `bilan_reel`, DC intact par rapport à `main`, page DC conservée, phrases JS.
- Un test a révélé un vrai défaut (`definitions.py` acceptait une sélection inconnue) : corrigé.

## 11. Risques ouverts
1. Défenses sans effet sur la décision : 625 scénarios = 25 couples. À toi de décider si B ou C (ou une autre confrontation) doit remplacer A ; l'audit n'en désigne aucune.
2. Calibrage sur la population jouable : peu de données (13 marchés avec seuil), seuils instables, écart résiduel de 4 points.
3. Aucune supériorité démontrée sur le bookmaker (réussite sous la probabilité implicite).
4. Échantillon court (5 semaines, 525 matchs, 171 en réserve) ; la réserve a été lue pour comparer les variantes (sans y apprendre) : une vraie validation exige les paris gelés réels.
5. Couverture limitée par la source (666 matchs sur 1 191 exclus).
6. Journal et page plus lourds.
7. Marchés calculables non générés (marge de victoire, buts exacts, quarts de ligne) : décision à prendre.
