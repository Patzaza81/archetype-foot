"""
archetype_model/audit/telemetry.py — Télémétrie du moteur (chantier
Patrick, 17/09/2026, module d'audit passif).

DEUX RESPONSABILITÉS DISTINCTES, DEUX MOMENTS DIFFÉRENTS :

1. enregistre_scan(signaux) -- appelée EN FIN DE NUIT, juste après que
   applique_archetype_model() (precalcul.py) a traité tous les matchs.
   Agrège, pour CETTE nuit, le nombre de marchés scannés et leur devenir
   à travers les VRAIS étages du pipeline tels qu'ils existent
   réellement dans archetype_model/main.py et
   archetype_model/signals/convergence.py -- PAS un entonnoir "P1 à P4"
   générique. Voir la note de correspondance ci-dessous.

2. calcule_scores_probabilistes() / enregistre_scores_probabilistes() --
   appelées SÉPARÉMENT, un jour plus tard (ou à la demande), une fois
   que archetype_model/learning/resultats.py a résolu les matchs
   réellement joués. Impossible de calculer un Brier score ou un
   log-loss AVANT de connaître le résultat réel -- ces fonctions ne
   RECALCULENT jamais un résultat elles-mêmes, elles lisent uniquement
   les enregistrements déjà marqués RESOLVED dans
   archetype_model/learning/archive/YYYY-MM.json (probabilite du modèle
   vs resultat_marche réel WIN/LOSS déjà tranché par
   archetype_model/learning/reglement.py).

NOTE DE CORRESPONDANCE (pourquoi ce n'est pas un entonnoir P1->P4) :
le pipeline réel (voir docstring de signals/convergence.py) est
    DONNEES -> ... -> PÉAGE 1 (matrice_croisement, seuil 0.85)
    -> FILTRE DE CONVERGENCE (n>=5, probabilité>=60%, cote dans
       [COTE_MIN, COTE_MAX], EDV >= table graduée, robustesse STABLE)
    -> DÉDOUBLONNAGE -> H2H (arbitre INFORMATIF, ne rejette jamais)
    -> SÉLECTION FINALE (P1 = meilleur EDV, P2 = meilleure probabilité
       parmi les survivants, P3 = meilleure cote parmi les survivants).
P1/P2/P3 sont des RANGS de sélection finale, jamais des péages
séquentiels avec seuil propre -- il n'existe pas de "P4" dans le
pipeline réel. Ce module mesure donc explicitement : Péage 1,
Filtre de convergence, H2H (distribution informative), Sélection
finale -- plutôt que d'inventer une correspondance qui n'existe pas
dans le code.

AUCUNE fonction de ce fichier n'écrit dans config/adaptive_parameters.json,
n'appelle calibration.py, ni ne modifie un enregistrement d'archive déjà
résolu (lecture seule sur archive/).
"""

from __future__ import annotations

import datetime
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from archetype_model.learning import archive as _archive
from archetype_model.learning import reglement as _reglement
from archetype_model.audit import circuit_breaker as _circuit_breaker

FICHIER_TELEMETRIE_DEFAUT = "data/audit_telemetry.json"
REPERTOIRE_ARCHIVE_DEFAUT = "archive"

MAX_RUNS_CONSERVES = 60
MAX_BRIER_CONSERVES = 60
MAX_MATCHS_NEUTRALISES_PAR_RUN = 50

STATUT_AUDIT_OK = _circuit_breaker.STATUT_OK

EPSILON_LOG_LOSS = 1e-9


# ============================================================================
# 1. TÉLÉMÉTRIE DE RÉTENTION PAR ÉTAGE (une entrée par run)
# ============================================================================

def _est_rejet_peage1(diagnostic: Mapping[str, Any]) -> bool:
    """Un diagnostic de Péage 1 (voir _motif_peage1 dans main.py) porte
    la clé 'motif_rejet' dans son 'filtre'. Un diagnostic ayant atteint
    le filtre de convergence porte AUSSI 'motif_rejet'
    (ResultatFiltreConvergent.as_dict(), convergence.py, valeur None si
    éligible sinon un motif MotifRejet) -- 'motif_rejet' seul ne suffit
    donc PAS à distinguer les deux formes (bug confirmé en production
    le 17/09/2026 : 100% des diagnostics classés Péage 1, motifs de
    convergence comme COTE_HORS_INTERVALLE/PROBABILITE_TROP_FAIBLE
    comptés à tort dans peage1_motifs). Seule 'resultats_par_scenario'
    est propre à ResultatFiltreConvergent.as_dict() -- absente d'un
    rejet Péage 1 (qui porte plutôt 'score_pondere'/'signal_matrice'/
    'seuil', voir _verifie_peage1/_motif_peage1 dans main.py)."""
    filtre = diagnostic.get("filtre") or {}
    return "motif_rejet" in filtre and "resultats_par_scenario" not in filtre


