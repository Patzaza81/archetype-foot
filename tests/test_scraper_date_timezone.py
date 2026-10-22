from scraper import convertit_date_cameroun


def test_date_matchendirect_apres_minuit_devient_veille_au_cameroun_en_heure_ete():
    # Le 23 octobre, Paris est encore en UTC+2 et Douala en UTC+1.
    assert convertit_date_cameroun("00:30", "2026-10-23") == "2026-10-22"


def test_date_reste_identique_quand_la_conversion_ne_change_pas_le_jour():
    assert convertit_date_cameroun("20:00", "2026-10-23") == "2026-10-23"


def test_date_source_conservee_si_heure_non_exploitable():
    assert convertit_date_cameroun("TER", "2026-10-23") == "2026-10-23"
