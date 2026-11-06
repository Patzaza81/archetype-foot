import glob, gzip, json, math, os, pytest
import integration_calibration as ic, p1_page_donnees as pd, calibration_p1 as cp

P = {"dom": .5, "nul": .3, "ext": .2, "o15": .8, "o25": .55, "o35": .3, "btts": .5}
def rec(i, ko, gele="2026-11-01T10:00:00Z"):
    return {"statut": "OK", "match_id": f"m{i}", "date": ko[:10], "competition": "C", "division": "E0", "domicile": "A", "exterieur": "B", "coup_d_envoi_utc": ko, "mode": "parallele",
            "p1_original": P, "p1_calibre": P, "methode": {}, "detail": {}, "n_historique_competition": 9}

def journal(tmp, ids_ko, gele="2026-11-01T10:00:00Z"):
    ic.ecrire([rec(i, ko) for i, ko in ids_ko], cp.charger(), str(tmp), maintenant=gele)

def flux(tmp, scores):
    os.makedirs(tmp, exist_ok=True)
    with gzip.open(os.path.join(tmp, "2026-11-10.json.gz"), "wt") as f: json.dump({k: {"match_id": k, "score": v} for k, v in scores.items()}, f)

def test_statuts_sans_invention(tmp_path):
    journal(tmp_path, [(1, "2026-11-02T19:00:00Z"), (2, "2026-11-02T19:00:00Z"), (3, "2026-11-20T19:00:00Z")]); flux(str(tmp_path / "f"), {"m1": {"buts_dom": 2, "buts_ext": 1}, "m2": None})
    d = pd.construire("2026-11-05T00:00:00Z", str(tmp_path), str(tmp_path / "f")); s = {m["match_id"]: m for m in d["matchs"]}
    assert s["m1"]["statut"] == "termine" and s["m1"]["resultat"]["buts_dom"] == 2
    assert s["m2"]["statut"] == "en_cours_ou_resultat_attendu" and s["m2"]["resultat"] is None and s["m2"]["evaluation"] is None
    assert s["m3"]["statut"] == "a_venir" and s["m3"]["resultat"] is None and d["performance"]["matchs_termines"] == 1 and d["journal"]["anomalies"] == []

def test_evaluation_valeurs_connues():
    ev = pd.evaluer({"p1_original": P, "p1_calibre": P}, {"buts_dom": 2, "buts_ext": 1}); o = ev["original"]
    assert ev["realise"] == {"dom": True, "nul": False, "ext": False, "o15": True, "o25": True, "o35": False, "btts": True}
    assert o["issue_1x2"] == "dom" and abs(o["logloss_1x2"] + math.log(.5)) < 1e-12 and abs(o["brier_1x2"] - (.25 + .09 + .04)) < 1e-12 and o["favori"] == "dom"
    assert pd.evaluer({"p1_original": P, "p1_calibre": P}, {"buts_dom": 0, "buts_ext": 0})["realise"]["o15"] is False

def test_performance_vide_ne_fabrique_rien():
    p = pd.performance([]); assert p["matchs_termines"] == 0 and p["periode"] is None and "par_version" not in p

def test_performance_calculee_sur_termines_seulement(tmp_path):
    journal(tmp_path, [(1, "2026-11-02T19:00:00Z"), (2, "2026-11-03T19:00:00Z")]); flux(str(tmp_path / "f"), {"m1": {"buts_dom": 2, "buts_ext": 1}, "m2": {"buts_dom": 0, "buts_ext": 1}})
    p = pd.construire("2026-11-05T00:00:00Z", str(tmp_path), str(tmp_path / "f"))["performance"]; o = p["par_version"]["original"]
    assert p["matchs_termines"] == 2 and p["periode"] == ["2026-11-02", "2026-11-03"] and o["favori_correct"] == 1 and abs(o["logloss_1x2"] - (-math.log(.5) - math.log(.2)) / 2) < 1e-12
    assert o == {**o, "marches": o["marches"]} and p["par_version"]["calibre"]["logloss_1x2"] == o["logloss_1x2"]

