"""Enregistrement des scores dans historique_pronostics.json (rétabli le 26/09/2026) et rattrapage des jours manquants.
Cas qui doivent remplir le score, et cas qui ne doivent JAMAIS l'écrire."""
import datetime

import enregistre_scores_historique as es

D = datetime.date
AUJ = D(2026, 9, 26)


def memes(a, b):
    return a.strip().lower() == b.strip().lower()


def hist():
    return [
        {"date": "2026-09-19", "matchs": [
            {"match_id": "m1", "domicile": "Norwich", "exterieur": "Leeds", "date": "2026-09-19", "score": None},
            {"match_id": "m2", "domicile": "Hull", "exterieur": "Derby", "date": "2026-09-19", "score": None},
            {"match_id": "m3", "domicile": "Wigan", "exterieur": "Bolton", "date": "2026-09-19", "score": "1-1"}]},
        {"date": "2026-09-20", "matchs": [
            {"match_id": "m1", "domicile": "Norwich", "exterieur": "Leeds", "date": "2026-09-19", "score": None},
            {"match_id": "m4", "domicile": "Austin", "exterieur": "San Diego", "date": "2026-09-20", "score": None}]},
        {"date": "2026-09-26", "matchs": [
            {"match_id": "m5", "domicile": "Aldershot", "exterieur": "Tamworth", "date": "2026-09-26", "score": None}]},
    ]


PAGES = {
    D(2026, 9, 19): [{"domicile": "Norwich", "exterieur": "Leeds", "score": "2-1", "heure": "TER"},
                     {"domicile": "Hull", "exterieur": "Derby", "score": "0-0", "heure": "REP"},     # reporté
                     {"domicile": "Wigan", "exterieur": "Bolton", "score": "3-0", "heure": "TER"}],
    D(2026, 9, 20): [{"domicile": "Austin", "exterieur": "San Diego", "score": "1-0", "heure": "TER"}],
}


def run(h, pages=PAGES):
    appels = []

    def charge(d):
        appels.append(d)
        if d not in pages:
            raise RuntimeError("page indisponible")
        return pages[d]
    return es.enregistre(h, AUJ, charge, memes, pause=0), appels


# --- doivent remplir ---------------------------------------------------------------------------------------------------
def test_match_termine_rempli():
    h = hist()
    bilan, _ = run(h)
    assert h[0]["matchs"][0]["score"] == "2-1" and h[1]["matchs"][1]["score"] == "1-0"
    assert bilan["matchs_remplis"] == 2


def test_toutes_les_entrees_d_un_meme_match_remplies():
    h = hist()
    run(h)
    assert h[1]["matchs"][0]["score"] == "2-1"       # m1 figure aussi dans le jour 20/09


def test_rattrapage_une_seule_page_par_jour():
    _, appels = run(hist())
    assert appels == [D(2026, 9, 19), D(2026, 9, 20)]


# --- ne doivent JAMAIS écrire -------------------------------------------------------------------------------------------
def test_match_non_termine_reste_sans_score():
    h = hist()
    bilan, _ = run(h)
    assert h[0]["matchs"][1]["score"] is None and bilan["sans_score_termine"] == 1


def test_score_deja_present_jamais_modifie():
    h = hist()
    run(h)
    assert h[0]["matchs"][2]["score"] == "1-1"       # la page dit 3-0 : l'existant est conservé


def test_jour_non_termine_jamais_traite():
    h = hist()
    _, appels = run(h)
    assert D(2026, 9, 26) not in appels and h[2]["matchs"][0]["score"] is None


def test_page_en_echec_signalee_sans_bloquer_les_autres_jours():
    h = hist()
    bilan, _ = run(h, pages={D(2026, 9, 20): PAGES[D(2026, 9, 20)]})
    assert bilan["pages_en_echec"] and h[1]["matchs"][1]["score"] == "1-0"


def test_limite_de_jours_pour_le_run_nocturne():
    assert list(es.jours_a_traiter(hist(), AUJ, jours_max=6)) == [D(2026, 9, 20)]
