"""Archive des indices (archive_indices.py) : chaque règle testée sur au moins 3 cas qui passent et 3 qui échouent."""
import datetime
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import archive_donnees_test as adt  # noqa: E402
import archive_indices as ai  # noqa: E402

UTC = datetime.timezone.utc
KO = datetime.datetime(2026, 10, 10, 15, 0, tzinfo=UTC)          # coup d'envoi
AVANT = KO - datetime.timedelta(hours=2)
APRES = KO + datetime.timedelta(hours=1)


def _eq(domicile, *scores):
    return [{"date": f"2026-09-{i + 1:02d}", "domicile": domicile, "buts_marques": a, "buts_encaisses": b,
             "adversaire": "X", "url_match": f"/m/{i}"} for i, (a, b) in enumerate(scores)]


def match(mid="m1", dom=None, ext=None, score=None):
    return {"match_id": mid, "date": "2026-10-10", "heure_cameroun": "17:00", "coup_d_envoi_utc": "2026-10-10T15:00:00Z",
            "domicile": "Alpha", "exterieur": "Beta", "competition": "Test",
            "equipe_dom": {"matchs": dom if dom is not None else _eq(True, (3, 0), (2, 1), (3, 1), (2, 0))},
            "equipe_ext": {"matchs": ext if ext is not None else _eq(False, (0, 2), (1, 2), (0, 3), (1, 2))},
            "score": score}


def ligne(m, marche_v3="1x2_1", source="v3", role="selection", marche=None):
    return ai.construit_ligne(source, role, "S1", {"cote": 1.5, "probabilite": 0.7}, m, marche_v3, marche or marche_v3)


def doc_vide():
    return {"lignes": {}}


# --- 1. indice calculé uniquement avec les matchs figés de l'archive ---------------------------------------------------

def test_indice_4_sur_4_quand_les_quatre_scenarios_valident():
    l = ligne(match(), "1x2_1")
    assert (l["indice"], l["sur"], l["niveau"]) == (4, 4, "SUR")
    assert l["n_domicile"] == 4 and l["n_exterieur"] == 4 and len(l["scenarios"]) == 4 and l["version_indice"] == 4


def test_indice_bas_quand_le_marche_est_contraire_aux_matchs():
    l = ligne(match(), "1x2_2")
    assert l["indice"] == 0 and l["niveau"] == "TRES_RISQUE"


def test_indice_calcule_aussi_pour_un_marche_a_deux_equipes_mixte():
    l = ligne(match(), "over_2_5")
    assert l["indice"] in (0, 1, 2, 3, 4) and l["scenarios"]


@pytest.mark.parametrize("marche_v3,dom,ext,raison", [
    ("score_1_0", None, None, "marche_sans_indice"),                 # marché sans marge continue
    (None, None, None, "marche_sans_indice"),                        # marché inconnu
    ("1x2_1", [], None, "historique_domicile_ou_exterieur_absent"),  # pas de matchs à domicile
    ("1x2_1", None, [], "historique_domicile_ou_exterieur_absent"),  # pas de matchs à l'extérieur
])
def test_pas_d_indice_jamais_devine(marche_v3, dom, ext, raison):
    l = ligne(match(dom=dom, ext=ext), marche_v3)
    assert l["indice"] is None and l["indice_raison"] == raison and l["scenarios"] is None


# --- 2. gel au coup d'envoi ---------------------------------------------------------------------------------------------

def _fusion(doc, lignes, maintenant, traites=None, m=None):
    m = m or match()
    return ai.fusionne(doc, lignes, traites if traites is not None else {("v3", "m1")}, "2026-10-10", {"m1": m}, maintenant)


def test_avant_le_coup_d_envoi_le_dernier_etat_remplace_le_precedent():
    doc = doc_vide()
    l1 = ligne(match()); _fusion(doc, [l1], AVANT - datetime.timedelta(hours=1))
    l2 = ligne(match()); l2["cote"] = 1.9; _fusion(doc, [l2], AVANT)
    assert doc["lignes"][l1["id"]]["cote"] == 1.9
    assert doc["lignes"][l1["id"]]["premiere_vue_le"] < doc["lignes"][l1["id"]]["derniere_vue_le"]


