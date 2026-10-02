from journal_schema import (
    SCHEMA_VERSION,
    ContexteMarche,
    FicheComportementaleMatch,
    MatchIdentity,
    MarcheObservation,
    NiveauObservation,
    RegimeComportement,
    StatutAnticipation,
)


def test_schema_version_and_minimal_match():
    identity = MatchIdentity(
        match_id="2026-10-03-TEST",
        date="2026-10-03",
        heure="18:00",
        championnat="Test League",
        saison="2026-2027",
        equipe_domicile="Alpha",
        equipe_exterieure="Beta",
    )
    fiche = FicheComportementaleMatch(identification=identity)
    payload = fiche.to_dict()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["identification"]["match_id"] == "2026-10-03-TEST"
    assert payload["anticipation_globale"] == StatutAnticipation.EN_ATTENTE.value


def test_market_observation_keeps_behavior_and_context():
    observation = MarcheObservation(
        marche="BTTS",
        equipe_reference="Alpha",
        contexte=ContexteMarche.DOMICILE,
        cote_tranche="1.70-1.89",
        echantillon=8,
        frequence=0.625,
        sequence_actuelle=["O", "O", "N", "O"],
        regime_detecte=RegimeComportement.RENFORCEMENT,
        niveau_observation=NiveauObservation.EXPLOITABLE,
    )
    assert observation.echantillon == 8
    assert observation.frequence == 0.625
    assert observation.regime_detecte == RegimeComportement.RENFORCEMENT
    assert observation.contexte == ContexteMarche.DOMICILE


def test_invalid_frequency_is_rejected():
    try:
        MarcheObservation(marche="BTTS", frequence=1.1)
    except ValueError as exc:
        assert "frequence" in str(exc)
    else:
        raise AssertionError("Une fréquence hors [0, 1] doit être rejetée")


def test_invalid_odd_is_rejected():
    from journal_schema import CoteObservation
    try:
        CoteObservation(marche="BTTS", cote_observee=1.0)
    except ValueError as exc:
        assert "cote" in str(exc)
    else:
        raise AssertionError("Une cote <= 1 doit être rejetée")
