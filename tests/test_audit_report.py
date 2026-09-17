"""Tests du générateur de dashboard (archetype_model/audit/report.py).

Vérifie les bornes exactes GREEN/YELLOW/RED, le cas "aucune donnée
encore" (INCONNU, jamais un GREEN optimiste inventé), et que le fichier
produit est un JSON valide et cohérent avec la dernière télémétrie.
"""

import json
from pathlib import Path

from archetype_model.audit import report as rpt
from archetype_model.audit import telemetry as tel


def _ecrit_telemetrie(fichier, runs=None, brier_history=None):
    contenu = {"runs": runs or [], "brier_history": brier_history or []}
    Path(fichier).write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")


def test_statut_green_a_la_limite(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    _ecrit_telemetrie(fichier_tel, brier_history=[{"brier_score_global": 0.20}])
    status = rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=str(tmp_path / "status.json"))
    assert status["statut_global"] == rpt.STATUT_GREEN


def test_statut_yellow_juste_au_dessus_de_green(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    _ecrit_telemetrie(fichier_tel, brier_history=[{"brier_score_global": 0.2001}])
    status = rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=str(tmp_path / "status.json"))
    assert status["statut_global"] == rpt.STATUT_YELLOW


def test_statut_yellow_a_la_limite_haute(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    _ecrit_telemetrie(fichier_tel, brier_history=[{"brier_score_global": 0.23}])
    status = rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=str(tmp_path / "status.json"))
    assert status["statut_global"] == rpt.STATUT_YELLOW


def test_statut_red_juste_au_dessus_de_yellow(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    _ecrit_telemetrie(fichier_tel, brier_history=[{"brier_score_global": 0.2301}])
    status = rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=str(tmp_path / "status.json"))
    assert status["statut_global"] == rpt.STATUT_RED


def test_statut_inconnu_sans_aucune_donnee(tmp_path):
    """Aucune télémétrie encore enregistrée -- jamais un GREEN inventé
    faute de donnée."""
    fichier_status = str(tmp_path / "status.json")
    status = rpt.genere_dashboard(
        fichier_telemetrie=str(tmp_path / "n_existe_pas.json"),
        fichier_status=fichier_status,
    )
    assert status["statut_global"] == rpt.STATUT_INCONNU
    assert status["brier_score_global"] is None


def test_dashboard_reprend_les_compteurs_du_dernier_run(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    _ecrit_telemetrie(
        fichier_tel,
        runs=[{
            "horodatage": "2026-09-17T00:00:00+00:00",
            "matchs_scannes_archetype_model": 500,
            "audit_integrite": {"DATA_CORRUPTED": 3, "INSUFFICIENT_DATA": 7, "OK": 490},
            "marches_scannes": 2000,
            "peage1": {"rejetes": 1500, "passes": 500, "motifs_rejet": {}},
            "filtre_convergence": {"eligibles": 200, "rejetes": 300, "motifs_rejet": {}},
            "selection_finale": {"P1": 150, "P2": 120, "P3": 90},
        }],
        brier_history=[{"brier_score_global": 0.18, "log_loss_global": 0.5}],
    )
    status = rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=str(tmp_path / "status.json"))
    assert status["run"]["matchs_scannes"] == 500
    assert status["run"]["matchs_rejetes_donnees"] == 10  # 3 + 7
    assert status["run"]["peage1_rejetes"] == 1500
    assert status["run"]["convergence_eligibles"] == 200
    assert status["run"]["qualifies_selection_finale"] == {"P1": 150, "P2": 120, "P3": 90}
    assert status["statut_global"] == rpt.STATUT_GREEN


def test_dashboard_ecrit_un_fichier_json_valide(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    fichier_status = str(tmp_path / "status.json")
    _ecrit_telemetrie(fichier_tel, brier_history=[{"brier_score_global": 0.15}])
    rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=fichier_status)
    with open(fichier_status, encoding="utf-8") as f:
        contenu = json.load(f)  # lève si invalide
    assert "statut_global" in contenu
    assert "horodatage_controle" in contenu


def test_dashboard_ne_modifie_jamais_la_telemetrie(tmp_path):
    fichier_tel = str(tmp_path / "telemetrie.json")
    _ecrit_telemetrie(fichier_tel, brier_history=[{"brier_score_global": 0.15}])
    avant = Path(fichier_tel).read_text(encoding="utf-8")
    rpt.genere_dashboard(fichier_telemetrie=fichier_tel, fichier_status=str(tmp_path / "status.json"))
    apres = Path(fichier_tel).read_text(encoding="utf-8")
    assert avant == apres
