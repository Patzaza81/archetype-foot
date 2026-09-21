"""Outil d'évaluation du moteur (21/09/2026) : appariement des résultats, règlement, métriques, fichier figé."""
import datetime
import json
import math
import os

import pytest

import evaluation_moteur as ev
import moteur_v2_6_9 as moteur

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(RACINE, "evaluation", "snapshot_moteur_v2_6_9_2026-09-20.json")


# ═══════════════ noms d'équipes : 3+ cas qui doivent correspondre, 3+ qui ne doivent PAS ═══════════════
@pytest.mark.parametrize("a,b", [("Atlético Madrid", "Atletico Madrid"), ("Alpha FC", "Alpha"), ("CD Cibao", "Cibao"), ("O&M", "O & M"),
                                 ("Independiente Rivadavia", "Rivadavia"), ("Sporting CP", "sporting cp"), ("Manta", "MANTA")])
def test_noms_qui_correspondent(a, b):
    assert ev.score_noms(a, b) >= ev.SEUIL_CORRESPONDANCE


@pytest.mark.parametrize("a,b", [("Manta", "Orense"), ("Real Madrid", "Real Sociedad"), ("Sporting Cristal", "Sporting Gijon"),
                                 ("Manchester City", "Manchester United"), ("Universidad Catolica", "Universidad de Chile"), ("", "Manta"), ("Spezia", "Vis Pesaro")])
def test_noms_qui_ne_doivent_pas_correspondre(a, b):
    assert ev.score_noms(a, b) < ev.SEUIL_CORRESPONDANCE


# ═══════════════════════════ lecture des résultats ═══════════════════════════
@pytest.mark.parametrize("ligne,attendu", [
    ("Manta - Orense 2-1", ("Manta", "Orense", 2, 1, None)),
    ("Manta – Orense 0:0", ("Manta", "Orense", 0, 0, None)),
    ("Manta 3-2 Orense", ("Manta", "Orense", 3, 2, None)),
    ("Manta;Orense;1;4", ("Manta", "Orense", 1, 4, None)),
    ("2026-09-20 Manta - Orense 2-1", ("Manta", "Orense", 2, 1, "2026-09-20")),
    ("Real Sociedad - Athletic Club 10-0", ("Real Sociedad", "Athletic Club", 10, 0, None)),
])
def test_lecture_des_formats(ligne, attendu):
    lus, refusees = ev.lit_resultats(ligne)
    assert not refusees and [(r["dom"], r["ext"], r["a"], r["b"], r["date"]) for r in lus] == [attendu]


@pytest.mark.parametrize("ligne", ["Manta Orense", "Manta - Orense", "Manta - Orense 25-1", "; ;", "score inconnu", "Manta - Orense 2-", "- 2-1 -"])
def test_lignes_non_comprises_refusees(ligne):
    lus, refusees = ev.lit_resultats(ligne)
    assert not lus and refusees == [ligne]


def test_commentaires_et_lignes_vides_ignores():
    lus, refusees = ev.lit_resultats("# résultats du 20/09\n\nManta - Orense 2-1\n   \n")
    assert len(lus) == 1 and not refusees


# ═══════════════════════════ appariement au snapshot ═══════════════════════════
def matchs_test():
    return [{"id": "1", "date": "2026-09-20", "heure": "20:00", "domicile": "Manta", "exterieur": "Orense"},
            {"id": "2", "date": "2026-09-20", "heure": "21:00", "domicile": "Independiente Rivadavia", "exterieur": "Racing Club"},
            {"id": "3", "date": "2026-09-20", "heure": "22:00", "domicile": "Independiente", "exterieur": "Boca Juniors"},
            {"id": "4", "date": "2026-09-21", "heure": "20:00", "domicile": "Manta", "exterieur": "Orense"}]


def assoc(ligne):
    lus, _ = ev.lit_resultats(ligne)
    return ev.associe(lus, matchs_test())


def test_associe_un_resultat_exact():
    att, rej, av = assoc("2026-09-20 Manta - Orense 2-1")
    assert att == {"1": {"buts_dom": 2, "buts_ext": 1, "ligne": "2026-09-20 Manta - Orense 2-1", "inverse": False}} and not rej and not av


def test_associe_detecte_l_ordre_inverse_et_inverse_le_score():
    att, rej, av = assoc("2026-09-20 Orense - Manta 0-3")
    assert att["1"]["buts_dom"] == 3 and att["1"]["buts_ext"] == 0 and att["1"]["inverse"] and len(av) == 1 and not rej


def test_associe_ne_confond_pas_independiente_et_independiente_rivadavia():
    att, _, _ = assoc("Independiente - Boca Juniors 1-0")
    assert list(att) == ["3"]
    att, _, _ = assoc("Independiente Rivadavia - Racing Club 2-2")
    assert list(att) == ["2"]


