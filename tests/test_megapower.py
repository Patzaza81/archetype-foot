"""MEGAPOWER : le cœur (apprentissage, jugement, sélection) et le journal gelé, sur des données fabriquées pour le test (aucune donnée du jour)."""
import json
from datetime import datetime, timezone

import numpy as np

import verif_pronostic as V
from megapower import coeur as C, signaux as S, suivi as SV


def _tableau(n_matchs, reussite, cote, marche="1", debut=1):
    """n_matchs matchs, un pari chacun sur `marche` à `cote`, gagnés selon `reussite` (fonction du rang)."""
    k = V.IDX[marche]
    T = {"match": np.arange(n_matchs), "marche": np.full(n_matchs, k), "cote": np.full(n_matchs, float(cote)), "y": np.array([float(reussite(i)) for i in range(n_matchs)])}
    for s in S.SIGNAUX:
        T[s] = np.full(n_matchs, 0.5)
    jours = np.array([f"2026-10-{debut + i * 20 // n_matchs:02d}" for i in range(n_matchs)])
    return T, jours


def test_famille_de_chaque_marche_du_catalogue():
    assert all(C.famille(n) in C.FAMILLES for n in S.NOMS)
    assert C.famille("1N&total_plus_1.5") == "double chance + total de buts" and C.famille("2") == "victoire ou nul" and C.famille("cage_dom_oui") == "cage inviolée"


def test_pari_perdant_jamais_retenu():
    T, jours = _tableau(600, lambda i: i % 2 == 0, 1.50)            # 50 % de réussite à 1,50 : perd 25 %
    mod = C.apprendre(T, jours, 1.26)
    J = C.juger(T, mod)
    assert (J["statut"] == 0).all() and J["gain"].max() < 0
    assert len(C.meilleur_par_match(T, J, 1)) == 0


def test_pari_nettement_gagnant_prouve_et_cote_min_respectee():
    T, jours = _tableau(600, lambda i: i % 10 != 0, 1.50)           # 90 % de réussite à 1,50 : gagne 35 %
    mod = C.apprendre(T, jours, 1.26)
    J = C.juger(T, mod)
    assert (J["statut"] == 2).all() and (J["gain_bas"] > 0).all()
    T2 = {k: v.copy() for k, v in T.items()}
    T2["cote"][:] = 1.20                                            # sous la cote minimale : jamais retenu, quoi que dise le modèle
    assert (C.juger(T2, mod)["statut"] == 0).all()


def test_un_seul_pari_par_match_le_meilleur():
    T, jours = _tableau(600, lambda i: i % 10 != 0, 1.50)
    mod = C.apprendre(T, jours, 1.26)
    T2 = {k: np.concatenate([v[:1], v[:1]]) for k, v in T.items()}
    T2["cote"] = np.array([1.40, 1.50])
    J = C.juger(T2, mod)
    i = C.meilleur_par_match(T2, J, 1)
    assert len(i) == 1 and J["gain"][i[0]] == J["gain"].max()
    T2["cote"] = np.array([1.50, 1.60])                              # 1,60 n'a jamais été gagné à l'apprentissage (cote la plus haute gagnée : 1,50) : le modèle ne devine pas
    J = C.juger(T2, mod)
    assert J["statut"].tolist() == [2, 0]


def test_accord_compte_les_lectures_disponibles():
    T, _ = _tableau(1, lambda i: 1, 2.0)                             # la cote dit 50 %
    for s in S.SIGNAUX:
        T[s] = np.array([np.nan])
    T["v_dom"], T["v_ext"], T["o_p"] = np.array([0.8]), np.array([0.6]), np.array([0.4])
    pour, dispo = C.accord(T)
    assert pour[0] == 1 and dispo[0] == 2                            # Verdict pour (70 %), Omega contre (40 %), Alpha et Gamma absents


