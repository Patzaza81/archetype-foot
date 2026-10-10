# Instructions — sélection et justification

## Règle du double contrôle — 26/09/2026

Tout nouveau moteur de sélection DOIT appliquer `regles_selection.double_controle` avant de retenir un pari.

Un pari n'est retenu que s'il passe les DEUX contrôles :
1. **Saison, dans les deux sens** : l'équipe à domicile jugée sur ses matchs à domicile ET l'équipe à l'extérieur sur ses matchs à l'extérieur, plus leur saison complète. Une victoire ne se justifie jamais par la seule faiblesse de l'adversaire.
2. **Forme récente** : les 6 derniers matchs de chaque équipe et les 3 derniers au même lieu.

Ajouts du 26/09 au soir (version 1.1.0) :
- **Seulement la même compétition** : les matchs utilisés sont ceux de la même compétition ou du même tournoi, jamais les coupes.
- **Pari limite** (adversaire exactement au maximum de victoires récentes autorisé, cas York – Gillingham) : exclu d'un combiné dès qu'un pari propre est disponible.

Détails, seuils et origine (cas Real Salt Lake – New England) : `docs/REGLE_DOUBLE_CONTROLE.md`. Tests : `tests/test_regles_selection.py`.

## Règle maîtresse — justification des marchés retenus

Cette règle est permanente et ne doit jamais être oubliée, simplifiée ou contournée.

Chaque marché retenu doit correspondre à une justification précise expliquant pourquoi CE marché a été retenu. Elle ne doit jamais être inventée, reconstruite après coup, générique ou choisie parce qu'une statistique disponible « fait joli ».

Chaîne obligatoire :
**critère réel de sélection → marché retenu → justification correspondante**

Il faut pouvoir remonter du marché publié au critère exact qui a imposé son choix.

Deux niveaux à conserver :
1. **Preuve spécifique au marché** : pourquoi le marché lui-même est cohérent avec les données réelles.
2. **Cause de sélection finale** : pourquoi ce marché précis a été retenu parmi les candidats éligibles.

Les deux doivent rester traçables. Une preuve EV générique ne remplace jamais une preuve spécifique au marché.

### NO DATA → NO GO

Si un marché n'a pas de preuve spécifique calculable sur les données réelles, il ne doit pas être retenu ni affiché comme choix.

La sélection est souveraine : si un marché est sélectionné, cela signifie qu'il a déjà satisfait toutes les exigences de sélection. La justification explique le choix ; elle ne constitue jamais un filtre supplémentaire et son absence ne peut jamais annuler rétroactivement un marché retenu.

### Causes de sélection V2.6.9

- **P1** : probabilité modèle la plus élevée parmi les marchés éligibles restants disposant d'une justification spécifique.
- **P2** : EDV le plus élevé parmi les marchés éligibles restants disposant d'une justification spécifique, après retrait de P1.
- **P3** : EDV le plus élevé parmi les marchés restants satisfaisant simultanément cote >= 2,91 et probabilité >= 20 %, avec justification spécifique.

Ces causes doivent être produites par la même logique que la sélection, puis attachées au bloc justification.

Interdit :
**marché retenu → chercher ensuite une statistique quelconque → appeler cela justification.**

Faire uniquement :
**critère ayant réellement retenu le marché → justification exacte de ce critère et du marché.**

Toute modification future de la sélection doit donc modifier simultanément son contrat de justification et ses tests.

## Couverture obligatoire des familles de marchés

La bibliothèque de justification doit couvrir tous les marchés réellement émis par `moteur_v2_6_9` et reconnus par `branchement_moteur.py` :
- 1X2 : victoire domicile, nul, victoire extérieure ;
- Double chance : 1X, X2, 12 ;
- BTTS : oui, non ;
- Total de buts : over/under sur toutes les lignes réellement produites ;
- Buts d'une équipe : over/under sur les lignes réellement produites ;
- Cage inviolée : domicile, extérieur ;
- Handicap : domicile/extérieur sur les lignes réellement produites.

