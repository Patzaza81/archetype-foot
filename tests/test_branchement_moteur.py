"""Branchement de moteur_v2_6_9.py (branchement_moteur.py + precalcul.applique_moteur_pipeline).

Ce que ces tests verrouillent :
  - la nomenclature (chaque marché du moteur a UN nom canonique, compris par le règlement) ;
  - la COHÉRENCE moteur <-> règlement : la probabilité que le moteur calcule pour un marché est exactement la somme
    des scores que le règlement compte gagnants (détecte toute erreur de côté, de ligne ou de convention) ;
  - la sélection P1/P2/P3 et son CONTRAT avec le site (archetype.js, remappeEnOngletsApp) ;
  - NO DATA -> NO GO, catégorie D écartée, statuts d'erreur sans repli, archive, sortie allégée, reproductibilité.
"""
import datetime
import json
import os
import random
import shutil
import subprocess

import pytest

import branchement_moteur as bm
import moteur_v2_6_9 as moteur
import pont_moteur
from archetype_model.learning import archive
from archetype_model.learning.reglement import evaluer_marche

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.datetime(2026, 9, 21, 21, 0, tzinfo=datetime.timezone.utc)
COMP = "Pays : Ligue"


# ─────────────────────────────── fixtures ───────────────────────────────
def _matchs(scores, domicile):
    return [{"domicile": domicile, "buts_marques": a, "buts_encaisses": b} for a, b in scores]


DOM = [(2, 0), (3, 1), (2, 1), (1, 0), (2, 0), (4, 0), (1, 1), (2, 0), (3, 0), (2, 1)]
EXT = [(0, 2), (1, 3), (0, 1), (1, 2), (0, 0), (0, 2), (1, 1), (0, 3), (1, 2), (0, 1)]
H2H = [{"buts_a": 2, "buts_b": 0}, {"buts_a": 1, "buts_b": 1}, {"buts_a": 3, "buts_b": 1}, {"buts_a": 2, "buts_b": 1}, {"buts_a": 0, "buts_b": 1}]


def stats():
    return {
        ("Alpha FC", COMP): {"nb_domicile": 10, "gf_domicile": 2.1, "ga_domicile": 0.6, "nb_exterieur": 10, "gf_exterieur": 1.4,
                             "ga_exterieur": 1.0, "matchs_domicile_bruts": _matchs(DOM, True), "matchs_exterieur_bruts": []},
        ("Beta FC", COMP): {"nb_domicile": 10, "gf_domicile": 1.0, "ga_domicile": 1.5, "nb_exterieur": 10, "gf_exterieur": 0.6,
                            "ga_exterieur": 1.9, "matchs_domicile_bruts": [], "matchs_exterieur_bruts": _matchs(EXT, False)},
    }


def signal(un=1.55, dc=1.30, mid="t1", **extra):
    cotes = {"1x2": {"1": un, "N": 3.7, "2": 4.6}, "double_chance": {"1N": dc, "N2": 2.3, "12": 1.28},
             "btts": {"Oui": 1.95, "Non": 1.8}, "over_under_1.5": {"plus": 1.32, "moins": 3.3},
             "over_under_2.5": {"plus": 2.0, "moins": 1.8}, "over_under_3.5": {"plus": 3.2, "moins": 1.3}}
    s = {"match_id": mid, "domicile": "Alpha FC", "exterieur": "Beta FC", "competition": COMP, "date": "2026-09-22",
         "heure": "20:45", "cotes_manuelles": cotes, "url_match": "https://x/m"}
    s.update(extra)
    return s


def analyse(sig=None, st=None, h2h=lambda s: H2H):
    return bm.analyse_signal(sig or signal(), stats() if st is None else st, NOW, h2h)


# ═══════════════════════════ 1. NOMENCLATURE ═══════════════════════════
def _toutes_les_cles_du_moteur():
    cles = set(moteur.MARCHES_STANDARD)
    for H in moteur.LIGNES_HANDICAP:
        cles.add(pont_moteur._cle_handicap("dom", H))
        cles.add(pont_moteur._cle_handicap("ext", -H))
    return sorted(cles)


def test_chaque_cle_du_moteur_a_un_nom_canonique_unique_reconnu_par_le_reglement():
    noms = {}
    for cle in _toutes_les_cles_du_moteur():
        canon = bm.nom_canonique(cle)
        assert canon is not None, cle
        assert evaluer_marche(canon, 1, 0).statut in ("WIN", "LOSS"), (cle, canon)
        assert bm.famille_et_groupe(canon)[0] != "AUTRE", canon
        assert canon not in noms, f"{cle} et {noms[canon]} donnent le même nom {canon}"
        noms[canon] = cle


