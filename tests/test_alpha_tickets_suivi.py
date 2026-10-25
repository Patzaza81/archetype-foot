"""Tickets alpha côté pipeline (25/10/2026) : palier 2, gel avant les matchs, résultats, bilan, et mêmes choix que la page."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_serie import palier2 as P2
from alpha_serie import tickets as T

RACINE = Path(__file__).resolve().parent.parent
JOUR = "2026-10-25"


def equipe(lieu_dom, buts):
    """buts : liste de (marqués, encaissés) au lieu demandé, avant JOUR."""
    return {"matchs": [{"date": f"2026-09-{i + 1:02d}", "domicile": lieu_dom, "buts_marques": m, "buts_encaisses": e} for i, (m, e) in enumerate(buts)]}


COTES = {"over_under_domicile_2.5": {"moins": 1.53, "plus": 2.40}}


# --- Palier 2 : 3 cas retenus, 3 cas écartés ----------------------------------------------------------------------------
def test_palier2_retenu():
    s = P2.selections(equipe(True, [(1, 0)] * 5), equipe(False, [(0, 1)] * 5), JOUR, COTES)        # 1 but attendu : P(≤2) ≈ 0,92
    assert s and s[0]["cle"] == ["over_under_domicile_2.5", "moins"] and s[0]["avantage"] > 0.10
    assert s[0]["domicile_au_plus_2"] == [5, 5] and s[0]["exterieur_encaisse_au_plus_2"] == [5, 5]
    assert P2.selections(equipe(True, [(2, 1)] * 10), equipe(False, [(1, 1)] * 10), JOUR, {"over_under_domicile_2.5": {"moins": 1.40}})
    assert P2.p_au_plus(1.0, 2) == pytest.approx(0.919698, abs=1e-6)


def test_palier2_ecarte():
    assert P2.selections(equipe(True, [(1, 0)] * 4), equipe(False, [(0, 1)] * 5), JOUR, COTES) == []          # 4 matchs seulement
    assert P2.selections(equipe(True, [(4, 0)] * 5), equipe(False, [(0, 3)] * 5), JOUR, COTES) == []          # beaucoup de buts attendus
    assert P2.selections(equipe(True, [(1, 0)] * 5), equipe(False, [(0, 1)] * 5), JOUR, {}) == []             # pas de cote : rien


# --- Gel, résultats, bilan ------------------------------------------------------------------------------------------------
def pari(marche, cote, valeur, cle, conf=(9, 12)):
    return {"marche": marche, "cote": cote, "valeur": valeur, "cle": cle, "explication": {"domicile": list(conf), "exterieur": list(conf)}}


def match(mid, heure, equipes=None, buts=None, palier2=None):
    return {"match_id": mid, "date": JOUR, "heure": heure, "statut": "analyse", "domicile": f"D{mid}", "exterieur": f"E{mid}", "competition": "Test",
            "n_domicile": 7, "n_exterieur": 7, "onglets": {"buts": buts or [], "equipes": equipes or [], "calibrees": []}, "palier2": palier2 or []}


PAGE = [match("a", "13:00", equipes=[pari("Pas de nul (12)", 1.30, 0.93, ["double_chance", "12"])]),
        match("b", "15:00", buts=[pari("Moins de 3,5 buts", 1.35, 0.93, ["over_under_3.5", "moins"])]),
        match("c", "17:30", palier2=[{"cle": ["over_under_domicile_2.5", "moins"], "marche": "Moins de 2,5 buts du domicile", "cote": 1.53, "avantage": 0.2}])]


def test_gel_regles_bilan(tmp_path):
    j = tmp_path / "t.jsonl"
    nuit = datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)
    assert T.geler(PAGE, nuit, j) == 1 and T.geler(PAGE, nuit, j) == 0                  # jamais regelé
    archive = [{"match_id": "a", "score_final": {"buts_dom": 2, "buts_ext": 1}}, {"match_id": "b", "score_final": {"buts_dom": 1, "buts_ext": 1}}]
    assert T.regler(archive, j) == 0                                                    # match c sans score : rien n'est réglé
    archive.append({"match_id": "c", "score_final": {"buts_dom": 3, "buts_ext": 0}})
    assert T.regler(archive, j) == 1
    b = T.bilan(j)
    assert b["palier1"] == {"tickets": 1, "gagnes": 1, "paris": 2, "paris_gagnes": 2, "rendement_par_ticket": pytest.approx(1.30 * 1.35 - 1, abs=1e-4)}
    assert b["palier2"]["gagnes"] == 0 and b["palier2"]["paris"] == 1                   # 3 buts du domicile : perdu


def test_aucun_gel_a_posteriori(tmp_path):
    j = tmp_path / "t.jsonl"
    assert T.geler(PAGE, datetime(2026, 10, 25, 12, 30, tzinfo=timezone.utc), j) == 0     # 13:30 à Douala : le match de 13:00 a commencé
    assert T.geler([], datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc), j) == 0


# --- Mêmes choix que la page (af-alpha-tickets.js) -------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_meme_ticket_que_la_page():
    page = [match(f"m{i}", h, equipes=[pari("Pas de nul (12)", c, v, ["double_chance", "12"], conf)])
            for i, (h, c, v, conf) in enumerate([("12:30", 1.30, 0.93, (9, 12)), ("13:15", 1.28, 0.93, (10, 12)), ("14:00", 1.35, 0.81, (5, 6)),
                                                ("15:00", 1.29, 0.81, (5, 6)), ("16:00", 1.40, 0.79, (9, 9)), ("18:30", 1.25, 1.0, (3, 4)),
                                                ("20:00", 1.29, 1.0, (9, 12)), ("22:30", 1.28, 0.86, (11, 12))])]
    code = ("const T = require(process.argv[1]); const d = JSON.parse(process.argv[2]);"
            "console.log(JSON.stringify(T.analyse(d, '%s').ticketLong.map((e) => e.ajout.match_id + '|' + e.ajout.categorie)));" % JOUR)
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-tickets.js"), json.dumps({"matchs": page})], capture_output=True, text=True, check=True)
    t = T.du_jour(page, JOUR)
    assert json.loads(r.stdout) == [f"{c['match_id']}|{c['categorie']}" for c in t["palier1"] + t["palier1_long"]]