Aucun type ne doit être justifié par une preuve appartenant à un autre marché. En particulier :
- une victoire sèche ne doit pas être justifiée par une simple série « sans défaite » ;
- un handicap doit être justifié par la capacité historique à couvrir sa propre ligne ;
- une cage inviolée doit être reliée à la capacité à ne pas concéder, pas simplement à une bonne forme ;
- 1X2 nul et « pas de nul » doivent reposer sur des signaux opposés ;
- les lignes Over/Under et les buts d'équipe doivent utiliser la ligne exacte du marché.

## Style de la justification visible

Le texte destiné à l'utilisateur ne doit pas ressembler à un journal de programme. Les noms techniques (EDV, market_family, selection_criterion, preuve_specifique_disponible, etc.) restent des données internes et ne doivent pas apparaître dans le discours utilisateur.

La formulation doit :
1. nommer naturellement l'équipe ou le contexte ;
2. expliquer le mécanisme sportif qui soutient ce marché précis ;
3. conserver les chiffres utiles ;
4. varier l'angle selon la preuve disponible : forme à domicile/extérieur, faiblesse adverse, rythme de buts, historique direct, capacité à couvrir une ligne, solidité défensive, etc. ;
5. éviter les phrases génériques interchangeables entre plusieurs marchés ;
6. ne jamais transformer une statistique disponible en justification si cette statistique n'explique pas réellement le marché retenu.

La variation doit être déterministe et fondée sur la preuve disponible, pas aléatoire : deux marchés opposés ne doivent jamais recevoir la même phrase simplement parce que le système dispose des mêmes chiffres.

## Conditions réelles

- La justification restitue le chemin quantitatif réel ayant conduit au marché retenu.
- Les données H2H sont affichées séparément à titre indicatif. Elles n'influencent ni le choix du marché ni sa justification. Une justification ne doit jamais devenir disponible uniquement grâce au H2H.
- Pour un total de buts (+/- X,5), la preuve porte sur le **total du match** et suit les données réellement utilisées par le moteur : buts marqués/encaissés dans le contexte domicile/extérieur, volume total observé, puis probabilité modèle du seuil exact.
- Exemple réel Stockport–Peterborough du 26/09/2026 : 3 matchs de Stockport à domicile et 3 de Peterborough à l'extérieur ; moyenne 4,00 buts ; Stockport 3,00 marqués / 2,33 encaissés à domicile ; Peterborough 0,33 marqué / 2,33 encaissés à l'extérieur ; lambda domicile 2,67, extérieur 1,33 ; 56,7 % pour +3,5. La justification doit suivre ce chemin, pas seulement afficher « 2,33 buts encaissés ».
- Le texte visible doit rester naturel : expliquer pourquoi le seuil précis est soutenu, avec les données utiles et la probabilité du modèle, sans jargon interne inutile.

## Tickets : marge d'erreur et rentabilité — 07/10/2026

Les deux moteurs (V2.6.10, V3) et le Journal fournissent chacun leurs paris au générateur de tickets (`generateur_tickets.py`). Cette règle n'en change ni la sélection ni l'éligibilité : elle ajoute une analyse à chaque ticket (`analyse` dans `data/tickets.json`, calculée aussi côté site par `tickets_analyse.js`).

