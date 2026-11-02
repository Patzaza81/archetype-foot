"""Pourcentage mixte : gel avant le coup d'envoi, ajout seul, résultats réglés une fois, calibration, page, aucun Edge/EV, journal Gamma intact."""
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from moteur_omega_v3 import marches as M, mixte as X, poisson as P, suivi as SV

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def championnat():
    L, j = [], 0
    for _ in range(6):
        for d, e, h, a in (("A", "C", 2, 1), ("C", "A", 1, 2), ("B", "D", 1, 2), ("D", "B", 2, 1), ("C", "D", 1, 1), ("D", "C", 1, 1), ("A", "D", 3, 0), ("B", "C", 0, 1), ("D", "A", 1, 1), ("C", "B", 2, 0)):
            L.append({"date": f"2026-10-{1 + j % 28:02d}", "dom": d, "ext": e, "h": h, "a": a, "id": f"x{j}"})
            j += 1
    return L


def calibreurs():
    p = np.linspace(0, 1, 5000)
    return {k: P.Calibreur(p, np.random.default_rng(1).uniform(size=5000) < p, np.ones(5000, dtype=bool)) for k in ("MIXTE", "FORCE")}


def match(ko_dans_heures=5, **kw):
    ko = (NOW + timedelta(hours=ko_dans_heures)).isoformat().replace("+00:00", "Z")
    return {"id": "m1", "ligue": "L", "jour": "2026-11-02", "heure": "17:00", "competition": "Test", "domicile": "A", "exterieur": "B", "eq_dom": "A", "eq_ext": "B",
            "coup_d_envoi_utc": ko, "h": None, "a": None, "cotes": {"1x2": {"1": 1.6, "N": 3.5, "2": 5.0}, "double_chance": {"1N": 1.1}}, **kw}


class Ligues:
    def __init__(self, L):
        self.matchs = {"L": L}


def test_gel_ajout_seul_et_pas_de_doublon(tmp_path):
    j = tmp_path / "j.jsonl"
    lg = Ligues(championnat())
    assert X.geler(NOW, j, lg, [match()], calibreurs()) == 1
    assert X.geler(NOW + timedelta(minutes=5), j, lg, [match()], calibreurs()) == 0          # rien n'a changé : aucune nouvelle ligne
    m2 = match(cotes={"1x2": {"1": 1.7}})
    assert X.geler(NOW + timedelta(minutes=10), j, lg, [m2], calibreurs()) == 1               # la cote a changé : nouvelle ligne, l'ancienne reste
    L = SV._lire(j)
    assert len(L) == 2 and all(l["type"] == "pronostic" for l in L)


def test_match_commence_ou_joue_jamais_gele(tmp_path):
    j = tmp_path / "j.jsonl"
    lg = Ligues(championnat())
    assert X.geler(NOW, j, lg, [match(ko_dans_heures=-1)], calibreurs()) == 0
    assert X.geler(NOW, j, lg, [match(h=1, a=0)], calibreurs()) == 0


def test_fiche_contient_tous_les_marches_et_la_cote_n_entre_pas_dans_le_calcul():
    lg = Ligues(championnat())
    f1 = X.fiche(match(), lg.matchs["L"], calibreurs())
    f2 = X.fiche(match(cotes={"1x2": {"1": 9.9}}), lg.matchs["L"], calibreurs())
    assert len(f1["p"]) == len(M.CLES) == len(f1["cotes"]) and f1["modele"] in ("MIXTE", "FORCE")
    assert f1["p"] == f2["p"]                                                                   # même probabilité quelle que soit la cote


def test_historique_insuffisant_aucun_pronostic_invente():
    f = X.fiche(match(), championnat()[:3], calibreurs())
    assert f["modele"] is None and "p" not in f and "insuffisantes" in f["raison"]
    assert X.fiche(match(), [], calibreurs())["modele"] is None


