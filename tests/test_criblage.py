"""Tests de la piste A (criblage). Règles de décision : au moins 3 cas qui passent et 3 qui échouent ; anti-fuite ; signal planté / bruit."""
import numpy as np
import pytest

from moteur_dc import criblage as K, modele as MO


# --- règle de décision (borne basse de l'intervalle > 0)
@pytest.mark.parametrize("bas", [1e-9, 0.0004, 0.01])
def test_retenu_si_borne_basse_positive(bas):
    assert K.retenu(bas)


@pytest.mark.parametrize("bas", [0.0, -1e-9, -0.01, float("nan")])
def test_retire_si_borne_basse_nulle_negative_ou_nan(bas):
    assert not K.retenu(bas)


def test_holm_cas_qui_passent_et_qui_echouent():
    p = {"a": 0.0001, "b": 0.0004, "c": 0.02, "d": 0.5}                    # m = 4 : seuils 0,025/4, /3, /2, /1
    h = K.holm(p)
    assert h["a"] and h["b"] and not h["c"] and not h["d"]
    assert not any(K.holm({"a": 0.03, "b": 0.2, "c": 0.9}).values())          # rien ne passe
    assert all(K.holm({"a": 0.0001, "b": 0.0002, "c": 0.0003}).values())      # tout passe
    assert K.holm({"a": 0.03, "b": 0.0001}) == {"b": True, "a": False}        # l'ordre d'entrée ne compte pas


# --- encodage des paramètres
def _equipe(**kw):
    base = {"profil": "Mur", "profil_id": 3, "style_tag": "Balanced", "serie": "3V", "score_modal": "1-1", "score_modal_dom": "2-0",
            "score_modal_ext": None, "J": 8, "MBM": 1.5, "IE": None, "rangs": {"classement": 4, "attaque": 2}, "ok": True}
    base.update(kw)
    return base


def test_groupes_encodage():
    g = K.groupes(_equipe())
    assert g["score_modal"] == {"score_modal": 1.0} and g["score_modal_dom"] == {"score_modal_dom": 0.0} and g["score_modal_ext"] == {"score_modal_ext": None}
    assert g["serie"] == {"serie_len": 3.0, "serie_V": 1.0, "serie_N": 0.0, "serie_D": 0.0}
    assert g["profil_id"]["profil_3"] == 1.0 and sum(g["profil_id"].values()) == 1.0
    assert g["style_tag"]["style_Balanced"] == 1.0
    assert g["rang_classement"] == {"rang_classement": 4.0} and g["IE"] == {"IE": None}
    assert "profil" not in g and "ok" not in g                                # doublon textuel et booléen ignorés


def test_groupes_memes_colonnes_quelle_que_soit_l_equipe():
    a, b = K.groupes(_equipe()), K.groupes(_equipe(serie="1D", profil_id=5, style_tag="Defensive", score_modal=None, IE=1.1))
    assert {k: list(v) for k, v in a.items()} == {k: list(v) for k, v in b.items()}


# --- anti-fuite : la standardisation vient de l'apprentissage seulement
def test_standardisation_utilise_l_apprentissage_seul():
    A = np.array([[1.0], [2.0], [3.0]])
    T = np.array([[10.0], [20.0]])
    ZA, mu, sd = K.standardiser(A)
    ZT, mu2, sd2 = K.standardiser(T, mu, sd)
    assert mu[0] == pytest.approx(2.0) and mu2 is mu and sd2 is sd
    assert ZT[0, 0] == pytest.approx((10 - 2) / sd[0])                      # pas recentré sur le test
    assert abs(ZT.mean()) > 1


def test_valeur_manquante_et_colonne_constante():
    Z, mu, sd = K.standardiser(np.array([[1.0, 5.0], [np.nan, 5.0], [3.0, 5.0]]))
    assert Z[1, 0] == 0.0 and np.all(Z[:, 1] == 0.0)


# --- ridge et choix de α
def test_ridge_retrouve_un_signal_et_alpha_grand_l_ecrase():
    rng = np.random.default_rng(0)
    Z = rng.normal(size=(4000, 2))
    r = 0.5 * Z[:, 0] + rng.normal(size=4000)
    th = K.ridge(Z, r, 1.0)
    assert th[0] == pytest.approx(0.5, abs=0.06) and abs(th[1]) < 0.06
    assert np.all(np.abs(K.ridge(Z, r, 1e9)) < 1e-3)


