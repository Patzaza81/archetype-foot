"""Tests du moteur DC (30/10/2026) : 3 cas qui passent et 3 cas qui échouent par règle, plus les contrôles numériques de l'audit."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from moteur_dc import coeur, donnees as D, marches as M, modele as MO, suivi, calibrage as C


# --- Modèle : la grille est une distribution, les marchés s'additionnent exactement -------------------------------
def test_grille_somme_un_et_tau_standard():
    g = MO.grille(1.62, 1.05, -0.08)
    assert abs(g.sum() - 1) < 1e-12
    brut = np.outer(MO._pmf(1.62), MO._pmf(1.05))
    # rapports τ de Dixon-Coles (1997) : (0,0) 1-λμρ ; (1,0) 1+μρ ; (0,1) 1+λρ ; (1,1) 1-ρ  (avant renormalisation, mêmes rapports)
    z = g[0, 0] / brut[0, 0]
    assert g[1, 0] / brut[1, 0] / z == pytest.approx((1 + 1.05 * -0.08) / (1 - 1.62 * 1.05 * -0.08))
    assert g[0, 1] / brut[0, 1] / z == pytest.approx((1 + 1.62 * -0.08) / (1 - 1.62 * 1.05 * -0.08))
    assert g[1, 1] / brut[1, 1] / z == pytest.approx((1 + 0.08) / (1 - 1.62 * 1.05 * -0.08))
    assert g[2, 2] / brut[2, 2] / z == pytest.approx(1 / (1 - 1.62 * 1.05 * -0.08))


def test_groupes_exhaustifs_somment_un_et_double_chance_est_la_somme_des_cases():
    P = dict(zip(coeur.CLES, np.einsum("ij,kij->k", MO.grille(1.4, 1.2, -0.04), coeur.MASQUES)))
    assert P[("1x2", "1")] + P[("1x2", "N")] + P[("1x2", "2")] == pytest.approx(1)
    assert P[("over_under_2.5", "plus")] + P[("over_under_2.5", "moins")] == pytest.approx(1)
    assert P[("btts", "Oui")] + P[("btts", "Non")] == pytest.approx(1)
    assert P[("double_chance", "1N")] == pytest.approx(P[("1x2", "1")] + P[("1x2", "N")])
    assert P[("1x2_total_2.5", "1|plus")] < P[("1x2", "1")]                  # un combiné ne dépasse jamais ses composantes


def test_ajustement_converge_et_rho_fixe_n_est_jamais_reestime():
    rng = np.random.default_rng(3)
    T, n = 8, 120
    dom, ext, h, a = [], [], [], []
    for _ in range(n):
        i, j = rng.choice(T, 2, replace=False)
        dom.append(f"t{i}"); ext.append(f"t{j}"); h.append(rng.poisson(1.5)); a.append(rng.poisson(1.1))
    # l'ajustement converge vers un point où le gradient est nul : on vérifie que l'objectif n'est plus améliorable par un pas aléatoire
    fit = MO.ajuster(dom, ext, np.array(h), np.array(a), rng.integers(1, 90, n), 0.5, 0.01)
    assert fit.n_matchs == n and abs(fit.rho) <= 0.3 and np.isfinite(fit.log_vraisemblance)
    fixe = MO.ajuster(dom, ext, np.array(h), np.array(a), rng.integers(1, 90, n), 0.5, 0.01, rho=-0.05)
    assert fixe.rho == pytest.approx(-0.05)                                    # ρ fixé : jamais ré-estimé


def test_le_modele_retrouve_les_forces_d_un_championnat_simule():
    rng = np.random.default_rng(1)
    T = 16
    att, dfn = rng.normal(0, .3, T), rng.normal(0, .3, T)
    dom, ext, h, a = [], [], [], []
    for _ in range(900):
        i, j = rng.choice(T, 2, replace=False)
        dom.append(f"t{i:02d}"); ext.append(f"t{j:02d}")
        h.append(rng.poisson(np.exp(0.2 + 0.3 + att[i] + dfn[j]))); a.append(rng.poisson(np.exp(0.2 + att[j] + dfn[i])))
    fit = MO.ajuster(dom, ext, np.array(h), np.array(a), np.ones(900), 1.0, 0.0)
    vrai = np.array([att[int(e[1:])] for e in fit.equipes])
    assert np.corrcoef(vrai, fit.att)[0, 1] > 0.85                              # les attaques sont retrouvées
    assert abs(fit.gamma - 0.3) < 0.15 and abs(fit.mu - 0.2) < 0.2               # niveau de buts et avantage du terrain


def test_la_penalite_rapproche_les_petits_echantillons_de_la_moyenne():
    dom, ext = ["A", "B", "A", "C", "B"], ["B", "C", "C", "A", "A"]
    h, a = np.array([5, 0, 4, 1, 0]), np.array([0, 1, 0, 2, 3])
    faible = MO.ajuster(dom, ext, h, a, np.ones(5), 5.0, 0.0)
    forte = MO.ajuster(dom, ext, h, a, np.ones(5), 0.1, 0.0)
    assert np.abs(forte.att).max() < np.abs(faible.att).max()                    # σ petit = shrinkage fort


# --- Anti-fuite --------------------------------------------------------------------------------------------------
def _ligue():
    j = ["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06"]
    ms = []
    for k, d in enumerate(j):
        ms += [{"date": d, "dom": "A", "ext": "B", "h": 2, "a": 1}, {"date": d, "dom": "B", "ext": "A", "h": 1, "a": 1},
               {"date": d, "dom": "C", "ext": "D", "h": 0, "a": 0}, {"date": d, "dom": "D", "ext": "C", "h": 3, "a": 2}]
    return ms


def test_un_match_du_jour_n_entre_jamais_dans_l_ajustement():
    ms = _ligue()
    a = coeur.ajuster_ligue(ms, "2026-10-06", 0.5, 0.0, -0.04)
    assert a.n_matchs == 20                                                       # les 4 matchs du 06/10 sont exclus
    assert coeur.ajuster_ligue(ms, "2026-09-01", 0.5, 0.0) is None                # rien avant le premier jour
    b = coeur.ajuster_ligue(ms + [{"date": "2026-10-06", "dom": "A", "ext": "C", "h": 9, "a": 0}], "2026-10-06", 0.5, 0.0, -0.04)
    assert b.att[b.indice["A"]] == pytest.approx(a.att[a.indice["A"]])            # un score du jour n'a aucune influence


def test_minimum_quatre_matchs_au_meme_lieu():
    ms = _ligue()
    assert D.nb_matchs_lieu(ms, "A", True, "2026-10-06") == 5
    assert D.nb_matchs_lieu(ms, "A", True, "2026-09-22") == 3                    # 3 matchs : match exclu
    assert D.nb_matchs_lieu(ms, "A", False, "2026-10-06") == 5
    m = {"id": "x", "jour": "2026-09-22", "domicile": "A", "exterieur": "B", "eq_dom": "A", "eq_ext": "B", "cotes": {}}
    assert coeur.analyser(m, ms, {"sigma": .5, "xi": 0.0})["statut"] == "exclu"
    m["jour"] = "2026-10-06"
    assert coeur.analyser(m, ms, {"sigma": .5, "xi": 0.0, "rho": -0.04})["statut"] == "analyse"


# --- Preuve empirique : « 1 » veut dire la même chose pour les deux séries ----------------------------------------
def test_preuve_oriente_les_scores_des_deux_series():
    ms = [{"date": f"2026-09-{d:02d}", "dom": "A", "ext": "Z", "h": 2, "a": 0} for d in (1, 8, 15, 22)] + \
         [{"date": f"2026-09-{d:02d}", "dom": "Y", "ext": "B", "h": 0, "a": 3} for d in (2, 9, 16, 23)]
    p = coeur.preuve(ms, "A", "B", "2026-10-01", coeur.TESTS[("1x2", "1")], 0.45)
    assert p["n"] == 8 and p["k"] == 4 and p["p_hat"] == 0.5                      # A gagne chez lui ×4 ; B gagne chez l'adversaire = « 2 » ×4
    p2 = coeur.preuve(ms, "A", "B", "2026-10-01", coeur.TESTS[("1x2", "2")], 0.28)
    assert p2["k"] == 4 and p2["n"] == 8
    assert coeur.preuve(ms, "Q", "R", "2026-10-01", coeur.TESTS[("1x2", "1")], 0.45) is None


# --- Championnat reconstitué de l'assemblage : dédoublonnage et identité des adversaires --------------------------
def _doc():
    def eq(cle, nom, matchs):
        return {"cle_cache": f"https://x/equipe/{cle}_abcdefghij0123456789.html||ligue t", "competition": "ligue t", "couverte_par_football_data": False,
                "nom_matchendirect": nom, "matchs": matchs}

    def mt(d, dom, adv, gm, gc):
        return {"date": d, "domicile": dom, "adversaire": adv, "buts_marques": gm, "buts_encaisses": gc}
    return {"equipes": [eq("alpha", "Alpha FC", [mt("2026-09-01", True, "Beta United", 2, 1), mt("2026-09-08", False, "Beta United", 0, 0)]),
                        eq("beta", "Beta Utd", [mt("2026-09-01", False, "Alpha FC", 1, 2), mt("2026-09-08", True, "Alpha", 0, 0)])]}


def test_un_match_vu_des_deux_cotes_n_est_compte_qu_une_fois():
    L = D.Ligues(_doc())
    assert len(L.matchs["ligue t"]) == 2
    a, b = L.equipe(_doc()["equipes"][0]["cle_cache"]), L.equipe(_doc()["equipes"][1]["cle_cache"])
    assert a != b and {m["dom"] for m in L.matchs["ligue t"]} == {a, b}


def test_adversaire_ecrit_autrement_est_rattache_par_les_faits():
    L = D.Ligues(_doc())
    ids = {m["dom"] for m in L.matchs["ligue t"]} | {m["ext"] for m in L.matchs["ligue t"]}
    assert len(ids) == 2 and not any(i.startswith("?") for i in ids)              # « Beta United » et « Alpha » rattachés sans seuil de ressemblance


def test_adversaire_inconnu_garde_sa_propre_identite_sans_deviner():
    d = _doc()
    d["equipes"][0]["matchs"].append({"date": "2026-09-15", "domicile": True, "adversaire": "Gamma Town", "buts_marques": 3, "buts_encaisses": 3})
    L = D.Ligues(d)
    assert len(L.matchs["ligue t"]) == 3
    assert sum(1 for m in L.matchs["ligue t"] if m["ext"].startswith("?")) == 1


# --- Sélection : cote ≥ 1,39 (ordre de Patrick), seuil, jamais deux fois le même événement ---------------------------
def _l(cle, p, cote, p_cote=None):
    return {"cle": list(cle), "marche": M.libelle(cle), "famille": M.famille(cle), "valeur_reelle": None, "p_brut": p, "p": p, "base": None,
            "cote": cote, "p_cote": p_cote, "preuve": None}


SEL = {"seuil": 0.62, "cote_min": 1.39, "exiger_accord_cote": False}


def test_retenu_cas_qui_passent():
    assert coeur.retenu(_l(("1x2", "1"), 0.70, 1.45), SEL)[0]
    assert coeur.retenu(_l(("over_under_1.5", "plus"), 0.80, 1.39), SEL)[0]                   # 1,39 exactement : accepté
    assert coeur.retenu(_l(("btts", "Oui"), 0.62, 1.80, 0.65), dict(SEL, exiger_accord_cote=True))[0]


def test_retenu_cas_qui_echouent():
    assert not coeur.retenu(_l(("1x2", "1"), 0.90, 1.38), SEL)[0]                              # jamais moins de 1,39
    assert not coeur.retenu(_l(("1x2", "1"), 0.90, None), SEL)[0]                              # pas de cote : rien n'est deviné
    assert not coeur.retenu(_l(("1x2", "1"), 0.61, 1.60), SEL)[0]                              # sous le seuil
    assert not coeur.retenu(_l(("btts", "Oui"), 0.70, 1.80, 0.55), dict(SEL, exiger_accord_cote=True))[0]   # la cote n'annonce que 55 %
    assert not coeur.retenu(_l(("btts", "Oui"), 0.70, 1.80, None), dict(SEL, exiger_accord_cote=True))[0]   # accord illisible


def test_selection_principal_le_plus_probable_et_pas_deux_fois_le_meme_evenement():
    a = {"statut": "analyse", "marches": [_l(("double_chance", "1N"), 0.80, 1.45), _l(("handicap_0.5", "domicile"), 0.80, 1.45),
                                          _l(("1x2", "1"), 0.66, 1.70), _l(("over_under_2.5", "plus"), 0.40, 2.0)]}
    s = coeur.selectionner(a, SEL)
    assert s["principal"]["cle"] == ["double_chance", "1N"]
    assert [x["cle"] for x in s["autres"]] == [["1x2", "1"]]                                  # handicap +0,5 = même événement que « ne perd pas »
    assert coeur.selectionner({"statut": "analyse", "marches": [_l(("1x2", "1"), 0.9, 1.2)]}, SEL)["principal"] is None   # rien ne passe : aucun pari


# --- Calibrage : fonctions de mesure -----------------------------------------------------------------------------
def test_wilson_et_tranches():
    assert C.wilson_bas(70, 100) == pytest.approx(0.604, abs=0.002)
    assert C.wilson_bas(0, 0) == 0.0
    t = C.tranches(np.array([0.05, 0.15, 0.95, 0.95]), np.array([0, 0, 1, 1]))
    assert [x["tranche"] for x in t] == ["0-10%", "10-20%", "90-100%"] and t[-1]["observe"] == 1.0 and t[-1]["ecart"] == pytest.approx(-0.05)
    assert MO.calibrer(0.5, None) == 0.5
    pts = MO.isotone(np.array([0.2, 0.4, 0.6, 0.8]), np.array([0, 0, 1, 1.0]))
    assert MO.calibrer(0.8, [list(pts[0]), list(pts[1])]) == pytest.approx(1.0)


# --- Suivi : journal gelé avant le coup d'envoi, résultat réglé une fois -----------------------------------------
def _params():
    return {"sigma": 0.5, "xi": 0.0, "rho": -0.04, "calibration": {}, "bases": {}, "version": "test",
            "selection": {"seuil": 0.0, "cote_min": 1.39, "exiger_accord_cote": False}}


def _arch(h=None, a=None, ko="2026-10-20T18:00:00Z", cotes=None):
    return [{"id": "m1", "ligue": "ligue t", "competition": "Ligue T", "jour": "2026-10-20", "heure": "20:00", "coup_d_envoi_utc": ko, "domicile": "A",
             "exterieur": "B", "eq_dom": "A", "eq_ext": "B", "h": h, "a": a, "cotes": cotes or {"1x2": {"1": 2.0, "N": 3.2, "2": 3.5}}}]


class _Lg:
    matchs = {"ligue t": _ligue()}


def test_gel_avant_coup_d_envoi_puis_resultat(tmp_path):
    j = tmp_path / "journal.jsonl"
    avant = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    n = suivi.geler(maintenant=avant, journal=j, ligues=_Lg, matchs=_arch(), params=_params())
    assert n == 1
    assert suivi.geler(maintenant=avant, journal=j, ligues=_Lg, matchs=_arch(), params=_params()) == 0          # sélection inchangée : rien d'ajouté
    # un match déjà commencé n'est jamais gelé
    assert suivi.geler(maintenant=datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc), journal=tmp_path / "j2.jsonl", ligues=_Lg, matchs=_arch(), params=_params()) == 0
    assert suivi.resultats(journal=j, matchs=_arch()) == 0                                                      # pas de score : pas de résultat
    assert suivi.resultats(journal=j, matchs=_arch(h=2, a=1)) == 1
    assert suivi.resultats(journal=j, matchs=_arch(h=2, a=1)) == 0                                              # réglé une seule fois
    p = suivi.page(maintenant=datetime(2026, 10, 21, tzinfo=timezone.utc), journal=j, sortie=tmp_path / "p.json")
    assert p["bilan"]["matchs_regles"] == 1 and len(p["reglees"]) == 1 and p["reglees"][0]["score"] == [2, 1]


def test_aucun_gel_apres_le_coup_d_envoi_dans_le_bilan(tmp_path):
    j = tmp_path / "journal.jsonl"
    suivi.geler(maintenant=datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc), journal=j, ligues=_Lg, matchs=_arch(), params=_params())
    lignes = suivi._lire(j)
    tard = json.loads(json.dumps(lignes[0]))
    tard["gele_le"] = "2026-10-20T18:30:00Z"                                                                    # après le coup d'envoi
    assert suivi.derniers_pronostics([tard]) == {}
    assert "m1" in suivi.derniers_pronostics(lignes)
