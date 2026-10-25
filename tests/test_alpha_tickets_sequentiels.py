"""Traitement séquentiel des tickets du moteur alpha (af-alpha-tickets.js, 25/10/2026) : règles de l'audit validé, calculées par node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
JOUR = "2026-10-25"


def node(code, donnees):
    entete = "const T = require(process.argv[1]); const d = JSON.parse(process.argv[2]); "
    r = subprocess.run(["node", "-e", entete + code, str(RACINE / "af-alpha-tickets.js"), json.dumps(donnees)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def pari(marche, cote, valeur, conf=(9, 12), cle=None):
    return {"marche": marche, "cote": cote, "valeur": valeur, "cle": cle or ["x", marche], "explication": {"domicile": list(conf), "exterieur": list(conf)}}


def match(mid, heure, buts=None, equipes=None, calibrees=None, n=7, date=JOUR):
    return {"match_id": mid, "date": date, "heure": heure, "statut": "analyse", "domicile": f"D{mid}", "exterieur": f"E{mid}", "competition": "Test",
            "n_domicile": n, "n_exterieur": n, "onglets": {"buts": buts or [], "equipes": equipes or [], "calibrees": calibrees or []}}


ANALYSE = ("const a = T.analyse(d, '%s'); console.log(JSON.stringify({ tr: a.tranches.map((t) => ({ nom: t.nom, ticket: t.ticket.map((s) => s.match_id + ':' + s.categorie), "
           "statuts: Object.fromEntries(t.candidats.map((c) => [c.match_id + ':' + c.categorie, c.statut])), cote: t.cote })), "
           "A: a.methodeA.map((e) => e.cote), B: a.chaines.map((c) => ({ etapes: c.etapes.map((e) => ({ t: e.tranche, s: e.selections.map((s) => s.match_id), cond: e.conditionnel, partiel: e.partiel })), cote: c.cote })) }));" % JOUR)


# --- Admissibilité : 3 paris qui passent, 3 qui doivent être écartés -----------------------------------------------
def test_admissibles_et_ecartes():
    d = {"matchs": [
        match("ok1", "12:30", equipes=[pari("Pas de nul (12)", 1.30, 0.93)]),
        match("ok2", "13:00", buts=[pari("Moins de 3,5 buts", 1.35, 0.80, conf=(3, 4))], n=5),          # pile aux seuils : 80 %, 75 %, 5 matchs
        match("ok3", "15:00", buts=[pari("Plus de 1,5 buts", 1.25, 0.90)]),                                  # cote pile à 1,25
        match("ko1", "12:00", equipes=[pari("Victoire domicile", None, 0.95), pari("Pas de nul (12)", 1.40, 0.90)]),   # remplaçant
        match("ko2", "13:30", buts=[pari("Moins de 4,5 buts", 1.27, 0.79)]),                                 # valeur 79 %
        match("ko3", "15:30", equipes=[pari("Handicap +1,5 domicile", 1.28, 0.95, conf=(2, 3))], n=4),       # confirmation 67 %, 4 matchs
    ]}
    r = node(ANALYSE, d)
    st = {k: v for t in r["tr"] for k, v in t["statuts"].items()}
    assert st["ok1:equipes"].startswith("retenu") and st["ok2:buts"].startswith("retenu") and st["ok3:buts"].startswith("retenu")
    assert "remplaçant" in st["ko1:equipes"] and "79 %" in st["ko2:buts"]
    assert "67 %" in st["ko3:equipes"] and "4 matchs comparés" in st["ko3:equipes"]


def test_classement_ex_aequo_et_un_seul_pari_par_match():
    d = {"matchs": [
        match("a", "14:00", equipes=[pari("Plus de 0,5 buts du domicile", 1.28, 0.81, conf=(5, 6))], n=5),
        match("b", "15:00", equipes=[pari("Handicap +1,5 extérieur", 1.29, 0.81, conf=(5, 6))], n=5),       # égalité totale sauf la cote : a passe devant
        match("c", "14:30", buts=[pari("Moins de 3,5 buts", 1.35, 0.93)], equipes=[pari("Handicap +1,5 domicile", 1.27, 0.93)]),
    ]}
    r = node(ANALYSE, d)
    t = next(x for x in r["tr"] if x["nom"] == "14h–16h")
    assert t["ticket"] == ["c:equipes", "a:equipes"]                       # c : cote la plus basse des deux catégories ; puis a devant b
    assert "autre marché de ce match" in t["statuts"]["c:buts"]
    assert "au-delà des 2 meilleurs" in t["statuts"]["b:equipes"]


# --- Calculs : cotes, méthode A, enchaînements faisables -------------------------------------------------------------
AUDIT = {"matchs": [
    match("atyrau", "13:00", equipes=[pari("Pas de nul (12)", 1.30, 0.9286)]),
    match("jelgava", "14:00", buts=[pari("Moins de 3,5 buts", 1.35, 0.9286, conf=(10, 12))]),
    match("ameliano", "15:00", buts=[pari("Moins de 3,5 buts", 1.31, 0.9286)]),
    match("komarno", "16:30", equipes=[pari("Handicap +1,5 extérieur", 1.29, 0.81, conf=(4, 5))], n=5),
    match("nublense", "17:30", equipes=[pari("Plus de 0,5 buts de l'extérieur", 1.26, 0.9286)]),
    match("borac", "18:30", buts=[pari("Moins de 3,5 buts", 1.49, 0.90, conf=(4, 5))], n=5),
    match("calera", "20:00", equipes=[pari("Pas de nul (12)", 1.29, 1.0)]),
    match("moquegua", "20:15", buts=[pari("Moins de 3,5 buts", 1.25, 0.9286)]),
    match("pacific", "22:00", buts=[pari("Moins de 4,5 buts", 1.27, 1.0, conf=(10, 12))]),
    match("palestino", "22:30", equipes=[pari("Handicap +1,5 domicile", 1.28, 0.8571, conf=(11, 12))]),
]}


def test_cotes_de_l_audit_valide():
    r = node(ANALYSE, AUDIT)
    cotes = {t["nom"]: t["cote"] for t in r["tr"] if t["cote"]}
    assert cotes == pytest.approx({"12h–14h": 1.30, "14h–16h": 1.7685, "16h–18h": 1.6254, "18h–20h": 1.49, "20h–22h": 1.6125, "22h–24h": 1.6256})
    assert r["A"][-1] == pytest.approx(5.3979314571)                        # 1,30 × 1,35 × 1,26 × 1,49 × 1,29 × 1,27


def test_reinvestissement_seulement_si_le_ticket_precedent_est_fini():
    r = node(ANALYSE, AUDIT)
    b1 = r["B"][0]
    assert [e["t"] for e in b1["etapes"]] == ["12h–14h", "16h–18h", "20h–22h", "22h–24h"]
    assert b1["etapes"][-1]["s"] == ["palestino"] and b1["etapes"][-1]["partiel"] and b1["etapes"][-1]["cond"]   # Pacific (22:00) trop tôt
    assert b1["cote"] == pytest.approx(4.36127328)
    h = {m["match_id"]: int(m["heure"][:2]) * 60 + int(m["heure"][3:]) for m in AUDIT["matchs"]}
    for c in r["B"]:                                       # chaque étape commence après la fin estimée (115 min) + règlement (15 min)
        for avant, apres in zip(c["etapes"], c["etapes"][1:]):
            assert min(h[s] for s in apres["s"]) >= max(h[s] for s in avant["s"]) + 115 + 15


def test_montants_tout_reinvestir_et_prudent():
    code = ANALYSE.split("console.log")[0] + "const f = T.finances(a.chaines[0], 500); console.log(JSON.stringify(f));"
    f = node(code, AUDIT)
    assert f["finalTotal"] == pytest.approx(2180.6366, abs=0.01) and f["finalPrudent"] == pytest.approx(1003.22, abs=0.01)
    assert [round(x["retour"], 2) for x in f["total"]] == [650.0, 1056.51, 1703.62, 2180.64]
    assert all(x["siPerdSolde"] == 0 and x["siPerdPerteTotale"] == 500 for x in f["total"])
    assert f["prudent"][0]["siPerdPerteTotale"] == 500 and all(x["siPerdSolde"] == 500 and x["siPerdPerteTotale"] == 0 for x in f["prudent"][1:])


def test_aucun_pari_hors_regles_ni_autre_jour():
    d = {"matchs": [match("x", "13:00", equipes=[pari("Pas de nul (12)", 1.30, 0.93)], date="2026-10-26"),
                    match("y", "09:30", equipes=[pari("Pas de nul (12)", 1.30, 0.93)]),                    # avant 10 h
                    match("z", "13:00", buts=[pari("Multigoals 1-4", None, 0.99, cle=["multigoals", "1-4"])])]}  # multigoal exclu
    r = node(ANALYSE, d)
    assert all(not t["ticket"] for t in r["tr"]) and r["A"] == [] and r["B"] == []


def test_page_branchee():
    html = (RACINE / "tickets_alpha.html").read_text(encoding="utf-8")
    assert html.index("af-alpha-selection.js") < html.index("af-alpha-tickets.js") < html.index("af-alpha-tickets-vue.js")
    assert "Traitement séquentiel des tickets" in html and 'href="tickets_alpha.html" aria-current="page"' in html
    alpha = (RACINE / "pronostics_comportement.html").read_text(encoding="utf-8")
    assert 'href="tickets_alpha.html">Traitement séquentiel des tickets</a>' in alpha


def test_ticket_long_premiers_puis_deuxiemes():
    code = ANALYSE.split("console.log")[0] + "console.log(JSON.stringify(a.ticketLong.map((e) => [e.ajout.match_id, e.cote])));"
    r = node(code, AUDIT)
    assert [x[0] for x in r] == ["atyrau", "jelgava", "nublense", "borac", "calera", "pacific", "ameliano", "komarno", "moquegua", "palestino"]
    assert r[5][1] == pytest.approx(5.3979314571) and r[-1][1] == pytest.approx(1.30 * 1.7685 * 1.6254 * 1.49 * 1.6125 * 1.6256)