def test_alpha_grand_sans_signal_petit_avec_signal():
    rng = np.random.default_rng(1)
    Z = rng.normal(size=(3000, 3))
    blocs = np.repeat(np.arange(10), 300)
    bruit = rng.normal(size=3000)
    assert K.choisir_alpha(Z, bruit, blocs) >= 1000
    assert K.choisir_alpha(Z, 0.5 * Z[:, 0] + bruit, blocs) <= 100


# --- mesure : écart nul sans ajustement, positif si l'ajustement va dans le bon sens, négatif sinon
def _lignes(n=300, seed=0):
    rng = np.random.default_rng(seed)
    lh, la = rng.uniform(0.8, 2.0, n), rng.uniform(0.6, 1.6, n)
    h, a = rng.poisson(lh * 1.3), rng.poisson(la)                          # les vrais buts sont plus hauts que λ côté domicile
    return {"n": n, "lh": lh, "la": la, "rho": np.full(n, -0.04), "h": np.minimum(h, MO.N_BUTS), "a": np.minimum(a, MO.N_BUTS)}


def test_gain_ll_nul_sans_ajustement_et_signe():
    L = _lignes()
    assert np.allclose(K.gain_ll(L, np.zeros(2 * L["n"])), 0.0)
    mieux = np.concatenate([0.3 * np.sqrt(L["lh"]), np.zeros(L["n"])])     # relève λ domicile : correct
    pire = np.concatenate([-0.3 * np.sqrt(L["lh"]), np.zeros(L["n"])])
    assert K.gain_ll(L, mieux).mean() > 0 > K.gain_ll(L, pire).mean()


def test_bootstrap_intervalle():
    rng = np.random.default_rng(2)
    b = K.bootstrap(rng.normal(0.05, 0.1, 2000), rng, 500)
    assert b["bas"] > 0 and K.retenu(b["bas"])
    b0 = K.bootstrap(rng.normal(0.0, 0.1, 2000), np.random.default_rng(3), 500)
    assert b0["bas"] < 0 < b0["haut"] and not K.retenu(b0["bas"])


# --- bout en bout sur données synthétiques : signal planté retenu, bruit retiré, placebo ne retient presque rien
def _jeu(n, seed, signal=True):
    rng = np.random.default_rng(seed)
    lh, la = rng.uniform(1.0, 2.0, n), rng.uniform(0.8, 1.6, n)
    z_s = rng.normal(size=2 * n)                                           # variable informative (côté domicile puis extérieur)
    z_b = rng.normal(size=2 * n)
    mult = np.exp((0.35 * z_s if signal else 0) / np.sqrt(np.concatenate([lh, la])))
    lam_vrai = np.concatenate([lh, la]) * mult
    y = rng.poisson(lam_vrai).astype(float)
    X = np.column_stack([z_s, rng.normal(size=2 * n), z_b, rng.normal(size=2 * n)])
    return {"X": X, "index": {"signal": [0, 1], "bruit": [2, 3]}, "lam": np.concatenate([lh, la]), "y": y, "n": n,
            "mois": np.array([f"2026-{1 + i % 8:02d}" for i in range(n)]), "lh": lh, "la": la, "rho": np.full(n, -0.04),
            "h": np.minimum(y[:n], MO.N_BUTS).astype(int), "a": np.minimum(y[n:], MO.N_BUTS).astype(int)}


def test_bout_en_bout_signal_plante():
    App, Test = _jeu(6000, 10), _jeu(3000, 11)
    r = K.cribler(App, Test, np.random.default_rng(0))["parametres"]
    assert r["signal"]["retenu"] and r["signal"]["retenu_holm"]
    assert not r["bruit"]["retenu"]


def test_bout_en_bout_sans_signal_et_placebo():
    App, Test = _jeu(6000, 20, signal=False), _jeu(3000, 21, signal=False)
    assert not any(v["retenu_holm"] for v in K.cribler(App, Test, np.random.default_rng(0))["parametres"].values())
    App, Test = _jeu(6000, 30), _jeu(3000, 31)
    pl = K.cribler(App, Test, np.random.default_rng(0), melange=True)["parametres"]
    assert not pl["signal"]["retenu_holm"]                                  # le placebo casse le signal planté