def test_resultats_regles_une_seule_fois_et_page(tmp_path):
    j = tmp_path / "j.jsonl"
    lg = Ligues(championnat())
    X.geler(NOW, j, lg, [match()], calibreurs())
    fini = {**match(), "h": 2, "a": 1}
    assert X.resultats(j, [fini]) == 1 and X.resultats(j, [fini]) == 0
    b = X.bilan(SV._lire(j))
    assert b["matchs"] == 1 and b["marches_evalues"] > 100 and b["tranches"]
    p = X.page(NOW + timedelta(hours=8), j, tmp_path / "p.json")
    assert p["a_venir"] == [] and p["bilan"]["matchs"] == 1


def test_gel_apres_le_coup_d_envoi_ne_compte_pas_dans_le_bilan(tmp_path):
    j = tmp_path / "j.jsonl"
    lg = Ligues(championnat())
    X.geler(NOW + timedelta(hours=6), j, lg, [match(ko_dans_heures=7)], calibreurs())         # gelé 1 h avant : valide
    L = SV._lire(j)
    L[0]["gele_le"] = (NOW + timedelta(hours=9)).isoformat()                                     # on triche : gel après le coup d'envoi (NOW + 5 h)
    j.write_text("\n".join(json.dumps(l) for l in L) + "\n")
    X.resultats(j, [{**match(), "h": 1, "a": 0}])
    assert X.bilan(SV._lire(j)) == {"matchs": 0}


def test_haut_de_liste_seulement_des_marches_cotes_et_plus_probables_que_d_habitude():
    f = X.fiche(match(), championnat(), calibreurs())
    base = [0.5] * len(M.CLES)
    L = X.haut_de_liste(f, 10, base)
    assert L and all(x["cote"] is not None and x["p"] > 0.5 for x in L)
    assert [x["p"] for x in L] == sorted((x["p"] for x in L), reverse=True)
    assert X.haut_de_liste(f, 10, [1.0] * len(M.CLES)) == []                                      # rien ne dépasse l'habituel : rien n'est proposé
    assert X.haut_de_liste({**f, "cotes": [None] * len(M.CLES)}, 10, base) == []                  # aucune cote : rien n'est proposé


def test_aucun_edge_ev_ni_value_dans_le_calcul_et_rien_de_bookmaker_dans_la_page():
    code = (ROOT / "moteur_omega_v3/mixte.py").read_text(encoding="utf-8")
    assert "p_implicite" not in code and "* cote" not in code and "cote *" not in code
    for f in ("archetype_mixte.js", "pronostics_mixte.html"):
        t = (ROOT / f).read_text(encoding="utf-8")
        assert "betpawa" not in t.lower() and " EV" not in t and "Edge" not in t and not re.search(r"\bvalue\b", t.lower())


def test_le_journal_et_la_page_gamma_ne_sont_pas_touches():
    assert X.JOURNAL != SV.JOURNAL and X.PAGE != SV.PAGE
    assert "journal_mixte" in str(X.JOURNAL)


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_page_js_affiche_et_echappe():
    script = """
global.document = {getElementById: () => null, body: {classList: {toggle() {}}}, createElement: () => ({addEventListener() {}, setAttribute() {}, classList: {contains: () => true, toggle() {}}})};
global.window = {};
const g = require(process.argv[1]);
console.log(JSON.stringify([g.mxLigne({libelle: "<b>x</b>", p: 0.94, habituel: 0.9, cote: 1.06}), g.mxModele("FORCE"), g.mxBilan({matchs: 0}), g.mxCote(null)]));
"""
    r = subprocess.run(["node", "-e", script, str(ROOT / "archetype_mixte.js")], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    ligne, modele, bilan, cote = json.loads(r.stdout)
    assert "&lt;b&gt;" in ligne and "94 %" in ligne and "1,06" in ligne and "90 %" in ligne
    assert "moins de 5 matchs" in modele and "Aucun match terminé" in bilan and cote == "—"
