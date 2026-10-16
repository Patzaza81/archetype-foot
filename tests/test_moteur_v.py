"""Tests du moteur v : marchés, verrou d'échantillon, forces, choix principal + autres, fiabilité par zone, carnet, exécution, page."""
import datetime
import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v import carnet as K, coeur as C, execution as X, historique as HI, marches as MK, modele as M, pronostics as P  # noqa: E402

UTC = datetime.timezone.utc
RACINE = pathlib.Path(__file__).parent.parent


def hm(date, dom, bm, be, adv="X"):
    return dict(date=date, domicile=dom, buts_marques=bm, buts_encaisses=be, adversaire=adv)


# ---------------------------------------------------------------- marchés : 3 qui passent / 3 qui échouent
def test_marches_cas_qui_passent():
    assert MK.gagne("1X2 - 1", 2, 1) is True and MK.gagne("1X2 - X", 1, 1) is True and MK.gagne("1X2 - 2", 0, 3) is True
    assert MK.gagne("Plus de 2.5 buts", 2, 1) is True and MK.gagne("Moins de 3.5 buts", 1, 1) is True
    assert MK.gagne("Handicap -1.5 - Extérieur", 1, 0) is True            # l'extérieur reçoit +1,5 : 0+1,5 > 1
    assert MK.gagne("BTTS - non", 2, 0) is True and MK.gagne("Cage inviolée - Domicile", 1, 0) is True


def test_marches_cas_qui_echouent():
    assert MK.gagne("1X2 - 1", 1, 1) is False and MK.gagne("Plus de 2.5 buts", 1, 1) is False
    assert MK.gagne("Handicap -1.5 - Domicile", 2, 1) is False            # il faut gagner d'au moins 2 buts
    assert MK.gagne("Handicap -1.5 - Extérieur", 3, 0) is False
    assert MK.gagne("BTTS - oui", 2, 0) is False
    assert MK.gagne("Total buts - pair", 1, 1) is None                      # non lu
    assert MK.market_def("Handicap 2.5 - Domicile") is None                 # handicap extrême exclu


def test_cote_cote():
    assert MK.cote_cote("1X2 - 1") == 1 and MK.cote_cote("Double chance - X2") == -1 and MK.cote_cote("Plus de 2.5 buts") == 0


# ---------------------------------------------------------------- verrou d'échantillon (règle de Patrick, inchangeable)
def test_coef_k_et_exclusion():
    assert C.coef_k(3) is None and C.coef_k(4) == 0.8 and C.coef_k(5) == 0.9 and C.coef_k(6) == 1.0 and C.coef_k(12) == 1.0


def test_match_exclu_si_une_equipe_a_moins_de_4_matchs_au_lieu():
    six = [(2, 1)] * 6
    n, c = C.analyse(six, [(1, 1)] * 3, {"BTTS - oui": 1.9})
    assert n == 3 and c is None                                             # une équipe à 3 : match exclu
    n, c = C.analyse(six, [(1, 1)] * 4, {"BTTS - oui": 1.9})
    assert n == 4 and c[0]["k"] == 0.8 and abs(c[0]["final_moy"] - 0.8) < 1e-9
    assert C.analyse(six, six, {"BTTS - oui": 1.2}) == (6, [])               # cote < 1,26 écartée


def test_lignes_sans_fuite_du_futur():
    hist = [hm("2026-09-01", True, 2, 0), hm("2026-09-10", True, 3, 1), hm("2026-09-20", True, 0, 0), hm("2026-09-15", False, 1, 1)]
    assert C.lignes(hist, True, "2026-09-20") == [(2, 0), (3, 1)]            # le match du jour et le futur exclus, lieu respecté
    assert C.lignes(hist, False, "2026-09-20") == [(1, 1)]
    assert C.lignes(hist, True, "2026-09-01") == []


# ---------------------------------------------------------------- forces : pas de fuite, bon sens
def entree(nom_d, nom_e, matchs_d, matchs_e, date="2026-09-05", comp="L1"):
    return dict(date=date, competition=comp, domicile=nom_d, exterieur=nom_e,
                equipe_dom=dict(nom=nom_d, matchs=matchs_d), equipe_ext=dict(nom=nom_e, matchs=matchs_e))


