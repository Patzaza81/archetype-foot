"""Tests de la télémétrie (archetype_model/audit/telemetry.py).

Deux volets testés séparément, comme le code : l'agrégation de
rétention par étage (enregistre_scan, données synthétiques en mémoire)
et le calcul Brier/log-loss (calcule_scores_probabilistes, sur une
fausse archive écrite sur disque dans tmp_path -- jamais sur la vraie
archive/ du dépôt).
"""

import json
import math
from pathlib import Path

from archetype_model.audit import telemetry as tel
from archetype_model.learning import archive as arch
from archetype_model.learning import reglement as regl


# ----------------------------------------------------------------------
# enregistre_scan -- agrégation de rétention par étage
# ----------------------------------------------------------------------

def _diag_peage1_rejete(marche="over_2.5"):
    return {
        "marche": marche,
        "filtre": {
            "eligible": False,
            "motif_rejet": "MATRIX_SIGNAL_TOO_LOW",
            "score_pondere": 0.5,
            "signal_matrice": "over_2_5",
            "seuil": 0.85,
        },
        "h2h_statut": None,
    }


def _diag_convergence(eligible, motif=None, h2h_statut=None):
    return {
        "marche": "1x2_domicile",
        "filtre": {
            "decision": "ELIGIBLE" if eligible else "REJETE",
            "eligible": eligible,
            "motif": motif,
        },
        "h2h_statut": h2h_statut,
    }


def _signal_archetype_model(diagnostics, selection=None, statut="OK", moteur="archetype_model"):
    return {
        "moteur_utilise": moteur,
        "archetype_model": {
            "statut": statut,
            "diagnostics": diagnostics,
            "selection": selection or {"P1": None, "P2": None, "P3": None},
        },
    }