def _agrege_diagnostics(tous_diagnostics: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    marches_scannes = 0
    peage1_rejetes = 0
    peage1_motifs: Counter[str] = Counter()
    convergence_eligibles = 0
    convergence_rejetes = 0
    convergence_motifs: Counter[str] = Counter()
    h2h_statuts: Counter[str] = Counter()

    for diag in tous_diagnostics:
        marches_scannes += 1
        filtre = diag.get("filtre") or {}

        h2h_statut = diag.get("h2h_statut")
        if h2h_statut is not None:
            h2h_statuts[str(h2h_statut)] += 1

        if _est_rejet_peage1(diag):
            peage1_rejetes += 1
            peage1_motifs[str(filtre.get("motif_rejet"))] += 1
            continue

        # A atteint le filtre de convergence (accepté ou rejeté là).
        if filtre.get("eligible"):
            convergence_eligibles += 1
        else:
            convergence_rejetes += 1
            # ResultatFiltreConvergent.as_dict() porte le motif de rejet
            # sous "motif_rejet" (jamais "motif" -- cette dernière clé
            # appartient à ResultatFiltre.as_dict(), la version
            # par-scénario interne à filtre_marche_convergent(), jamais
            # celle qui atterrit dans diagnostics -- confirmé en
            # production le 17/09/2026, corrigé au même moment que
            # _est_rejet_peage1 ci-dessus).
            convergence_motifs[str(filtre.get("motif_rejet"))] += 1

    return {
        "marches_scannes": marches_scannes,
        "peage1_rejetes": peage1_rejetes,
        "peage1_motifs": peage1_motifs,
        "convergence_eligibles": convergence_eligibles,
        "convergence_rejetes": convergence_rejetes,
        "convergence_motifs": convergence_motifs,
        "h2h_statuts": h2h_statuts,
    }


def charge_telemetrie(fichier: str) -> dict[str, Any]:
    if not os.path.exists(fichier):
        return {"runs": [], "brier_history": []}
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            contenu = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"runs": [], "brier_history": []}
    if not isinstance(contenu, dict):
        return {"runs": [], "brier_history": []}
    contenu.setdefault("runs", [])
    contenu.setdefault("brier_history", [])
    return contenu


def _ecrit_atomique(fichier: str, contenu: Mapping[str, Any]) -> None:
    dossier = os.path.dirname(fichier) or "."
    os.makedirs(dossier, exist_ok=True)
    fd, temporaire = tempfile.mkstemp(prefix=".audit_telemetry.", suffix=".tmp", dir=dossier)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaire, fichier)
    except Exception:
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


def _ajoute_entree(fichier: str, cle: str, entree: Mapping[str, Any]) -> None:
    contenu = charge_telemetrie(fichier)
    contenu[cle].append(entree)
    limite = MAX_RUNS_CONSERVES if cle == "runs" else MAX_BRIER_CONSERVES
    if len(contenu[cle]) > limite:
        contenu[cle] = contenu[cle][-limite:]
    _ecrit_atomique(fichier, contenu)