def test_forces_sans_fuite_et_sens():
    e = entree("A", "B", [hm("2026-08-01", True, 3, 0, "B")], [])
    f = M.Forces([e])
    assert f.lambdas("2026-08-01", "A", "B") is None                         # aucun match connu avant le 01/08 (le match du jour exclu)
    ld, le = f.lambdas("2026-08-02", "A", "B")
    assert ld > le                                                           # A a battu B 3-0 : A plus fort
    assert f.lambdas("2026-08-02", "Z", "A") is None                         # équipe inconnue


def test_proba_marche():
    assert abs(M.proba_marche(lambda h, a: h + a >= 1, 1.5, 1.0) - (1 - 2.718281828 ** -2.5)) < 1e-6
    s = sum(M.proba_marche(f, 1.4, 1.1) for f in (lambda h, a: h > a, lambda h, a: h == a, lambda h, a: h < a))
    assert abs(s - 1) < 1e-6


def test_lambdas_simples_point_de_vue_de_chaque_equipe():
    assert M.lambdas_simples([(3, 0)] * 6, [(0, 2)] * 6) == (2.5, 0.05)        # dom marque 3 / encaisse 0 ; ext marque 0 / encaisse 2
    assert M.lambdas_simples([(1, 1)] * 6, [(2, 0)] * 6) == (0.5, 1.5)         # ext marque 2 / encaisse 0 : λdom=(1+0)/2, λext=(2+1)/2
    assert M.lambdas_simples([(0, 0)] * 4, [(0, 0)] * 4) == (0.05, 0.05)       # plancher


def test_pronostics_utilise_les_lignes_brutes_pour_le_calcul_simple():
    # Garde-fou de la régression du 16/10/2026 : l'équipe extérieure marque beaucoup et encaisse peu -> λext élevé, pas inversé.
    cap = {}
    orig = M.lambdas_simples
    M.lambdas_simples = lambda rh, ra: cap.setdefault("lam", orig(rh, ra))
    try:
        m = dict(id="z", date="2026-10-14", ligue="L1", h=None, a=None, cotes={"Plus de 1.5 buts": 1.3}, dom="A", ext="B",
                 kickoff="2026-10-14T18:00:00Z", hd=[hm(f"2026-09-{1 + i:02d}", i % 2 == 0, 1, 1) for i in range(8)],
                 he=[hm(f"2026-09-{1 + i:02d}", i % 2 == 0, 3, 0) for i in range(8)])
        entrees = [entree("A", "B", m["hd"], m["he"], date="2026-10-10")]
        P.proposer(m, M.Forces(entrees), M.Classements(entrees))
    finally:
        M.lambdas_simples = orig
    ld, le = cap["lam"]
    assert abs(ld - 0.5) < 1e-9 and abs(le - 2.0) < 1e-9                          # λdom=(1+0)/2, λext=(3+1)/2 : pas (1.5, 1.0)


# ---------------------------------------------------------------- fiabilité par zone
def test_zones():
    assert M.zone_fiabilite(1.30) == (0.748, "SÛR") and M.zone_fiabilite(1.40)[1] == "MOYEN" and M.zone_fiabilite(1.81)[1] == "RISQUÉ"
    assert M.zone_fiabilite(2.20) == (None, "NON CALIBRÉ") and M.zone_fiabilite(1.20) == (None, "NON CALIBRÉ")
    assert M.zone_fiabilite(1.3)[0] > M.zone_fiabilite(1.4)[0] > M.zone_fiabilite(1.6)[0]


# ---------------------------------------------------------------- principal + autres
def cand(m, cote, f):
    return {"marche": m, "cote": cote, "pred": f}


CS = [cand("Plus de 0.5 buts", 1.30, lambda h, a: h + a >= 1), cand("Plus de 1.5 buts", 1.50, lambda h, a: h + a >= 2),
      cand("Moins de 4.5 buts", 1.28, lambda h, a: h + a <= 4), cand("Moins de 4.5 buts copie", 1.35, lambda h, a: h + a <= 4),
      cand("Plus de 5.5 buts", 6.0, lambda h, a: h + a >= 6), cand("Cote trop basse", 1.10, lambda h, a: True)]


