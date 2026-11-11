"""Sources de calendrier : format commun, comparaison des noms, rapprochement un pour un, lecture d'ESPN et d'openfootball, mesure complète.
Aucun accès réseau et aucune donnée du jour : tout est fabriqué pour le test."""
import gzip
import json
from datetime import datetime, timezone

import pytest

from sources_calendrier import mesure as ME, rapprochement as R
from sources_calendrier.modele import Match, sans_doublons
from sources_calendrier.noms import meme_equipe
from sources_calendrier.sources import espn, matchendirect, openfootball


# ---------------------------------------------------------------- noms d'équipes : au moins 3 cas qui passent et 3 qui échouent par règle
@pytest.mark.parametrize("a,b", [("Arsenal FC", "Arsenal"), ("Séville", "Seville FC"), ("Washington", "Washington Spirit"), ("Allemagne", "Germany"),
                                 ("États-Unis", "United States"), ("Köge", "Koge"), ("AS Monaco", "Monaco"),
                                 ("Gérone", "Girona"), ("Colchester Utd", "Colchester United"), ("S. Wednesday", "Sheffield Wednesday"),
                                 ("Atl. Mineiro", "Atlético Mineiro"), ("Dep. Pasto", "Deportivo Pasto")])
def test_meme_equipe_oui(a, b):
    assert meme_equipe(a, b) and meme_equipe(b, a)


@pytest.mark.parametrize("a,b", [("Arsenal", "Arsenal Women"), ("Chelsea féminines", "Chelsea"), ("Real Madrid", "Real Madrid B"), ("Espagne", "Espagne U19"),
                                 ("Italie U17", "Italie U19"), ("Manchester United", "Manchester City"), ("Real Madrid", "Real Sociedad"), ("", "Arsenal"), ("FC", "Arsenal"),
                                 ("S. Wednesday", "Sheffield United"), ("Colchester Utd", "Manchester United"), ("Atl. Mineiro", "Atlético Madrid"),
                                 ("Atl. Junior", "Atlético Nacional"), ("Dep. Pasto", "Deportivo Cali"), ("Gérone", "Gimnàstic")])
def test_meme_equipe_non(a, b):
    assert not meme_equipe(a, b) and not meme_equipe(b, a)


# ---------------------------------------------------------------- rapprochement
def _m(source, ident, jour, dom, ext):
    return Match(source, ident, jour, dom, ext)


def test_rapprochement_un_pour_un_jours_voisins():
    ref = [_m("matchendirect", "a", "2026-11-14", "Arsenal", "Chelsea"), _m("matchendirect", "b", "2026-11-14", "Lyon", "Nice"), _m("matchendirect", "c", "2026-11-14", "Porto", "Braga")]
    cand = [_m("espn", "1", "2026-11-15", "Arsenal FC", "Chelsea FC"),        # match de la nuit : jour voisin accepté
            _m("espn", "2", "2026-11-16", "Lyon", "Nice"),                    # deux jours d'écart : refusé
            _m("espn", "3", "2026-11-14", "Braga", "Porto")]                  # domicile et extérieur inversés : ce n'est pas le même match
    r = R.rapprocher(ref, cand)
    assert set(r["paires"]) == {"a"} and r["paires"]["a"].id_source == "1" and sorted(r["sans"]) == ["b", "c"] and r["ambigus"] == []


def test_rapprochement_doute_egale_ambigu_jamais_un_choix():
    ref = [_m("matchendirect", "a", "2026-11-14", "Real", "Betis")]
    cand = [_m("espn", "1", "2026-11-14", "Real Madrid", "Real Betis"), _m("espn", "2", "2026-11-14", "Real Sociedad", "Betis")]
    r = R.rapprocher(ref, cand)
    assert r["paires"] == {} and r["ambigus"] == ["a"]
    ref2 = [_m("matchendirect", "a", "2026-11-14", "Arsenal", "Chelsea"), _m("matchendirect", "b", "2026-11-15", "Arsenal FC", "Chelsea")]   # deux références pour un seul candidat
    r2 = R.rapprocher(ref2, [_m("espn", "1", "2026-11-14", "Arsenal", "Chelsea")])
    assert r2["paires"] == {} and sorted(r2["ambigus"]) == ["a", "b"]


def test_sans_doublons_garde_le_premier():
    L = [_m("espn", "1", "2026-11-14", "A", "B"), _m("espn", "1", "2026-11-15", "A", "B"), _m("openfootball", "1", "2026-11-14", "A", "B")]
    assert [(m.source, m.jour) for m in sans_doublons(L)] == [("espn", "2026-11-14"), ("openfootball", "2026-11-14")]