def enregistre_scan(
    signaux: Iterable[Mapping[str, Any]],
    fichier: str = FICHIER_TELEMETRIE_DEFAUT,
    horodatage: Optional[str] = None,
) -> dict[str, Any]:
    """Agrège la rétention de la nuit à partir des `signaux` déjà
    traités par applique_archetype_model() (precalcul.py) -- ne relit
    rien sur le réseau, ne recalcule aucune décision, se contente de
    compter ce que le moteur a déjà produit (s["archetype_model"] et,
    si présent, s["audit_integrite"] posé par circuit_breaker.py).

    Ajoute une entrée horodatée à `fichier` (clé "runs") et la retourne.
    """
    horodatage = horodatage or datetime.datetime.now(datetime.timezone.utc).isoformat()

    tous_diagnostics: list[Mapping[str, Any]] = []
    matchs_scannes_am = 0
    matchs_statut_ok = 0
    selection_counts = {"P1": 0, "P2": 0, "P3": 0}
    audit_integrite_counts: Counter[str] = Counter()
    matchs_neutralises: list[dict[str, Any]] = []

    for s in signaux:
        if s.get("moteur_utilise") != "archetype_model":
            continue
        matchs_scannes_am += 1

        resultat = s.get("archetype_model") or {}

        # Posé par circuit_breaker.evalue_integrite() DANS
        # analyse_match_complet() (archetype_model/main.py), avant le
        # Péage 1 -- additif au résultat, présent même quand statut !=
        # "OK" (COTES_INDISPONIBLES notamment n'a pas ce champ, la
        # vérification d'intégrité intervient après ce point de sortie
        # anticipé -- absence normale, jamais une erreur).
        audit = resultat.get("audit_integrite")
        if audit:
            statut_audit = str(audit.get("statut"))
            audit_integrite_counts[statut_audit] += 1
            # Liste légère des matchs neutralisés (nom + motifs), pour le
            # dashboard (Bloc 2 "Filtre d'intégrité") -- indépendante du
            # statut global du match (un audit DATA_CORRUPTED n'empêche
            # jamais le pipeline de continuer, voir circuit_breaker.py :
            # module purement passif). Plafonnée pour rester légère --
            # un run avec des centaines de matchs dégradés reste visible
            # via les compteurs ci-dessus même si la liste est tronquée.
            if statut_audit != STATUT_AUDIT_OK and len(matchs_neutralises) < MAX_MATCHS_NEUTRALISES_PAR_RUN:
                matchs_neutralises.append({
                    "domicile": s.get("domicile"),
                    "exterieur": s.get("exterieur"),
                    "date": s.get("date"),
                    "statut": statut_audit,
                    "motifs": [m.get("motif") for m in (audit.get("motifs") or [])],
                })

        if resultat.get("statut") != "OK":
            continue
        matchs_statut_ok += 1

        tous_diagnostics.extend(resultat.get("diagnostics") or [])

        selection = resultat.get("selection") or {}
        for rang in ("P1", "P2", "P3"):
            if selection.get(rang):
                selection_counts[rang] += 1

    compteurs = _agrege_diagnostics(tous_diagnostics)

    entree = {
        "horodatage": horodatage,
        "matchs_scannes_archetype_model": matchs_scannes_am,
        "matchs_statut_ok": matchs_statut_ok,
        "audit_integrite": dict(audit_integrite_counts),
        "matchs_neutralises": matchs_neutralises,
        "marches_scannes": compteurs["marches_scannes"],
        "peage1": {
            "rejetes": compteurs["peage1_rejetes"],
            "passes": compteurs["marches_scannes"] - compteurs["peage1_rejetes"],
            "motifs_rejet": dict(compteurs["peage1_motifs"]),
        },
        "filtre_convergence": {
            "eligibles": compteurs["convergence_eligibles"],
            "rejetes": compteurs["convergence_rejetes"],
            "motifs_rejet": dict(compteurs["convergence_motifs"]),
        },
        "h2h_informatif": dict(compteurs["h2h_statuts"]),
        "selection_finale": selection_counts,
    }

    _ajoute_entree(fichier, "runs", entree)
    return entree


# ============================================================================
# 2. BRIER SCORE / LOG-LOSS À FROID (lecture seule sur l'archive résolue)
# ============================================================================

def _brier(p: float, y: float) -> float:
    return (p - y) ** 2


def _log_loss(p: float, y: float) -> float:
    p_clip = min(max(p, EPSILON_LOG_LOSS), 1.0 - EPSILON_LOG_LOSS)
    return -(y * math.log(p_clip) + (1.0 - y) * math.log(1.0 - p_clip))


