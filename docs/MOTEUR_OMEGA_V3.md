# Moteur Gamma (`moteur_omega_v3/`, page `pronostics_gamma.html`) — 02/11/2026

Remplace le moteur DC sur la page Gamma, sur ordre de Patrick (« remplacer le moteur gamma … par ce dernier »), à partir de la spécification « NOUVEAU MOTEUR OMEGA V1 ».
Branche `moteur-gamma-omega-v3`, **non fusionnée** : la spécification dit elle-même qu'un remplacement de production demande une validation explicite. Fusion sur l'ordre « Fusionner » seulement.
Autonome (aucun import d'un autre moteur), hors générateur de tickets. L'ancien moteur DC (`moteur_dc/`, `data/dc/`, `docs/MOTEUR_DC.md`) est conservé sans modification.

## Méthode
- 4 séquences au même lieu : attaque et défense de A (à domicile), attaque et défense de B (à l'extérieur). **Règle de Patrick du 03/11/2026 : au moins 5 matchs au même lieu pour chaque équipe (sinon le match n'est pas analysé), au plus les 19 derniers.** Le nombre de scénarios est n_A² × n_B² (625 pour 5 et 5, jusqu'à 130 321 pour 19 et 19), aucun supprimé. Ancienne règle (fenêtre fixe de 5, spécification Omega V1) abandonnée.
- Les fréquences par palier sont calculées par comptage (mêmes valeurs que l'énumération, testé) pour tenir 130 321 scénarios.
- Score d'un scénario = (attaque A i, attaque B k). Les observations de défense ne servent qu'à la **compatibilité** : écart = max(|attA − défB|, |attB − défA|). Paliers cumulatifs strict (0) / intermédiaire (≤ 1) / élargi (≤ 2) / incompatible (> 2), paramétrables.
- 174 marchés générés depuis les scores (1N2, double chance, totaux, buts par équipe, handicaps, combinés, scores exacts…). Mi-temps, premier buteur, corners, cartons : non calculables, jamais inventés.
- Stabilité : fréquence recalculée en retirant une observation à la fois. **Fréquence robuste g = minimum** de ces valeurs et du brut. C'est la seule statistique de décision (pas d'indice composite).
- Une fréquence de scénarios **n'est pas une probabilité**. La probabilité calibrée = réussite réelle lissée de la tranche de g (archive).
- Sélection : g ≥ seuil du marché appris sur l'archive (protocole 70 % lissé, tranches de 5 points, PAV monotone, ≥ 30 prédictions, remboursements exclus) ; cote connue ≥ 1,26 ; jamais deux fois le même événement ; score exact jamais retenu. « AUCUN MARCHÉ RETENU » est un résultat valide.
- Les cotes ne changent jamais l'exploration. EV = information seulement.
- Contrôles mathématiques (§14) : un échec bloque la publication du match et fait échouer l'étape.
- Journal gelé `data/gamma/journal.jsonl` (ajout seul, dernier gel avant le coup d'envoi compte, résultat réglé une fois). Page : `data/gamma/pronostics.json`. Recalibrage : `python -m moteur_omega_v3.calibrage`.

## Interprétations (à confirmer par Patrick)
- « Score du scénario » = (attaque A, attaque B) ; la défense ne fait que filtrer par compatibilité.
- Les seuils par marché reprennent son protocole 70 % déjà approuvé, faute de seuil fixe dans la spécification (pas de constante arbitraire).

## Recalibrage du 03/11/2026 (nouvelle fenêtre 5 à 19 matchs)
Les seuils appris sur la fenêtre fixe de 5 ne valaient pas pour une fenêtre variable : recalibrage complet avec la nouvelle règle, sur l'archive disponible dans le dépôt le 03/11 (206 matchs joués analysables du 28/09 au 02/11, 4 marchés ont un seuil ; réserve chronologique : 24 paris, 75,0 % réussis contre 81,4 % annoncés). Échantillon plus petit que celui de l'audit ci-dessous : à refaire à mesure que l'archive grossit. Les chiffres ci-dessous décrivent l'ancienne règle (fenêtre de 5).

## Résultats de calibrage / validation de l'ancienne règle (fenêtre de 5 ; archive, 525 matchs du 28/09 au 01/11/2026)
Mis à jour par l'audit du 02/11/2026 : voir `docs/AUDIT_OMEGA_V3.md` (méthode, sources, limites).
- 383 marchés générés ; calibrage sur la **population jouable** (cote ≥ 1,26) : 13 marchés ont un seuil.
- Réserve chronologique (28/10 au 01/11, seuils appris avant) : 269 paris, 71,8 % réussis contre 75,7 % annoncés (écart 4,0 points, IC 95 % −0,9 à +10,0).
- Ancien calibrage (toutes observations) : 533 paris, 69,8 % contre 77,1 % : biais de sélection prouvé (voir l'audit).
- Aucune validation n'est annoncée ; seuls les paris gelés réels trancheront.

## Étoiles de l'échantillon et remarque « échantillons réels » (règle de Patrick, 03/11/2026)
- Chaque carte affiche des étoiles selon le nombre de matchs de chaque équipe (le plus petit des deux) : 5 matchs = 1 étoile ; 6 = 2 ; 7 à 8 = 3 ; 9 à 15 = 4 ; 16 à 19 = 5.
- Quand la fréquence robuste est à 100 % ET que les matchs réels confirment à 100 % pour les deux équipes, la carte écrit « Échantillons réels 6/6 pour les deux équipes » (ou « 6/6 et 7/7 »). Aucun message dans les autres cas. Page Gamma seulement.

## Calibrage provisoire du 03/11/2026 (résultats uniquement)

- Source : archive de test complète, 3 334 matchs joués, 1 156 analysables avec la règle inchangée (5 à 19 matchs au même lieu), sans cotes. Seuils appris sur les 70 % de matchs les plus anciens, vérifiés sur les 30 % suivants.
- Seuls les marchés confirmés sont mis à jour dans `parametres.json` (24 marchés : taux de base inférieur à 1/1,26, vérification ≥ 30 paris et ≥ 65 %). Les autres seuils (domicile marque +0,5, extérieur ne garde pas sa cage inviolée) restent tels quels ; aucun marché n'est interdit ou ajouté en dehors de ces 24.
- Un seuil à 0,50 ne filtre rien : le marché franchit 70 % grâce à son taux de base. Calibrage provisoire, à confirmer par les paris gelés (`bilan_reel.py`). Détail : clé `calibrage_provisoire` de `parametres.json`.