def test_proposer_cas_qui_passent():
    r = M.proposer(CS, (1.5, 1.2), (1.5, 1.2))
    assert r["principal"]["marche"] == "Plus de 0.5 buts"                    # le plus probable, même à cote basse
    assert sum("4.5" in d["marche"] for d in [r["principal"]] + r["autres"]) == 1   # doublon fusionné
    assert all(d["sig"] != r["principal"]["sig"] for d in r["autres"])
    p = [d["p_modele"] for d in r["autres"]]
    assert p == sorted(p, reverse=True)
    r2 = M.proposer([cand("Plus de 0.5 buts", 1.60, lambda h, a: h + a >= 1), cand("Moins de 4.5 buts", 1.30, lambda h, a: h + a >= 5)], (1.5, 1.2), (1.5, 1.2))
    assert r2["principal"]["cote"] == 1.60 and r2["principal"]["niveau"] == "RISQUÉ"   # la cote n'impose pas le choix


def test_proposer_cas_qui_echouent():
    r = M.proposer(CS, (1.5, 1.2), (1.5, 1.2))
    assert all(d["p_modele"] >= 0.70 for d in r["autres"]) and all(d["marche"] != "Plus de 5.5 buts" for d in r["autres"])
    assert all(d["marche"] != "Cote trop basse" for d in [r["principal"]] + r["autres"])
    assert len(M.proposer(CS, (1.5, 1.2), (1.5, 1.2), seuil_autres=0.0, max_autres=1)["autres"]) <= 1
    assert M.proposer(CS, None, (1.5, 1.2)) is None and M.proposer(CS, (1.5, 1.2), None) is None
    assert M.proposer([cand("x", 1.10, lambda h, a: True)], (1.5, 1.2), (1.5, 1.2)) is None


def test_alertes_contexte():
    assert M.alerte_contexte("1X2 - 1", -0.5, None) and M.alerte_contexte("1X2 - 2", 0.5, None) and M.alerte_contexte("Double chance - 1X", None, -0.4)
    assert not M.alerte_contexte("1X2 - 1", 0.4, 0.4) and not M.alerte_contexte("Plus de 2.5 buts", -0.9, -0.9) and not M.alerte_contexte("1X2 - 1", None, None)


# ---------------------------------------------------------------- carnet
def ligne(mid, ko, principal="Plus de 1.5 buts", autres=("Moins de 4.5 buts",)):
    pari = lambda m, c=1.5: dict(marche=m, cote=c, p_modele=.8, p_honnete=.748, niveau="SÛR", resultat=None, profit=None)
    return dict(match_id=mid, coup_d_envoi_utc=ko, principal=pari(principal), autres=[pari(a) for a in autres])


def test_carnet_ecrit_avant_ko_fige_et_regle_une_fois():
    t0 = datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
    c = {}
    assert K.enregistre(c, ligne("a", "2026-10-14T18:00:00Z"), t0)
    assert not K.enregistre(c, ligne("b", "2026-10-14T09:00:00Z"), t0)        # coup d'envoi déjà passé : refusé
    assert not K.enregistre(c, ligne("c", None), t0)                           # coup d'envoi inconnu : refusé
    t1 = datetime.datetime(2026, 10, 14, 19, 0, tzinfo=UTC)
    K.fige(c, t1)
    assert c["a"]["fige"] and not K.enregistre(c, ligne("a", "2026-10-14T18:00:00Z", "BTTS - oui"), t1)   # figé : jamais réécrit
    assert K.regle(c, {"a": (2, 1)}) == 1
    assert c["a"]["principal"]["resultat"] == "WIN" and c["a"]["autres"][0]["resultat"] == "WIN" and c["a"]["profit"] == 0.5
    assert K.regle(c, {"a": (0, 0)}) == 0 and c["a"]["principal"]["resultat"] == "WIN"                   # réglé une seule fois


def test_carnet_ne_regle_pas_une_ligne_non_figee():
    t0 = datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
    c = {}
    K.enregistre(c, ligne("a", "2026-10-14T18:00:00Z"), t0)
    assert K.regle(c, {"a": (2, 1)}) == 0 and c["a"]["resultat"] is None