def _lit_records_resolus(
    mois: Optional[str] = None,
    repertoire_archive: str = REPERTOIRE_ARCHIVE_DEFAUT,
) -> list[dict[str, Any]]:
    """mois au format 'YYYY-MM', ou None pour lire tous les fichiers
    archive/*.json trouvés. Ne lève jamais si le dossier ou un mois
    précis est absent -- retourne simplement une liste vide (rien à
    calculer pour l'instant, pas une erreur)."""
    repertoire = Path(repertoire_archive)
    if mois:
        chemins = [repertoire / f"{mois}.json"]
    elif repertoire.exists():
        chemins = sorted(repertoire.glob("*.json"))
    else:
        chemins = []

    records: list[dict[str, Any]] = []
    for chemin in chemins:
        if not chemin.exists():
            continue
        records.extend(_archive.charger_archive(chemin))

    return [r for r in records if r.get("resultat_statut") == _archive.STATUT_RESOLVED]


def _calcule_depuis_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Coeur du calcul, isolé de la lecture disque pour rester testable
    sur des records synthétiques sans dépendre de la validation stricte
    d'archive.py (laquelle garantit déjà, côté écriture, qu'un
    enregistrement RESOLVED a toujours un resultat_marche WIN/LOSS --
    voir archive._valider_record). Cette fonction reste défensive quand
    même : un enregistrement sans probabilité exploitable, ou dont le
    résultat n'est ni WIN ni LOSS, est compté à part dans
    "n_records_ignores", jamais mélangé silencieusement au calcul."""
    records = list(records)
    par_marche: dict[str, dict[str, Any]] = {}
    brier_global: list[float] = []
    logloss_global: list[float] = []
    ignores = 0

    for r in records:
        p = r.get("probabilite")
        resultat_marche = r.get("resultat_marche")
        if not isinstance(p, (int, float)) or resultat_marche not in (_reglement.WIN, _reglement.LOSS):
            ignores += 1
            continue

        y = 1.0 if resultat_marche == _reglement.WIN else 0.0
        b = _brier(float(p), y)
        ll = _log_loss(float(p), y)

        brier_global.append(b)
        logloss_global.append(ll)

        marche = r.get("marche") or "inconnu"
        bucket = par_marche.setdefault(marche, {"brier": [], "logloss": []})
        bucket["brier"].append(b)
        bucket["logloss"].append(ll)

    def _moyenne(valeurs: list[float]) -> Optional[float]:
        return round(sum(valeurs) / len(valeurs), 6) if valeurs else None

    return {
        "n_records_resolus": len(records),
        "n_records_utilises": len(brier_global),
        "n_records_ignores": ignores,
        "brier_score_global": _moyenne(brier_global),
        "log_loss_global": _moyenne(logloss_global),
        "par_marche": {
            marche: {
                "n": len(bucket["brier"]),
                "brier_score": _moyenne(bucket["brier"]),
                "log_loss": _moyenne(bucket["logloss"]),
            }
            for marche, bucket in sorted(par_marche.items())
        },
    }


def calcule_scores_probabilistes(
    mois: Optional[str] = None,
    repertoire_archive: str = REPERTOIRE_ARCHIVE_DEFAUT,
) -> dict[str, Any]:
    """Brier score et log-loss, globaux et par marché, calculés
    UNIQUEMENT sur les enregistrements déjà résolus (resultat_statut ==
    RESOLVED) d'archetype_model/learning/archive/. Ne modifie jamais ces
    enregistrements -- lecture seule (voir _calcule_depuis_records pour
    le coeur du calcul, testable indépendamment de la lecture disque)."""
    records = _lit_records_resolus(mois, repertoire_archive)
    return _calcule_depuis_records(records)


def enregistre_scores_probabilistes(
    mois: Optional[str] = None,
    repertoire_archive: str = REPERTOIRE_ARCHIVE_DEFAUT,
    fichier: str = FICHIER_TELEMETRIE_DEFAUT,
    horodatage: Optional[str] = None,
) -> dict[str, Any]:
    """Calcule (calcule_scores_probabilistes) puis persiste le résultat,
    horodaté, dans `fichier` (clé "brier_history"). Fonction séparée de
    enregistre_scan() à dessein -- appelée à un autre moment du cycle
    (une fois les résultats réels connus), jamais depuis
    applique_archetype_model() elle-même."""
    resultat = calcule_scores_probabilistes(mois, repertoire_archive)
    entree = {
        "horodatage": horodatage or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **resultat,
    }
    _ajoute_entree(fichier, "brier_history", entree)
    return entree