# ---------------------------------------------------------------- lecture des sources (formats relevés le 11/11/2026)
def _evenement(ident, quand, dom, ext, ligue="700"):
    return {"id": ident, "uid": f"s:600~l:{ligue}~e:{ident}", "date": quand,
            "competitions": [{"id": ident, "date": quand, "competitors": [{"homeAway": "away", "team": {"displayName": ext}}, {"homeAway": "home", "team": {"displayName": dom}}]}]}


ESPN_JOUR = json.dumps({"leagues": [{"calendar": []}], "events": [
    _evenement("401", "2026-11-14T17:00Z", "Arsenal", "Chelsea"), _evenement("402", "2026-11-15T01:00Z", "Jamaica", "Mexico", "19267"),
    {"id": "403", "date": "2026-11-14T17:00Z", "competitions": [{"competitors": [{"homeAway": "home", "team": {"displayName": "Seul"}}]}]},      # une seule équipe : ignoré
    {"id": "404", "competitions": [{"competitors": []}]}]}).encode()                                                                                 # sans date ni équipes : ignoré


def test_espn_lecture_et_orientation():
    L = espn.lire_reponse(ESPN_JOUR)
    assert [(m.id_source, m.domicile, m.exterieur, m.jour, m.coup_d_envoi_utc) for m in L] == [
        ("401", "Arsenal", "Chelsea", "2026-11-14", "2026-11-14T17:00:00Z"), ("402", "Jamaica", "Mexico", "2026-11-15", "2026-11-15T01:00:00Z")]
    assert L[1].competition == "ligue ESPN 19267"


def test_espn_veille_demandee_sans_doublon_et_erreurs_notees():
    vus = []
    def faux(url):
        vus.append(url)
        if "20261114" in url:
            raise RuntimeError("panne")
        return ESPN_JOUR
    conf = {"url": "https://x/?dates={AAAAMMJJ}&limit={limite}", "limite": 1000}
    matchs, erreurs = espn.lire(["2026-11-13", "2026-11-14"], conf, faux)
    assert [u.split("dates=")[1][:8] for u in vus] == ["20261112", "20261113", "20261114"]            # la veille du premier jour est demandée aussi
    assert len(matchs) == 2 and len(erreurs) == 1 and "2026-11-14" in erreurs[0]                       # même match lu deux fois : un seul exemplaire
    _, coupee = espn.lire(["2026-11-13"], {"url": conf["url"], "limite": 2}, lambda u: ESPN_JOUR)
    assert any("limite atteinte" in e for e in coupee)


OPEN = json.dumps({"name": "English Premier League 2026/27", "matches": [
    {"round": "Matchday 1", "date": "2026-08-21", "time": "20:00", "team1": "Arsenal FC", "team2": "Coventry City FC", "score": {"ht": [2, 0], "ft": [3, 0]}},
    {"round": "Matchday 11", "date": "2026-11-21", "time": "15:00", "team1": "Chelsea FC", "team2": "Leeds United FC"},
    {"round": "Matchday 11", "date": "2026-11-21", "team1": "", "team2": "Fulham FC"}]}).encode()


def test_openfootball_lecture_par_jour_et_fichier_en_panne():
    def faux(url):
        if "de.1" in url:
            raise RuntimeError("404")
        return OPEN
    conf = {"url": "https://x/{fichier}", "fichiers": ["2026-27/en.1.json", "2026-27/de.1.json"]}
    matchs, erreurs = openfootball.lire(["2026-11-21"], conf, faux)
    assert [(m.domicile, m.exterieur, m.competition) for m in matchs] == [("Chelsea FC", "Leeds United FC", "English Premier League 2026/27")]
    assert len(erreurs) == 1 and "de.1" in erreurs[0]


