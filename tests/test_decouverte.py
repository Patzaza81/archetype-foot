"""Protocole commun de recherche d'indices (26/10/2026) : pas de fuite, seuil propre au marché, stabilité exigée, suivi prospectif générique."""
import copy
import json
import random
from datetime import datetime, timezone

import pytest

pytest.importorskip("numpy")
from alpha_serie import coeur, decouverte as D, indice_alpha as I, parametres as P, robustesse as RB, suivi as S


def lignes_synthetiques(signal, graine=1, n=1800, jours=360, marche="vic_dom"):
    """n matchs sur `jours` jours à partir de 2025-07-01 ; si signal(periode) > 0 la variable xh augmente la probabilité de la victoire à domicile."""
    rnd = random.Random(graine)
    from datetime import date, timedelta
    rows = []
    for i in range(n):
        j = (date(2025, 7, 1) + timedelta(days=int(i * jours / n))).isoformat()
        per = "A" if j < D.FIN_A else "B" if j < D.FIN_B else "C"
        f = {v: rnd.random() * 3 for v in D.VARIABLES}
        p = 0.3 + signal(per) * (0.55 if f["xh"] >= 2.0 else 0.0)
        gagne = rnd.random() < p
        rows.append({"id": f"s{i}", "jour": j, "src": "FD", "h": 2 if gagne else 0, "a": 0 if gagne else 1, "f": f, "moy": {}, "bp": {}})
    return rows


def test_signal_reel_present_partout_est_trouve_et_en_validation():
    r = D.rechercher(lignes_synthetiques(lambda per: 1.0), "vic_dom")
    assert r["verdict"] == "en_validation" and any(c["var"] == "xh" and c["op"] == ">=" for c in r["regle"])
    assert r["verification_C"]["wilson_bas_95"] > r["taux_de_base_C"]


def test_bruit_pur_ne_donne_jamais_un_indice_en_validation():
    for graine in (1, 2, 3):
        assert D.rechercher(lignes_synthetiques(lambda per: 0.0, graine=graine), "vic_dom")["verdict"] != "en_validation", graine


def test_signal_qui_disparait_apres_la_selection_n_est_pas_valide():
    r = D.rechercher(lignes_synthetiques(lambda per: 0.0 if per == "C" else 1.0), "vic_dom")
    assert r["verdict"] in ("en_etude", "aucun_indice") and r["verdict"] != "en_validation"


def test_aucune_fuite_la_regle_est_choisie_sans_regarder_la_periode_de_verification():
    rows = lignes_synthetiques(lambda per: 1.0)
    autre = copy.deepcopy(rows)
    rnd = random.Random(99)
    for x in autre:
        if x["jour"] >= D.FIN_B:                                        # on brouille tous les résultats de C
            g = rnd.random() < 0.5
            x["h"], x["a"] = (2, 0) if g else (0, 1)
    a, b = D.rechercher(rows, "vic_dom"), D.rechercher(autre, "vic_dom")
    assert a["regle"] == b["regle"] and a["apprentissage_A"] == b["apprentissage_A"] and a["selection_B"] == b["selection_B"]
    assert a["verification_C"] != b["verification_C"]                    # seule la vérification change


def test_verdict_depend_du_taux_de_base_du_marche_pas_d_un_seuil_commun():
    stats = lambda n, g: {"matchs": n, "gagnes": g, "perdus": n - g, "taux": g / n if n else None, "wilson_bas_95": round(D.wilson_bas(g, n), 4) if n else 0.0, "par_jour": 1.0}
    ab = stats(300, 270)
    assert D._verdict(stats(100, 90), 0.75, ab)[0] == "en_validation"       # base 75 % : 90 % sur 100 matchs prouve un écart
    assert D._verdict(stats(100, 90), 0.85, ab)[0] == "en_etude"            # base 85 % : même résultat, preuve insuffisante
    assert D._verdict(stats(100, 90), 0.95, ab)[0] == "aucun_indice"        # base 95 % : sous la base
    assert D._verdict(stats(100, 50), 0.30, stats(300, 190))[0] == "en_etude"   # 50 % bat la base 30 % mais s'est dégradé (A+B : 63 %)
    assert D._verdict(stats(0, 0) | {"taux": None}, 0.5, ab)[0] == "aucun_indice"


def test_variables_calculees_a_la_main():
    f = D.features({"dom": 1.0, "ext": 2.0, "total": 3.0}, [[2, 1], [0, 1]], [[1, 0], [1, 2]])      # A=(2,0) B=(1,1) C=(1,1) D=(0,2)
    assert (f["gfh"], f["gfa"], f["gaa"], f["gah"]) == (1.0, 1.0, 1.0, 1.0) and f["xh"] == 1.0 and f["xa"] == 1.0 and f["tot"] == 2.0 and f["sup"] == 0.0
    assert f["T"] == 3.0 and f["mn"] == 1.0 and f["mx"] == 2.0 and D.features({"dom": 1, "ext": 1, "total": 2}, [], []) is None


