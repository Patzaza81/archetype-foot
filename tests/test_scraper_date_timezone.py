from scraper import convertit_date_cameroun


def test_date_matchendirect_apres_minuit_devient_veille_au_cameroun_en_heure_ete():
    # Le 23 octobre, Paris est encore en UTC+2 et Douala en UTC+1.
    assert convertit_date_cameroun("00:30", "2026-10-23") == "2026-10-22"


def test_date_reste_identique_quand_la_conversion_ne_change_pas_le_jour():
    assert convertit_date_cameroun("20:00", "2026-10-23") == "2026-10-23"


def test_date_source_conservee_si_heure_non_exploitable():
    assert convertit_date_cameroun("TER", "2026-10-23") == "2026-10-23"


# --- 24/10/2026 : matchs de la nuit listés sur deux pages consécutives (Amériques, Asie, Océanie) --------------------
from scraper import corrige_dates_minuit  # noqa: E402


def _m(mid, heure, page, dom="A"):
    return {"match_id": mid, "domicile": dom, "exterieur": "B", "heure": heure, "date_source": page,
            "date": convertit_date_cameroun(heure, page), "heure_cameroun": None}


def test_match_de_la_nuit_redate_au_lendemain():
    jour = [_m("mls", "01:30", "2026-10-24"), _m("j1", "07:00", "2026-10-24"), _m("bre", "00:30", "2026-10-24")]
    demain = [_m("mls", "01:30", "2026-10-25"), _m("j1", "07:00", "2026-10-25"), _m("bre", "00:30", "2026-10-25")]
    assert corrige_dates_minuit(jour, demain) == 3
    mls, j1, bre = jour
    assert (mls["date"], mls["heure_cameroun"], mls["date_page"]) == ("2026-10-25", "00:30", "2026-10-24")   # MLS : nuit du 24 au 25
    assert (j1["date"], j1["heure_cameroun"]) == ("2026-10-25", "07:00")          # Japon : après le passage à l'heure d'hiver
    assert (bre["date"], bre["heure_cameroun"]) == ("2026-10-24", "23:30")        # Brésil : 00:30 à Paris = 23:30 la veille à Douala


def test_aucune_preuve_aucune_correction():
    seul = [_m("caledonie", "04:30", "2026-10-24")]                               # vu sur une seule page : jamais déplacé
    soir = [_m("soir", "20:45", "2026-10-24")]
    loin = [_m("x", "01:00", "2026-10-24"), _m("x", "01:00", "2026-10-26")]       # pages non consécutives : rien
    assert corrige_dates_minuit(seul, soir, loin) == 0
    assert seul[0]["date"] == "2026-10-24" and "date_page" not in seul[0]
    assert soir[0]["date"] == "2026-10-24" and "date_page" not in soir[0]
    assert {m["date_source"] for m in loin} == {"2026-10-24", "2026-10-26"}


def test_heure_reprise_d_une_page_si_l_autre_affiche_un_statut():
    jour, demain = [_m("t", "TER", "2026-10-24")], [_m("t", "03:00", "2026-10-25")]
    corrige_dates_minuit(jour, demain)
    assert (jour[0]["date"], jour[0]["heure_cameroun"]) == ("2026-10-25", "03:00")
