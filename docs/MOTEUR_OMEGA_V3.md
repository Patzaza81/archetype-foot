# Moteur Gamma = Omega V3 (`moteur_omega_v3/`, page `pronostics_gamma.html`) — 02/11/2026

Remplace le moteur DC sur la page Gamma, sur ordre de Patrick (« remplacer le moteur gamma … par ce dernier »), à partir de la spécification « NOUVEAU MOTEUR OMEGA V1 ».
Branche `moteur-gamma-omega-v3`, **non fusionnée** : la spécification dit elle-même qu'un remplacement de production demande une validation explicite. Fusion sur l'ordre « Fusionner » seulement.
Autonome (aucun import d'un autre moteur), hors générateur de tickets. L'ancien moteur DC (`moteur_dc/`, `data/dc/`, `docs/MOTEUR_DC.md`) est conservé sans modification.

## Méthode
- 4 séquences de 5 matchs au même lieu : attaque et défense de A (à domicile), attaque et défense de B (à l'extérieur). 5 × 5 × 5 × 5 = **625 scénarios**, aucun supprimé.
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

## Résultats de calibrage / validation (archive, 525 matchs du 28/09 au 01/11/2026)
Mis à jour par l'audit du 02/11/2026 : voir `docs/AUDIT_OMEGA_V3.md` (méthode, sources, limites).
- 383 marchés générés ; calibrage sur la **population jouable** (cote ≥ 1,26) : 13 marchés ont un seuil.
- Réserve chronologique (28/10 au 01/11, seuils appris avant) : 269 paris, 71,8 % réussis contre 75,7 % annoncés (écart 4,0 points, IC 95 % −0,9 à +10,0).
- Ancien calibrage (toutes observations) : 533 paris, 69,8 % contre 77,1 % : biais de sélection prouvé (voir l'audit).
- Aucune validation n'est annoncée ; seuls les paris gelés réels trancheront.