def test_bilan_statuts_et_gel():
    assert K.bilan({})["statut"] == "observation"
    def l(i, niveau, gagne):
        d = ligne(f"m{i}", "2026-10-14T18:00:00Z"); d["principal"].update(niveau=niveau, p_honnete=.75, resultat="WIN" if gagne else "LOSS", profit=.5 if gagne else -1.0)
        d["autres"] = []; d["resultat"] = d["principal"]["resultat"]; return d
    ok = {f"m{i}": l(i, "SÛR", i % 4 != 0) for i in range(60)}                 # 75 % réel pour 75 % annoncé
    assert K.bilan(ok)["statut"] == "observation" and K.bilan(ok)["niveaux_geles"] == []
    mauvais = {f"m{i}": l(i, "SÛR", i % 2 == 0) for i in range(60)}            # 50 % réel pour 75 % annoncé, 60 paris : gel
    assert K.bilan(mauvais)["statut"] == "gel" and K.bilan(mauvais)["niveaux_geles"] == ["SÛR"]
    peu = {f"m{i}": l(i, "SÛR", False) for i in range(30)}                      # 30 paris perdus : pas assez pour geler
    assert K.bilan(peu)["statut"] == "observation"


# ---------------------------------------------------------------- exécution de bout en bout (données synthétiques)
def hist(n=8, marque=2, encaisse=1):
    return [hm(f"2026-09-{1 + i:02d}", i % 2 == 0, marque, encaisse, "Z") for i in range(n)]


def match(mid, date, h=None, a=None, kickoff=None):
    return dict(id=mid, date=date, ligue="L1", h=h, a=a, cotes={"Plus de 1.5 buts": 1.30, "Moins de 4.5 buts": 1.28, "BTTS - oui": 1.9},
                dom="A", ext="B", kickoff=kickoff, hd=hist(), he=hist())


def test_execution_de_bout_en_bout():
    entrees = [entree("A", "B", hist(), hist(), date="2026-10-10")]
    with tempfile.TemporaryDirectory() as d:
        t0 = datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
        s = X.execute([match("m1", "2026-10-14", kickoff="2026-10-14T18:00:00Z"), match("m2", "2026-10-14", kickoff=None)], entrees, d, t0)
        assert len(s["a_venir"]) == 1 and s["a_venir"][0]["match_id"] == "m1"          # sans coup d'envoi : jamais écrit
        assert s["a_venir"][0]["principal"]["marche"] in ("Plus de 1.5 buts", "Moins de 4.5 buts", "BTTS - oui")
        assert s["statut"] == "observation" and s["avertissement"]
        t1 = datetime.datetime(2026, 10, 14, 23, 0, tzinfo=UTC)
        s2 = X.execute([match("m1", "2026-10-14", h=2, a=1, kickoff="2026-10-14T18:00:00Z")], entrees, d, t1)
        assert s2["reglees_aujourdhui"] == 1 and len(s2["reglees"]) == 1 and s2["a_venir"] == []
        assert s2["reglees"][0]["principal"]["resultat"] in ("WIN", "LOSS")
        assert json.load(open(os.path.join(d, "pronostics_v.json")))["parametres_version"] == M.PARAMETRES_VERSION


def test_passage_nocturne_ne_leve_jamais(monkeypatch=None):
    r = X.passage_nocturne(dossier=os.path.join(tempfile.gettempdir(), "v_test_inexistant", "x"))
    assert isinstance(r, (dict, str))


def test_pronostics_exclut_un_match_a_moins_de_4_matchs_au_lieu():
    m = match("x", "2026-10-14", kickoff="2026-10-14T18:00:00Z")
    m["hd"] = hist(2)
    assert P.proposer(m, M.Forces([]), M.Classements([])) is None


# ---------------------------------------------------------------- page et branchement
def test_page_v_branchee():
    html = (RACINE / "pronostics_v.html").read_text(encoding="utf-8")
    js = (RACINE / "archetype_v.js").read_text(encoding="utf-8")
    for ident in ("mv-statut", "mv-bilan", "mv-zones", "mv-avenir", "mv-encours", "mv-regles"):
        assert f'id="{ident}"' in html and ident in js
    assert "archetype_v.js" in html and "data/v/pronostics_v.json" in js
    assert "Autres paris possibles" in js and "réussite mesurée" in js
    assert "pronostics_v.html" in (RACINE / "index.html").read_text(encoding="utf-8")