def test_journal_immuable_modification_detectee(tmp_path):
    journal(tmp_path, [(1, "2026-11-02T19:00:00Z"), (2, "2026-11-03T19:00:00Z")]); assert ic.verifier_journal(str(tmp_path)) == []
    ch = tmp_path / "journal.jsonl"; L = ch.read_text().split("\n"); r = json.loads(L[0]); r["p1_original"]["dom"] = .9; L[0] = json.dumps(r); ch.write_text("\n".join(L))
    assert any(a[2] == "empreinte" for a in ic.verifier_journal(str(tmp_path)))

def test_gel_apres_coup_d_envoi_refuse_et_detecte(tmp_path):
    n, _ = ic.ecrire([rec(1, "2026-11-02T19:00:00Z")], cp.charger(), str(tmp_path), maintenant="2026-11-02T19:00:01Z"); assert n == 0
    ic.ecrire([rec(2, "2026-11-02T19:00:00Z")], cp.charger(), str(tmp_path), maintenant="2026-11-02T10:00:00Z"); assert ic.verifier_journal(str(tmp_path)) == []
    r = ic.lire_journal(str(tmp_path))[0]; corps = {k: v for k, v in r.items() if k != "empreinte"}; corps["gele_le"] = "2026-11-02T20:00:00Z"
    (tmp_path / "journal.jsonl").write_text(json.dumps({**corps, "empreinte": ic._empreinte("", corps)}) + "\n"); assert ic.verifier_journal(str(tmp_path)) == [(0, "m2", "gele apres le coup d envoi")]

def test_journal_reel_intact_et_page_coherente_avec_le_journal():
    assert ic.verifier_journal() == []
    d = json.load(open(pd.SORTIE, encoding="utf-8")); J = {r["match_id"]: r for r in ic.lire_journal()}
    assert d["journal"]["lignes"] == len(J) == len(d["matchs"])
    for m in d["matchs"]:
        r = J[m["match_id"]]; assert m["p1_original"] == r["p1_original"] and m["p1_calibre"] == r["p1_calibre"] and m["empreinte"] == r["empreinte"]
        assert m["p1_original"] == m["p1_calibre"] or d["calibration"]["couples_valides"] > 0

def test_page_n_ecrit_que_page_p1_json(tmp_path, monkeypatch):
    monkeypatch.setattr(pd, "SORTIE", str(tmp_path / "p.json")); av = {f: os.path.getmtime(f) for f in glob.glob("data/*/pronostics.json") + ["precalcul.json"] if os.path.exists(f)}
    pd.ecrire(pd.construire()); assert os.path.exists(tmp_path / "p.json") and av == {f: os.path.getmtime(f) for f in av}

def test_navigation_toutes_pages_a_navigation_moteurs():
    for f in glob.glob("*.html"):
        s = open(f, encoding="utf-8").read()
        if 'class="af-nav"' in s: assert "pronostics_p1.html" in s, f
    s = open("pronostics_p1.html", encoding="utf-8").read(); assert 'href="pronostics_p1.html" aria-current="page"' in s and "P1 – ANALYSE STATISTIQUE" in s
    assert "pronostics_p1.html" in open("index.html", encoding="utf-8").read()

def test_affichage_exact_dans_le_navigateur():
    pytest.importorskip("playwright"); import verifier_page_p1 as v
    d = json.load(open(pd.SORTIE, encoding="utf-8")); r = v.affichage(d)
    assert r["cartes"] == r["attendu"] and r.get("paris_incoherents", 0) == 0 and r["ecart_max_pct"] == 0 and not r["erreurs_console"] and not r["debordement_horizontal"]
    assert r.get("cartes_avec_onglets", 0) > 0 and r.get("onglets_defaut_incorrects", 0) == 0 and r.get("listes_incorrectes", 0) == 0