def test_regle_vraie_inclut_les_bornes():
    c = [{"var": "xh", "op": ">=", "val": 1.5}, {"var": "mn", "op": "<=", "val": 1.0}]
    assert D.regle_vraie(c, {"xh": 1.5, "mn": 1.0}) and not D.regle_vraie(c, {"xh": 1.49, "mn": 1.0}) and not D.regle_vraie(c, {"xh": 2.0, "mn": 1.01})


def test_resultats_des_marches_sur_trois_cas_gagnants_et_trois_perdants():
    cas = {"vic_dom": ([(2, 1), (1, 0), (3, 0)], [(1, 1), (0, 1), (0, 2)]), "plus_2_5": ([(2, 1), (4, 0), (0, 3)], [(1, 1), (1, 0), (0, 0)]),
           "btts_oui": ([(1, 1), (2, 3), (4, 1)], [(1, 0), (0, 0), (0, 2)]), "hcp_ext_p1_5": ([(1, 0), (0, 0), (2, 1)], [(3, 0), (2, 0), (4, 2)]),
           "hcp_dom_m1_5": ([(2, 0), (3, 1), (5, 0)], [(1, 0), (1, 1), (0, 2)]), "dc_12": ([(1, 0), (0, 2), (3, 1)], [(0, 0), (1, 1), (2, 2)])}
    for mid, (ok, ko) in cas.items():
        assert all(D.MARCHES[mid]["gagne"](h, a) for h, a in ok), mid
        assert not any(D.MARCHES[mid]["gagne"](h, a) for h, a in ko), mid


def test_catalogue_coherent_avec_les_cotes_betpawa_reelles():
    """La probabilité implicite des cotes BetPawa (marge comprise) doit rester proche de la fréquence réelle : détecte un marché ou un côté mal associé."""
    arch = RB.charger_archive_archetype()
    for mid, d in D.MARCHES.items():
        r = [m for m in arch if D.cote_betpawa(mid, m.get("cotes"))]
        assert len(r) > 400, mid
        implicite = sum(1 / D.cote_betpawa(mid, m["cotes"]) for m in r) / len(r)
        reel = sum(bool(d["gagne"](m["h"], m["a"])) for m in r) / len(r)
        assert abs(implicite - reel) < 0.1, (mid, implicite, reel)


# ---- suivi prospectif générique ----
def regle_large(tmp_path, cond=None):
    f = tmp_path / "regles.json"
    f.write_text(json.dumps({"regles": {"vic_ext": {"nom": "t", "regle": cond or [{"var": "tot", "op": ">=", "val": 0.0}], "taux_de_base_C": 0.3}}}), encoding="utf-8")
    return f


def futurs():
    return [m for m in S.charger_matchs() if not m.get("score_final")]


def test_gel_generique_tous_les_matchs_qui_verifient_la_regle_sans_doublon_ni_gel_tardif(tmp_path):
    ms, params = futurs(), P.charger()
    assert len(ms) > 5
    j, f = tmp_path / "j.jsonl", regle_large(tmp_path)
    tot = S.geler_regles(datetime(2026, 9, 1, tzinfo=timezone.utc), j, ms, params, f)
    attendus, classements = set(), S._classements()
    for m in ms:
        a = S.analyser(m, params, classements)
        f_ = D.features(a["niveaux"], a["scenarios_offensifs"], a["scenarios_defensifs"]) if a["statut"] == "analyse" else None
        if S._coup_d_envoi(m) and f_ and D.regle_vraie([{"var": "tot", "op": ">=", "val": 0.0}], f_):
            attendus.add(m["match_id"])  # le gel dédoublonne : un match = une ligne
    assert tot == len(attendus) > 0
    assert S.geler_regles(datetime(2026, 9, 1, tzinfo=timezone.utc), j, ms, params, f) == 0                  # jamais regelé
    assert S.geler_regles(datetime(2026, 9, 1, tzinfo=timezone.utc), tmp_path / "k.jsonl", ms, params, f) == tot
    assert S.geler_regles(datetime(2030, 1, 1, tzinfo=timezone.utc), tmp_path / "l.jsonl", ms, params, f) == 0   # coups d'envoi passés : rien


def test_regle_qui_ne_verifie_personne_ne_gele_rien(tmp_path):
    f = regle_large(tmp_path, [{"var": "tot", "op": ">=", "val": 99.0}])
    assert S.geler_regles(datetime(2026, 9, 1, tzinfo=timezone.utc), tmp_path / "j.jsonl", futurs(), P.charger(), f) == 0