def test_hook_nocturne_present_et_isole():
    src = (RACINE / "enregistre_scores_historique.py").read_text(encoding="utf-8")
    i = src.index("from moteur_v.execution import passage_nocturne")
    assert "try:" in src[i - 300:i] and "except Exception" in src[i:i + 400]
    assert "moteur_v2r.execution" in src                                     # v2r inchangé


def test_independance_v_ne_depend_d_aucun_autre_moteur():
    for f in (RACINE / "moteur_v").glob("*.py"):
        t = f.read_text(encoding="utf-8")
        for interdit in ("moteur_v2r", "moteur_v3", "moteur_europe", "moteur_v2_6", "journal_rentabilite"):
            assert interdit not in t, f"{f.name} dépend de {interdit}"


def test_historique_documente_et_reference():
    h = (RACINE / "docs" / "MOTEUR_V_HISTORIQUE.md").read_text(encoding="utf-8")
    for titre in ("Cahier des charges", "Tests subis et résultats", "Erreurs découvertes", "Valeurs de référence", "Comment suivre v", "Décisions ouvertes"):
        assert titre in h, titre
    assert "CLAUDE.md" not in h and "docs/MOTEUR_V.md" in h
    assert "MOTEUR_V_HISTORIQUE.md" in (RACINE / "CLAUDE.md").read_text(encoding="utf-8")
    assert "MOTEUR_V_HISTORIQUE.md" in (RACINE / "docs" / "MOTEUR_V.md").read_text(encoding="utf-8")
    for f in ("jeu_reglage_ids.json", "test_aveugle.py", "rejoue_niveaux.py"):
        assert (RACINE / "evaluation" / "moteur_v" / f).exists(), f
    ids = json.load(open(RACINE / "evaluation" / "moteur_v" / "jeu_reglage_ids.json"))
    assert len(ids) == 440 and len(set(ids)) == 440                      # jeu de réglage figé : 440 matchs distincts


# ---------------------------------------------------------------- historique durable (append-only)
def _jeu(d):
    entrees = [entree("A", "B", hist(), hist(), date="2026-10-10")]
    t0 = datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
    X.execute([match("m1", "2026-10-14", kickoff="2026-10-14T18:00:00Z")], entrees, d, t0)
    return entrees, t0


def _n(d, sous):
    return sum(len(HI.lit(f)) for f in HI._fichiers(d, sous))


def test_historique_version_ecrite_une_fois_puis_pas_de_doublon():
    with tempfile.TemporaryDirectory() as d:
        entrees, t0 = _jeu(d)
        assert _n(d, "versions") == 1
        X.execute([match("m1", "2026-10-14", kickoff="2026-10-14T18:00:00Z")], entrees, d, t0 + datetime.timedelta(hours=1))
        assert _n(d, "versions") == 1                      # pronostic identique : rien de nouveau


def test_historique_nouvelle_version_si_le_pronostic_change():
    with tempfile.TemporaryDirectory() as d:
        entrees, t0 = _jeu(d)
        m = match("m1", "2026-10-14", kickoff="2026-10-14T18:00:00Z")
        m["cotes"] = {"Plus de 1.5 buts": 1.34, "Moins de 4.5 buts": 1.27, "BTTS - oui": 1.9}       # la cote bouge avant le match
        X.execute([m], entrees, d, t0 + datetime.timedelta(hours=1))
        v = [o for f in HI._fichiers(d, "versions") for o in HI.lit(f)]
        assert len(v) == 2 and v[0]["signature"] != v[1]["signature"]


