"""
archetype_model/audit/report.py — Synthèse dashboard (chantier Patrick,
17/09/2026, module d'audit passif).

Lit la dernière entrée de "runs" (rétention de la nuit) et la dernière
entrée de "brier_history" (Brier score à froid) dans
data/audit_telemetry.json, produites respectivement par
telemetry.enregistre_scan() et telemetry.enregistre_scores_probabilistes().
Produit un fichier léger data/audit_status.json pour un dashboard --
lecture seule sur la télémétrie, n'écrit jamais ailleurs, ne modifie
aucun seuil de production.

Statut GREEN/YELLOW/RED déterminé UNIQUEMENT par le Brier score global
le plus récent -- seuils propres à ce dashboard (0.20 / 0.23, choix de
Patrick, 17/09/2026), sans aucun lien avec les seuils de production
(SEUIL_PEAGE1, COTE_MIN/MAX, EDV_MIN_*) ni avec
archetype_model/learning/calibration.py -- ce module ne fait AUCUNE
promotion, ne touche jamais config/adaptive_parameters.json.

Si aucun Brier score n'a encore été calculé (aucun match résolu, ou
enregistre_scores_probabilistes() jamais encore appelée), le statut est
"INCONNU" -- jamais un GREEN optimiste inventé faute de donnée.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
from typing import Any, Mapping, Optional

from archetype_model.audit import telemetry as _telemetry

FICHIER_STATUS_DEFAUT = "data/audit_status.json"

# Seuils du dashboard UNIQUEMENT -- sans lien de code avec les seuils de
# production. Les changer n'a aucun effet sur la sélection P1/P2/P3.
SEUIL_BRIER_GREEN = 0.20
SEUIL_BRIER_YELLOW = 0.23

STATUT_GREEN = "GREEN"
STATUT_YELLOW = "YELLOW"
STATUT_RED = "RED"
STATUT_INCONNU = "INCONNU"


def _statut_depuis_brier(brier_score_global: Optional[float]) -> str:
    if brier_score_global is None:
        return STATUT_INCONNU
    if brier_score_global <= SEUIL_BRIER_GREEN:
        return STATUT_GREEN
    if brier_score_global <= SEUIL_BRIER_YELLOW:
        return STATUT_YELLOW
    return STATUT_RED


def _ecrit_atomique(fichier: str, contenu: Mapping[str, Any]) -> None:
    dossier = os.path.dirname(fichier) or "."
    os.makedirs(dossier, exist_ok=True)
    fd, temporaire = tempfile.mkstemp(prefix=".audit_status.", suffix=".tmp", dir=dossier)
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


def genere_dashboard(
    fichier_telemetrie: str = _telemetry.FICHIER_TELEMETRIE_DEFAUT,
    fichier_status: str = FICHIER_STATUS_DEFAUT,
    horodatage: Optional[str] = None,
) -> dict[str, Any]:
    """Construit et persiste le résumé exécutif du dashboard à partir de
    la télémétrie déjà enregistrée. Ne calcule rien elle-même -- se
    contente de lire les dernières entrées de `fichier_telemetrie` et de
    les mettre en forme. Ne lève jamais si la télémétrie est encore
    vide -- retourne un statut INCONNU avec des compteurs à zéro plutôt
    qu'une exception (premier run avant tout historique)."""
    contenu = _telemetry.charge_telemetrie(fichier_telemetrie)
    dernier_run = contenu["runs"][-1] if contenu.get("runs") else None
    dernier_brier = contenu["brier_history"][-1] if contenu.get("brier_history") else None

    brier_score_global = (dernier_brier or {}).get("brier_score_global")
    statut = _statut_depuis_brier(brier_score_global)

    audit_integrite = (dernier_run or {}).get("audit_integrite", {})
    matchs_rejetes_donnees = sum(
        v for k, v in audit_integrite.items()
        if k in ("DATA_CORRUPTED", "INSUFFICIENT_DATA")
    )

    selection_finale = (dernier_run or {}).get("selection_finale") or {"P1": 0, "P2": 0, "P3": 0}
    filtre_convergence = (dernier_run or {}).get("filtre_convergence") or {}
    peage1 = (dernier_run or {}).get("peage1") or {}

    status = {
        "horodatage_controle": horodatage or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "statut_global": statut,
        "brier_score_global": brier_score_global,
        "log_loss_global": (dernier_brier or {}).get("log_loss_global"),
        "seuils_statut": {
            "GREEN": f"<= {SEUIL_BRIER_GREEN}",
            "YELLOW": f"<= {SEUIL_BRIER_YELLOW}",
            "RED": f"> {SEUIL_BRIER_YELLOW}",
        },
        "run": {
            "horodatage_run": (dernier_run or {}).get("horodatage"),
            "matchs_scannes": (dernier_run or {}).get("matchs_scannes_archetype_model", 0),
            "matchs_rejetes_donnees": matchs_rejetes_donnees,
            "marches_scannes": (dernier_run or {}).get("marches_scannes", 0),
            "peage1_rejetes": peage1.get("rejetes", 0),
            "convergence_eligibles": filtre_convergence.get("eligibles", 0),
            "qualifies_selection_finale": selection_finale,
        },
    }

    _ecrit_atomique(fichier_status, status)
    return status
