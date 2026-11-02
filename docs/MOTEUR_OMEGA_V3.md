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
- 34 marchés sur 174 ont un seuil ; les autres n'ont jamais atteint 70 % sur l'archive.
- Réserve chronologique (matchs du 28/10 au 01/11, seuils appris avant) : 530 paris, **69,8 % réussis contre 77,1 % annoncés**.
- Brier : fréquence brute prise pour probabilité 0,1531 ; réussite lissée apprise 0,1445. Log loss : 0,6655 contre 0,4541.
- Sur la réserve, g 0,7–0,8 → 68 % réels ; g 0,9–1,0 → 90 % réels : la fréquence brute **surestime**.

## Limites et risques
- Minimum 5 matchs au même lieu : 659 matchs de l'archive exclus (données insuffisantes), couverture réduite.
- Échantillon court (5 semaines), seuils fragiles, taux annoncé surestimé d'environ 7 points.
- Les 625 scénarios ne sont pas indépendants : ils viennent de 20 observations seulement (4 séquences de 5).
- Aucune comparaison possible avec l'ancien Omega ou le DC avant d'avoir des matchs gelés réels (`bilan_reel.py`).
- Journal et page plus lourds que ceux du DC (≈ 1,4 Mo en 165 gels).
- Tests : `tests/test_moteur_omega_v3.py` (spécification §18), `tests/test_gamma_js.py`.
