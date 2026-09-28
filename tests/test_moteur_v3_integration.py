"""Intégration V3 sur de VRAIS matchs (fixture tirée de l'archive de test du 27/09/2026) : chemin public complet
(archive -> cotes -> double contrôle -> evaluate_match -> fichier de sortie) et isolation vis-à-vis de la V2."""
import datetime
import gzip
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import moteur_v3_pipeline as mp  # noqa: E402
from moteur_v3.calibration import IsotonicCalibrator  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "v3_matchs_reels_2709.json")
MAINTENANT = datetime.datetime(2026, 9, 27, 12, 0, tzinfo=datetime.timezone.utc)
YEOVIL, BURGOS, MAS = "81ogjeojnzp73z644r68ki6ms", "3oezwb4beel1a2jdx0uqf5clw", "8xvhavt5exiugjqqyutj6revo"


def _reels():
    with open(FIXTURE, encoding="utf-8") as f:
        return {e["match_id"]: e for e in json.load(f)["enregistrements"]}


def _calibrateur_identite():
    """Calibration quasi neutre (taux réel = probabilité annoncée) : isole les AUTRES verrous de la V3."""
    ps, ys = [], []
    for k in range(5, 100, 10):
        ps += [k / 100] * 100
        ys += [1] * k + [0] * (100 - k)
    c = IsotonicCalibrator()
    assert c.fit(ps, ys).ready
    return c


def test_chemin_public_sur_un_vrai_match():
    e = _reels()[YEOVIL]
    r = mp.evalue_enregistrement(e, _calibrateur_identite())
    assert r["statut"] == "EVALUE" and r["n_dom"] >= 3 and r["n_ext"] >= 3
    assert {c["marche"] for c in r["tous_les_candidats"]} == set(mp.cotes_v3(e))
    assert all(c["calibree"] for c in r["tous_les_candidats"])


def test_double_controle_reellement_branche():
    p = mp.preuves(_reels()[YEOVIL], mp.cotes_v3(_reels()[YEOVIL]))
    assert p["btts_yes"]["double_control_ok"] and "marquent" in p["btts_yes"]["justification"]
    assert not p["under_2_5"]["double_control_ok"] and p["under_2_5"]["justification"] is None
    b = mp.preuves(_reels()[BURGOS], mp.cotes_v3(_reels()[BURGOS]))
    assert b["1x2_1"]["double_control_ok"] and "Burgos" in b["1x2_1"]["justification"]


def test_dispersion_n_est_plus_un_cv_en_pourcentage():
    r = mp.evalue_enregistrement(_reels()[YEOVIL], _calibrateur_identite())
    btts = next(c for c in r["tous_les_candidats"] if c["marche"] == "btts_yes")
    assert "DISPERSION_SUP_8" not in btts["raisons"]
    assert "SURDISPERSION_SUP_1_50" not in btts["raisons"]


def test_match_sans_assez_de_matchs_non_evalue_sans_planter():
    r = mp.evalue_enregistrement(_reels()[MAS], _calibrateur_identite())
    assert r["statut"].startswith("NON_EVALUE") and r["selections"] == []


def _empreintes(dossier):
    out = {}
    for racine, _, fichiers in os.walk(dossier):
        for f in fichiers:
            p = os.path.join(racine, f)
            with open(p, "rb") as h:
                out[os.path.relpath(p, dossier)] = hashlib.sha256(h.read()).hexdigest()
    return out


def test_isolation_la_v3_n_ecrit_que_son_fichier(tmp_path):
    racine = tmp_path / "depot"
    archive = racine / "data" / "archive_test"
    os.makedirs(archive)
    with gzip.open(archive / "2026-09-27.json.gz", "wt", encoding="utf-8") as f:
        json.dump(_reels(), f)
    for nom in ("precalcul.json", "precalcul_leger.json", "historique_pronostics.json"):   # fichiers de la V2
        (racine / nom).write_text('{"v2": true}', encoding="utf-8")
    avant = _empreintes(racine)
    mp.execution(dossier=str(archive), fichier_sortie=str(racine / "data" / "v3" / "pronostics_v3.json"),
                 maintenant=MAINTENANT)
    apres = _empreintes(racine)
    assert {k: v for k, v in apres.items() if k in avant} == avant           # rien d'existant n'est modifié
    assert set(apres) - set(avant) == {os.path.join("data", "v3", "pronostics_v3.json")}
