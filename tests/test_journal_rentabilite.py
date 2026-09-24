"""Journal de rentabilité (24/09/2026) : règlement des libellés, conventions de handicap, contrôle de cohérence,
statuts des segments, verdict d'un marché. Chaque fonction de comparaison est testée sur des cas qui doivent
passer ET des cas qui doivent échouer."""
import json

import pytest

import journal_rentabilite as jr


def regle(libelle, h, a):
    an = jr.analyse_libelle(libelle)
    assert an is not None, libelle
    return an[1](h, a)


# --- Règlement : doivent GAGNER -------------------------------------------------------------------------------
@pytest.mark.parametrize("libelle,h,a", [
    ("1X2 - 1", 2, 1), ("1X2 - X", 1, 1), ("1X2 - 2", 0, 3),
    ("Double chance - 1X", 1, 1), ("Double chance - X2", 0, 0), ("Double chance - 12", 3, 2),
    ("BTTS - oui", 1, 1), ("BTTS - non", 2, 0),
    ("Plus de 2.5 buts", 2, 1), ("Moins de 2.5 buts", 1, 1),
    ("Plus de 0.5 buts - Domicile", 1, 0), ("Moins de 1.5 buts - Extérieur", 3, 1),
    ("Cage inviolée - Domicile", 2, 0), ("Encaisse au moins 1 but - Extérieur", 1, 0),
    ("Handicap -1.5 - Domicile", 3, 1),        # domicile -1.5, gagne de 2
    ("Handicap -0.5 - Extérieur", 1, 1),       # ligne vue du domicile : extérieur +0.5, nul = gagné
    ("Handicap 0.5 - Extérieur", 0, 1),        # extérieur -0.5 : victoire extérieure = gagné
    ("Handicap 1.5 - Extérieur", 0, 2),        # extérieur -1.5 : gagne de 2
    ("Total buts - pair", 1, 1),
])
def test_libelles_gagnants(libelle, h, a):
    assert regle(libelle, h, a) == 1


# --- Règlement : doivent PERDRE -------------------------------------------------------------------------------
@pytest.mark.parametrize("libelle,h,a", [
    ("1X2 - 1", 1, 1), ("1X2 - 2", 2, 1), ("BTTS - oui", 2, 0),
    ("Plus de 2.5 buts", 1, 1), ("Cage inviolée - Extérieur", 1, 1),
    ("Handicap -1.5 - Domicile", 2, 1),        # domicile ne gagne que de 1
    ("Handicap -0.5 - Extérieur", 1, 0),       # extérieur +0.5 perd si le domicile gagne
    ("Handicap 0.5 - Extérieur", 1, 1),        # extérieur -0.5 perd sur un nul
    ("Handicap 1.5 - Extérieur", 0, 1),        # extérieur -1.5 ne gagne que de 1
    ("Total buts - impair", 2, 2),
])
def test_libelles_perdants(libelle, h, a):
    assert regle(libelle, h, a) == -1


@pytest.mark.parametrize("libelle", ["Corners - plus de 9.5", "Plus de 2 buts", "Handicap - Domicile", None, "1X2 - 3"])
def test_libelles_refuses(libelle):
    assert jr.analyse_libelle(libelle) is None


# --- Traduction des noms de marchés des moteurs -----------------------------------------------------------------
@pytest.mark.parametrize("moteur,libelle", [
    ("1x2_domicile", "1X2 - 1"), ("double_chance_X2", "Double chance - X2"),
    ("over_under_total_3.5_under", "Moins de 3.5 buts"), ("buts_equipe_exterieur_0.5_over", "Plus de 0.5 buts - Extérieur"),
    ("handicap_domicile_-0.5", "Handicap -0.5 - Domicile"), ("handicap_exterieur_-0.5", "Handicap 0.5 - Extérieur"),
    ("handicap_exterieur_1.5", "Handicap -1.5 - Extérieur"),
])
def test_traduction_moteur(moteur, libelle):
    assert jr.libelle_depuis_moteur(moteur) == libelle


def test_traduction_moteur_et_reglement_concordent():
    # handicap_exterieur_-0.5 (extérieur -0.5) doit se régler comme une victoire extérieure
    lib = jr.libelle_depuis_moteur("handicap_exterieur_-0.5")
    assert regle(lib, 0, 1) == 1 and regle(lib, 1, 1) == -1


@pytest.mark.parametrize("moteur", ["corners_over_9.5", "", None, "1x2_milieu"])
def test_traduction_moteur_refusee(moteur):
    assert jr.libelle_depuis_moteur(moteur) is None


# --- Contrôle de cohérence des handicaps -------------------------------------------------------------------------
BASE = {"1X2 - 1": 1.80, "1X2 - 2": 4.20, "Double chance - 1X": 1.25, "Double chance - X2": 2.10}


@pytest.mark.parametrize("libelle,cote", [
    ("Handicap -0.5 - Domicile", 1.78),     # = victoire domicile
    ("Handicap 0.5 - Extérieur", 4.10),     # extérieur -0.5 = victoire extérieure
    ("Handicap -0.5 - Extérieur", 2.05),    # extérieur +0.5 = double chance X2
    ("Handicap -1.5 - Domicile", 3.10),     # plus difficile que gagner : cote plus haute
])
def test_coherence_garde_les_cotes_plausibles(libelle, cote):
    propres, rejets = jr.controle_coherence(dict(BASE, **{libelle: cote}))
    assert libelle in propres and not rejets