def test_historique_reglement_archive_une_seule_fois_avec_le_detail():
    with tempfile.TemporaryDirectory() as d:
        entrees, _ = _jeu(d)
        t1 = datetime.datetime(2026, 10, 14, 23, 0, tzinfo=UTC)
        m = match("m1", "2026-10-14", h=2, a=1, kickoff="2026-10-14T18:00:00Z")
        X.execute([m], entrees, d, t1)
        X.execute([m], entrees, d, t1 + datetime.timedelta(days=1))
        X.execute([m], entrees, d, t1 + datetime.timedelta(days=2))
        r = [o for f in HI._fichiers(d, "reglements") for o in HI.lit(f)]
        assert len(r) == 1 and r[0]["score"] == [2, 1] and r[0]["resultat"] in ("WIN", "LOSS")
        assert r[0]["marches"] and {"pf", "ps", "pm", "c"} <= set(r[0]["marches"][0]) and r[0]["lambdas"]["force"]
        assert r[0]["parametres_version"] == M.PARAMETRES_VERSION
        assert HI.verifie(d) == []


def test_historique_ne_reecrit_jamais_le_passe():
    with tempfile.TemporaryDirectory() as d:
        entrees, _ = _jeu(d)
        f = HI._fichiers(d, "versions")[0]
        avant = open(f, encoding="utf-8").read()
        t1 = datetime.datetime(2026, 10, 14, 23, 0, tzinfo=UTC)
        X.execute([match("m1", "2026-10-14", h=2, a=1, kickoff="2026-10-14T18:00:00Z")], entrees, d, t1)
        assert open(f, encoding="utf-8").read().startswith(avant)          # le passé est intact, on n'a fait qu'ajouter
        b = HI.lit(os.path.join(d, "historique", "bilans.jsonl"))
        assert len(b) >= 2 and b[-1]["bilan"]["principal"]["regles"] == 1 and b[0]["bilan"]["principal"]["regles"] == 0


def test_historique_bilan_identique_pas_de_doublon():
    with tempfile.TemporaryDirectory() as d:
        entrees, t0 = _jeu(d)
        n = _n(d, "versions")
        X.execute([match("m1", "2026-10-14", kickoff="2026-10-14T18:00:00Z")], entrees, d, t0 + datetime.timedelta(hours=2))
        assert len(HI.lit(os.path.join(d, "historique", "bilans.jsonl"))) == 1 and _n(d, "versions") == n


def test_historique_verifie_detecte_les_anomalies():
    with tempfile.TemporaryDirectory() as d:
        entrees, _ = _jeu(d)
        t1 = datetime.datetime(2026, 10, 14, 23, 0, tzinfo=UTC)
        X.execute([match("m1", "2026-10-14", h=2, a=1, kickoff="2026-10-14T18:00:00Z")], entrees, d, t1)
        f = HI._fichiers(d, "reglements")[0]
        ligne = open(f, encoding="utf-8").read()
        open(f, "a", encoding="utf-8").write(ligne)                         # doublon
        assert any("deux fois" in p for p in HI.verifie(d))
        open(f, "w", encoding="utf-8").write("{pas du json\n")
        assert any("illisible" in p for p in HI.verifie(d))


def test_historique_page_allegee_et_documente():
    with tempfile.TemporaryDirectory() as d:
        entrees, t0 = _jeu(d)
        s = json.load(open(os.path.join(d, "pronostics_v.json")))
        assert s["a_venir"] and "marches" not in s["a_venir"][0] and "lambdas" not in s["a_venir"][0]
        assert "marches" in json.load(open(os.path.join(d, "carnet.json")))["m1"]
    doc = (RACINE / "docs" / "MOTEUR_V.md").read_text(encoding="utf-8")
    assert "data/v/historique" in doc and "bilans.jsonl" in doc


# ---------------------------------------------------------------- plancher du pronostic principal (16/10/2026b)
def _un_pari(lam):
    return M.proposer([cand("Plus de 0.5 buts", 1.60, lambda h, a: h + a >= 1)], lam, lam)


def test_plancher_cas_qui_passent_un_principal_est_propose():
    assert _un_pari((1.5, 1.2))["principal"]["p_modele"] > 0.9                    # très probable
    assert _un_pari((0.5, 0.4))["principal"] is not None                          # ~0.59 : au-dessus du plancher
    r = M.proposer([cand("Plus de 0.5 buts", 1.60, lambda h, a: h + a >= 1)], (0.35, 0.35), (0.35, 0.35))   # 1-exp(-0.7)=0.503
    assert r["principal"] is not None and r["principal"]["p_modele"] >= M.PLANCHER_PRINCIPAL


