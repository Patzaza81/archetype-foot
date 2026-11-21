# Infos de match par IA gratuite (21/11/2026)

Demande de Patrick : trouver automatiquement blessés, absents, suspendus et cartons rouges, avec une IA qui utilise la recherche Google, **gratuitement**. Les H2H existent déjà sur la page (onglet H2H de « Derniers matchs », calculés sur nos données).

## Ce que fait le module (`infos_matchs.py`)

- Appelle l'API Gemini (`gemini-2.5-flash`) avec l'outil `google_search`, un appel par match, sur les matchs à venir dans les 30 prochaines heures qui figurent sur la page de vérification.
- Écrit `data/infos_matchs/infos.json` ; la page `pronostics_verif.html` l'affiche sous chaque match : « Absents et sanctions », les sources consultées, la date de consultation, et la mention **non confirmé**.
- **Mode mesure** : ni la collecte, ni `contrat_moteur.py`, ni un moteur, ni un pronostic, ni un journal gelé ne lisent ce fichier. Un test l'impose.

## Gratuité (vérifiée sur la page officielle des tarifs, 21/11/2026)

- Recherche Google gratuite en niveau gratuit : Gemini 2.5 Flash et Flash-Lite, jusqu'à **500 requêtes par jour** (quota partagé). Les modèles Gemini 3 et le modèle Pro n'ont pas cet accès gratuit.
- Le plafond du module est de 400 appels par jour (`plafond_appels_par_jour`) et 120 par passage : sous le quota.
- **Ne jamais activer la facturation sur le projet de la clé** : le niveau payant fait payer la recherche au-delà du quota. Une clé sans facturation ne peut pas être débitée.
- Au niveau gratuit, Google peut utiliser les requêtes pour améliorer ses produits : le module n'envoie que les noms d'équipes, la compétition et la date.
- Un refus 429 arrête le passage (jamais de nouvel essai forcé).

## Règles de lecture de la réponse

- Aucune source renvoyée par la recherche → tout est jeté (`sans_source`). Une IA qui répond sans avoir cherché n'est pas crue.
- Une ligne est gardée seulement si l'équipe désigne une seule des deux équipes du match, si le joueur est nommé et si le statut est connu (blessé, suspendu, absent, incertain). Le doute = rien. Les doublons sont retirés.
- La clé n'est jamais écrite dans les données ni dans un message d'erreur.

## Limites connues

- **Non testé en réel** : la clé n'existait pas au moment de l'écriture. La réponse de l'API change (forme `generateContent` avec `groundingMetadata`, et forme « Interactions » avec `url_citation`) : le lecteur gère les deux. Premier test : `python infos_matchs.py essai "Équipe A" "Équipe B"` (une requête, rien d'écrit), ou le workflow à la main avec « essai ».
- Une IA peut citer une blessure ancienne comme actuelle ou en oublier une. D'où « non confirmé » et la consigne de vérifier la composition officielle (publiée environ une heure avant le match).
- Pas de mesure de fiabilité encore : à faire sur plusieurs semaines (absences annoncées contre matchs réellement joués) avant toute intégration dans un moteur.

## Activer

1. Google AI Studio : créer une clé API **sans facturation**.
2. Dépôt GitHub : Settings → Secrets and variables → Actions → nouveau secret `GEMINI_API_KEY`.
3. Lancer le workflow « Infos de match (IA gratuite) » (il s'exécute ensuite après la calibration quotidienne).

Tests : `tests/test_infos_matchs.py` (hors ligne, fausses réponses).