@pytest.mark.parametrize("cle,attendu", [
    ("victoire", "1x2_domicile"), ("nul", "1x2_nul"), ("defaite", "1x2_exterieur"),
    ("dc_1X", "double_chance_1X"), ("clean_sheet_dom", "cage_inviolee_domicile"), ("clean_sheet_ext", "cage_inviolee_exterieur"),
    ("over_2_5", "over_under_total_2.5_over"), ("under_0_5", "over_under_total_0.5_under"),
    ("buts_dom_over_1_5", "buts_equipe_domicile_1.5_over"), ("buts_ext_under_0_5", "buts_equipe_exterieur_0.5_under"),
    ("handicap_dom_-1_5", "handicap_domicile_-1.5"), ("handicap_ext_+1_5", "handicap_exterieur_1.5"),
    ("handicap_dom_0_0", "handicap_domicile_0.0"), ("handicap_ext_+2_0", "handicap_exterieur_2.0"),
    ("handicap_dom_+0_5", "handicap_domicile_0.5"), ("handicap_ext_-0_5", "handicap_exterieur_-0.5"),
])
def test_nom_canonique(cle, attendu):
    assert bm.nom_canonique(cle) == attendu


@pytest.mark.parametrize("cle", ["", None, 5, "foo", "handicap_dom_x", "over_x_5", "handicap_milieu_-1_5", "buts_dom_5"])
def test_nom_canonique_refuse_ce_qui_n_existe_pas(cle):
    assert bm.nom_canonique(cle) is None


# ═══════════ 2. COHÉRENCE MOTEUR <-> RÈGLEMENT (le test le plus important) ═══════════
def _p_reglement(mat, canon):
    n = len(mat)
    return sum(mat[i][j] for i in range(n) for j in range(n) if evaluer_marche(canon, i, j).statut == "WIN")


@pytest.mark.parametrize("lam", [(1.6, 1.1), (0.9, 2.3), (2.8, 0.6)])
def test_la_probabilite_du_moteur_est_celle_que_compte_le_reglement(lam):
    mat = moteur.construire_matrice(*lam)
    for cle, p in moteur.probas_standard(mat).items():
        assert abs(p - _p_reglement(mat, bm.nom_canonique(cle))) < 1e-9, cle
    for H in moteur.LIGNES_HANDICAP:
        wd, push, we = moteur.handicap_probas(mat, H)
        cle_dom, cle_ext = pont_moteur._cle_handicap("dom", H), pont_moteur._cle_handicap("ext", -H)
        assert abs(wd - _p_reglement(mat, bm.nom_canonique(cle_dom))) < 1e-9, cle_dom
        assert abs(we - _p_reglement(mat, bm.nom_canonique(cle_ext))) < 1e-9, cle_ext


def test_un_nom_faux_est_bien_detecte_par_ce_controle():
    # contrôle du contrôle : avec l'ancien règlement (victoire réglée comme double chance), l'écart serait visible
    mat = moteur.construire_matrice(1.6, 1.1)
    p_victoire = moteur.probas_standard(mat)["victoire"]
    p_double_chance = _p_reglement(mat, "double_chance_1X")
    assert abs(p_victoire - p_double_chance) > 0.1


# ═══════════════════════════ 3. SÉLECTION ═══════════════════════════
def c(marche, p, cote, edv):
    return {"marche": marche, "probabilite": p, "cote": cote, "edv": edv}


def roles(sel):
    return tuple(sel[r]["marche"] if sel[r] else None for r in bm.RANGS)


def test_selection_vide():
    assert roles(bm.selectionne([])) == (None, None, None)


def test_un_seul_candidat_est_le_favori():
    assert roles(bm.selectionne([c("a", 0.5, 1.9, 0.05)])) == ("a", None, None)


def test_le_favori_est_la_probabilite_la_plus_haute_la_value_le_meilleur_ev_des_restants():
    sel = bm.selectionne([c("a", 0.55, 1.9, 0.12), c("b", 0.80, 1.3, 0.05), c("d", 0.60, 1.8, 0.25)])
    assert roles(sel) == ("b", "d", None)


def test_coup_de_poker_cote_et_probabilite_aux_seuils_exacts():
    base = [c("fav", 0.8, 1.3, 0.05), c("val", 0.5, 1.9, 0.30)]
    assert roles(bm.selectionne(base + [c("p", 0.20, 2.91, 0.1)]))[2] == "p"          # frontière incluse
    assert roles(bm.selectionne(base + [c("p", 0.25, 3.50, 0.1)]))[2] == "p"
    assert roles(bm.selectionne(base + [c("p", 0.40, 2.95, 0.1)]))[2] == "p"


