"""Modèles Poisson d'Omega V3 (branche expérimentale) : forces du championnat, calibrage, absence de fuite."""
import numpy as np
import pytest

from moteur_omega_v3 import donnees as D, marches as M, poisson as P


def champ(n=10):
    """Championnat fictif : A marque 2 / encaisse 1 ; B marque 1 / encaisse 2 ; C et D neutres (1-1)."""
    L = []
    j = 1
    for k in range(n):
        for dom, ext, h, a in (("A", "C", 2, 1), ("C", "A", 1, 2), ("B", "D", 1, 2), ("D", "B", 2, 1), ("C", "D", 1, 1), ("D", "C", 1, 1)):
            L.append({"date": f"2026-09-{j:02d}", "dom": dom, "ext": ext, "h": h, "a": a})
            j = j % 28 + 1
        j = j
    return sorted(L, key=lambda m: m["date"])


def test_forces_donnent_plus_de_buts_a_la_meilleure_attaque():
    f = P.forces_championnat(champ(), "A", "B", "2026-12-01")
    assert f["lam_dom"] > f["lam_ext"] > 0


def test_championnat_sans_difference_donne_la_moyenne():
    L = [{"date": f"2026-09-{1 + k % 28:02d}", "dom": d, "ext": e, "h": 1, "a": 1} for k, (d, e) in enumerate([("A", "B"), ("B", "A"), ("A", "C"), ("C", "A"), ("B", "C"), ("C", "B")] * 3)]
    f = P.forces_championnat(L, "A", "B", "2026-12-01")
    assert f["lam_dom"] == pytest.approx(1.0) and f["lam_ext"] == pytest.approx(1.0)


def test_aucun_match_futur_ni_le_match_lui_meme():
    L = champ()
    avant = P.forces_championnat(L, "A", "B", "2026-09-15")
    L2 = L + [{"date": "2026-09-30", "dom": "A", "ext": "B", "h": 9, "a": 0}, {"date": "2026-09-15", "dom": "A", "ext": "B", "h": 7, "a": 7}]
    apres = P.forces_championnat(L2, "A", "B", "2026-09-15")
    assert avant["lam_dom"] == pytest.approx(apres["lam_dom"]) and avant["lam_ext"] == pytest.approx(apres["lam_ext"])


@pytest.mark.parametrize("cas", ["peu_de_matchs", "championnat_vide", "equipe_inconnue"])
def test_donnees_insuffisantes_jamais_inventees(cas):
    L = champ(1) if cas == "peu_de_matchs" else ([] if cas == "championnat_vide" else champ())
    equipes = ("A", "B") if cas != "equipe_inconnue" else ("A", "Z")
    with pytest.raises(ValueError):
        P.forces_championnat(L, *equipes, "2026-12-01")


def test_probabilites_de_marches_coherentes():
    p = P.proba_lambdas(1.8, 1.1)
    i = {c: k for k, c in enumerate(M.CLES)}
    assert p[i[("1x2", "1")]] + p[i[("1x2", "N")]] + p[i[("1x2", "2")]] == pytest.approx(1, abs=1e-6)
    assert p[i[("over_under_2.5", "plus")]] + p[i[("over_under_2.5", "moins")]] == pytest.approx(1, abs=1e-6)
    assert p[i[("1x2", "1")]] > p[i[("1x2", "2")]]
    assert p[i[("btts_total_2.5", "Oui|plus")]] < p[i[("btts", "Oui")]]          # un événement joint ne dépasse jamais l'une de ses conditions


def test_calibreur_croissant_et_fidele_aux_frequences():
    rng = np.random.default_rng(0)
    p = rng.uniform(size=20000)
    s = rng.uniform(size=20000) < p * 0.8                    # le modèle surestime de 20 % : le calibreur doit le corriger
    c = P.Calibreur(p, s, np.ones_like(s, dtype=bool))
    assert np.all(np.diff(c.table) >= -1e-12) and np.all(np.diff(c(np.linspace(0, 1, 500))) >= -1e-12)
    assert c(np.array([0.9]))[0] == pytest.approx(0.72, abs=0.04)
    assert c(np.array([0.5]))[0] == pytest.approx(0.40, abs=0.04)


