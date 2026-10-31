"""Règle n°1 (compatibilité) : outils d'évaluation. Chaque règle de décision a des cas qui passent ET des cas qui échouent."""
import numpy as np
import pytest

from moteur_dc import coeur, compatibilite as CP, compatibilite_eval as E, selecteur as S


@pytest.mark.parametrize("k,n", [(7, 10), (0, 5), (5, 5), (30, 100)])
def test_wilson_bas_identique_au_selecteur(k, n):
    assert E.wilson_bas(np.array([k]), np.array([n]))[0] == pytest.approx(S.wilson(k, n)[0])


def test_wilson_bas_sans_historique_vaut_zero():
    assert E.wilson_bas(np.array([0]), np.array([0]))[0] == 0.0


def test_petit_echantillon_moins_compatible_que_grand():
    assert E.wilson_bas(np.array([4]), np.array([4]))[0] < E.wilson_bas(np.array([40]), np.array([40]))[0]


@pytest.mark.parametrize("bas", [0.0001, 0.01, 0.2])
def test_retenu_quand_borne_basse_positive(bas):
    assert E.retenu(bas)


@pytest.mark.parametrize("bas", [0.0, -0.0001, -0.3])
def test_non_retenu_quand_borne_basse_nulle_ou_negative(bas):
    assert not E.retenu(bas)


def test_variantes_de_croisement():
    L = {"dom": np.array([0.8, 0.2]), "ext": np.array([0.4, 0.6])}
    assert list(E.comp_croisee(L, "min")) == [0.4, 0.2]
    assert list(E.comp_croisee(L, "moyenne")) == pytest.approx([0.6, 0.4])
    assert list(E.comp_croisee(L, "produit")) == pytest.approx([0.32, 0.12])


def _paire_meme_groupe():
    for i, a in enumerate(coeur.CLES):
        for j in range(i + 1, len(coeur.CLES)):
            if coeur.CLES[j][0] == a[0]:
                return i, j
    raise AssertionError


def _paire_meme_evenement():
    for i in range(len(coeur.CLES)):
        for j in range(i + 1, len(coeur.CLES)):
            if E.SIG_ID[i] == E.SIG_ID[j] and E.GRP_ID[i] != E.GRP_ID[j]:
                return i, j
    return None


def test_une_seule_issue_par_marche():
    i, j = _paire_meme_groupe()
    s = np.zeros((1, 103))
    s[0, i], s[0, j] = 0.9, 0.8
    m = E.candidats(s, s)
    assert m[0, i] and not m[0, j]


def test_issue_la_mieux_classee_gagne():
    i, j = _paire_meme_groupe()
    s = np.zeros((1, 103))
    s[0, i], s[0, j] = 0.5, 0.9
    m = E.candidats(s, s)
    assert m[0, j] and not m[0, i]


def test_jamais_deux_fois_le_meme_evenement():
    p = _paire_meme_evenement()
    if p is None:
        pytest.skip("aucun événement dupliqué dans le catalogue")
    i, j = p
    s = np.zeros((1, 103))
    s[0, i], s[0, j] = 0.9, 0.8
    m = E.candidats(s, s)
    assert m[0, i] and not m[0, j]


def test_marches_de_groupes_et_evenements_differents_tous_gardes():
    choix = []
    for j in range(103):
        if all(E.GRP_ID[j] != E.GRP_ID[k] and E.SIG_ID[j] != E.SIG_ID[k] for k in choix):
            choix.append(j)
        if len(choix) == 3:
            break
    s = np.zeros((1, 103))
    s[0, choix] = 0.9
    m = E.candidats(s, s)
    assert all(m[0, j] for j in choix)


def test_seuil_appris_quand_la_reussite_monte():
    rng = np.random.default_rng(1)
    s = rng.uniform(0.5, 1.0, 5000)
    y = (rng.uniform(size=5000) < s).astype(float)
    r = E.pav_seuil(s, y)
    assert r["seuil"] is not None and 0.5 <= r["seuil"] <= 0.85


def test_pas_de_seuil_si_la_reussite_reste_basse():
    rng = np.random.default_rng(2)
    s = rng.uniform(0.5, 1.0, 5000)
    y = (rng.uniform(size=5000) < 0.4).astype(float)
    assert E.pav_seuil(s, y)["seuil"] is None


def test_pas_de_seuil_sans_assez_de_paris():
    s = np.full(10, 0.95)
    assert E.pav_seuil(s, np.ones(10))["seuil"] is None