def test_resultats_defaites_comprises_et_regle_modifiee_repart_de_zero(tmp_path):
    ms, params, j = futurs(), P.charger(), tmp_path / "j.jsonl"
    f = regle_large(tmp_path)
    n = S.geler_regles(datetime(2026, 9, 1, tzinfo=timezone.utc), j, ms, params, f)
    finis = [dict(m, score_final={"buts_dom": (i % 3), "buts_ext": ((i + 1) % 3)}) for i, m in enumerate(ms)]
    assert S.resultats_regles(j, finis) == n and S.resultats_regles(j, finis) == 0
    res = [l for l in S._lire(j) if l["type"] == "resultat_indice_regle"]
    assert any(not l["gagne"] for l in res) and any(l["gagne"] for l in res)                                  # les défaites sont enregistrées
    assert all(l["gagne"] == (l["score"]["buts_ext"] > l["score"]["buts_dom"]) for l in res)
    avant = S.empreinte_regle(S.regles_decouvertes(f)["vic_ext"])
    g = regle_large(tmp_path, [{"var": "tot", "op": ">=", "val": 0.5}])
    assert S.empreinte_regle(S.regles_decouvertes(g)["vic_ext"]) != avant
    assert S.geler_regles(datetime(2026, 9, 1, tzinfo=timezone.utc), j, ms, params, g) > 0                    # nouvelle règle = nouveaux gels, anciens intacts
    assert sum(1 for l in S._lire(j) if l["type"] == "indice_regle") > n


def test_les_variables_gelees_sont_celles_du_rejeu(tmp_path):
    m, params = futurs()[0], P.charger()
    a = S.analyser(m, params)
    r = coeur.analyser_match((m.get("assemblage") or {}).get("equipe_dom") or {}, (m.get("assemblage") or {}).get("equipe_ext") or {}, str(m["date"])[:10], params)
    if a["statut"] == "analyse":
        assert D.features(a["niveaux"], a["scenarios_offensifs"], a["scenarios_defensifs"]) == D.features(r["niveaux"], r["scenarios_offensifs"], r["scenarios_defensifs"])


def test_indice_alpha_ne_compte_que_les_gels_de_la_regle_actuelle(tmp_path, monkeypatch):
    f = regle_large(tmp_path)
    monkeypatch.setattr(S, "regles_decouvertes", lambda fichier=None: S.regles_decouvertes.__wrapped__(f) if hasattr(S.regles_decouvertes, "__wrapped__") else json.loads(f.read_text())["regles"])
    emp = S.empreinte_regle(json.loads(f.read_text())["regles"]["vic_ext"])
    j = tmp_path / "j.jsonl"
    ligne = lambda t, mid, e, **k: {"type": t, "indice": "vic_ext", "empreinte_regle": e, "match_id": mid, "date": "2026-11-02", "gele_le": "2026-11-02T01:00:00Z",
                                    "coup_d_envoi_utc": "2026-11-02T14:00:00Z", **k}
    j.write_text("\n".join(json.dumps(x) for x in [ligne("indice_regle", "a", emp), ligne("resultat_indice_regle", "a", emp, gagne=True),
                                                    ligne("indice_regle", "b", "ancienne"), ligne("resultat_indice_regle", "b", "ancienne", gagne=False)]), encoding="utf-8")
    s = I._source_regle("vic_ext", j)
    assert [(p["match_id"], p["gagne"]) for p in s["paris"]] == [("a", True)] and len(s["geles"]) == 1 and s["doublons"] == 0


def test_le_pipeline_nocturne_gele_les_regles_decouvertes():
    import inspect
    src = inspect.getsource(S.pipeline)
    assert "geler_regles(matchs=matchs)" in src and "resultats_regles(matchs=matchs)" in src


def test_fichiers_publies_coherents():
    res = json.loads((D.RESULTATS).read_text(encoding="utf-8"))
    assert {r["marche"] for r in res["resultats"]} == set(D.MARCHES) and all(r["verdict"] in ("en_validation", "en_etude", "aucun_indice") for r in res["resultats"])
    gel = json.loads(D.GELEES.read_text(encoding="utf-8"))["regles"]
    en_val = {r["marche"] for r in res["resultats"] if r["verdict"] == "en_validation" and not r.get("cote_source")}
    assert set(gel) == en_val and all(v["regle"] for v in gel.values())
    reg = I.charger_registre()
    assert {i["source"] for i in reg["indices"] if i["source"].startswith("regle:")} == {"regle:" + m for m in gel}