**Modèle : plans de tickets disjoints.** Les n paris sont répartis en t tickets séparés (ex. 12 paris en 4 tickets de 3). Plans testés : 1 combiné, 2 à n/2 tickets, n paris simples. Pour chaque plan, 4 répartitions sont comparées (déterministes) : cotes équilibrées, sécurité équilibrée, paris sûrs ensemble, ligues séparées. La retenue maximise les erreurs garanties, puis la chance d'être rentable, puis le gain espéré ; à égalité, cotes équilibrées. Les 4 résultats sont publiés (`variantes`). Choisir la meilleure de 4 répartitions sur un modèle indépendant est un léger sur-ajustement : le suivi statistique reste le juge.
- **Mise** au prorata de 1/cote du ticket : n'importe quel ticket gagnant rapporte alors R = 1 / Σ(1/cote_ticket) par unité misée ; W tickets gagnants rapportent R × W.
- **Gagnants requis** = ceil(1/R). **Erreurs garanties** = t − gagnants requis : une erreur fait perdre au plus un ticket, donc ce nombre d'erreurs est couvert quelle que soit leur place. Avec 12 paris à 1,70 en 4×3, un ticket gagnant suffit (3 erreurs garanties) ; à 1,20 il en faut 3 (1 erreur).
- **Chance d'être rentable** : loi du nombre de tickets gagnants (probabilité d'un ticket = produit des probabilités de ses paris, indépendance supposée). **Gain espéré** = R × Σ P_ticket − 1. « Rentable » = mise au moins remboursée.
- `plan_marge_max` (plus d'erreurs garanties), `plan_le_plus_regulier` (plus de chances d'être rentable), `meilleur_plan` (gain espéré maximal, souvent le combiné, le plus risqué) : les deux premiers ne portent que sur les plans à gain espéré positif.

Limites à ne pas masquer : indépendance supposée, probabilités des moteurs non recalibrées, le bookmaker doit accepter plusieurs tickets, et les erreurs garanties valent en cas de pire répartition : des erreurs groupées dans un même ticket coûtent moins.

## Suivi statistique des tickets — 07/10/2026

`suivi_tickets.py`, lancé au début de `construit_etat_systeme.py` (donc dans `pipeline.yml` et `journal.yml`, après `generateur_tickets.py`) :
- `data/tickets_historique.json` : chaque ticket généré (clé `date|scénario`) avec ses paris, ses cotes, ses probabilités et l'analyse prévue. Une entrée est remplacée par la version la plus récente tant qu'elle est en attente et qu'aucun score n'est connu ; ensuite elle est figée.
- Règlement avec les scores réels (`historique_pronostics.json`). Un pari annulé ou un marché non reconnu **exclut** le ticket (jamais compté comme perdu par défaut). Les libellés d'affichage acceptés sont en liste blanche.
- `data/tickets_bilan.json`, repris dans `etat_systeme.json` (clé `suivi_tickets`) et affiché dans `systeme.html` : par scénario, paris justes prévus/observés, histogramme des erreurs ; par plan, chance d'être rentable prévue/observée, gain espéré/ROI observé ; par source (V2, V3, Journal), probabilité estimée/taux de réussite.
- Non suivis : les tickets « VOTRE_TICKET_COTE_x » construits dans le navigateur. Petits échantillons : un écart n'est significatif qu'avec beaucoup de tickets réglés ; `journal.yml` doit lister `data/tickets_historique.json` et `data/tickets_bilan.json` dans son `git add` (sinon seul le pipeline quotidien les publie) ; des exécutions concurrentes des workflows peuvent écraser des entrées.

Tests : `tests/test_generateur_tickets.py` (Python et JavaScript doivent donner le même calcul), `tests/test_suivi_tickets.py`.

## Générateur de tickets : V2 exclu (09/10/2026)

- Sources du générateur : V3 et Journal, 15 paris au maximum chacune, 30 au maximum au total.
- V2.6.10 est exclu du générateur (trop instable). Son moteur et son archive continuent de tourner.
- Réintégration : ajouter `moteur_v2_6_10` à `SOURCES` dans `generateur_tickets.py` (et revoir `MAX_PAR_SOURCE`).
- Tests : `test_v2_est_exclu_du_generateur`, `test_quinze_par_source_au_maximum_et_rien_de_force`.

## Archive de la sélection du générateur — 10/10/2026

Problème : `data/tickets.json` est réécrit à chaque exécution, donc la liste des paris (V3 + Journal, 15 au maximum par source, par plage de dates) que le générateur a vraiment eue était perdue, et deux exécutions du même jour peuvent différer (ex. 09/10 : 11:50 UTC et 16:43 UTC).