def test_derniers_matchs_reels_sans_fuite():
    import datetime, pouvoir_predictif as pp
    d = json.load(open(pd.SORTIE, encoding="utf-8")); verifies = 0
    for m in d["matchs"][:12]:
        h = ic.historique(m["division"]); jour = pp._date(m["date"]); fd = m["detail"]
        for cote, equipe, dom in (("dom", fd["fd_dom"], True), ("ext", fd["fd_ext"], False)):
            L = m["derniers_matchs"][cote]; assert len(L) <= 5 and [x["date"] for x in L] == sorted((x["date"] for x in L), reverse=True)   # du plus récent au plus ancien
            for x in L:
                j = pp._date(x["date"]); assert j < jour                                        # jamais le match lui-meme ni le futur
                ref = [t for t in h if t[0] == j and t[2 if dom else 3] == equipe and t[3 if dom else 2] == x["adversaire"]]
                assert len(ref) == 1 and (ref[0][4], ref[0][5]) == ((x["marques"], x["encaisses"]) if dom else (x["encaisses"], x["marques"])); verifies += 1
    assert verifies > 20

def test_derniers_matchs_cas_limites():
    h = [(10, "s", "A", "B", 1, 0), (20, "s", "A", "C", 2, 2), (30, "s", "D", "A", 0, 3), (40, "s", "A", "E", 0, 1)]
    r = pd.derniers_matchs(h, "A", "A", 40)
    assert [x["adversaire"] for x in r["dom"]] == ["C", "B"] and [x["adversaire"] for x in r["ext"]] == ["D"]    # le match du jour 40 est exclu ; plus récent d'abord
    assert r["ext"][0]["marques"] == 3 and r["ext"][0]["encaisses"] == 0 and pd.derniers_matchs(h, "Z", "Z", 99) == {k: [] for k in ("dom", "ext", "dom_ext", "ext_dom", "h2h")}
    assert len(pd.derniers_matchs([(i, "s", "A", "B", 1, 1) for i in range(1, 12)], "A", "B", 99)["dom"]) == 5

def test_onglets_autre_lieu_et_h2h():
    h = [(10, "s", "A", "B", 1, 0), (20, "s", "B", "A", 2, 2), (30, "s", "A", "C", 4, 1), (35, "s", "C", "B", 0, 5), (40, "s", "B", "A", 3, 0), (50, "s", "A", "B", 9, 9)]
    r = pd.derniers_matchs(h, "A", "B", 50)
    assert [x["adversaire"] for x in r["dom"]] == ["C", "B"] and [x["adversaire"] for x in r["dom_ext"]] == ["B", "B"]                # A à domicile / A à l'extérieur
    assert [x["adversaire"] for x in r["ext"]] == ["C", "A"] and [x["adversaire"] for x in r["ext_dom"]] == ["A", "A"]                       # B à l'extérieur / B à domicile
    assert [x["domicile"] for x in r["h2h"]] == [False, False, True]
    assert [(x["marques"], x["encaisses"]) for x in r["h2h"]] == [(0, 3), (2, 2), (1, 0)] and len(r["h2h"]) == 3                                       # point de vue de A, plus récent d'abord, sans le match du jour
    assert pd.derniers_matchs(h, "A", "Z", 99)["h2h"] == [] and pd.derniers_matchs(h, "A", "A", 99)["h2h"] == []

def test_page_sans_rubriques_supprimees():
    js = open("archetype_p1.js", encoding="utf-8").read(); html = open("pronostics_p1.html", encoding="utf-8").read()
    for interdit in ("Autres options intéressantes", "om-autres", "Probabilités de P1", "p1-tabstats"): assert interdit not in js and interdit not in html, interdit
    assert "d'avantage (cote" in js and "Pourquoi ?" not in js and 'data-onglet' in js and '"H2H"' in js
