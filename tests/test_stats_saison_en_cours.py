"""Source de statistiques du moteur : saison en cours seule, matchs les plus récents (21/09/2026).

Règle du propriétaire (loader.py, 08/09/2026, « non négociable ») : jamais de repli sur la saison précédente ; et la page
liste les matchs du plus ancien au plus récent, donc la fenêtre est la FIN de la liste.
"""
import pytest

import bibliotheque_justification as bj
import pont_moteur
import precalcul
import stats_saison_en_cours as ss


def hist(n_dom, n_ext, debut=0):
    """Historique CHRONOLOGIQUE croissant, intercalant domicile / extérieur ; le score encode le rang (0 = plus ancien)."""
    out, d, e = [], 0, 0
    for i in range(n_dom + n_ext):
        dom = (i % 2 == 0 and d < n_dom) or e >= n_ext
        if dom:
            out.append({"domicile": True, "buts_marques": d + debut, "buts_encaisses": 0}); d += 1
        else:
            out.append({"domicile": False, "buts_marques": e + debut, "buts_encaisses": 1}); e += 1
    return out


@pytest.fixture
def fake(monkeypatch):
    appels = []
    def installe(h):
        def _f(url, comp, nom):
            appels.append((url, comp, nom)); return h
        monkeypatch.setattr(ss._loader, "recupere_historique_saison_courante", _f)
        return appels
    return installe


def test_garde_les_12_plus_recents_par_lieu_en_ordre_croissant(fake):
    appels = fake(hist(15, 14))
    r = ss.stats_saison_en_cours("http://x/eq", "A", "France : Ligue 1")
    assert (r["nb_domicile"], r["nb_exterieur"]) == (12, 12)
    assert [m["buts_marques"] for m in r["matchs_domicile_bruts"]] == list(range(3, 15))     # les 12 derniers, du plus ancien au plus récent
    assert [m["buts_marques"] for m in r["matchs_exterieur_bruts"]] == list(range(2, 14))
    assert r["matchs_domicile_bruts"][-1]["buts_marques"] == 14                              # le plus récent est EN DERNIER
    assert r["gf_domicile"] == sum(range(3, 15)) / 12 and r["source"] == "saison_en_cours_seule"
    assert appels == [("http://x/eq", "France : Ligue 1", "A")]                             # UN seul fetch, aucune URL ?season=


def test_debut_de_saison_aucun_complement_par_la_saison_precedente(fake):
    appels = fake(hist(3, 2))
    r = ss.stats_saison_en_cours("http://x/eq", "A", "C")
    assert (r["nb_domicile"], r["nb_exterieur"], r["nb_matchs_saison_courante"]) == (3, 2, 5)   # 3 et 2, pas 10 et 10
    assert len(appels) == 1 and "season" not in appels[0][0]


@pytest.mark.parametrize("h", [[], None])
def test_aucun_match_cette_saison_est_refuse_avec_une_raison(fake, h):
    fake(h if h is not None else [])
    assert ss.stats_saison_en_cours("u", "A", "C") == {"raison_non_traite": "aucun_match_saison_en_cours"}


def test_equipe_sans_match_a_l_exterieur_n_a_pas_de_moyenne_exterieure(fake):
    fake(hist(4, 0))
    r = ss.stats_saison_en_cours("u", "A", "C")
    assert r["nb_exterieur"] == 0 and "gf_exterieur" not in r and "ga_exterieur" not in r and r["nb_domicile"] == 4


def test_le_format_est_lisible_par_le_pont(fake):
    fake(hist(6, 5))
    r = ss.stats_saison_en_cours("u", "Alpha", "C")
    eq = pont_moteur.equipe_vers_moteur("Alpha", r, "dom")
    assert eq["matchs_joues"] == 6 and eq["buts_marques_moy"] == r["gf_domicile"]
    with pytest.raises(ValueError):                                                          # équipe refusée : le pont le dit
        pont_moteur.equipe_vers_moteur("Alpha", {"raison_non_traite": "aucun_match_saison_en_cours"}, "dom")