def test_apres_le_coup_d_envoi_la_ligne_existante_ne_change_plus():
    doc = doc_vide()
    l1 = ligne(match()); _fusion(doc, [l1], AVANT)
    l2 = ligne(match()); l2["cote"] = 9.99; l2["indice"] = 0
    b = _fusion(doc, [l2], APRES)
    assert b["gelees"] == 1 and doc["lignes"][l1["id"]]["cote"] == 1.5 and doc["lignes"][l1["id"]]["indice"] == 4


def test_une_ligne_avec_score_n_est_jamais_modifiee_meme_avant_le_coup_d_envoi():
    doc = doc_vide()
    l1 = ligne(match()); _fusion(doc, [l1], AVANT)
    doc["lignes"][l1["id"]]["score"] = {"buts_dom": 1, "buts_ext": 0}
    l2 = ligne(match()); l2["cote"] = 7.0
    _fusion(doc, [l2], AVANT)
    assert doc["lignes"][l1["id"]]["cote"] == 1.5


# --- 3. origine natif / recalculé ---------------------------------------------------------------------------------------

def test_origine_native_si_ecrite_avant_le_coup_d_envoi():
    doc = doc_vide(); l = ligne(match()); _fusion(doc, [l], AVANT)
    assert doc["lignes"][l["id"]]["origine"] == "natif"


def test_origine_recalculee_si_ecrite_apres_le_coup_d_envoi():
    doc = doc_vide(); l = ligne(match()); _fusion(doc, [l], APRES)
    assert doc["lignes"][l["id"]]["origine"] == "recalcule"


def test_origine_sans_heure_connue_native_le_jour_du_match_seulement():
    m = match(); m["coup_d_envoi_utc"] = None; m["heure_cameroun"] = None
    d1, d2 = doc_vide(), doc_vide()
    ai.fusionne(d1, [ligne(m)], {("v3", "m1")}, "2026-10-10", {"m1": m}, datetime.datetime(2026, 10, 10, 8, tzinfo=UTC))
    ai.fusionne(d2, [ligne(m)], {("v3", "m1")}, "2026-10-10", {"m1": m}, datetime.datetime(2026, 10, 11, 8, tzinfo=UTC))
    assert list(d1["lignes"].values())[0]["origine"] == "natif" and list(d2["lignes"].values())[0]["origine"] == "recalcule"


# --- 4. pari retiré avant le coup d'envoi : conservé mais inactif --------------------------------------------------------

def test_pari_retire_avant_le_coup_d_envoi_devient_inactif_sans_etre_supprime():
    doc = doc_vide(); a, b = ligne(match(), "1x2_1"), ligne(match(), "dc_1X")
    _fusion(doc, [a, b], AVANT - datetime.timedelta(hours=1))
    _fusion(doc, [a], AVANT)
    assert doc["lignes"][b["id"]]["actif"] is False and doc["lignes"][a["id"]]["actif"] is True


def test_pari_retire_apres_le_coup_d_envoi_reste_actif():
    doc = doc_vide(); a, b = ligne(match(), "1x2_1"), ligne(match(), "dc_1X")
    _fusion(doc, [a, b], AVANT)
    _fusion(doc, [a], APRES)
    assert doc["lignes"][b["id"]]["actif"] is True


def test_match_non_examine_ne_desactive_rien():
    doc = doc_vide(); a = ligne(match(), "1x2_1")
    _fusion(doc, [a], AVANT - datetime.timedelta(hours=1))
    _fusion(doc, [], AVANT, traites=set())
    assert doc["lignes"][a["id"]]["actif"] is True


# --- 5. résultat écrit une seule fois ------------------------------------------------------------------------------------

def _prepare(tmp_path, score, resultat_existant=None):
    arch, ind = str(tmp_path / "archive"), str(tmp_path / "indices")
    m = match(score=score)
    adt.sauve_fichier(adt._chemin(arch, "2026-10-10"), {"m1": m})
    doc = {"lignes": {}}
    l = ligne(match()); l["fige_le"] = "x"
    if resultat_existant:
        l["score"] = {"buts_dom": 0, "buts_ext": 0}; l["resultat"] = resultat_existant
    doc["lignes"][l["id"]] = l
    adt.sauve_fichier(ai.chemin(ind, "2026-10-10"), doc)
    return arch, ind, l["id"]