@pytest.mark.parametrize("libelle,cote", [
    ("Handicap -0.5 - Domicile", 4.10),     # côtés inversés
    ("Handicap 0.5 - Extérieur", 1.80),     # côtés inversés
    ("Handicap -0.5 - Extérieur", 4.20),    # +0.5 plus cher que la victoire sèche : impossible
    ("Handicap -1.5 - Domicile", 1.20),     # -1.5 moins cher que la victoire : impossible
])
def test_coherence_retire_les_cotes_impossibles(libelle, cote):
    propres, rejets = jr.controle_coherence(dict(BASE, **{libelle: cote}))
    assert libelle not in propres and rejets == [libelle]


# --- Statuts -------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("args,attendu", [
    ((60, 0.08, 0.01, 0.15, 0.05, 0.10), "A_JOUER"),
    ((30, 0.05, -0.10, 0.20, 0.02, 0.07), "A_SURVEILLER"),
    ((30, -0.12, -0.20, -0.03, -0.10, -0.14), "A_EVITER"),
])
def test_statuts_attribues(args, attendu):
    assert jr.statut_segment(*args) == attendu


@pytest.mark.parametrize("args,attendu", [
    ((30, 0.08, 0.01, 0.15, 0.05, 0.10), "A_SURVEILLER"),   # IC positif mais moins de 40 matchs -> pas A_JOUER
    ((60, 0.08, 0.01, 0.15, -0.02, 0.18), "NEUTRE"),        # une moitié négative -> ni A_JOUER ni A_SURVEILLER
    ((20, -0.30, -0.50, -0.10, -0.3, -0.3), "NEUTRE"),      # trop peu de matchs pour A_EVITER
])
def test_statuts_refuses(args, attendu):
    assert jr.statut_segment(*args) == attendu


# --- Verdict d'un marché : le niveau le plus précis non neutre décide ----------------------------------------------
def _seg(statut, roi=0.1):
    return {"statut": statut, "roi": roi, "matchs": 50}


def test_verdict_precis_l_emporte_sur_le_general():
    index = {"ligue_marche": {"L1 | BTTS - oui": _seg("A_JOUER")}, "marches": {"BTTS - oui": _seg("A_EVITER", -0.1)}}
    assert jr.verdict_marche(index, "L1", "BTTS - oui", 1.8)[0] == "A_JOUER"


def test_verdict_general_si_precis_neutre():
    index = {"ligue_marche": {"L1 | BTTS - oui": _seg("NEUTRE")}, "marches": {"BTTS - oui": _seg("A_EVITER", -0.1)}}
    assert jr.verdict_marche(index, "L1", "BTTS - oui", 1.8)[0] == "A_EVITER"


def test_verdict_libelle_inconnu():
    assert jr.verdict_marche({}, "L1", "Corners - plus de 9.5", 1.8)[0] == "INCONNU"


# --- Bout en bout sur données minimales (fichiers temporaires) ----------------------------------------------------
def test_chargement_filtre_les_cotes_non_betpawa(tmp_path):
    ech = tmp_path / "ech.json"
    ech.write_text(json.dumps({"matchs": [{"match_id": "a", "date": "2026-09-10", "competition": "L1", "score": "2-1",
                                           "cotes": {"1X2 - 1": 1.9}}]}), encoding="utf-8")
    hist = tmp_path / "hist.json"
    hist.write_text(json.dumps([{"date": "2026-09-11", "matchs": [
        {"match_id": "b", "date": "2026-09-11", "competition": "L1", "score": "0-0", "source_cotes": "manuel",
         "TOUS_MARCHES_EVALUES": [{"marche": "1X2 - X", "cote_observee": 3.1}]},
        {"match_id": "c", "date": "2026-09-11", "competition": "L1", "score": "1-0", "source_cotes": "matchendirect_bet365",
         "TOUS_MARCHES_EVALUES": [{"marche": "1X2 - 1", "cote_observee": 1.5}]},
        {"match_id": "a", "date": "2026-09-10", "competition": "L1", "score": "2-1", "source_cotes": "manuel",
         "TOUS_MARCHES_EVALUES": [{"marche": "1X2 - 1", "cote_observee": 2.5}]}]}]), encoding="utf-8")
    matchs, diag = jr.charge_matchs_betpawa(str(ech), str(hist))
    ids = {m["match_id"]: m for m in matchs}
    assert set(ids) == {"a", "b"}                      # c (bet365) exclu
    assert ids["a"]["cotes"]["1X2 - 1"] == 1.9         # l'échantillon figé est prioritaire
    paris, inconnus, incoherentes = jr.paris_depuis_matchs(matchs)
    assert sorted(round(p["profit"], 2) for p in paris) == [0.9, 2.1]