def test_aucune_value_ni_ev_dans_le_module():
    t = open(P.__file__, encoding="utf-8").read().lower()
    assert "p_implicite" not in t and "* cote" not in t and "value >" not in t


def test_proba_officielle_mixte_puis_force_puis_rien():
    L = champ()
    cal = {k: P.Calibreur(np.linspace(0, 1, 2000), np.linspace(0, 1, 2000) > 0.5, np.ones(2000, dtype=bool)) for k in ("MIXTE", "FORCE")}
    r = P.proba_officielle(L, "A", "B", "2026-12-01", cal)
    assert r["modele"] in ("MIXTE", "FORCE") and r["calibre"].shape == r["brut"].shape
    # une équipe sans assez de matchs à son lieu mais avec assez au total → FORCE seul
    L2 = [m for m in L if not (m["dom"] == "A" and m["date"] > "2026-09-02")] + [{"date": f"2026-09-{d:02d}", "dom": "C", "ext": "A", "h": 1, "a": 2} for d in range(3, 12)]
    assert P.proba_officielle(L2, "A", "B", "2026-12-01", cal)["modele"] == "FORCE"
    # moins de 5 matchs au total → rien, avec la raison
    r3 = P.proba_officielle(champ(1), "A", "B", "2026-12-01", cal)
    assert r3["modele"] is None and "insuffisantes" in r3["raison"]


def test_calibreur_distingue_deux_probabilites_proches_pas_de_marches_d_escalier():
    rng = np.random.default_rng(2)
    p = rng.uniform(size=30000)
    s = rng.uniform(size=30000) < p
    c = P.Calibreur(p, s, np.ones_like(s, dtype=bool))
    v = c(np.array([0.60, 0.62, 0.64, 0.66, 0.68]))
    assert len(set(np.round(v, 4))) == 5 and np.all(np.diff(v) > 0)              # cinq probabilités différentes → cinq pourcentages différents
    assert c(np.array([0.62]))[0] == pytest.approx(0.62, abs=0.03)                 # et fidèles à la réussite réelle


# --- profondeur : toute la saison au même lieu, 5 matchs minimum (règle de Patrick du 02/11/2026) ---
def _lieu(n_dom, n_ext):
    ms = []
    for i in range(n_dom):
        ms.append({"dom": "A", "ext": f"X{i}", "date": f"2026-01-{i + 1:02d}", "h": i % 3, "a": 1, "dom_nom": "A", "ext_nom": f"X{i}"})
    for i in range(n_ext):
        ms.append({"dom": f"Y{i}", "ext": "B", "date": f"2026-01-{i + 1:02d}", "h": 1, "a": i % 2, "dom_nom": f"Y{i}", "ext_nom": "B"})
    return ms


@pytest.mark.parametrize("n_dom,n_ext,attendu", [(5, 5, (5, 5)), (12, 9, (12, 9)), (19, 19, (19, 19))])
def test_toute_la_saison_prise(n_dom, n_ext, attendu):
    s = D.sequences(_lieu(n_dom, n_ext), "A", "B", "2026-06-01", n=D.TOUT_LE_LIEU)
    assert (len(s["att_a"]), len(s["att_b"])) == attendu


@pytest.mark.parametrize("n_dom,n_ext", [(4, 10), (10, 4), (0, 0)])
def test_moins_de_cinq_refuse(n_dom, n_ext):
    with pytest.raises(ValueError):
        D.sequences(_lieu(n_dom, n_ext), "A", "B", "2026-06-01", n=D.TOUT_LE_LIEU)


def test_defaut_inchange_cinq():
    assert len(D.sequences(_lieu(12, 12), "A", "B", "2026-06-01")["att_a"]) == 5
