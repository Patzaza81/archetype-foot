# ROADMAP — Archetype Foot

Suivi de l'état des chantiers majeurs. Chaque statut ci-dessous n'est
posé qu'après vérification réelle (exécution de code, lecture directe
de la configuration active ou de l'historique git) -- jamais une
supposition. Voir `TRANSITION.md` pour le détail narratif complet de
chaque session.

Dernière mise à jour : 17/09/2026 (session #51 de `TRANSITION.md`).

---

## État des chantiers

### Péage 3 (EDV / filtre de cote) — **Actif & Verrouillé sur [1.26 - 1.80]**

- Plage active confirmée dans `config/adaptive_parameters.json`
  (`COTE_MIN: 1.26`, `COTE_MAX: 1.80`), lue dynamiquement par
  `archetype_model/signals/convergence.py` via `config_loader.py`.
- `COTE_MAX` promu de 1.74 à 1.80 le 16/09/2026 (commit `472c79e`,
  décision explicite de Patrick, édition directe du fichier de
  configuration).
- **Nuance à garder en tête** : "verrouillé" signifie que la valeur est
  active et volontaire, pas qu'elle est figée dans le code -- `COTE_MAX`
  reste un paramètre calibrable (`archetype_model/learning/garde_fous.py`,
  `PARAMETRES_CALIBRABLES`) que `calibration.py` pourrait promouvoir à
  nouveau à l'avenir, sous garde-fous renforcés (±2 % par cycle, ±8 %
  cumulé depuis l'origine 1.74).
- Trois assertions de `audit_permanent.py`, restées codées sur l'ancienne
  valeur 1.74, corrigées le 17/09/2026 (commits `8fb8272`, `a239fd6`) --
  voir session #51 de `TRANSITION.md`.

### Module d'audit passif (`archetype_model/audit/`) — **Déployé et branché**

- `circuit_breaker.py`, `telemetry.py`, `report.py` codés, 39 tests
  unitaires verts, intégrés dans `archetype_model/main.py` (avant Péage 1)
  et `precalcul.py` (télémétrie + dashboard en fin de nuit).
- Brier score mesuré sur les vraies données déjà résolues :
  **0,299 (zone RED)**.
- **Limite connue** : aucun déclenchement automatique de
  `telemetry.enregistre_scores_probabilistes()` n'existe encore dans
  `pipeline.yml` -- `archetype_model/learning/resultats.py` (qui résout
  les résultats réels) n'y est lui-même pas câblé (limite préexistante,
  pas propre à ce chantier). Le Brier score ne se met donc pas à jour
  seul aujourd'hui ; à appeler manuellement ou à brancher.
- **Limite connue** : au point d'intégration choisi, le motif
  `ECHANTILLON_INSUFFISANT` du circuit breaker ne peut plus se déclencher
  en pratique (le pipeline garantit déjà `n >= 5` avant ce point) --
  reste correct et testé, utile si le module est un jour appelé plus tôt.

---

## Prochaine étape prioritaire

**Finalisation des contrôles d'ingestion Data/Cache et intégration du
Dashboard Frontend.**

- Ingestion Data/Cache : consolider les contrôles déjà en place
  (`cache_equipes.py`, `cache_betpawa.py`, `cache_h2h.py`,
  `cache_classement.py`, TTL) avec le circuit breaker du module d'audit,
  aujourd'hui indépendants l'un de l'autre.
- Dashboard Frontend : afficher `data/audit_status.json` sur une page du
  site, sur le modèle de `systeme.html` (déjà existant pour le bilan
  comportemental et la calibration) -- pas commencée à ce jour.

## Connu, non planifié, à ne pas perdre de vue

- 14 échecs pré-existants dans `audit_permanent.py`, confirmés sans
  rapport avec le module d'audit (voir session #51 de `TRANSITION.md`) --
  en particulier un rejeu réel du 10/09/2026 dont les chiffres obtenus
  (35 candidats / 29 matchs) ne correspondent plus aux chiffres attendus
  (68/48), possible divergence de comportement réelle du moteur jamais
  expliquée.
- `garde_fous.verifier_rollback()` existe mais n'est jamais appelé par
  `calibre_archetype_model.py` -- aucun rollback automatique aujourd'hui
  si un paramètre promu se révèle mauvais après coup (signalé depuis la
  session #47 de `TRANSITION.md`, toujours pas traité).