def test_plancher_cas_qui_echouent_aucun_principal():
    for lam in ((0.3, 0.3), (0.1, 0.1), (0.0, 0.0)):                              # 0.45, 0.18, 0.0
        r = _un_pari(lam)
        assert r["principal"] is None and r["autres"] == [] and r["meilleur_score"] < M.PLANCHER_PRINCIPAL
    r = M.proposer([cand("Plus de 4.5 buts", 6.0, lambda h, a: h + a >= 5)], (1.5, 1.2), (1.5, 1.2))
    assert r["principal"] is None                                                 # pari rare : score très bas


def test_plancher_le_match_sans_pronostic_n_entre_pas_au_carnet_et_un_ancien_pronostic_est_retire():
    entrees = [entree("A", "B", hist(), hist(), date="2026-10-10")]
    with tempfile.TemporaryDirectory() as d:
        t0 = datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
        m = match("m1", "2026-10-14", kickoff="2026-10-14T18:00:00Z")
        X.execute([m], entrees, d, t0)
        assert "m1" in json.load(open(os.path.join(d, "carnet.json")))
        pauvre = dict(m, hd=hist(8, 0, 0), he=hist(8, 0, 0), cotes={"Plus de 1.5 buts": 1.30})        # plus aucun but : tout est sous le plancher
        s = X.execute([pauvre], entrees, d, t0 + datetime.timedelta(hours=1))
        assert "m1" not in json.load(open(os.path.join(d, "carnet.json")))                       # retiré (non figé)
        assert [x["match_id"] for x in s["sans_pronostic"]] == ["m1"] and s["a_venir"] == []
        v = [o for f in HI._fichiers(d, "versions") for o in HI.lit(f)]
        assert any(o.get("retire") for o in v) and len(v) >= 2                                   # l'ancienne version et le retrait restent archivés
        assert HI.verifie(d) == []


def test_plancher_retire_ne_touche_pas_un_pronostic_fige_ou_regle():
    c = {"a": {"fige": True, "resultat": None}, "b": {"fige": False, "resultat": "WIN"}, "c": {"fige": False, "resultat": None}}
    assert K.retire(c, "a") is False and K.retire(c, "b") is False and K.retire(c, "inconnu") is False
    assert K.retire(c, "c") is True and "c" not in c and "a" in c and "b" in c


