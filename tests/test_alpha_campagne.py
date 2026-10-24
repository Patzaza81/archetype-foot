"""Tests de la campagne d'optimisation de l'alpha (alpha_serie/campagne.py)."""
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from alpha_serie import campagne as C  # noqa: E402


def _col(lignes):
    """lignes : (etape, jour, n, d, h, gagne, cote)."""
    return {"etape": np.array([x[0] for x in lignes]), "jour": np.array([x[1] for x in lignes]), "id": [f"m{i}" for i in range(len(lignes))],
            "n": np.array([x[2] for x in lignes], dtype=np.int8), "d": np.array([x[3] for x in lignes]), "h": np.array([x[4] for x in lignes]),
            "g": np.array([x[5] for x in lignes], dtype=bool), "cote": np.array([np.nan if x[6] is None else x[6] for x in lignes])}


def _etape(etape, mois, n_par_jour, taux_filtre, taux_reste, cote=None, jours=10):
    out = []
    for j in range(1, jours + 1):
        for k in range(n_par_jour):
            filtre = k % 2 == 0
            taux = taux_filtre if filtre else taux_reste
            out.append((etape, f"2026-{mois}-{j:02d}", 6, 1.0 if filtre else 0.0, 1.0 if filtre else 0.0, (k // 2) % 10 < taux * 10, cote))
    return out


def test_categories_sans_plafond():
    assert C.categories(None) == ["toutes"]
    assert C.categories(1.24) == []                                  # sous la cote minimale : jamais proposable
    assert C.categories(1.30) == ["toutes", "A"] and C.categories(1.39) == ["toutes", "B"] and C.categories(15.0) == ["toutes", "B"]


def test_recherche_choisit_la_preuve_pas_le_volume():
    col = _col(_etape("apprentissage", "01", 40, 0.9, 0.3))
    moitie = col["jour"] < "2026-01-06"
    cfg, nb = C.chercher("toutes", col["n"], col["d"], col["h"], col["g"].astype(float), moitie)
    assert nb > 0 and cfg["marge_defavorable"] == 1.0 and cfg["paris"] == 200   # pas « tout prendre » (400 paris)


def test_filtre_sans_amelioration_aucune_configuration():
    col = _col(_etape("apprentissage", "01", 40, 0.7, 0.7))
    cfg, _ = C.chercher("toutes", col["n"], col["d"], col["h"], col["g"].astype(float), col["jour"] < "2026-01-06")
    assert cfg is None


def test_grosse_cote_retenue_pour_son_rendement():
    col = _col(_etape("apprentissage", "01", 40, 0.3, 0.1, cote=8.0))  # 30 % à 8,0 : très rentable malgré une faible réussite
    v = C._valeurs("B", col["g"], col["cote"])
    cfg, _ = C.chercher("B", col["n"], col["d"], col["h"], v, col["jour"] < "2026-01-06")
    assert cfg is not None and cfg["valeur"] > 0                      # jamais rejetée pour le montant de sa cote


def test_combo_retenu_sous_le_niveau_des_simples():
    col = _col(_etape("apprentissage", "01", 40, 0.4, 0.1))            # 40 % : bien sous 72 %, mais nettement au-dessus du reste
    cfg, _ = C.chercher("toutes", col["n"], col["d"], col["h"], col["g"].astype(float), col["jour"] < "2026-01-06")
    assert cfg is not None and cfg["valeur"] == 0.4


def _tab(final_taux_filtre, val_taux_filtre=0.9):
    lignes = (_etape("apprentissage", "01", 40, 0.9, 0.3) + _etape("validation", "05", 40, val_taux_filtre, 0.3)
              + _etape("final", "10", 40, final_taux_filtre, 0.3))
    return {("Marché test", "toutes"): _col(lignes)}, {"Marché test": {"cle": ("over_under_2.5", "plus"), "famille": "totaux"}}


def test_statuts_bout_en_bout():
    assert C.campagne(*_tab(0.9))["fiches"][0]["statut"] == "exploitable"
    assert C.campagne(*_tab(0.3))["fiches"][0]["statut"] == "non confirmé"
    assert C.campagne(*_tab(0.9, val_taux_filtre=0.3))["fiches"][0]["statut"] == "écarté en validation"


def test_le_test_final_ne_sert_jamais_a_choisir():
    a = C.campagne(*_tab(0.9))["fiches"][0]["configuration"]
    b = C.campagne(*_tab(0.0))["fiches"][0]["configuration"]
    assert a == b                                                      # changer les résultats du test final ne change pas la configuration


def test_p_exacte_reproductible():
    col = _col(_etape("final", "10", 20, 0.3, 0.1, cote=6.0))
    v = C._valeurs("B", col["g"], col["cote"])
    sel = col["d"] >= 1.0
    assert C.p_exacte("B", v, sel, col["g"]) == C.p_exacte("B", v, sel, col["g"])
    assert C.p_exacte("toutes", col["g"].astype(float), np.ones(len(sel), dtype=bool), col["g"]) == 1.0   # tout prendre : aucune preuve


def test_etape_football_data_sans_recouvrement_avec_archetype():
    assert C.etape_fd({"jour": "2026-03-01", "saison": "2526"}) == "apprentissage"
    assert C.etape_fd({"jour": "2026-08-15", "saison": "2627"}) == "validation"
    assert C.etape_fd({"jour": "2026-09-28", "saison": "2627"}) is None


# --- Défaut 1 (corrigé le 24/10) : le découpage par étiquette de saison mêlait les dates ------------------------------
def test_decoupage_par_date_et_non_par_etiquette_de_saison():
    # un match « 2627 » d'un championnat sur l'année civile, joué en mars 2026, appartient à l'apprentissage (avant la validation)
    assert C.etape_fd({"jour": "2026-03-15", "saison": "2627"}) == "apprentissage"
    assert C.etape_fd({"jour": "2026-06-30", "saison": "2627"}) == "apprentissage"
    assert C.etape_fd({"jour": "2026-07-01", "saison": "2627"}) == "validation"


def test_decoupage_reel_strictement_chronologique_sans_identifiant_commun():
    import gzip
    import json
    liste = json.load(gzip.open(C.R.BLOC))["liste"]
    etapes = {}
    for m in liste:
        e = C.etape_fd({"jour": m["date"], "saison": m["saison"]})
        if e:
            etapes.setdefault(e, []).append(m)
    ap, va = etapes["apprentissage"], etapes["validation"]
    assert max(m["date"] for m in ap) < min(m["date"] for m in va) < C.DEBUT_ARCHETYPE
    assert not ({m["id"] for m in ap} & {m["id"] for m in va})
    assert any(m["saison"] == "2627" for m in ap)                     # les matchs civils 2026 avant juillet sont bien dans l'apprentissage


# --- Défaut 2 (corrigé le 24/10) : Benjamini-Hochberg appliqué après une présélection sur les résultats --------------
def _bloc(etape, mois, n1, w1, n0, w0, jours=10):
    out = [(etape, f"2026-{mois}-{1 + i % jours:02d}", 6, 1.0, 1.0, (i // jours) < w1 // jours, None) for i in range(n1)]
    return out + [(etape, f"2026-{mois}-{1 + i % jours:02d}", 6, 0.0, 0.0, (i // jours) < w0 // jours, None) for i in range(n0)]


def _tab_bh(n_nuls):
    tab, infos = {}, {}
    marginal = _etape("apprentissage", "01", 40, 0.9, 0.3) + _bloc("validation", "07", 100, 60, 100, 40) + _etape("final", "10", 40, 0.9, 0.3)
    tab[("Marginal", "toutes")] = _col(marginal)
    infos["Marginal"] = {"cle": ("over_under_2.5", "plus"), "famille": "totaux"}
    for i in range(n_nuls):                                            # bons à l'apprentissage, inversés en validation (apport négatif)
        nul = _etape("apprentissage", "01", 40, 0.9, 0.3) + _bloc("validation", "07", 100, 30, 100, 60) + _etape("final", "10", 40, 0.9, 0.3)
        tab[(f"Nul {i}", "toutes")] = _col(nul)
        infos[f"Nul {i}"] = {"cle": ("over_under_2.5", "plus"), "famille": "totaux"}
    return tab, infos


def test_bh_validation_porte_sur_toutes_les_hypotheses():
    seul = C.campagne(*_tab_bh(0))
    assert [f for f in seul["fiches"] if f["marche"] == "Marginal"][0]["statut"] == "exploitable"   # p = 0,0035, seule hypothèse
    avec = C.campagne(*_tab_bh(30))
    f = [f for f in avec["fiches"] if f["marche"] == "Marginal"][0]
    assert avec["hypotheses_validation"] == 31                          # les 30 hypothèses à apport négatif comptent aussi
    assert f["statut"] == "écarté en validation" and f["q_validation"] > 0.05   # l'ancienne présélection l'aurait gardé (m = 1)


def test_bh_final_porte_sur_toutes_les_candidates():
    tab, infos = {}, {}
    for i, taux in enumerate([0.9, 0.3, 0.3]):                          # trois candidates, dont deux sans apport au test final
        tab[(f"M{i}", "toutes")] = _col(_etape("apprentissage", "01", 40, 0.9, 0.3) + _etape("validation", "07", 40, 0.9, 0.3)
                                        + _etape("final", "10", 40, taux, 0.3))
        infos[f"M{i}"] = {"cle": ("over_under_2.5", "plus"), "famille": "totaux"}
    r = C.campagne(tab, infos)
    assert r["tests_finaux"] == 3 and all("q_final" in f for f in r["fiches"])
    assert [f["statut"] for f in r["fiches"]] == ["exploitable", "non confirmé", "non confirmé"]


def test_q_valeurs_benjamini_hochberg():
    q = C.q_valeurs({"a": 0.01, "b": 0.02, "c": 0.9})
    assert q == {"a": 0.03, "b": 0.03, "c": 0.9}