def _agr(rng, n_matchs, taux, par_match=3):
    n = np.full(n_matchs, float(par_match))
    w = rng.binomial(par_match, taux, n_matchs).astype(float)
    return n, w


def test_bootstrap_detecte_un_ecart_plante():
    rng = np.random.default_rng(3)
    nA, wA = _agr(rng, 1500, 0.80)
    nB, wB = _agr(rng, 1500, 0.70)
    ecart, bas, haut, sd = E.bootstrap_ecart(nA, wA, nB, wB, np.random.default_rng(4))
    assert ecart > 0.05 and E.retenu(bas)


def test_bootstrap_ne_retient_pas_un_ecart_nul():
    rng = np.random.default_rng(5)
    nA, wA = _agr(rng, 1500, 0.75)
    nB, wB = _agr(rng, 1500, 0.75)
    _, bas, haut, _ = E.bootstrap_ecart(nA, wA, nB, wB, np.random.default_rng(6))
    assert not E.retenu(bas) and bas < 0 < haut


def test_bootstrap_ne_retient_pas_un_ecart_inverse():
    rng = np.random.default_rng(7)
    nA, wA = _agr(rng, 1500, 0.65)
    nB, wB = _agr(rng, 1500, 0.80)
    ecart, bas, _, _ = E.bootstrap_ecart(nA, wA, nB, wB, np.random.default_rng(8))
    assert ecart < 0 and not E.retenu(bas)


def test_holm():
    assert E.holm([0.001, 0.2, 0.5]) == [True, False, False]
    assert E.holm([0.2, 0.3]) == [False, False]
    assert E.holm([0.02, 0.03]) == [False, False]
    assert E.holm([0.01, 0.012]) == [True, True]


def test_effectifs_par_equipe_somment_aux_effectifs_du_moteur():
    c = {"equipe_domicile": {"historique_matchs_dom": [{"buts_pour": 2, "buts_contre": 0}, {"buts_pour": 1, "buts_contre": 1}, {"buts_pour": 0, "buts_contre": 3}]},
         "equipe_exterieur": {"historique_matchs_ext": [{"buts_pour": 1, "buts_contre": 2}, {"buts_pour": 0, "buts_contre": 0}]}}
    kd, nd, ke, ne = CP.effectifs_cotes(c)
    K, n = coeur.effectifs(c)
    assert (nd, ne) == (3, 2) and nd + ne == n
    assert list(kd + ke) == list(K)


def test_effectifs_sans_historique():
    c = {"equipe_domicile": {"historique_matchs_dom": []}, "equipe_exterieur": {"historique_matchs_ext": [{"buts_pour": 1, "buts_contre": 0}]}}
    kd, nd, ke, ne = CP.effectifs_cotes(c)
    assert nd == 0 and ne == 1 and kd.sum() == 0


def _jeu(rng, beta, n=800):
    """Deux saisons simulées : issue ~ Bernoulli(sigmoïde(logit P + beta × écart de compatibilité au marché))."""
    def une():
        P = rng.uniform(0.5, 0.95, (n, 103))
        L = {"dom": rng.uniform(0.2, 0.9, (n, 103)), "ext": rng.uniform(0.2, 0.9, (n, 103))}
        s = np.minimum(L["dom"], L["ext"]) - 0.5
        z = np.log(P / (1 - P)) + beta * s
        return {"P": P, "L": L, "Y": (rng.uniform(size=P.shape) < 1 / (1 + np.exp(-z))).astype(float)}
    return une(), une()


def test_regression_centree_detecte_un_signal_plante():
    cal, tst = _jeu(np.random.default_rng(11), beta=4.0)
    r = E.regression(cal, tst, np.random.default_rng(12), centrer=True)
    assert r["min"]["retenu"] and r["min"]["coef_compat_std"] > 0


def test_regression_centree_ne_retient_rien_sans_signal():
    cal, tst = _jeu(np.random.default_rng(13), beta=0.0)
    r = E.regression(cal, tst, np.random.default_rng(14), centrer=True)
    assert not r["min"]["retenu"]


def test_regression_centree_signal_inverse_non_retenu():
    cal, tst = _jeu(np.random.default_rng(15), beta=-4.0)
    r = E.regression(cal, tst, np.random.default_rng(16), centrer=True)
    assert r["min"]["coef_compat_std"] < 0
