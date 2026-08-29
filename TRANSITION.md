# Archetype Foot — Document de transition
Dernière mise à jour : 29/08/2026 (canal de déclenchement automatique --
panier partagé, garde-fou d'échantillon insuffisant, chantier de
vérification des résultats), dans la continuité d'une session longue.
Objectif de ce document : permettre de reprendre le projet dans une nouvelle
fenêtre de conversation sans perdre l'historique de décisions, ni répéter
les erreurs déjà identifiées et corrigées.

---

## ✅ BUG RÉSOLU (26/08/2026) — cote invraisemblable sur ligne over/under haute

**Symptôme d'origine (25/08/2026)** : match Gil Vicente-Casa Pia,
lambda_home=1.96, lambda_away=0.60 → modèle donne 99.3% de probabilité sur
"Moins de 6.5 buts", cote scrapée = 1.61 (attendu : 1.00-1.05, cf. cotes
réelles observées sur des lignes similaires ailleurs dans le projet).

**Cause racine confirmée** : dans `recupere_cotes_marches`
(`scraper_details.py`), l'ancrage du titre de marché utilisait
`soup.find(string=...)`, qui retourne la PREMIÈRE occurrence du texte dans
tout le document. Or un même titre de marché peut apparaître deux fois sur
la page matchendirect : une fois dans un widget d'aperçu en haut de page
(sans Bet365 parmi les bookmakers affichés), une fois dans le tableau
complet plus bas (avec Bet365). Confirmé sur HTML réel récupéré le
26/08/2026 (match Valence-Real Betis, LaLiga) : le titre "Mi-temps -
Résultat" apparaît deux fois exactement selon ce schéma. Si un jour ce
widget d'aperçu affiche un marché réellement exploité (1N2, BTTS, une
ligne over/under) plutôt que "Mi-temps", `soup.find` ancre sur l'aperçu, et
la marche `find_all_next()` (sans limite) qui cherche ensuite le logo
Bet365 dérive à travers tout le contenu intermédiaire (Détails du match,
Pronostic...) jusqu'au prochain titre reconnu — pouvant renvoyer la cote
Bet365 d'un AUTRE marché, réelle mais mal associée, sans jamais lever
d'erreur ni de `None`. C'est le mécanisme le plus probable derrière la cote
de 1.61 : une valeur cohérente pour un marché 1N2, pas pour un
over/under 6.5.

**Correctif appliqué** : `soup.find` remplacé par `soup.find_all` +
sélection de la DERNIÈRE occurrence (le tableau complet étant
structurellement le dernier endroit où un titre de marché apparaît sur la
page). Commité sur `main` le 26/08/2026.

**Confirmé en conditions réelles le 28/08/2026** : plusieurs runs de
production depuis (25, 126 matchs) montrent `cote_1` systématiquement
renseigné, y compris sur des lignes over/under hautes -- plus aucune
occurrence du symptôme d'origine observée.

---

## ✅ BUG RÉSOLU (29/08/2026) — GO possible sur un échantillon d'1 match

**Symptôme confirmé sur run réel (126 matchs, 28/08/2026 23:19-23:35)** :
Bolton-Lincoln, verdict **GO à 95.1%**, étiqueté explicitement "confiance
FAIBLE (1 matchs domicile / 1 matchs extérieur)" -- le système savait que
sa donnée était insuffisante et l'a affiché, mais a quand même recommandé
un pari dessus. Même schéma sur Cardiff-Sheffield Utd (1/1) et un lambda
domicile calculé à 0.00 pour Gaziantep FK-Rizespor (1 match domicile,
un score nul entraînant une espérance de buts artificiellement nulle).

**Cause racine confirmée** : `confiance_lambda()` (`calculs.py`) calcule
bien l'étiquette FAIBLE/MOYENNE/NORMALE à partir du nombre de matchs
utilisés, mais son propre commentaire le dit explicitement -- *"indicateur
descriptif, ne modifie aucun calcul"*. `decision_go_nogo()` ne recevait
jamais cette information et ne pouvait donc jamais en tenir compte. Le
mécanisme de repli sur la saison précédente (`recupere_gf_ga_avec_repli`,
section 12) va bien chercher un complément, mais ne bascule en
"non traité" QUE si le total est de zéro match des deux côtés -- un seul
match trouvé après recherche des deux saisons est considéré comme
suffisant pour lancer le calcul complet.

**Correctif appliqué** : `decision_go_nogo()` (`calculs.py`) accepte deux
nouveaux paramètres optionnels (`nb_matchs_domicile_utilises`,
`nb_matchs_exterieur_utilises`) et force désormais **NO_GO** si l'un des
deux est sous le seuil `CONFIANCE_LAMBDA_SEUILS["FAIBLE"]` (8), quel que
soit l'EV calculé -- avec un motif explicite ("échantillon insuffisant --
X match(s) ... utilisés, minimum 8 requis"). `run_pipeline.py` transmet
ces deux valeurs à l'appel (déjà disponibles via `stats_domicile`/
`stats_exterieur`). Commité sur `main` le 29/08/2026.

**Confirmé en conditions réelles le 29/08/2026** : re-run du même lot,
Bolton-Lincoln et Cardiff-Sheffield Utd basculent tous les deux en NO_GO
avec le motif attendu. Aucun autre appelant de `decision_go_nogo()`
n'existant dans le dépôt, aucune régression possible ailleurs.

**Nuance assumée, à garder en tête** : le seuil bloque uniquement la
confiance FAIBLE (< 8 matchs). La confiance MOYENNE (8-14 matchs) reste
autorisée à produire un GO -- c'est un choix de seuil, pas un oubli, mais
à revoir si des faux positifs réapparaissent dans cette tranche.

---

## ⚠️ PROBLÈME IDENTIFIÉ, NON CORRIGÉ (29/08/2026) — moyenne GF/GA sensible à un score extrême

**Symptôme observé sur run réel (126 matchs, 28/08/2026)** : Panaitolikos-
PS PAE Kalamata, confiance MOYENNE (10 matchs domicile / 10 extérieur --
donc au-dessus du seuil corrigé ci-dessus), GO à 90.8%, EV 40.8% sur
Double chance X2. `gf_exterieur` (base) = 2.40 buts/match, largement
au-dessus d'une moyenne extérieure plausible (généralement 1.0-1.6). Un EV
de cet ordre est plus souvent le signe d'une entrée de données faussée que
d'une vraie opportunité manquée par le marché.

**Cause probable, non confirmée** : `recupere_gf_ga_avec_repli`
(`scraper_details.py`) calcule `gf_exterieur`/`ga_exterieur` comme une
simp