@pytest.mark.parametrize("poker", [c("p", 0.20, 2.90, 0.1), c("p", 0.19, 3.50, 0.1), c("p", 0.10, 5.0, 0.1)])
def test_pas_de_coup_de_poker_sous_les_seuils(poker):
    assert roles(bm.selectionne([c("fav", 0.8, 1.3, 0.05), c("val", 0.5, 1.9, 0.30), poker]))[2] is None


def test_un_candidat_n_apparait_qu_une_fois_et_au_plus_trois_choix():
    pool = [c(f"m{i}", 0.3 + i * 0.05, 2.0 + i * 0.4, 0.06 + i * 0.01) for i in range(8)]
    sel = bm.selectionne(pool)
    noms = [x["marche"] for x in sel.values() if x]
    assert len(noms) == len(set(noms)) <= 3
    assert [x["rang"] for x in sel.values() if x] == ["P1", "P2", "P3"][:len(noms)]


def test_selection_deterministe_a_egalite():
    pool = [c("b", 0.5, 2.0, 0.1), c("a", 0.5, 2.0, 0.1)]
    assert roles(bm.selectionne(pool)) == roles(bm.selectionne(list(reversed(pool))))


# ═════════════ 4. CONTRAT AVEC LE SITE (archetype.js / remappeEnOngletsApp) ═════════════
def _remap_js(selections):
    if shutil.which("node") is None:
        pytest.skip("node absent")
    r = subprocess.run(["node", os.path.join(RACINE, "tests", "contrat_remap.js"), os.path.join(RACINE, "archetype.js")],
                       input=json.dumps(selections), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_les_seuils_du_coup_de_poker_sont_les_memes_cote_backend_et_site():
    sorties = _remap_js([{}])
    assert sorties["seuils"] == [bm.SEUIL_COUP_DE_POKER_COTE, bm.SEUIL_COUP_DE_POKER_PROBA]


def test_le_site_retrouve_exactement_les_roles_du_backend():
    rnd = random.Random(20260921)
    cas, attendus = [], []
    for _ in range(300):
        n = rnd.randint(1, 9)
        pool = [c(f"m{i}", rnd.uniform(0.15, 0.9), rnd.choice([rnd.uniform(1.3, 2.9), rnd.uniform(2.91, 6.0)]), rnd.uniform(0.03, 0.3)) for i in range(n)]
        sel = bm.selectionne(pool)
        cas.append({r: v for r, v in sel.items() if v})
        attendus.append(roles(sel))
    sorties = _remap_js(cas)["sorties"]
    ecarts = [(a, (s["P1"], s["P2"], s["P3"])) for a, s in zip(attendus, sorties) if a != (s["P1"], s["P2"], s["P3"])]
    assert not ecarts, ecarts[:3]


# ═══════ 5. ANALYSE D'UN SIGNAL : justification, NO DATA -> NO GO, catégorie D ═══════
def test_choix_retenus_avec_justification_specifique():
    bloc, _ = analyse()
    assert bloc["statut"] == "OK"
    sel = bloc["selection"]
    assert roles(sel) == ("double_chance_1X", "1x2_domicile", None)
    for r in ("P1", "P2"):
        j = sel[r]["justification"]
        assert j["donnees_suffisantes"] is True and j["resume"] and j["preuves"]
        assert sel[r]["niveau"].startswith("CAT_") and sel[r]["robustesse"] is None
        assert sel[r]["market_family"] in ("DOUBLE_CHANCE", "RESULT")


def test_no_data_no_go_un_marche_sans_preuve_specifique_est_rejete():
    bloc, non_sel = analyse()
    assert {"marche": "btts_non", "motif": bm.MOTIF_JUSTIFICATION} in bloc["rejets"]
    assert "btts_non" not in [x["marche"] for x in bloc["selection"].values() if x]
    assert "btts_non" in [x["marche"] for x in non_sel]                     # archivé en contrefactuel, jamais affiché


def test_la_categorie_d_du_moteur_n_est_jamais_selectionnee_mais_archivee():
    bloc, non_sel = analyse(signal(un=1.85, dc=1.22))
    assert "1x2_domicile" not in [x["marche"] for x in bloc["candidats"]]
    d = [x for x in non_sel if x["marche"] == "1x2_domicile"]
    assert d and d[0]["categorie"] == "D"


def test_sans_value_aucun_choix_mais_statut_ok():
    bloc, _ = analyse(signal(un=1.50, dc=1.28))
    assert bloc["statut"] == "OK" and roles(bloc["selection"]) == (None, None, None)


def test_h2h_indisponible_ne_fait_pas_perdre_le_match():
    def casse(s):
        raise RuntimeError("réseau")
    bloc, _ = analyse(h2h=casse)
    assert bloc["statut"] == "OK" and bloc["selection"]["P1"]["marche"] == "double_chance_1X"


# ═══════════════ 6. STATUTS : refus explicites, jamais de repli ═══════════════
def _refus(sig=None, st=None):
    bloc, non_sel = analyse(sig, st)
    assert non_sel == [] and bloc["selection"] == {}
    return bloc


def test_refus_sans_cotes():
    b = _refus(signal(cotes_manuelles=None))
    assert (b["statut"], b["raison"]) == ("NON_EXPORTABLE", "pas_de_cotes_betpawa")


def test_refus_sans_historique():
    b = _refus(st={})
    assert b["statut"] == "NON_EXPORTABLE" and b["raison"].startswith("historique_indisponible")


def test_refus_match_commence_ou_termine():
    for heure in ("TER", "83'", "MT"):
        assert _refus(signal(heure=heure))["raison"] == "match_deja_commence_ou_termine"


def test_refus_sans_date():
    assert _refus(signal(date=None))["raison"] == "date_manquante"


def test_skip_du_moteur_quand_moins_de_trois_marches():
    s = signal()
    s["cotes_manuelles"] = {"btts": {"Oui": 1.9, "Non": 1.9}}                # 2 marchés < seuil de 3 (V9)
    b = _refus(s)
    assert b["statut"] == "SKIP" and "marchés valides" in b["raison"]


def test_un_match_reporte_est_saute_par_le_moteur():
    b = _refus(signal(heure="REP"))
    assert b["statut"] == "SKIP" and "V11" in b["raison"]


def test_exception_sur_un_match_donne_erreur_technique_sans_repli_et_sans_bloquer_les_autres(monkeypatch):
    vrai = moteur.analyser_match
    def piege(match, *a, **k):
        if match["id"] == "boom":
            raise ZeroDivisionError("panne simulée")
        return vrai(match, *a, **k)
    monkeypatch.setattr(moteur, "analyser_match", piege)
    sigs = [signal(mid="boom"), signal(mid="ok")]
    resume = bm.applique_moteur(sigs, stats(), maintenant=NOW, h2h_fetcher=lambda s: H2H)
    assert sigs[0][bm.CLE_BLOC]["statut"] == "ERREUR_TECHNIQUE" and "ZeroDivisionError" in sigs[0][bm.CLE_BLOC]["raison"]
    assert sigs[0][bm.CLE_BLOC]["selection"] == {}
    assert sigs[1][bm.CLE_BLOC]["statut"] == "OK"
    assert all(s["moteur_utilise"] == bm.NOM_MOTEUR for s in sigs)
    assert resume["statuts"] == {"ERREUR_TECHNIQUE": 1, "OK": 1}
    assert not any("archetype_model" in s for s in sigs)                       # aucun repli sur l'ancien moteur


# ═══════════════════════════ 7. ARCHIVE ═══════════════════════════
def test_archive_selected_et_counterfactual(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sigs = [signal(mid="m1"), signal(mid="m2", un=1.85, dc=1.22)]
    arch = lambda s, b, n: bm.archive_bloc(s, b, n, archive)
    resume = bm.applique_moteur(sigs, stats(), maintenant=NOW, h2h_fetcher=lambda s: H2H, archiver=arch)
    recs = json.load(open(tmp_path / "archive" / "2026-09.json", encoding="utf-8"))
    assert resume["nb_erreurs_archive"] == 0 and resume["nb_archives"] == len(recs)
    sel = [r for r in recs if r["categorie"] == "SELECTED"]
    assert {r["marche"] for r in sel} == {"double_chance_1X", "1x2_domicile"} and len(sel) == 2 and {r["match_id"] for r in sel} == {"m1"}
    assert any(r["categorie"] == "COUNTERFACTUAL" and r["match_id"] == "m2" and r["marche"] == "1x2_domicile" for r in recs)   # catégorie D
    assert all(r["model_version"] == "moteur_v2_6_9" and r["resultat_statut"] == "PENDING" for r in recs)
    assert any(r["categorie"] == "COUNTERFACTUAL" and r["marche"] == "btts_non" for r in recs)
    assert all(evaluer_marche(r["marche"], 1, 0).statut != "MARCHE_NON_RECONNU" for r in recs)


def test_archive_idempotente_et_resultat_resolu_immuable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arch = lambda s, b, n: bm.archive_bloc(s, b, n, archive)
    r1 = bm.applique_moteur([signal()], stats(), maintenant=NOW, h2h_fetcher=lambda s: H2H, archiver=arch)
    chemin = tmp_path / "archive" / "2026-09.json"
    n1 = len(json.load(open(chemin, encoding="utf-8")))
    bm.applique_moteur([signal()], stats(), maintenant=NOW, h2h_fetcher=lambda s: H2H, archiver=arch)
    assert len(json.load(open(chemin, encoding="utf-8"))) == n1 == r1["nb_archives"]        # pas de doublon
    rid = archive.construire_record_id("t1", "double_chance_1X", None)
    archive.mettre_a_jour_resultat(rid, buts_marques=2, buts_encaisses=0, resultat_marche="WIN", date_resolution="2026-09-22", chemin=chemin)
    r3 = bm.applique_moteur([signal()], stats(), maintenant=NOW, h2h_fetcher=lambda s: H2H, archiver=arch)
    assert r3["nb_erreurs_archive"] == 1                                                      # compté, jamais une exception


# ═══════════════════════ 8. SORTIE ALLÉGÉE POUR LE SITE ═══════════════════════
def test_bloc_leger_garde_la_selection_et_reduit_la_justification():
    bloc, _ = analyse()
    lg = bm.bloc_leger(bloc)
    assert set(lg) == {"statut", "moteur", "version_moteur", "statut_global", "raison", "selection"}
    j = lg["selection"]["P1"]["justification"]
    assert set(j) == {"resume", "preuves", "donnees_suffisantes", "bibliotheque"} and "inventaire" not in lg
    for champ in ("marche", "cote", "probabilite", "edge", "edv", "niveau", "market_family", "exposure_group", "rang"):
        assert champ in lg["selection"]["P1"], champ
    json.dumps(lg)                                                                            # sérialisable


def test_bloc_leger_cas_limites():
    assert bm.bloc_leger(None) is None
    assert bm.bloc_leger({"statut": "SKIP", "raison": "x"})["selection"] == {}
    assert bm.bloc_leger({"statut": "OK", "selection": {"P1": None}})["selection"] == {}


# ═════════════ 9. BRANCHEMENT DANS precalcul.py ═════════════
def test_precalcul_applique_le_moteur_et_allege_pour_le_site(tmp_path, monkeypatch):
    import precalcul
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(precalcul, "STATS_EQUIPES_VUES", stats())
    monkeypatch.setattr(precalcul, "_h2h_pour_signal", lambda s: H2H)
    sigs = precalcul.applique_moteur_pipeline([signal(), signal(mid="x", cotes_manuelles=None)])
    assert sigs[0]["moteur_utilise"] == "moteur_v2_6_9" and sigs[0]["moteur_v2_6_9"]["selection"]["P1"]["marche"] == "double_chance_1X"
    assert sigs[1]["moteur_v2_6_9"]["statut"] == "NON_EXPORTABLE"
    assert os.path.exists(tmp_path / "archive" / "2026-09.json")
    leger = precalcul._leger_pour_site(sigs[0])
    assert "inventaire" not in leger["moteur_v2_6_9"] and leger["moteur_v2_6_9"]["selection"]["P1"]["justification"]["bibliotheque"]


def test_l_ancien_modele_n_est_plus_appele_par_main():
    import inspect
    import precalcul
    source = inspect.getsource(precalcul.main)
    assert "applique_moteur_pipeline(" in source and "applique_archetype_model(" not in source


# ═════════════ 10. REPRODUCTIBILITÉ : le fichier exporté rejoue le même calcul ═════════════
def test_le_fichier_exporte_rejoue_exactement_le_meme_calcul(tmp_path):
    sig, st = signal(), stats()
    res = pont_moteur.exporte_matchs_moteur([sig], st, dossier=str(tmp_path), maintenant=NOW)
    assert res["nb_exportes"] == 1
    match = moteur.charger_matchs(res["fichiers"]["2026-09-22"])[0]
    rejoue = moteur.analyser_match(match, "2026-09-22", NOW)
    direct = bm.analyse_signal(sig, st, NOW, lambda s: H2H)[0]
    a = [(l["marche"], round(l["ev"], 9), l["is_value"]) for l in rejoue["inventaire"]]
    b = [(x["marche_moteur"], round(x["ev"], 9), x["is_value"]) for x in direct["inventaire"]]
    assert a == b and a