def test_reussite_necessaire_et_comptes():
    paris = [{"match_id": "a", "date": "2026-09-10", "cote": 2.0, "profit": 1.0, "resultat": 1},
             {"match_id": "b", "date": "2026-09-11", "cote": 1.5, "profit": -1.0, "resultat": -1}]
    s = jr.stats_segment(paris)
    assert s["gagnes"] == 1 and s["rembourses"] == 0
    assert s["reussite_necessaire"] == round(2 / 3.5, 4)      # 1 / cote moyenne (1,75)
    assert s["reussite"] == 0.5


# --- Équipes à suivre ------------------------------------------------------------------------------------------------
def _m(mid, dom, ext, h, a, cotes=None, ligue="L1", date="2026-09-10"):
    return {"match_id": mid, "date": date, "ligue": ligue, "domicile": dom, "exterieur": ext, "buts": (h, a), "cotes": cotes or {}}


def _fond(n=40):
    # matchs neutres entre autres équipes : fréquences générales basses pour les marchés testés
    return [_m(f"f{i}", f"X{i}", f"Y{i}", 1, 0) for i in range(n)]


def _marches(lignes, equipe):
    return {l["marche"] for l in lignes if l["equipe"] == equipe}


def test_equipe_a_suivre_detectee():
    # A marque 2+ dans 5 matchs sur 5, domicile ou extérieur : doit sortir sur « Marque 2 buts ou plus »
    matchs = _fond() + [_m("a1", "A", "B", 2, 0), _m("a2", "C", "A", 1, 3), _m("a3", "A", "D", 2, 2),
                        _m("a4", "E", "A", 0, 2), _m("a5", "A", "F", 4, 1)]
    lignes = jr.construit_equipes_a_suivre(matchs, "2026-09-24", prochains={})
    assert "Marque 2 buts ou plus" in _marches(lignes, "A")
    l = next(x for x in lignes if x["equipe"] == "A" and x["marche"] == "Marque 2 buts ou plus")
    assert (l["gagnes"], l["joues"], l["frequence"]) == (5, 5, 1.0)


def test_equipe_a_suivre_4_sur_5_suffit_et_cote_du_bon_cote():
    # A gagne 4 fois sur 5 ; la cote retenue doit être celle de SON côté (1X2 - 2 quand A joue à l'extérieur)
    matchs = _fond() + [_m("b1", "A", "B", 1, 0, {"1X2 - 1": 2.0}), _m("b2", "C", "A", 0, 1, {"1X2 - 2": 3.0}),
                        _m("b3", "A", "D", 2, 0, {"1X2 - 1": 1.5}), _m("b4", "E", "A", 1, 0, {"1X2 - 2": 2.5}),
                        _m("b5", "A", "F", 3, 1, {"1X2 - 1": 1.8})]
    l = next(x for x in jr.construit_equipes_a_suivre(matchs, "2026-09-24", prochains={}) if x["equipe"] == "A" and x["marche"] == "Victoire")
    assert l["frequence"] == 0.8 and l["paris_cotes"] == 5
    assert l["roi_betpawa"] == round((1.0 + 2.0 + 0.5 - 1.0 + 0.8) / 5, 4)


def test_prochain_match_rattache_avec_la_cote_de_l_equipe():
    matchs = _fond() + [_m(f"c{i}", "A", f"Z{i}", 3, 0) for i in range(5)]
    prochains = {("A", "L1"): {"date": "2026-09-26", "heure": "15:00", "adversaire": "Q", "cote_equipe": "ext",
                               "cotes": {"1X2 - 2": 2.4, "1X2 - 1": 3.1}, "betpawa_url": "u"}}
    l = next(x for x in jr.construit_equipes_a_suivre(matchs, "2026-09-24", prochains) if x["equipe"] == "A" and x["marche"] == "Victoire")
    assert l["prochain_match"]["cote_betpawa"] == 2.4 and l["prochain_match"]["lieu"] == "extérieur"


def test_equipe_sous_70_pourcent_exclue():
    # 3 victoires sur 5 = 60 %
    matchs = _fond() + [_m("d1", "A", "B", 1, 0), _m("d2", "A", "C", 1, 0), _m("d3", "A", "D", 1, 0),
                        _m("d4", "A", "E", 0, 1), _m("d5", "A", "F", 0, 0)]
    assert "Victoire" not in _marches(jr.construit_equipes_a_suivre(matchs, "2026-09-24", prochains={}), "A")


def test_equipe_avec_trop_peu_de_matchs_exclue():
    matchs = _fond() + [_m(f"e{i}", "A", f"Z{i}", 3, 0) for i in range(4)]     # 4 matchs < 5
    assert not _marches(jr.construit_equipes_a_suivre(matchs, "2026-09-24", prochains={}), "A")


def test_marche_banal_exclu_meme_a_100_pourcent():
    # « Au moins une équipe ne marque pas » passe dans presque tous les matchs du fond (1-0) : fréquence générale >= 70 %
    matchs = _fond() + [_m(f"g{i}", "A", f"Z{i}", 1, 0) for i in range(5)]
    assert "Au moins une équipe ne marque pas" not in _marches(jr.construit_equipes_a_suivre(matchs, "2026-09-24", prochains={}), "A")