def test_matchendirect_reprend_feminines_et_jeunes_de_la_competition(tmp_path):
    (tmp_path / "jour.json").write_text(json.dumps([
        {"match_id": "a", "date": "2026-11-11", "domicile": "OH Louvain", "exterieur": "Køge", "competition": "Europe :\n   Ligue des Champions Féminine Phase de Ligue"},
        {"match_id": "b", "date": "2026-11-11", "domicile": "Espagne", "exterieur": "Italie", "competition": "Europe : Championnat UEFA U19 Qualifications"},
        {"match_id": "c", "date": "2026-11-11", "domicile": "Arsenal", "exterieur": "Chelsea", "competition": "Angleterre : Premier League"},
        {"match_id": "c", "date": "2026-11-11", "domicile": "Arsenal", "exterieur": "Chelsea", "competition": "Angleterre : Premier League"},      # doublon
        {"match_id": "d", "date": "2026-11-20", "domicile": "Lyon", "exterieur": "Nice", "competition": "France : Ligue 1"},                        # autre jour
        {"match_id": "", "date": "2026-11-11", "domicile": "X", "exterieur": "Y"}]), encoding="utf-8")
    matchs, erreurs = matchendirect.lire(["2026-11-11"], {"fichiers": ["jour.json", "absent.json"]}, None, tmp_path)
    assert [(m.id_source, m.domicile, m.exterieur) for m in matchs] == [("a", "OH Louvain féminines", "Køge féminines"), ("b", "Espagne U19", "Italie U19"), ("c", "Arsenal", "Chelsea")]
    assert matchs[0].competition == "Europe : Ligue des Champions Féminine Phase de Ligue" and len(erreurs) == 1 and "absent.json" in erreurs[0]
    assert not meme_equipe(matchs[0].domicile, "OH Louvain") and meme_equipe(matchs[0].domicile, "OH Leuven Women") is False      # autre orthographe : à corriger dans sources_noms.json, jamais deviné


# ---------------------------------------------------------------- mesure complète
def test_mesure_de_bout_en_bout(tmp_path):
    (tmp_path / "jour.json").write_text(json.dumps([
        {"match_id": "a", "date": "2026-11-14", "domicile": "Arsenal", "exterieur": "Chelsea", "competition": "Angleterre : Premier League"},
        {"match_id": "b", "date": "2026-11-14", "domicile": "Jamaïque", "exterieur": "Mexique", "competition": "CONCACAF : Ligue des Nations"},
        {"match_id": "c", "date": "2026-11-14", "domicile": "Metapan", "exterieur": "Platense", "competition": "El Salvador : 1ère Division"}]), encoding="utf-8")
    (tmp_path / "flux").mkdir()
    with gzip.open(tmp_path / "flux" / "2026-11-14.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"a": {"cotes_betpawa": {"1x2": {"1": 1.5}}}, "c": {"cotes_betpawa": {"1x2": {"1": 2.0}}}, "b": {"cotes_betpawa": None}, "zzz": {"cotes_betpawa": {"x": 1}}}, f)
    conf = {"mode": "mesure", "sources": [
        {"nom": "matchendirect", "role": "principale", "fichiers": ["jour.json"]},
        {"nom": "espn", "role": "secours", "actif": True, "url": "https://x/?dates={AAAAMMJJ}&limit={limite}", "limite": 1000},
        {"nom": "openfootball", "role": "secours", "actif": True, "url": "https://x/{fichier}", "fichiers": ["2026-27/en.1.json"]},
        {"nom": "espn", "role": "secours", "actif": False, "url": "https://x"}]}
    def faux(url):
        if "dates=" in url:
            return ESPN_JOUR
        raise RuntimeError("hors service")
    r = ME.mesurer(conf, faux, tmp_path, datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc), tmp_path / "flux")
    assert r["jours"] == ["2026-11-14"] and r["reference"]["matchs"] == 3 and r["reference"]["avec_cotes_betpawa"] == 2 and len(r["sources"]) == 2
    e, o = r["sources"]
    assert (e["source"], e["joignable"], e["matchs_lus"], e["retrouves"], e["retrouves_avec_cotes"], e["part_retrouvee_avec_cotes"]) == ("espn", True, 2, 2, 1, 0.5)
    assert [x["domicile"] for x in e["exemples_avec_cotes_non_retrouves"]] == ["Metapan"] and e["matchs_absents_de_la_reference"] == 0
    assert (o["source"], o["joignable"], o["matchs_lus"], o["retrouves"]) == ("openfootball", False, 0, 0) and len(o["erreurs"]) == 1
    ME.ecrire(r, tmp_path / "sortie"); ME.ecrire(r, tmp_path / "sortie")
    assert len(json.loads((tmp_path / "sortie" / "historique.json").read_text(encoding="utf-8"))) == 2
    assert "espn" in ME.resume(r) and "INJOIGNABLE" in ME.resume(r)


def test_configuration_du_depot_coherente():
    conf = ME.config()
    noms = [s["nom"] for s in conf["sources"]]
    assert conf["mode"] == "mesure" and noms == ["matchendirect", "espn", "openfootball"] and len(set(noms)) == len(noms)
    assert [s["role"] for s in conf["sources"]] == ["principale", "secours", "secours"]
    for n in noms:
        assert hasattr(ME._source(n), "lire") and ME._source(n).NOM == n