@pytest.mark.parametrize("ligne,raison", [
    ("Manta - Cibao 2-1", "aucun match"),                        # une seule équipe correspond : JAMAIS associé
    ("Emelec - Orense 2-1", "aucun match"),
    ("Deportivo Quito - Aucas 1-1", "aucun match"),
    ("Manta - Orense 2-1", "ambigu"),                            # sans date : deux matchs (20 et 21/09) correspondent
])
def test_associe_rejette_le_doute(ligne, raison):
    att, rej, _ = assoc(ligne)
    assert not att and len(rej) == 1 and raison in rej[0]["raison"]


def test_le_filtre_de_date_departage_et_refuse():
    assert list(assoc("2026-09-21 Manta - Orense 1-0")[0]) == ["4"]
    att, rej, _ = assoc("2026-09-25 Manta - Orense 1-0")
    assert not att and rej


def test_un_match_ne_peut_etre_renseigne_deux_fois():
    att, rej, _ = assoc("2026-09-20 Manta - Orense 2-1\n2026-09-20 Manta - Orense 0-0")
    assert att["1"]["buts_dom"] == 2 and len(rej) == 1 and "déjà renseigné" in rej[0]["raison"]


def test_le_meilleur_candidat_est_propose_pour_corriger():
    _, rej, _ = assoc("Manta - Orensse Club 2-1")
    assert rej == [] or "Manta" in (rej[0]["meilleur_candidat"] or "")


# ═══════════════════ métriques : vérifiées contre des valeurs calculées à la main ═══════════════════
def ligne_inv(marche, p, pj, cote, value=False, cat=None, famille="RESULT"):
    return {"marche": marche, "marche_moteur": marche, "famille": famille, "probabilite": p, "p_juste": pj, "cote": cote, "edge": 0, "ev": 0,
            "push": 0, "statut": "x", "is_value": value, "categorie": cat}


def snapshot_test():
    m1 = {"id": "1", "date": "2026-09-20", "heure": "20:00", "domicile": "A", "exterieur": "B",
          "inventaire": [ligne_inv("1x2_domicile", 0.6, 0.5, 1.8, True, "A"), ligne_inv("1x2_nul", 0.25, 0.26, 3.8), ligne_inv("1x2_exterieur", 0.15, 0.2, 5.0, True, "D")],
          "choix_publies": [{"rang": "P1", "marche": "1x2_domicile", "cote": 1.8, "probabilite": 0.6, "niveau": "CAT_A", "resume": "x"}]}
    m2 = {"id": "2", "date": "2026-09-20", "heure": "21:00", "domicile": "C", "exterieur": "D",
          "inventaire": [ligne_inv("1x2_domicile", 0.5, 0.45, 2.0), ligne_inv("foo_inconnu", 0.5, None, 2.0), ligne_inv("1x2_nul", 0.3, 0.3, 1.0)],
          "choix_publies": []}
    m3 = {"id": "3", "date": "2026-09-20", "heure": "22:00", "domicile": "E", "exterieur": "F", "inventaire": [ligne_inv("1x2_domicile", 0.7, 0.6, 1.5)], "choix_publies": []}
    return {"matchs": [m1, m2, m3]}


def test_metriques_calculees_a_la_main():
    r = ev.evalue(snapshot_test(), {"1": {"buts_dom": 2, "buts_ext": 0}})              # A gagne 2-0 ; match 2 et 3 sans résultat
    tous = r["groupes"]["tous_les_marches"]["stats"]
    assert tous["n"] == 3 and tous["gagnes"] == 1 and tous["taux"] == pytest.approx(1 / 3)
    assert tous["p_modele"] == pytest.approx(1 / 3) and tous["ecart_calibration"] == pytest.approx(0.0)
    assert tous["brier_modele"] == pytest.approx((0.16 + 0.0625 + 0.0225) / 3)          # (0,6-1)² + 0,25² + 0,15²
    assert tous["brier_marche"] == pytest.approx((0.25 + 0.0676 + 0.04) / 3)            # (0,5-1)² + 0,26² + 0,2²
    assert tous["roi"] == pytest.approx((0.8 - 1 - 1) / 3)                              # +0,8 puis deux mises perdues
    assert tous["logloss_modele"] == pytest.approx(-(math.log(0.6) + math.log(0.75) + math.log(0.85)) / 3)
    choix = r["groupes"]["choix_publies"]["stats"]
    assert choix["n"] == 1 and choix["taux"] == 1.0 and choix["roi"] == pytest.approx(0.8)
    assert r["groupes"]["value_bets_hors_D"]["stats"]["n"] == 1 and r["groupes"]["value_bets_D"]["stats"]["n"] == 1
    assert r["groupes"]["value_bets_D"]["stats"]["gagnes"] == 0 and r["groupes"]["value_bets_D"]["stats"]["roi"] == -1.0


def test_lignes_non_reglables_et_sans_cote_exclues_et_signalees():
    r = ev.evalue(snapshot_test(), {"2": {"buts_dom": 1, "buts_ext": 1}})
    assert r["groupes"]["tous_les_marches"]["stats"]["n"] == 1                          # seul 1x2_domicile ; foo_inconnu et la cote 1,0 exclus
    assert any("foo_inconnu" in e for e in r["erreurs_reglement"])


