import copy

import pytest

import suivi_selection_generateur as ss
import suivi_tickets as st

T1 = "2026-10-09T11:50:00+00:00"
T2 = "2026-10-09T16:43:00+00:00"
MAINT = "2026-10-10T01:00:00+00:00"
EV = st.evaluateur_defaut()


def pari(dom="Cambrian", ext="Ammanford", marche="Match à plus de 2,5 buts", source="journal", cote=1.39, date="2026-10-09",
         match_id=None, equipe=None):
    return {"match_id": match_id, "date": date, "heure": "19:45", "competition": "X", "domicile": dom, "exterieur": ext,
            "marche": marche, "cote": cote, "probabilite_estimee": 0.69, "source": source, "rang": None,
            "journal_team": equipe}


def tickets(pool, genere_le=T1):
    return {"genere_le": genere_le, "jour_present": "2026-10-09", "plages": [{"id": "A", "pool": pool}]}


def match(dom, ext, h, a, date="2026-10-09", match_id=None):
    return {"match_id": match_id, "date": date, "domicile": dom, "exterieur": ext, "buts": (h, a) if h is not None else None}


def regle(pool, matchs):
    arch = ss.archive_vide()
    ss.enregistre(arch, tickets(pool))
    ss.regle(arch, matchs, EV, MAINT)
    return arch


def resultat(arch, i=0):
    return (arch["resultats"].get(arch["executions"][0]["paris"][i]["id"]) or {}).get("resultat")


# --- enregistrement -------------------------------------------------------------------------------------------------

def test_une_execution_identique_n_est_pas_dupliquee():
    arch = ss.archive_vide()
    assert ss.enregistre(arch, tickets([pari()], T1))
    assert not ss.enregistre(arch, tickets([pari()], T2))  # même liste, autre heure
    assert not ss.enregistre(arch, tickets([pari(cote=1.5)], T1))  # même genere_le : déjà archivé
    assert len(arch["executions"]) == 1


def test_une_liste_qui_change_est_gardee_en_plus_de_la_precedente():
    arch = ss.archive_vide()
    ss.enregistre(arch, tickets([pari()], T1))
    assert ss.enregistre(arch, tickets([pari(cote=1.45)], T2))
    assert [e["genere_le"] for e in arch["executions"]] == [T1, T2]
    assert arch["executions"][0]["paris"][0]["cote"] == 1.39  # l'ancienne exécution n'est jamais modifiée


def test_sans_pari_rien_n_est_archive():
    arch = ss.archive_vide()
    assert not ss.enregistre(arch, tickets([], T1))
    assert not ss.enregistre(arch, {"genere_le": T1, "pool": [{"marche": "x"}]})  # lignes sans équipes ignorées
    assert arch["executions"] == []


def test_un_meme_marche_propose_par_deux_sources_reste_deux_paris():
    v3 = pari(marche="over_under_total_2.5_over", source="moteur_v3", match_id="m1")
    jr = pari()
    paris = ss.paris_de(tickets([v3, jr]))
    assert len(paris) == 2


# --- règlement : 3 cas qui doivent passer ---------------------------------------------------------------------------

def test_pari_du_journal_sans_identifiant_regle_par_les_noms_meme_avec_accents_et_casse():
    p = pari("Étoile Carouge", "Yverdon", "Match à plus de 2,5 buts")
    arch = regle([p], [match("etoile carouge", "YVERDON", 1, 4)])
    assert resultat(arch) == "WIN"
    assert arch["resultats"][arch["executions"][0]["paris"][0]["id"]]["score"] == "1-4"


def test_pari_v3_regle_par_identifiant_meme_si_les_noms_different():
    p = pari("Sochaux", "US Boulogne", "over_under_total_2.5_under", "moteur_v3", match_id="abc")
    arch = regle([p], [match("FC Sochaux-Montbéliard", "Boulogne", 1, 1, match_id="abc")])
    assert resultat(arch) == "WIN"


def test_ne_perd_pas_de_l_equipe_exterieure_est_regle_dans_les_deux_sens():
    p = pari("A", "B", "Ne perd pas (victoire ou nul)", equipe="B")
    assert resultat(regle([p], [match("A", "B", 1, 1)])) == "WIN"
    assert resultat(regle([p], [match("A", "B", 3, 0)])) == "LOSS"


# --- règlement : 3 cas qui doivent échouer (rester sans résultat, jamais perdus par défaut) -------------------------

def test_autre_date_ou_equipes_inversees_ne_sont_pas_le_meme_match():
    p = pari("Cambrian", "Ammanford")
    assert resultat(regle([p], [match("Cambrian", "Ammanford", 0, 1, date="2026-10-10")])) is None
    assert resultat(regle([p], [match("Ammanford", "Cambrian", 0, 1)])) is None


def test_marche_non_reconnu_reste_sans_resultat():
    p = pari("A", "B", "handicap3_domicile_1_1", "moteur_v3", match_id="z")
    arch = regle([p], [match("A", "B", 2, 0, match_id="z")])
    assert resultat(arch) is None and arch["resultats"] == {}


def test_match_sans_score_reste_sans_resultat():
    assert resultat(regle([pari()], [match("Cambrian", "Ammanford", None, None)])) is None


# --- règlement figé et bilan ---------------------------------------------------------------------------------------

def test_un_resultat_ecrit_n_est_jamais_modifie():
    arch = regle([pari()], [match("Cambrian", "Ammanford", 0, 1)])
    avant = copy.deepcopy(arch["resultats"])
    ss.regle(arch, [match("Cambrian", "Ammanford", 3, 3)], EV, "plus tard")
    assert arch["resultats"] == avant
    assert resultat(arch) == "LOSS"


def test_bilan_par_source():
    pool = [pari("A", "B", "Match à plus de 2,5 buts"), pari("C", "D", "Match à plus de 2,5 buts"),
            pari("E", "F", "over_under_total_2.5_under", "moteur_v3", match_id="e")]
    arch = regle(pool, [match("A", "B", 2, 1), match("C", "D", 0, 0), match("E", "F", 1, 0, match_id="e")])
    b = ss.bilan(arch, MAINT)
    assert b["par_source"]["journal"]["paris"] == 2 and b["par_source"]["journal"]["reussis"] == 1
    assert b["par_source"]["journal"]["taux_reussite"] == 0.5
    assert b["par_source"]["moteur_v3"]["taux_reussite"] == 1.0
    assert b["paris_regles"] == 3


def test_archive_corrompue_repart_d_une_archive_vide(tmp_path):
    f = tmp_path / "a.json"
    f.write_text("{pas du json", encoding="utf-8")
    assert ss.charge_archive(f) == ss.archive_vide()
    f.write_text('{"executions": 3}', encoding="utf-8")
    assert ss.charge_archive(f) == ss.archive_vide()
