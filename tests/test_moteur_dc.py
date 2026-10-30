"""Tests du moteur DC (30/10/2026, v2 : Modules 1, 1.5, 2 avec effets, 3 et 4 de Patrick) : 3 cas qui passent et 3 qui échouent par règle."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from moteur_dc import ajustements as AJ, calibrage as K, coeur, contrat as C, donnees as D, marches as M, modele as MO, module1 as M1, selecteur as S, suivi


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


# --- Ligue de test --------------------------------------------------------------------------------------------------
def _ligue():
    j = ["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", "2026-10-06"]
    ms = []
    for k, d in enumerate(j):
        ms += [{"date": d, "dom": "A", "ext": "B", "h": 2, "a": 1}, {"date": d, "dom": "B", "ext": "A", "h": 1, "a": 1},
               {"date": d, "dom": "C", "ext": "D", "h": 0, "a": 0}, {"date": d, "dom": "D", "ext": "C", "h": 3, "a": 2}]
    return ms


P0 = {"sigma": 0.5, "xi": 0.0, "rho": -0.04, "effets": dict(AJ.NEUTRES), "emac": 0.02}


# --- Anti-fuite ------------------------------------------------------------------------------------------------------
def test_un_match_du_jour_n_entre_jamais_dans_l_ajustement_ni_dans_le_module1():
    ms = _ligue()
    a = coeur.ajuster_ligue(ms, "2026-10-06", P0)
    assert a.n_matchs == 20                                                       # les 4 matchs du 06/10 sont exclus
    assert coeur.ajuster_ligue(ms, "2026-09-01", P0) is None                      # rien avant le premier jour
    plus = ms + [{"date": "2026-10-06", "dom": "A", "ext": "C", "h": 9, "a": 0}]
    b = coeur.ajuster_ligue(plus, "2026-10-06", P0)
    assert b.att[b.indice["A"]] == pytest.approx(a.att[a.indice["A"]])            # un score du jour n'a aucune influence
    assert M1.tableau(plus, "2026-10-06")["equipes"]["A"] == M1.tableau(ms, "2026-10-06")["equipes"]["A"]


# --- Module 1 --------------------------------------------------------------------------------------------------------
def test_module1_blocs_de_base():
    p = M1.tableau(_ligue(), "2026-10-20")["equipes"]
    a = p["A"]                                                                    # 6 × (2-1 à dom.) + 6 × (1-1 à l'ext.)
    assert (a["J"], a["V"], a["N"], a["D"], a["BP"], a["BC"], a["Pts"]) == (12, 6, 6, 0, 18, 12, 24)
    assert a["PPM"] == pytest.approx(2.0) and a["MBM_dom"] == 2 and a["MBE_ext"] == 1 and a["TN_ext"] == 1
    assert a["score_modal_dom"] == "2-1" and a["clean_sheet"] == 0 and a["streak_sans_defaite"] == 12
    assert p["A"]["position"] == 1 and p["A"]["CBD"] == pytest.approx((2 + 1 + 0 + 3) / 4)


def test_forme_ppm_formule_de_patrick_et_cas_j_inferieur_a_6():
    assert M1.forme_ppm([3, 3, 3, 0, 0, 0, 0, 0]) == pytest.approx((9 / 3 + 1.5 * 0 / 5) / 2.5)   # J = 8
    assert M1.forme_ppm([0, 0, 0, 3, 3, 3, 3, 3]) == pytest.approx((0 + 1.5 * 15 / 5) / 2.5)
    assert M1.forme_ppm([3, 1, 0]) == pytest.approx(4 / 3)                        # J ≤ 5 : PPM simple (la formule divise par J − 5)
    assert M1.forme_ppm([]) is None


def test_score_modal_departage_sans_hasard():
    assert M1.score_modal([(1, 0), (1, 0), (2, 2)]) == "1-0"
    assert M1.score_modal([(2, 2), (0, 0)]) == "0-0"                              # égalité : le moins de buts
    assert M1.score_modal([(1, 0), (0, 1)]) == "0-1"                              # puis l'ordre du texte
    assert M1.score_modal([]) is None


def test_ie_vaut_points_sur_points_attendus_et_profils():
    p = M1.tableau(_ligue(), "2026-10-20")["equipes"]
    for e in "ABCD":
        assert p[e]["IE"] == pytest.approx(p[e]["Pts"] / p[e]["xPts"])
        assert p[e]["profil_id"] in M1.PROFILS and p[e]["style_tag"] in ("Defensive", "Offensive_Volatile", "Balanced")
    assert p["A"]["profil_id"] in (1, 4) and p["C"]["profil_id"] == 5               # A : attaque et défense au-dessus ; C : les deux en dessous


# --- Module 1.5 : contrat ---------------------------------------------------------------------------------------------
def test_contrat_valide_cas_qui_passent():
    ms = _ligue()
    c = C.construire(ms, "A", "B", "2026-10-20")
    assert c["equipe_domicile"]["matchs_joues_dom"] == 6 and len(c["equipe_exterieur"]["historique_matchs_ext"]) == 6
    assert C.construire(ms, "D", "C", "2026-10-20")["gap"] is not None
    assert C.construire(ms, "A", "B", "2026-10-06")["equipe_domicile"]["matchs_joues_dom"] == 5


def test_contrat_cas_qui_echouent():
    ms = _ligue()
    with pytest.raises(ValueError, match="Filtre 0"):
        C.construire(ms, "A", "B", "2026-09-22")                                  # 3 matchs à domicile
    c = C.construire(ms, "A", "B", "2026-10-20")
    c["equipe_domicile"]["stats_agregees_dom"]["ie"] = float("nan")
    with pytest.raises(ValueError, match="NaN"):
        C.valider(c)
    c = C.construire(ms, "A", "B", "2026-10-20")
    h = c["equipe_exterieur"]["historique_matchs_ext"]
    h[0], h[1] = h[1], h[0]
    with pytest.raises(ValueError, match="chronologique"):
        C.valider(c)


def test_un_match_exclu_par_le_contrat_garde_sa_raison():
    m = {"id": "x", "jour": "2026-09-22", "domicile": "A", "exterieur": "B", "eq_dom": "A", "eq_ext": "B", "cotes": {}}
    a = coeur.analyser(m, _ligue(), P0)
    assert a["statut"] == "exclu" and "Filtre 0" in a["raison"]
    m["jour"] = "2026-10-06"
    assert coeur.analyser(m, _ligue(), P0)["statut"] == "analyse"


# --- Module 2 : effets des paramètres du Module 1 ---------------------------------------------------------------------
F0 = {"ie_dom": -0.3, "ie_ext": 0.4, "amplitude": 0.5, "modal": 0.5, "style_dom": 0.6, "style_ext": -0.2}


def test_effets_nuls_ne_changent_rien_et_ie_penalise_qui_gache():
    assert AJ.appliquer(1.5, 1.1, -0.04, F0, AJ.NEUTRES) == (1.5, 1.1, -0.04)
    lh, la, _ = AJ.appliquer(1.5, 1.1, -0.04, F0, {"ie": 0.5})
    assert lh < 1.5 and la > 1.1                                                  # IE < 1 : λ baisse ; IE > 1 : λ monte
    assert AJ.mult_xi(["A"], ["B"], {"A": 1.0}, 0.0) is None
    assert AJ.mult_xi(["A"], ["B"], {"A": 1.0, "B": 0.0}, 2.0)[0] == pytest.approx(np.exp(1.0))   # dynamique moyenne 0,5 × 2


def test_rho_suit_variance_et_score_modal_et_reste_borne():
    _, _, r = AJ.appliquer(1.5, 1.1, -0.04, F0, {"amplitude": -0.02, "modal": -0.04})
    assert r == pytest.approx(-0.04 - 0.01 - 0.02)
    _, _, r = AJ.appliquer(1.5, 1.1, -0.04, F0, {"modal": -10})
    assert r == MO.RHO_BORNES[0]                                                  # jamais de case de score impossible
    lh, la, rv = AJ.appliquer_vect(np.array([1.5]), np.array([1.1]), np.array([-0.04]), {k: np.array([v]) for k, v in F0.items()}, {"amplitude": -0.02, "ie": 0.3})
    assert (lh[0], la[0], rv[0]) == pytest.approx(AJ.appliquer(1.5, 1.1, -0.04, F0, {"amplitude": -0.02, "ie": 0.3}))


def test_style_croise_sans_match_contre_ce_profil_ne_devine_rien():
    ms = _ligue()
    t = M1.tableau(ms, "2026-10-20")
    fit = coeur.ajuster_ligue(ms, "2026-10-20", P0, t)
    ex = AJ.excedents(ms, "A", "D", "2026-10-20", t, fit)                         # A n'a reçu que B, D n'a joué à l'extérieur que chez C
    if t["equipes"]["B"]["profil_id"] != t["equipes"]["D"]["profil_id"]:
        assert ex["n_a"] == 0 and ex["a_marque"] == 0.0
    ex = AJ.excedents(ms, "A", "B", "2026-10-20", t, fit)
    assert ex["n_a"] == 6 and ex["n_b"] == 6                                      # A a reçu 6 fois B (même profil, par construction)


def test_les_forces_apprises_sont_appliquees_dans_l_analyse():
    m = {"id": "x", "jour": "2026-10-20", "domicile": "A", "exterieur": "B", "eq_dom": "A", "eq_ext": "B", "cotes": {}}
    a0 = coeur.analyser(m, _ligue(), P0)
    a1 = coeur.analyser(m, _ligue(), dict(P0, effets=dict(AJ.NEUTRES, style=0.3)))
    assert a0["buts_attendus"] == a0["buts_attendus_avant_effets"]
    assert a1["buts_attendus"]["dom"] != pytest.approx(a1["buts_attendus_avant_effets"]["dom"])


# --- Module 3 -----------------------------------------------------------------------------------------------------------
def test_multigoal_somme_des_cases_et_effectifs_orientes():
    P = dict(zip(coeur.CLES, np.einsum("ij,kij->k", MO.grille(1.4, 1.2, -0.04), coeur.MASQUES)))
    assert P[("multigoal", "0-1")] + P[("multigoal", "2-3")] + P[("multigoal", "4+")] == pytest.approx(1)
    assert P[("multigoal", "2-3")] == pytest.approx(P[("over_under_1.5", "plus")] - P[("over_under_3.5", "plus")])
    ms = [{"date": f"2026-09-{d:02d}", "dom": "A", "ext": "Z", "h": 2, "a": 0} for d in (1, 8, 15, 22)] + \
         [{"date": f"2026-09-{d:02d}", "dom": "Y", "ext": "B", "h": 0, "a": 3} for d in (2, 9, 16, 23)]
    c = C.construire(ms, "A", "B", "2026-10-01")
    K_, n = coeur.effectifs(c)
    k = dict(zip(coeur.CLES, K_))
    assert n == 8 and k[("1x2", "1")] == 4 and k[("1x2", "2")] == 4                 # B gagne chez l'adversaire = « 2 » : orientation gardée


# --- Module 4 -----------------------------------------------------------------------------------------------------------
def _l(cle, p, base, k, n, cote=None):
    return {"cle": list(cle), "marche": M.libelle(cle), "famille": M.famille(cle), "p": p, "base": base, "cote": cote,
            "preuve": {"k": k, "n": n, "p_hat": round(k / n, 4)}}


def test_wilson_n_est_plus_qu_un_avertissement():
    assert S.wilson(43, 60) == pytest.approx((0.5913, 0.8143), abs=0.002)
    assert S.wilson(0, 0) == (0.0, 1.0)
    l = _l(("btts", "Oui"), 0.86, 0.50, 6, 10)                                     # 86 % hors de [31 % ; 83 %]
    ok, r = S.tester(l, 0.005)
    assert ok and l["avertissement"] and "avertissement" in r
    l = _l(("btts", "Oui"), 0.80, 0.50, 8, 10)
    assert S.tester(l, 0.005)[0] and l["avertissement"] is None


def test_option_b_cas_qui_passent():
    assert S.tester(_l(("over_under_1.5", "plus"), 0.80, 0.68, 9, 10), 0.005)[0]      # Edge +12 %
    assert S.tester(_l(("1x2", "1"), 0.76, 0.45, 2, 10), 0.005)[0]                    # passe même avec p̂ faible (avertissement)
    assert S.tester(_l(("double_chance", "1N"), 0.95, 0.70, 20, 20), 0.005)[0]
    assert S.tester(_l(("btts", "Non"), 0.75, 0.65, 8, 10), 0.005)[0]               # 75 % et Edge 10 % pile : acceptés


def test_option_b_cas_qui_echouent():
    ok, r = S.tester(_l(("over_under_1.5", "plus"), 0.749, 0.50, 9, 10), 0.005)
    assert not ok and r.startswith("P")                                           # sous 75 % : rejet immédiat, Edge ni Wilson calculés
    ok, r = S.tester(_l(("over_under_0.5", "plus"), 0.93, 0.84, 10, 10), 0.005)
    assert not ok and r.startswith("Edge")                                        # Edge +9 % ≤ 10 %
    ok, r = S.tester(_l(("btts", "Non"), 0.90, 0.50, 9, 10), 0.45)
    assert not ok and r.startswith("Edge")                                        # Edge +40 % sous une EMAC de 45 %
    assert not S.tester(dict(_l(("1x2", "1"), 0.9, 0.5, 9, 10), base=None), 0.005)[0]


def test_option_b_une_issue_par_marche_avertis_apres_et_jamais_deux_fois_le_meme_evenement():
    a = {"statut": "analyse", "marches": [_l(("1x2", "1"), 0.80, 0.45, 8, 10), _l(("double_chance", "1N"), 0.95, 0.70, 10, 10),
                                          _l(("handicap_0.5", "domicile"), 0.95, 0.70, 10, 10), _l(("over_under_1.5", "plus"), 0.97, 0.70, 3, 10)]}
    s = S.selectionner(a, 0.005)
    cles = [s["principal"]["cle"]] + [x["cle"] for x in s["autres"]]
    assert cles[0] in (["double_chance", "1N"], ["handicap_0.5", "domicile"])     # le plus probable sans avertissement en tête
    assert cles[-1] == ["over_under_1.5", "plus"]                                 # 97 % mais hors Wilson : classé après
    assert (["double_chance", "1N"] in cles) != (["handicap_0.5", "domicile"] in cles)
    assert ["1x2", "1"] in cles
    assert S.selectionner({"statut": "analyse", "marches": [_l(("1x2", "1"), 0.6, 0.45, 6, 10)]}, 0.005)["principal"] is None


def test_emac_mesure_la_calibration_pas_l_erreur_individuelle():
    p = np.array([0.7] * 10 + [0.2] * 10)
    y = np.array([1] * 7 + [0] * 3 + [1] * 2 + [0] * 8)
    assert K.emac(p, y) == 0.0                                                    # parfaitement calibré : 0 (la formule |P − Y| donnerait 0,36)
    assert K.emac(np.array([0.9] * 10), np.array([1] * 5 + [0] * 5)) == pytest.approx(0.4)


# --- Suivi : journal gelé avant le coup d'envoi, résultat réglé une fois ------------------------------------------------
def _params():
    return {"sigma": 0.5, "xi": 0.0, "rho": -0.04, "effets": dict(AJ.NEUTRES), "emac": 1.0, "version": "test"}


def _arch(h=None, a=None, ko="2026-10-20T18:00:00Z", cotes=None):
    return [{"id": "m1", "ligue": "ligue t", "competition": "Ligue T", "jour": "2026-10-20", "heure": "20:00", "coup_d_envoi_utc": ko, "domicile": "A",
             "exterieur": "B", "eq_dom": "A", "eq_ext": "B", "h": h, "a": a, "cotes": cotes or {"1x2": {"1": 2.0, "N": 3.2, "2": 3.5}}}]


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


class _Lg:
    matchs = {"ligue t": _ligue()}


def test_gel_avant_coup_d_envoi_puis_resultat(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "tester", lambda l, e, z: (l["cle"] == ["1x2", "1"], "test"))                         # un pari forcé pour suivre la mécanique
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


def test_emac_glissante_sur_30_jours_du_journal_sinon_valeur_du_calibrage():
    def ligne(mid, jour, p):
        return {"type": "pronostic", "match_id": mid, "gele_le": f"{jour}T10:00:00+00:00",
                "fiche": {"jour": jour, "coup_d_envoi_utc": f"{jour}T18:00:00Z", "p_marches": [p] * len(coeur.CLES)}}
    matchs = [{"id": "a", "h": 1, "a": 0}, {"id": "b", "h": 0, "a": 0}]
    L = [ligne("a", "2026-10-10", 0.5), ligne("b", "2026-08-01", 0.5)]
    e, src, n = suivi.emac_glissante(L, "2026-10-20", matchs, 0.0054)
    assert n == 1 and "journal" in src                                              # « b » est hors des 30 jours
    assert suivi.emac_glissante(L, "2026-12-20", matchs, 0.0054) == (0.0054, "calibrage hors échantillon (Football-Data 2026-27)", 0)
    assert suivi.emac_glissante([ligne("c", "2026-10-10", 0.5)], "2026-10-20", matchs, 0.0054)[2] == 0   # match non terminé : ignoré