def test_la_serie_de_la_bibliotheque_decrit_bien_les_matchs_les_plus_recents(fake):
    # 4 défaites anciennes puis 4 victoires récentes : « invaincu depuis 4 matchs ». Avec l'ancien ordre / l'ancien repli : 0.
    matchs = ([{"domicile": True, "buts_marques": 0, "buts_encaisses": 2}] * 4) + ([{"domicile": True, "buts_marques": 2, "buts_encaisses": 0}] * 4)
    fake(matchs)
    r = ss.stats_saison_en_cours("u", "A", "C")
    d = bj.construit_donnees("1x2_domicile", r["matchs_domicile_bruts"], [], [])
    assert d["home_unbeaten_streak"] == 4
    d_inverse = bj.construit_donnees("1x2_domicile", list(reversed(r["matchs_domicile_bruts"])), [], [])
    assert d_inverse["home_unbeaten_streak"] == 0                                          # preuve que l'ordre change le texte


# ───────────────────────── charge_stats_saison (precalcul.py) ─────────────────────────
def sig(mid, dom, ext, cotes=True, url="http://m/" ):
    return {"match_id": mid, "domicile": dom, "exterieur": ext, "competition": "C", "url_match": url + mid,
            "cotes_manuelles": {"1x2": {}} if cotes else None}


def test_charge_seulement_les_matchs_avec_cotes_et_appelle_une_fois_par_equipe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(precalcul, "STATS_EQUIPES_VUES", {})
    appels = []
    def f(url, nom, comp, max_matchs=12):
        appels.append(nom); return {"nb_domicile": 1, "nb_exterieur": 1, "gf_domicile": 1.0, "ga_domicile": 1.0, "matchs_domicile_bruts": [], "matchs_exterieur_bruts": []}
    det = {"http://m/a": {"url_equipe_domicile": "u1", "url_equipe_exterieur": "u2"}, "http://m/b": {"url_equipe_domicile": "u1", "url_equipe_exterieur": "u3"},
           "http://m/c": {"url_equipe_domicile": "u4", "url_equipe_exterieur": "u5"}}
    r = precalcul.charge_stats_saison([sig("a", "X", "Y"), sig("b", "X", "Z"), sig("c", "P", "Q", cotes=False)], det, f)
    assert r == {"équipe chargée": 3} and sorted(appels) == ["X", "Y", "Z"]                  # X chargée UNE fois ; le match sans cotes est ignoré
    assert set(precalcul.STATS_EQUIPES_VUES) == {("X", "C"), ("Y", "C"), ("Z", "C")}
    import os
    assert os.path.exists(tmp_path / "cache_equipes_saison.json") and not os.path.exists(tmp_path / "cache_equipes.json")


def test_une_equipe_en_erreur_reste_absente_sans_bloquer_les_autres_ni_repli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(precalcul, "STATS_EQUIPES_VUES", {})
    def f(url, nom, comp, max_matchs=12):
        if nom == "Y":
            raise RuntimeError("réseau")
        return {"raison_non_traite": "aucun_match_saison_en_cours"} if nom == "Z" else {"nb_domicile": 1, "gf_domicile": 1.0, "ga_domicile": 1.0, "matchs_domicile_bruts": [], "matchs_exterieur_bruts": [], "nb_exterieur": 0}
    det = {"http://m/a": {"url_equipe_domicile": "u1", "url_equipe_exterieur": "u2"}, "http://m/b": {"url_equipe_domicile": "u1", "url_equipe_exterieur": "u3"}}
    r = precalcul.charge_stats_saison([sig("a", "X", "Y"), sig("b", "X", "Z")], det, f)
    assert r == {"équipe chargée": 1, "équipe en erreur": 1, "équipe sans match cette saison": 1}
    assert ("Y", "C") not in precalcul.STATS_EQUIPES_VUES and ("X", "C") in precalcul.STATS_EQUIPES_VUES


@pytest.mark.parametrize("d", [{}, {"url_equipe_domicile": "u1"}, {"url_equipe_exterieur": "u2"}, None])
def test_match_sans_url_d_equipe_est_compte_et_ignore(tmp_path, monkeypatch, d):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(precalcul, "STATS_EQUIPES_VUES", {})
    r = precalcul.charge_stats_saison([sig("a", "X", "Y")], {"http://m/a": d} if d is not None else {}, lambda *a, **k: {"x": 1})
    assert r == {"match sans URL d'équipe": 1} and precalcul.STATS_EQUIPES_VUES == {}


def test_le_collecteur_a_repli_n_alimente_plus_le_moteur():
    import inspect
    src = inspect.getsource(precalcul._recupere_gf_ga_avec_cache)
    assert "STATS_EQUIPES_VUES" not in src
    assert "charge_stats_saison(signaux)" in inspect.getsource(precalcul.applique_moteur_pipeline)