def _regle(l, h, a):
    return "WIN" if h > a else "LOSS"


@pytest.mark.parametrize("sc,att", [({"buts_dom": 2, "buts_ext": 0}, "WIN"), ({"buts_dom": 0, "buts_ext": 1}, "LOSS"),
                                    ({"buts_dom": 3, "buts_ext": 1}, "WIN")])
def test_resultat_ecrit_quand_le_score_existe(tmp_path, sc, att):
    arch, ind, cle = _prepare(tmp_path, sc)
    ai.complete_resultats(ind, arch, APRES, regle=_regle)
    l = adt.charge_fichier(ai.chemin(ind, "2026-10-10"))["lignes"][cle]
    assert l["resultat"] == att and l["score"] == sc and l["regle_le"]


def test_pas_de_resultat_sans_score(tmp_path):
    arch, ind, cle = _prepare(tmp_path, None)
    ai.complete_resultats(ind, arch, APRES, regle=_regle)
    l = adt.charge_fichier(ai.chemin(ind, "2026-10-10"))["lignes"][cle]
    assert l["resultat"] is None and l["score"] is None


def test_resultat_existant_jamais_modifie(tmp_path):
    arch, ind, cle = _prepare(tmp_path, {"buts_dom": 5, "buts_ext": 0}, resultat_existant="LOSS")
    ai.complete_resultats(ind, arch, APRES, regle=_regle)
    l = adt.charge_fichier(ai.chemin(ind, "2026-10-10"))["lignes"][cle]
    assert l["resultat"] == "LOSS" and l["score"] == {"buts_dom": 0, "buts_ext": 0}


# --- 6. bilan : seules les lignes actives, réglées et de rôle « selection » comptent -------------------------------------

def _ecrit(tmp_path, lignes):
    ind = str(tmp_path / "indices")
    adt.sauve_fichier(ai.chemin(ind, "2026-10-10"), {"lignes": {l["id"]: l for l in lignes}})
    return ind


def _l(i, **kw):
    base = {"id": f"id{i}", "source": "v3", "role": "selection", "actif": True, "resultat": "WIN", "indice": 4, "sur": 4, "cote": 1.5}
    base.update(kw)
    return base


def test_bilan_compte_les_paris_actifs_et_regles(tmp_path):
    ind = _ecrit(tmp_path, [_l(1), _l(2, resultat="LOSS")])
    assert "1/2" in ai.bilan(ind) and "50.0%" in ai.bilan(ind)


@pytest.mark.parametrize("kw", [{"actif": False}, {"resultat": None}, {"role": "alternative"}])
def test_bilan_ignore_inactifs_non_regles_et_alternatives(tmp_path, kw):
    ind = _ecrit(tmp_path, [_l(1, **kw)])
    assert "4/4" not in ai.bilan(ind)


# --- 7. Journal : marché traduit selon le côté de l'équipe suivie ---------------------------------------------------------

def test_journal_traduit_le_marche_selon_le_cote_de_l_equipe():
    m = match()
    pari = {"date": "2026-10-10", "domicile": "Alpha", "exterieur": "Beta", "journal_team": "Alpha", "marche": "Victoire",
            "marche_canonique": "1x2_domicile", "cote": 1.4, "probabilite_estimee": 0.6}
    ext = dict(pari, journal_team="Beta", marche_canonique="1x2_exterieur")
    l1 = ai.lignes_journal([pari], "2026-10-10", {"m1": m})[0]
    l2 = ai.lignes_journal([ext], "2026-10-10", {"m1": m})[0]
    assert (l1["marche_v3"], l2["marche_v3"]) == ("1x2_1", "1x2_2") and l1["indice"] == 4 and l2["indice"] == 0
    assert l1["id"] != l2["id"]


@pytest.mark.parametrize("pari", [{"journal_team": None}, {"date": "2026-10-09"}, {"domicile": "Inconnu"}])
def test_journal_ignore_un_pari_non_rapproche(pari):
    base = {"date": "2026-10-10", "domicile": "Alpha", "exterieur": "Beta", "journal_team": "Alpha", "marche": "Victoire",
            "marche_canonique": "1x2_domicile", "cote": 1.4}
    assert ai.lignes_journal([dict(base, **pari)], "2026-10-10", {"m1": match()}) == []