def test_enregistre_scan_compte_les_rejets_peage1(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    signaux = [
        _signal_archetype_model([_diag_peage1_rejete(), _diag_convergence(True)]),
    ]
    entree = tel.enregistre_scan(signaux, fichier=fichier)
    assert entree["marches_scannes"] == 2
    assert entree["peage1"]["rejetes"] == 1
    assert entree["peage1"]["passes"] == 1
    assert entree["peage1"]["motifs_rejet"] == {"MATRIX_SIGNAL_TOO_LOW": 1}


def test_enregistre_scan_compte_les_rejets_convergence(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    signaux = [
        _signal_archetype_model([
            _diag_convergence(True),
            _diag_convergence(False, motif="EDV_INSUFFISANTE"),
            _diag_convergence(False, motif="COTE_HORS_INTERVALLE"),
        ]),
    ]
    entree = tel.enregistre_scan(signaux, fichier=fichier)
    assert entree["filtre_convergence"]["eligibles"] == 1
    assert entree["filtre_convergence"]["rejetes"] == 2
    assert entree["filtre_convergence"]["motifs_rejet"] == {
        "EDV_INSUFFISANTE": 1,
        "COTE_HORS_INTERVALLE": 1,
    }


def test_enregistre_scan_compte_la_selection_finale(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    signaux = [
        _signal_archetype_model(
            [_diag_convergence(True)],
            selection={"P1": {"marche": "1x2_domicile"}, "P2": None, "P3": None},
        ),
        _signal_archetype_model(
            [_diag_convergence(True)],
            selection={"P1": None, "P2": None, "P3": None},
        ),
    ]
    entree = tel.enregistre_scan(signaux, fichier=fichier)
    assert entree["selection_finale"] == {"P1": 1, "P2": 0, "P3": 0}


def test_enregistre_scan_ignore_les_matchs_hors_archetype_model(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    signaux = [
        {"moteur_utilise": "ancien (fallback technique)"},
        _signal_archetype_model([_diag_convergence(True)]),
    ]
    entree = tel.enregistre_scan(signaux, fichier=fichier)
    assert entree["matchs_scannes_archetype_model"] == 1


def test_enregistre_scan_ignore_les_statuts_non_ok(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    signaux = [
        _signal_archetype_model([_diag_convergence(True)], statut="INSUFFISANT"),
    ]
    entree = tel.enregistre_scan(signaux, fichier=fichier)
    assert entree["matchs_scannes_archetype_model"] == 1
    assert entree["matchs_statut_ok"] == 0
    assert entree["marches_scannes"] == 0


def test_enregistre_scan_compte_audit_integrite(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    signal = _signal_archetype_model([_diag_convergence(True)])
    signal["archetype_model"]["audit_integrite"] = {"statut": "DATA_CORRUPTED", "motifs": []}
    entree = tel.enregistre_scan([signal], fichier=fichier)
    assert entree["audit_integrite"] == {"DATA_CORRUPTED": 1}


def test_enregistre_scan_h2h_est_informatif_pas_un_rejet(tmp_path):
    """Le H2H ne rejette jamais -- il est simplement compté par statut,
    sans influencer eligibles/rejetes."""
    fichier = str(tmp_path / "telemetrie.json")
    signaux = [
        _signal_archetype_model([
            _diag_convergence(True, h2h_statut="CORROBORE"),
            _diag_convergence(True, h2h_statut="CONTREDIT"),
        ]),
    ]
    entree = tel.enregistre_scan(signaux, fichier=fichier)
    assert entree["h2h_informatif"] == {"CORROBORE": 1, "CONTREDIT": 1}
    assert entree["filtre_convergence"]["eligibles"] == 2


def test_enregistre_scan_persiste_et_plafonne_l_historique(tmp_path):
    fichier = str(tmp_path / "telemetrie.json")
    for _ in range(tel.MAX_RUNS_CONSERVES + 5):
        tel.enregistre_scan([_signal_archetype_model([_diag_convergence(True)])], fichier=fichier)
    contenu = json.loads(Path(fichier).read_text(encoding="utf-8"))
    assert len(contenu["runs"]) == tel.MAX_RUNS_CONSERVES


def test_enregistre_scan_ecrit_un_json_valide_meme_apres_plusieurs_appels(tmp_path):
    """Garde-fou direct contre le bug du run du 16-17/09 (TypeError:
    Object of type function is not JSON serializable) -- l'écriture est
    atomique et le fichier doit toujours être un JSON valide,
    intégralement rechargeable."""
    fichier = str(tmp_path / "telemetrie.json")
    for _ in range(3):
        tel.enregistre_scan([_signal_archetype_model([_diag_convergence(True)])], fichier=fichier)
    with open(fichier, encoding="utf-8") as f:
        contenu = json.load(f)  # lève si le JSON est invalide
    assert len(contenu["runs"]) == 3


# ----------------------------------------------------------------------
# calcule_scores_probabilistes -- Brier score / log-loss
# ----------------------------------------------------------------------

def _record_resolu(marche, probabilite, resultat_marche, date_match="2026-09-01"):
    return {
        "schema_version": 1,
        "record_id": f"id_{marche}_{probabilite}_{resultat_marche}",
        "match_id": "match_test",
        "date_match": date_match,
        "equipe_dom": "Equipe A",
        "equipe_ext": "Equipe B",
        "marche": marche,
        "categorie": arch.CATEGORIE_SELECTED,
        "model_version": "test_v1",
        "config_version": "test_v1",
        "resultat_statut": arch.STATUT_RESOLVED,
        "probabilite": probabilite,
        "resultat_marche": resultat_marche,
        "buts_marques": 1,
        "buts_encaisses": 0,
        "date_resolution": "2026-09-02T00:00:00+00:00",
    }


def _ecrit_archive_mensuelle(dossier, mois, records):
    chemin = Path(dossier) / f"{mois}.json"
    chemin.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return chemin


def test_calcule_scores_probabilistes_brier_parfait(tmp_path):
    records = [
        _record_resolu("btts_oui", 1.0, regl.WIN),
        _record_resolu("btts_oui", 0.0, regl.LOSS),
    ]
    _ecrit_archive_mensuelle(tmp_path, "2026-09", records)
    resultat = tel.calcule_scores_probabilistes(repertoire_archive=str(tmp_path))
    assert resultat["n_records_utilises"] == 2
    assert resultat["brier_score_global"] == 0.0


def test_calcule_scores_probabilistes_brier_valeur_connue(tmp_path):
    # Brier = (0.7 - 1)^2 = 0.09 pour un WIN à p=0.7
    records = [_record_resolu("over_2.5", 0.7, regl.WIN)]
    _ecrit_archive_mensuelle(tmp_path, "2026-09", records)
    resultat = tel.calcule_scores_probabilistes(repertoire_archive=str(tmp_path))
    assert math.isclose(resultat["brier_score_global"], 0.09, rel_tol=1e-6)


def _record_pending(marche, probabilite, date_match="2026-09-01"):
    """Un enregistrement PENDING réel (voir archive._valider_record) ne
    peut porter AUCUN champ de résultat -- tous None, jamais un résultat
    déjà connu en attendant confirmation."""
    return {
        "schema_version": 1,
        "record_id": f"id_pending_{marche}_{probabilite}",
        "match_id": "match_test_pending",
        "date_match": date_match,
        "equipe_dom": "Equipe A",
        "equipe_ext": "Equipe B",
        "marche": marche,
        "categorie": arch.CATEGORIE_SELECTED,
        "model_version": "test_v1",
        "config_version": "test_v1",
        "resultat_statut": arch.STATUT_PENDING,
        "probabilite": probabilite,
        "resultat_marche": None,
        "buts_marques": None,
        "buts_encaisses": None,
        "date_resolution": None,
    }


def test_calcule_scores_probabilistes_ignore_les_non_resolus(tmp_path):
    records = [
        _record_resolu("over_2.5", 0.7, regl.WIN),
        _record_pending("over_2.5", 0.6),
    ]
    _ecrit_archive_mensuelle(tmp_path, "2026-09", records)
    resultat = tel.calcule_scores_probabilistes(repertoire_archive=str(tmp_path))
    assert resultat["n_records_resolus"] == 1
    assert resultat["n_records_utilises"] == 1


def test_calcule_depuis_records_ignore_resultat_non_win_loss():
    """archive.py garantit déjà, à l'écriture, qu'un enregistrement
    RESOLVED a toujours resultat_marche in {WIN, LOSS} (MARCHE_NON_RECONNU
    reste PENDING pour toujours -- voir resultats.py). Ce test vérifie
    directement le coeur du calcul (sans passer par l'archive, qui
    rendrait cet état impossible à construire) : la garde défensive de
    telemetry.py reste correcte si jamais cette invariante venait à
    changer ailleurs dans le projet."""
    records = [{"marche": "over_2.5", "probabilite": 0.7, "resultat_marche": regl.MARCHE_NON_RECONNU}]
    resultat = tel._calcule_depuis_records(records)
    assert resultat["n_records_resolus"] == 1
    assert resultat["n_records_utilises"] == 0
    assert resultat["n_records_ignores"] == 1


def test_calcule_depuis_records_ignore_probabilite_absente():
    records = [{"marche": "over_2.5", "probabilite": None, "resultat_marche": regl.WIN}]
    resultat = tel._calcule_depuis_records(records)
    assert resultat["n_records_utilises"] == 0
    assert resultat["n_records_ignores"] == 1


def test_calcule_scores_probabilistes_agrege_par_marche(tmp_path):
    records = [
        _record_resolu("btts_oui", 0.8, regl.WIN),
        _record_resolu("btts_oui", 0.6, regl.LOSS),
        _record_resolu("over_2.5", 0.9, regl.WIN),
    ]
    _ecrit_archive_mensuelle(tmp_path, "2026-09", records)
    resultat = tel.calcule_scores_probabilistes(repertoire_archive=str(tmp_path))
    assert resultat["par_marche"]["btts_oui"]["n"] == 2
    assert resultat["par_marche"]["over_2.5"]["n"] == 1


def test_calcule_scores_probabilistes_dossier_absent_retourne_vide(tmp_path):
    resultat = tel.calcule_scores_probabilistes(repertoire_archive=str(tmp_path / "n_existe_pas"))
    assert resultat["n_records_resolus"] == 0
    assert resultat["brier_score_global"] is None


def test_calcule_scores_probabilistes_filtre_par_mois(tmp_path):
    _ecrit_archive_mensuelle(tmp_path, "2026-08", [_record_resolu("btts_oui", 0.5, regl.WIN)])
    _ecrit_archive_mensuelle(tmp_path, "2026-09", [_record_resolu("btts_oui", 0.5, regl.LOSS)])
    resultat_sept = tel.calcule_scores_probabilistes(mois="2026-09", repertoire_archive=str(tmp_path))
    assert resultat_sept["n_records_resolus"] == 1


def test_enregistre_scores_probabilistes_persiste_dans_brier_history(tmp_path):
    dossier_archive = tmp_path / "archive"
    dossier_archive.mkdir()
    _ecrit_archive_mensuelle(dossier_archive, "2026-09", [_record_resolu("btts_oui", 0.7, regl.WIN)])
    fichier_telemetrie = str(tmp_path / "telemetrie.json")

    entree = tel.enregistre_scores_probabilistes(
        repertoire_archive=str(dossier_archive), fichier=fichier_telemetrie,
    )
    assert entree["n_records_utilises"] == 1
    contenu = json.loads(Path(fichier_telemetrie).read_text(encoding="utf-8"))
    assert len(contenu["brier_history"]) == 1


def test_ce_module_ne_modifie_jamais_larchive(tmp_path):
    """Garde-fou explicite : lecture seule sur l'archive -- le fichier
    ne doit jamais être réécrit par calcule_scores_probabilistes."""
    dossier_archive = tmp_path / "archive"
    dossier_archive.mkdir()
    chemin = _ecrit_archive_mensuelle(
        dossier_archive, "2026-09", [_record_resolu("btts_oui", 0.7, regl.WIN)]
    )
    contenu_avant = chemin.read_text(encoding="utf-8")
    tel.calcule_scores_probabilistes(repertoire_archive=str(dossier_archive))
    contenu_apres = chemin.read_text(encoding="utf-8")
    assert contenu_avant == contenu_apres