def test_un_match_sans_resultat_est_ignore_et_aucun_resultat_donne_des_groupes_vides():
    r = ev.evalue(snapshot_test(), {})
    assert all(g["stats"] is None for g in r["groupes"].values())


def test_bootstrap_deterministe_et_encadre_l_estimation():
    par_match = {str(i): [{"gagne": i % 2, "p": 0.5, "pj": 0.5, "cote": 2.0}] * 3 for i in range(20)}
    a, b = ev._bootstrap(par_match), ev._bootstrap(par_match)
    assert a == b
    lo, hi = a["taux"]
    assert lo <= 0.5 <= hi and lo < hi
    assert ev._bootstrap({str(i): [{"gagne": 1, "p": .5, "pj": .5, "cote": 2.0}] for i in range(4)}) is None      # < 5 matchs


def test_le_rapport_avertit_sous_le_seuil_de_conclusion():
    snap = snapshot_test()
    r = ev.evalue(snap, {"1": {"buts_dom": 2, "buts_ext": 0}})
    txt = ev.rapport_texte({"moteur": "t", "origine": "o", "n_snapshot": 3, "n_avec_resultat": 1, "integrite": True}, r)
    assert "PAS concluant" in txt and "INTACT" in txt and "CHOIX PUBLIÉS" in txt
    assert "MODIFIÉ" in ev.rapport_texte({"moteur": "t", "origine": "o", "n_snapshot": 3, "n_avec_resultat": 1, "integrite": False}, r)


# ═══════════════════════════ le fichier figé ═══════════════════════════
@pytest.fixture(scope="module")
def snapshot():
    return json.load(open(SNAPSHOT, encoding="utf-8"))


def test_le_snapshot_est_intact_selon_son_empreinte():
    assert ev.integrite(SNAPSHOT) is True


def test_contenu_du_snapshot(snapshot):
    assert snapshot["nb_matchs"] == len(snapshot["matchs"]) == 80 and snapshot["moteur"] == {"nom": "moteur_v2_6_9", "version": "2.6.9"}
    assert {m["date"] for m in snapshot["matchs"]} == {"2026-09-20"}
    for m in snapshot["matchs"]:
        assert m["entree_moteur"]["id"] == m["id"] and m["inventaire"] and all("p_juste" in l for l in m["inventaire"])
        assert all(l["marche"] is not None for l in m["inventaire"])


def test_tout_marche_du_snapshot_est_reglable(snapshot):
    from archetype_model.learning.reglement import evaluer_marche
    marches = {l["marche"] for m in snapshot["matchs"] for l in m["inventaire"]}
    assert marches and all(evaluer_marche(mk, 2, 1).statut in ("WIN", "LOSS") for mk in marches)


def test_rejouer_le_moteur_sur_les_entrees_figees_redonne_l_inventaire_fige(snapshot):
    import branchement_moteur as bm
    t0 = datetime.datetime(2026, 9, 20, 0, 18, tzinfo=datetime.timezone.utc)
    for m in snapshot["matchs"]:
        res = moteur.analyser_match(m["entree_moteur"], m["entree_moteur"]["date_match"], t0)
        rejoue = sorted((bm.nom_canonique(l["marche"]), round(l["proba_modele"], 9), round(l["ev"], 9)) for l in res["inventaire"])
        fige = sorted((l["marche"], round(l["probabilite"], 9), round(l["ev"], 9)) for l in m["inventaire"])
        assert rejoue == fige, m["id"]


def test_de_bout_en_bout_sur_le_vrai_snapshot(snapshot, tmp_path, capsys):
    ms = snapshot["matchs"][:6]
    lignes = "\n".join(f"{m['date']} {m['domicile']} - {m['exterieur']} {i % 4}-{(i * 2) % 3}" for i, m in enumerate(ms))
    f = tmp_path / "res.txt"; f.write_text(lignes + "\nÉquipe Inconnue - Autre Club 1-0\n", encoding="utf-8")
    assert ev.main([SNAPSHOT, str(f), "--json", str(tmp_path / "r.json")]) == 0
    sortie = capsys.readouterr().out
    assert "ÉVALUATION DU MOTEUR moteur_v2_6_9 v2.6.9 — 6 matchs avec résultat sur 80" in sortie and "REJETÉE : Équipe Inconnue" in sortie and "74 match(s) du snapshot sans résultat" in sortie
    r = json.load(open(tmp_path / "r.json", encoding="utf-8"))
    assert r["entete"]["n_avec_resultat"] == 6 and r["groupes"]["tous_les_marches"]["stats"]["n"] > 100


def test_la_liste_a_renseigner_reprend_les_80_matchs(snapshot, capsys):
    assert ev.main([SNAPSHOT, "--liste"]) == 0
    lignes = capsys.readouterr().out.strip().splitlines()
    assert len(lignes) == 80 and all(" - " in l for l in lignes)
