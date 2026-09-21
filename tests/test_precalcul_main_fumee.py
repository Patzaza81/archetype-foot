"""Test de fumée de precalcul.main() de bout en bout, RÉSEAU SIMULÉ (21/09/2026).

Pourquoi : main() avait été modifié (moteur, statistiques saison en cours, option jours=2, export, purge) sans jamais être
exécuté entièrement avant un run réel de plusieurs heures. Ce test l'exécute dans un dossier vide, avec des faux pour
tout ce qui touche le réseau (BetPawa, pages d'équipe, H2H), et vérifie ce qui est écrit.
"""
import json
import os

import pytest

import branchement_moteur as bm
import precalcul
import run_pipeline
import stats_saison_en_cours as ss

COMP = "France : Ligue 1"
COTES = {"1x2": {"1": 1.55, "N": 3.7, "2": 4.6}, "double_chance": {"1N": 1.30, "N2": 2.3, "12": 1.28}, "btts": {"Oui": 1.95, "Non": 1.8},
         "over_under_1.5": {"plus": 1.32, "moins": 3.3}, "over_under_2.5": {"plus": 2.0, "moins": 1.8}, "over_under_3.5": {"plus": 3.2, "moins": 1.3}}


def _matchs(n, domicile, gf, ga):
    return [{"domicile": domicile, "buts_marques": gf, "buts_encaisses": ga}] * n


def _stats(nb_dom, nb_ext):
    r = {"nb_domicile": nb_dom, "nb_exterieur": nb_ext, "matchs_domicile_bruts": _matchs(nb_dom, True, 2, 0), "matchs_exterieur_bruts": _matchs(nb_ext, False, 0, 2),
         "source": ss.SOURCE, "nb_matchs_saison_courante": nb_dom + nb_ext}
    if nb_dom:
        r["gf_domicile"], r["ga_domicile"] = 2.0, 0.0 + 0.6
    if nb_ext:
        r["gf_exterieur"], r["ga_exterieur"] = 0.7, 1.9
    return r


@pytest.fixture
def monde(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PRECALCUL_JOURS", "2")
    j0, j1, j2 = precalcul.date_aujourdhui(), precalcul.date_j1(), sorted(precalcul.dates_j2_j3())[0]

    def m(mid, dom, ext, d):
        return {"match_id": mid, "date": d, "domicile": dom, "exterieur": ext, "competition": COMP, "heure": "20:45", "url_match": f"https://x/{mid}"}
    json.dump([m("a", "Alpha FC", "Beta FC", j0), m("b", "Petit FC", "Gamma FC", j0)], open("matchs_du_jour.json", "w"))
    json.dump([m("c", "Delta FC", "Eps FC", j1)], open("matchs_demain.json", "w"))
    json.dump([m("z", "Zeta FC", "Eta FC", j2)], open("matchs_semaine.json", "w"))          # J+2 : doit être ignoré (jours=2)

    stats = {"Alpha FC": _stats(6, 0), "Beta FC": _stats(0, 6), "Petit FC": _stats(1, 0), "Gamma FC": _stats(0, 6), "Delta FC": _stats(5, 0), "Eps FC": _stats(0, 5)}
    monkeypatch.setattr(ss, "stats_saison_en_cours", lambda url, nom, comp, max_matchs=12: stats[nom])
    monkeypatch.setattr(precalcul, "resout_cotes_betpawa", lambda fenetre: {"betpawa_tentes": len(fenetre), "betpawa_cotes_extraites": 2})
    monkeypatch.setattr(precalcul, "_h2h_pour_signal", lambda s: [])
    monkeypatch.setattr(precalcul, "STATS_EQUIPES_VUES", {})
    monkeypatch.setattr(precalcul, "DETAILS_VUS", {})
    monkeypatch.setattr(precalcul, "_recupere_details_pipeline_reelle",
                        lambda url: {"url_equipe_domicile": url + "/dom", "url_equipe_exterieur": url + "/ext"})

    def faux_construit_signaux(fenetre):
        sigs = []
        for x in fenetre:
            run_pipeline.recupere_details_match(x["url_match"])            # passe par la capture réelle de precalcul.py
            sigs.append({**x, "traite": True, "cotes_manuelles": None if x["match_id"] == "c" else COTES})
        return sigs
    monkeypatch.setattr(precalcul, "construit_signaux", faux_construit_signaux)
    monkeypatch.setattr(run_pipeline, "recupere_details_match", precalcul._recupere_details_avec_capture)
    return tmp_path


def test_main_de_bout_en_bout(monde):
    precalcul.main()
    complet = json.load(open("precalcul.json", encoding="utf-8"))
    leger = json.load(open("precalcul_leger.json", encoding="utf-8"))
    ids = sorted(s["match_id"] for s in complet["signaux"])
    assert ids == ["a", "b", "c"], ids                                          # J+2 ("z") ignoré
    assert complet["moteur"] == {"nom": "moteur_v2_6_9", "version": "2.6.9"} and leger["moteur"] == complet["moteur"]
    blocs = {s["match_id"]: s[bm.CLE_BLOC] for s in complet["signaux"]}
    assert blocs["a"]["statut"] == "OK" and blocs["a"]["nb_marches_evalues"] > 0
    assert blocs["b"]["statut"] == "NON_EXPORTABLE" and blocs["b"]["raison"].startswith("echantillon_insuffisant")
    assert blocs["c"]["statut"] == "NON_EXPORTABLE" and blocs["c"]["raison"] == "pas_de_cotes_betpawa"
    assert all(s["moteur_utilise"] == "moteur_v2_6_9" and "archetype_model" not in s for s in complet["signaux"])
    la = next(s for s in leger["signaux"] if s["match_id"] == "a")[bm.CLE_BLOC]
    assert "inventaire" not in la and la["statut"] == "OK"


def test_main_ecrit_l_export_les_caches_et_l_archive(monde):
    precalcul.main()
    exportes = []
    for f in os.listdir("export_moteur"):
        if f.startswith("matchs_moteur_"):
            exportes += [m["id"] for m in json.load(open(os.path.join("export_moteur", f), encoding="utf-8"))["matchs"]]
    assert exportes == ["a"]                                                    # b (échantillon insuffisant) n'est PAS exporté
    assert os.path.exists("export_moteur/diagnostic_pont.json") and os.path.exists("cache_equipes_saison.json")
    assert not os.path.exists("cache_equipes.json")                             # l'ancien cache à repli n'est pas touché
    archive = [f for f in os.listdir("archive")]
    assert len(archive) == 1 and json.load(open(os.path.join("archive", archive[0]), encoding="utf-8"))[0]["model_version"] == "moteur_v2_6_9"
    assert precalcul.STATS_EQUIPES_VUES.keys() >= {("Alpha FC", COMP), ("Beta FC", COMP)} and ("Zeta FC", COMP) not in precalcul.STATS_EQUIPES_VUES


def test_main_a_4_jours_prend_aussi_j2(monde, monkeypatch):
    monkeypatch.setenv("PRECALCUL_JOURS", "4")
    monkeypatch.setattr(ss, "stats_saison_en_cours", lambda url, nom, comp, max_matchs=12: _stats(6, 6))
    precalcul.main()
    ids = sorted(s["match_id"] for s in json.load(open("precalcul.json", encoding="utf-8"))["signaux"])
    assert ids == ["a", "b", "c", "z"], ids