def test_plancher_documente_et_page():
    doc = (RACINE / "docs" / "MOTEUR_V.md").read_text(encoding="utf-8")
    assert "plancher" in doc.lower() and "PLANCHER_PRINCIPAL" in doc
    assert 'id="mv-sans"' in (RACINE / "pronostics_v.html").read_text(encoding="utf-8")
    assert "mv-sans" in (RACINE / "archetype_v.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------- présentation pour un parieur (16/10/2026)
def _node(expr):
    import subprocess
    js = (RACINE / "archetype_v.js").read_text(encoding="utf-8")
    prog = js[js.index("function mvEchappe"):js.index("function mvListe")] + "\nconsole.log(" + expr + ");"
    return subprocess.run(["node", "-e", prog], capture_output=True, text=True, check=True).stdout


def _puce(lieu, bm, be):
    import re
    out = _node("mvHistorique({domicile:'A',exterieur:'B',forme:{domicile:[{lieu:%r,bm:%d,be:%d,date:'2026-10-01',adversaire:'X'}],exterieur:[]}})" % (lieu, bm, be))
    m = re.search(r'mv-l-([GNP])">[GNP]</i> (\d+-\d+)<small class="mv-lieu">(dom\.|ext\.)', out)
    return m.groups()


def test_forme_toujours_ecrite_du_point_de_vue_de_l_equipe_cas_qui_passent():
    assert _puce("D", 2, 0) == ("G", "2-0", "dom.")
    assert _puce("E", 5, 0) == ("G", "5-0", "ext.")       # gagné à l'extérieur : 5-0, plus d'inversion
    assert _puce("E", 1, 2) == ("P", "1-2", "ext.")


def test_forme_cas_qui_echouent_pas_d_inversion_ni_de_mauvaise_lettre():
    assert _puce("E", 0, 4) != ("G", "4-0", "ext.") and _puce("E", 0, 4)[0] == "P"
    assert _puce("D", 0, 1)[0] != "G"
    assert _puce("E", 1, 1) == ("N", "1-1", "ext.")
    assert _puce("D", 3, 3)[1] == "3-3"


def test_chance_cas_qui_passent():
    t = _node("mvChance({cote:1.68,p_honnete:0.543})")
    assert "<b>54</b> sur 100" in t and "Cote trop basse" in t and "mv-rente-non" in t and "−90 F" in t.replace("\u2212", "−")
    t2 = _node("mvChance({cote:1.30,p_honnete:0.85})")
    assert "Cote correcte" in t2 and "mv-rente-oui" in t2
    assert "Cote non évaluée" in _node("mvChance({cote:3.45,p_honnete:null})")


def test_chance_cas_qui_echouent_pas_de_signal_contradictoire():
    t = _node("mvChance({cote:1.30,p_honnete:0.748})")                    # 74,8 % < 77 % : sous le seuil
    assert "Cote correcte" not in t and "mv-rente-oui" not in t and "⚠" in t
    assert "mv-sous" not in t and "mv-sur" not in t                       # la barre n'est plus rouge/verte : elle est neutre, le jugement est dans la phrase
    assert "mv-rente-non" not in _node("mvChance({cote:1.30,p_honnete:0.85})")
    assert _node("mvChance({cote:1,p_honnete:0.9})").strip() == ""
    for expr in ("mvChance({cote:1.30,p_honnete:0.748})", "mvChance({cote:1.68,p_honnete:0.543})", "mvChance({cote:3.45,p_honnete:null})"):
        t = _node(expr).lower()
        assert "rentable" not in t and "sûr de gagner" not in t and "garanti" not in t


def test_mot_du_verdict_decrit_la_chance_pas_la_rentabilite():
    assert "TRÈS PROBABLE" in _node("mvVerdict('SÛR')") and "PROBABLE" in _node("mvVerdict('MOYEN')")
    assert "INCERTAIN" in _node("mvVerdict('RISQUÉ')") and "NON ÉVALUÉ" in _node("mvVerdict('NON CALIBRÉ')")
    for n in ("SÛR", "MOYEN", "RISQUÉ", "NON CALIBRÉ"):
        assert "SOLIDE" not in _node("mvVerdict(%r)" % n)                   # « solide » laissait croire à un pari à jouer


def test_alertes_en_clair():
    assert "très défavorisé" in _node("mvAlerteTexte('côté parié très défavorisé aux points',{})")
    assert "cassée" in _node("mvAlerteTexte('musique dom:rupture',{domicile:'Abha',exterieur:'Z'})") and "Abha" in _node("mvAlerteTexte('musique dom:rupture',{domicile:'Abha',exterieur:'Z'})")
    assert "Z" in _node("mvAlerteTexte('musique ext:pic',{domicile:'Abha',exterieur:'Z'})")


def test_page_allegee_donne_buts_attendus_et_lecture_du_pari():
    with tempfile.TemporaryDirectory() as d:
        _jeu(d)
        l = json.load(open(os.path.join(d, "pronostics_v.json")))["a_venir"][0]
        assert len(l["attendus"]) == 2 and all(x > 0 for x in l["attendus"]) and len(l["lecture"]) == 2 and "marches" not in l


def test_message_de_rentabilite_court():
    for expr in ("mvChance({cote:1.68,p_honnete:0.543})", "mvChance({cote:1.30,p_honnete:0.85})"):
        import re
        phrase = re.search(r'class="mv-rente [^"]*">(.*?)</div>', _node(expr), re.S).group(1)
        assert len(re.sub(r"<[^>]+>", "", phrase)) <= 50                     # une ligne, pas un paragraphe
    assert len(re.sub(r"<[^>]+>", "", re.search(r'class="mv-rente [^"]*">(.*?)</div>', _node("mvChance({cote:3.45,p_honnete:null})"), re.S).group(1))) <= 50
    assert "Passe souvent" not in _node("mvChance({cote:1.68,p_honnete:0.543})")   # le verdict TRÈS PROBABLE / INCERTAIN le dit déjà