`suivi_selection_generateur.py`, lancé par `construit_etat_systeme.py` (après `generateur_tickets.py`, dans `pipeline.yml` et `journal.yml`) écrit `data/selection_generateur_historique.json` :
- `executions` : une entrée par exécution dont la liste a changé (cote, probabilité, source, rang, plages où le pari figure). Jamais modifiée après coup.
- `resultats` : score et WIN/LOSS par pari (identité = match + marché canonique + source), écrits une seule fois quand le match est terminé. Journal (sans `match_id`) : rapprochement par date + noms d'équipes normalisés (`match_key`) ; V3 : par `match_id`. Équipes inversées ou autre date = autre match. Marché non reconnu, match sans score, match introuvable : pas de résultat, jamais « perdu » par défaut.
- `bilan` : réussite réelle contre probabilité estimée, par source et par jour du match. `derniere_erreur` affiche toute erreur de lecture des scores.
- Rattrapage depuis l'historique Git (si des exécutions ont été écrasées par des workflows concurrents) : `python suivi_selection_generateur.py --rattrapage`.
- `journal.yml` doit lister le fichier dans son `git add` (fait) ; `pipeline.yml` utilise `git add -A`.
- `scores_rattrapage.yml` règle aussi la sélection juste après avoir comblé les scores (étape dédiée + `git add` du fichier) : les résultats arrivent dès que les scores sont écrits, sans attendre le prochain pipeline.
- Limite connue : `suivi_tickets.py` règle les tickets par `match_id` ; les paris du Journal n'en ont pas (`match_id` nul) et leurs libellés ne sont pas reconnus tels quels par son évaluateur, donc les tickets contenant un pari du Journal restent « PENDING ». L'archive de sélection ne dépend pas de ce défaut.

Tests : `tests/test_selection_generateur.py` (cas qui passent et cas qui échouent par règle).


## Indice de performance du marché V3 — 10/10/2026

Code : `moteur_v3/performance.py` ; affiché par `archetype_v3.js` (champ `indice_performance` de chaque candidat) et dans le 7e bloc de la justification.

- Par équipe, sur ses matchs au même lieu (ceux de la justification) : **moyen** = somme des buts marqués ÷ nombre de matchs ; **pire** = le match qui éprouve le plus le marché. Pour (pire, pire) on teste toutes les paires (match du domicile, match de l'extérieur) et on garde la plus dure : aucun scénario ne peut être pire, pour tous les types de marchés (y compris la double chance 12). Pour (pire, moyen) et (moyen, pire), le pire match est celui de marge minimale face à la moyenne de l'adversaire.
- 4 scénarios : (domicile moyen/pire) × (extérieur moyen/pire). **Seuls les buts marqués comptent** : buts domicile = ce que marque le domicile dans son profil, buts extérieur = ce que marque l'extérieur dans le sien (correction de Patrick du 10/10 ; les buts encaissés ne servent pas).
- Un scénario valide le marché si sa marge contre la ligne est strictement > 0 (égalité exacte : non validé).
- Indice = scénarios validés sur 4 : 4/4 Sûr · 3/4 Recommandé · 2/4 Attention · 1/4 Risqué · 0/4 « Très risqué » (niveau ajouté par Claude, non défini par Patrick).
- Information seulement : ne change ni la probabilité, ni la sélection, ni la calibration. Marchés sans marge continue (score exact, nombre exact de buts, pair/impair, handicap X) : pas d'indice.
- Exemple de référence : Virton (3-0, 0-1, 3-0) – Hasselt (1-0, 0-3, 2-1), moins de 3,5 buts : pire = 3 + 2 = 5 buts → 1/4 Risqué.
- Tests : `tests/test_moteur_v3_performance.py`.
- Alternatives (ajout du 10/10) : sous l'indice du pari retenu, la carte affiche jusqu'à 3 marchés valides mais écartés par V3 (dominés ou trop liés), avec leur propre indice, par exemple « Alternative : Les deux équipes marquent (cote 1,52) · 4/4 · Sûr ». Champ `alternatives_indice`. Information seulement : la sélection ne change jamais.