def test_gel_avant_le_coup_d_envoi_et_reglement(tmp_path):
    journal = tmp_path / "journal.jsonl"
    k = V.IDX["1"]
    sig = {s: np.full(S.NB, np.nan) for s in S.SIGNAUX}
    cote = np.full(S.NB, np.nan); cote[k] = 1.5
    m = {"id": "m1", "jour": "2026-11-20", "ko": "2026-11-20T18:00:00Z", "competition": "Test", "domicile": "A", "exterieur": "B", "heure": "19:00", "signaux": sig, "cote": cote, "n_dom": 5, "n_ext": 5}
    T = {"match": np.array([0]), "marche": np.array([k]), "cote": np.array([1.5]), "y": np.array([np.nan]), **{s: np.array([np.nan]) for s in S.SIGNAUX}}
    J = {"p": np.array([0.9]), "gain": np.array([0.35]), "gain_bas": np.array([0.2]), "statut": np.array([2])}
    avant = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    assert SV.geler([m], T, J, {}, avant, journal) == (1, 1)
    assert SV.geler([m], T, J, {}, avant, journal) == (0, 1)        # même pari : pas de nouvelle ligne
    apres = datetime(2026, 11, 20, 19, 0, tzinfo=timezone.utc)
    assert SV.geler([m], T, J, {}, apres, journal) == (0, 0)        # match commencé : plus aucun gel
    assert SV.resultats({"m1": (2, 0)}, journal) == 1 and SV.resultats({"m1": (2, 0)}, journal) == 0
    b = SV.bilan(SV._lire(journal))
    assert b["prouvé"] == {"paris": 1, "reussite": 1.0, "cote_moyenne": 1.5, "rendement": 0.5, "du": "2026-11-20", "au": "2026-11-20"}
    lignes = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines()]
    assert [l["type"] for l in lignes] == ["pronostic", "resultat"] and lignes[0]["fiche"]["pari"]["statut"] == "prouvé"


def test_gel_tardif_ne_compte_pas(tmp_path):
    journal = tmp_path / "journal.jsonl"
    f = {"match_id": "m1", "jour": "2026-11-20", "coup_d_envoi_utc": "2026-11-20T18:00:00Z", "pari": {"marche": "1", "cote": 1.5, "statut": "prouvé"}}
    SV._ajouter(journal, [{"type": "pronostic", "match_id": "m1", "gele_le": "2026-11-20T18:30:00+00:00", "fiche": f}])
    assert SV.gels_valides(SV._lire(journal)) == {} and SV.resultats({"m1": (1, 0)}, journal) == 0


def test_page_megapower_branchee_et_moteurs_desactives():
    import pathlib
    from megapower import actifs
    racine = pathlib.Path(__file__).parent.parent
    html = (racine / "pronostics_megapower.html").read_text(encoding="utf-8")
    js = (racine / "archetype_megapower.js").read_text(encoding="utf-8")
    for ident in ("mp-verdict", "mp-avenir", "mp-observation", "mp-encours", "mp-regles", "mp-chiffres"):
        assert f'id="{ident}"' in html and ident in js
    assert "archetype_megapower.js" in html and "megapower/pronostics.json" in js and 'href="pronostics_megapower.html" aria-current="page"' in html
    assert "megapower.suivi pipeline" in (racine / ".github" / "workflows" / "pipeline.yml").read_text(encoding="utf-8")
    assert set(actifs.desactives()) == {"v2r", "v", "dc", "mixte"} and actifs.actif("gamma") and not actifs.actif("dc")
    assert actifs.desactives(racine / "inexistant.json") == {}          # fichier absent : rien n'est désactivé


def test_cotes_relevees_pendant_le_match_ecartees():
    from megapower.donnees import cotes_avant_match
    assert cotes_avant_match({"coup_d_envoi_utc": "2026-10-31T18:30:00Z", "run": {"pris_le": "2026-10-31T10:00:00Z"}})
    assert not cotes_avant_match({"coup_d_envoi_utc": "2026-10-31T18:30:00Z", "run": {"pris_le": "2026-10-31T19:35:00Z"}})     # relevées pendant le match
    assert not cotes_avant_match({"coup_d_envoi_utc": None, "run": {"pris_le": "2026-10-31T19:35:00Z"}})                       # heure du match inconnue : doute, écarté
    assert not cotes_avant_match({"coup_d_envoi_utc": "2026-10-31T18:30:00Z"})
