"""Prior à moyenne Elo dans le Dixon-Coles pénalisé (branche moteur-dc-elo)."""
import numpy as np
import pytest

from moteur_dc import modele as MO


def _ligue(seed=0, n_eq=16, tours=1, g_vrai=0.25, d_vrai=-0.2, bruit_elo=0.3):
    rng = np.random.default_rng(seed)
    noms = [f"E{k:02d}" for k in range(n_eq)]
    z = rng.normal(size=n_eq)
    att, dfn = g_vrai * z + 0.05 * rng.normal(size=n_eq), d_vrai * z + 0.05 * rng.normal(size=n_eq)
    dom, ext, h, a = [], [], [], []
    for _ in range(tours):
        for i in range(n_eq):
            for j in range(n_eq):
                if i != j:
                    dom.append(noms[i]); ext.append(noms[j])
                    h.append(rng.poisson(np.exp(0.2 + 0.25 + att[i] + dfn[j]))); a.append(rng.poisson(np.exp(0.2 + att[j] + dfn[i])))
    elo = {noms[k]: 1500 + 100 * (z[k] + bruit_elo * rng.normal()) for k in range(n_eq)}
    return noms, dom, ext, np.array(h), np.array(a), np.full(len(h), 5.0), elo, att, dfn


def _fit(dom, ext, h, a, age, **kw):
    return MO.ajuster(dom, ext, h, a, age, 0.25, 0.004, rho=-0.04, **kw)


def test_sans_elo_aucun_changement():
    _, dom, ext, h, a, age, elo, _, _ = _ligue()
    sans = _fit(dom, ext, h, a, age)
    vide = _fit(dom, ext, h, a, age, elo={})                     # Elo fourni mais aucune équipe couverte : E = 0 partout
    assert sans.gamma_elo == 0.0 and sans.delta_elo == 0.0
    assert np.allclose(sans.att, vide.att, atol=1e-4) and np.allclose(sans.dfn, vide.dfn, atol=1e-4)
    assert abs(vide.gamma_elo) < 1e-6 and abs(vide.delta_elo) < 1e-6


def test_signes_et_amplitude_retrouves():
    _, dom, ext, h, a, age, elo, _, _ = _ligue(seed=1, tours=2)
    r = _fit(dom, ext, h, a, age, elo=elo)
    assert r.gamma_elo > 0.1 and r.delta_elo < -0.08            # vrais 0,25 et −0,20, estimés avec du bruit


def test_prior_elo_aide_quand_peu_de_matchs_et_ne_nuit_pas_sans_signal():
    noms, dom, ext, h, a, age, elo, att, dfn = _ligue(seed=2, tours=1)
    idx = np.random.default_rng(3).choice(len(h), size=len(h) // 3, replace=False)       # peu de matchs par équipe
    pick = lambda x: [x[i] for i in idx]
    r0 = _fit(pick(dom), pick(ext), h[idx], a[idx], age[idx])
    r1 = _fit(pick(dom), pick(ext), h[idx], a[idx], age[idx], elo=elo)
    err = lambda r: float(np.mean((r.att - att[[noms.index(e) for e in r.equipes]]) ** 2 + (r.dfn - dfn[[noms.index(e) for e in r.equipes]]) ** 2))
    assert err(r1) < err(r0)


def test_equipe_sans_elo_traitee_comme_moyenne_et_elo_constant_neutre():
    _, dom, ext, h, a, age, elo, _, _ = _ligue(seed=5)
    partiel = {k: v for k, v in list(elo.items())[:10]}           # 6 équipes sans Elo
    r = _fit(dom, ext, h, a, age, elo=partiel)
    assert np.all(np.isfinite(r.att)) and r.gamma_elo != 0.0
    plat = _fit(dom, ext, h, a, age, elo={k: 1500.0 for k in elo})  # écart-type nul : pas de signal exploitable
    sans = _fit(dom, ext, h, a, age)
    assert np.allclose(plat.att, sans.att, atol=1e-4)
    un_seul = _fit(dom, ext, h, a, age, elo={"E00": 1700.0})        # une seule équipe couverte : pas de standardisation possible
    assert np.allclose(un_seul.att, sans.att, atol=1e-4)


def test_coefficients_figes_pas_de_parametre_libre_et_nuisibles_si_faux():
    noms, dom, ext, h, a, age, elo, att, dfn = _ligue(seed=6)
    bon = _fit(dom, ext, h, a, age, elo=elo, elo_coefs=(0.25, -0.2))
    assert bon.gamma_elo == 0.25 and bon.delta_elo == -0.2
    nul = _fit(dom, ext, h, a, age, elo=elo, elo_coefs=(0.0, 0.0))
    sans = _fit(dom, ext, h, a, age)
    assert np.allclose(nul.att, sans.att, atol=1e-4) and np.allclose(nul.dfn, sans.dfn, atol=1e-4)    # (0, 0) = ridge actuel
    idx = np.random.default_rng(7).choice(len(h), size=len(h) // 4, replace=False)
    sel = lambda v: [v[i] for i in idx]
    err = lambda r: float(np.mean((r.att - att[[noms.index(e) for e in r.equipes]]) ** 2 + (r.dfn - dfn[[noms.index(e) for e in r.equipes]]) ** 2))
    bon, faux, ridge = (_fit(sel(dom), sel(ext), h[idx], a[idx], age[idx], **kw) for kw in
                        ({"elo": elo, "elo_coefs": (0.25, -0.2)}, {"elo": elo, "elo_coefs": (-0.25, 0.2)}, {}))
    assert err(bon) < err(ridge) < err(faux)                         # bon prior aide, prior inversé nuit


def test_mode_libre_bruit_avec_peu_d_equipes():
    _, dom, ext, h, a, age, elo, _, _ = _ligue(seed=8, n_eq=60, tours=1)
    rng = np.random.default_rng(9)
    r = _fit(dom, ext, h, a, age, elo={k: 1500 + 100 * rng.normal() for k in elo})
    assert abs(r.gamma_elo) < 0.1 and abs(r.delta_elo) < 0.1          # Elo sans rapport : proche de 0 si assez d'équipes
