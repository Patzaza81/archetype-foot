"""Archive de test (archive_donnees_test.py) : chaque règle testée sur au moins 3 cas qui passent et 3 qui échouent."""
import datetime
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import archive_donnees_test as adt  # noqa: E402

UTC = datetime.timezone.utc


def t(j, h, m=0):
    return datetime.datetime(2026, 9, j, h, m, tzinfo=UTC)


# --- coup d'envoi ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("date,heure,attendu", [
    ("2026-09-27", "17:00", t(27, 16)),
    ("2026-09-27", "00:30", t(26, 23, 30)),
    ("2026-09-28", "9:05", t(28, 8, 5)),
])
def test_coup_d_envoi_lisible(date, heure, attendu):
    assert adt.coup_d_envoi_utc(date, heure) == attendu


@pytest.mark.parametrize("date,heure", [("2026-09-27", None), (None, "17:00"), ("2026-09-27", "17'"),
                                        ("27/09/2026", "17:00")])
def test_coup_d_envoi_jamais_devine(date, heure):
    assert adt.coup_d_envoi_utc(date, heure) is None


# --- figé au coup d'envoi -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("existant,coup,maintenant", [
    (None, t(27, 16), t(28, 1)),                           # jamais archivé : on écrit, même tard
    ({"score": None}, t(27, 16), t(27, 15, 59)),           # une minute avant le coup d'envoi
    ({"score": None}, None, t(27, 23)),                    # heure inconnue : jusqu'au jour du match inclus
])
def test_mise_a_jour_autorisee(existant, coup, maintenant):
    assert adt.peut_mettre_a_jour(existant, "2026-09-27", coup, maintenant) is True


@pytest.mark.parametrize("existant,coup,maintenant", [
    ({"score": None}, t(27, 16), t(27, 16)),               # pile au coup d'envoi
    ({"score": None}, None, t(28, 0, 1)),                  # heure inconnue, lendemain
    ({"score": {"buts_dom": 1, "buts_ext": 0}}, t(27, 16), t(27, 10)),   # score présent : jamais
])
def test_mise_a_jour_refusee(existant, coup, maintenant):
    assert adt.peut_mettre_a_jour(existant, "2026-09-27", coup, maintenant) is False


# --- anti-fuite -----------------------------------------------------------------------------------------------------

def m(date, bm=1, be=0, dom=True):
    return {"date": date, "domicile": dom, "adversaire": "X", "buts_marques": bm, "buts_encaisses": be}


@pytest.mark.parametrize("date_equipe", ["2026-09-26", "2026-08-01", "2025-12-31"])
def test_match_d_avant_garde(date_equipe):
    gardes, apres, inval = adt.matchs_avant([m(date_equipe)], "2026-09-27")
    assert len(gardes) == 1 and apres == 0 and inval == 0


@pytest.mark.parametrize("date_equipe", ["2026-09-27", "2026-09-28", "2026-10-15"])
def test_match_du_jour_ou_apres_retire(date_equipe):
    gardes, apres, _ = adt.matchs_avant([m(date_equipe)], "2026-09-27")
    assert gardes == [] and apres == 1


@pytest.mark.parametrize("brut", [m(None), m("2026-09-20", bm=None), m("2026-09-20", be=-1)])
def test_match_invalide_retire(brut):
    gardes, _, inval = adt.matchs_avant([brut], "2026-09-27")
    assert gardes == [] and inval == 1


def test_ordre_chronologique():
    gardes, _, _ = adt.matchs_avant([m("2026-09-20"), m("2026-08-01"), m("2026-09-01")], "2026-09-27")
    assert [g["date"] for g in gardes] == ["2026-08-01", "2026-09-01", "2026-09-20"]


# --- lecture du score -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("texte,attendu", [("2-1", (2, 1)), (" 0 - 0 ", (0, 0)), ("10-3", (10, 3))])
def test_score_lisible(texte, attendu):
    assert adt.lit_score(texte) == attendu


@pytest.mark.parametrize("texte", [None, "", "2-", "2:1", "reporté", 21])
def test_score_illisible(texte):
    assert adt.lit_score(texte) is None


# --- bout en bout : écriture, gel, score --------------------------------------------------------------------------

def signal(mid, dom, ext, heure="17:00", cotes=True):
    return {"match_id": mid, "date": "2026-09-27", "heure_cameroun": heure, "domicile": dom, "exterieur": ext,
            "competition": "Italie :\n   Série C", "url_match": f"u/{mid}",
            "cotes_manuelles": {"1x2": {"1": 2.0, "N": 3.2, "2": 3.5}} if cotes else None,
            "TOUS_MARCHES_EVALUES": [], "moteur_v2_6_9": {"statut": "NON_EXPORTABLE", "selection": {}}}


def stats_ok():
    return {"matchs_domicile_bruts": [m("2026-09-10"), m("2026-09-27")],   # le 2e est le jour même : retiré
            "matchs_exterieur_bruts": [m("2026-09-14", dom=False)]}


def test_bout_en_bout(tmp_path):
    dossier = str(tmp_path / "archive_test")
    comp = "Italie :\n   Série C"
    stats = {("A", comp): stats_ok(), ("B", comp): stats_ok(), ("C", comp): {"raison_non_traite": "aucun_match"}}
    sig = [signal("m1", "A", "B"), signal("m2", "C", "B", heure="20:00"), signal("m3", "A", "B", cotes=False)]
    b = adt.archive_run(sig, stats, {"u/m1": {"url_equipe_domicile": "eqA"}}, dossier=dossier,
                        maintenant=t(27, 1), commit="abc")
    assert b["ecrits"] == 2 and b["testables"] == 1                     # m3 sans cote : pas archivé
    d = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))
    assert d["m1"]["testable"] and not d["m2"]["testable"]
    assert d["m1"]["equipe_dom"]["url_equipe"] == "eqA"
    assert d["m1"]["equipe_dom"]["matchs_retires_apres_date"] == 1
    assert [x["date"] for x in d["m1"]["equipe_dom"]["matchs"]] == ["2026-09-10", "2026-09-14"]

    # 2e run après le coup d'envoi de m1 (16h UTC) mais avant m2 (19h UTC) : m1 figé, m2 remplacé
    b2 = adt.archive_run(sig, stats, {}, dossier=dossier, maintenant=t(27, 17), commit="def")
    assert b2["figes_non_modifies"] == 1 and b2["ecrits"] == 1
    d = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))
    assert d["m1"]["run"]["commit"] == "abc" and d["m2"]["run"]["commit"] == "def"

    # scores : m1 joué et connu, m2 pas encore joué à 18h UTC
    hist = tmp_path / "historique.json"
    hist.write_text(json.dumps([{"date": "2026-09-27", "matchs": [{"match_id": "m1", "score": "2-1"},
                                                                  {"match_id": "m2", "score": "0-0"}]}]))
    s = adt.complete_scores(dossier, str(hist), maintenant=t(27, 18))
    assert s["scores_ecrits"] == 1
    d = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))
    assert d["m1"]["score"]["buts_dom"] == 2 and d["m2"]["score"] is None

    # un score existant n'est jamais modifié
    hist.write_text(json.dumps([{"date": "2026-09-27", "matchs": [{"match_id": "m1", "score": "5-5"}]}]))
    adt.complete_scores(dossier, str(hist), maintenant=t(28, 3))
    d = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))
    assert (d["m1"]["score"]["buts_dom"], d["m1"]["score"]["buts_ext"]) == (2, 1)
    assert adt.bilan_archive(dossier)["testables_avec_score"] == 1


def test_fichier_identique_si_contenu_identique(tmp_path):
    a, b = str(tmp_path / "a.json.gz"), str(tmp_path / "b.json.gz")
    adt.sauve_fichier(a, {"x": 1, "y": [1, 2]})
    adt.sauve_fichier(b, {"y": [1, 2], "x": 1})
    assert open(a, "rb").read() == open(b, "rb").read()


# --- rapprochement match -> équipes par adresse exacte -------------------------------------------------------------

def _cache(*equipes, comp="Italie :\n   Série C Girone A"):
    return {f"https://www.matchendirect.fr/equipe/{slug}_abc123.html||{' '.join(comp.split()).lower()}":
            {"horodatage": "x", "resultat": {"matchs_domicile_bruts": [], "matchs_exterieur_bruts": []}}
            for slug in equipes}


URL = "https://www.matchendirect.fr/live-score/{}_zz9.html"
COMP = "Italie :\n   Série C Girone A"


@pytest.mark.parametrize("slug_match,equipes,dom,ext", [
    ("pescara-spezia", ("pescara", "spezia", "foggia"), "pescara", "spezia"),
    ("moghreb-rsb-berkane", ("moghreb", "rsb-berkane", "rsb"), "moghreb", "rsb-berkane"),
    ("real-salt-lake-new-england", ("real-salt-lake", "new-england", "real"), "real-salt-lake", "new-england"),
])
def test_equipes_retrouvees_exactement(slug_match, equipes, dom, ext):
    idx = adt.index_cache_saison(_cache(*equipes))
    (u_dom, _), (u_ext, _) = adt.equipes_du_match(URL.format(slug_match), COMP, idx)
    assert f"/{dom}_" in u_dom and f"/{ext}_" in u_ext


@pytest.mark.parametrize("slug_match,equipes,comp", [
    ("pescara-spezia", ("pescara",), COMP),                              # équipe extérieure absente du cache
    ("pescara-spezia", ("pescara", "spezia"), "Italie : Série B"),       # autre compétition : jamais
    ("a-b-c", ("a", "b-c", "a-b", "c"), COMP),                           # deux découpages possibles : aucun choisi
])
def test_equipes_non_retrouvees(slug_match, equipes, comp):
    idx = adt.index_cache_saison(_cache(*equipes))
    assert adt.equipes_du_match(URL.format(slug_match), comp, idx) is None


@pytest.mark.parametrize("url,attendu", [
    ("https://www.matchendirect.fr/equipe/rsb-berkane_8q9aa.html", "rsb-berkane"),
    ("/live-score/pescara-spezia_c7mg423.html", "pescara-spezia"),
    (None, None),
    ("https://www.matchendirect.fr/equipe/", None),
])
def test_slug_adresse(url, attendu):
    assert adt.slug_adresse(url) == attendu


def test_archive_depuis_fichiers(tmp_path):
    cache = _cache("pescara", "spezia")
    for e in cache.values():
        e["resultat"] = stats_ok()
    (tmp_path / "cache.json").write_text(json.dumps(cache))
    s = signal("m1", "Pescara", "Spezia")
    s["competition"], s["url_match"] = COMP, URL.format("pescara-spezia")
    autre = signal("m2", "Inconnu", "Spezia")
    autre["competition"], autre["url_match"] = COMP, URL.format("inconnu-spezia")
    (tmp_path / "precalcul.json").write_text(json.dumps({"signaux": [s, autre]}))
    dossier = str(tmp_path / "archive_test")
    b = adt.archive_depuis_fichiers(str(tmp_path / "precalcul.json"), str(tmp_path / "cache.json"), dossier,
                                    maintenant=t(27, 1), commit="x")
    assert b["ecrits"] == 2 and b["testables"] == 1
    d = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))
    assert d["m1"]["testable"] and "/pescara_" in d["m1"]["equipe_dom"]["url_equipe"]
    assert d["m2"]["equipe_dom"]["statut"] == "ABSENTE" and not d["m2"]["testable"]


# --- une donnée plus ancienne ne remplace jamais une plus récente --------------------------------------------------

@pytest.mark.parametrize("pris_existant,maintenant", [
    ("2026-09-27T05:00:00Z", t(27, 1)),        # precalcul.json resté d'avant
    ("2026-09-27T01:00:01Z", t(27, 1)),
    ("2026-09-28T00:00:00Z", t(27, 23)),
])
def test_donnee_plus_ancienne_refusee(pris_existant, maintenant):
    assert adt._plus_recent({"run": {"pris_le": pris_existant}}, maintenant) is True


@pytest.mark.parametrize("existant,maintenant", [
    ({"run": {"pris_le": "2026-09-26T21:28:00Z"}}, t(27, 1)),
    ({"run": {"pris_le": "2026-09-27T01:00:00Z"}}, t(27, 1)),   # même instant : on peut réécrire
    (None, t(27, 1)),
])
def test_donnee_plus_recente_acceptee(existant, maintenant):
    assert adt._plus_recent(existant, maintenant) is False


@pytest.mark.parametrize("texte,attendu", [
    ("2026-09-26 21:28 UTC", t(26, 21, 28)),
    ("2026-09-01 00:05 UTC", t(1, 0, 5)),
    ("2026-09-30 23:59 UTC", t(30, 23, 59)),
])
def test_genere_le_lisible(texte, attendu):
    assert adt.lit_genere_le(texte) == attendu


@pytest.mark.parametrize("texte", ["26/09/2026 21:28", None, "", "2026-09-26T21:28:00Z"])
def test_genere_le_illisible(texte):
    assert adt.lit_genere_le(texte) is None


def test_genere_le_sert_d_heure_de_reference(tmp_path):
    cache = _cache("pescara", "spezia")
    for e in cache.values():
        e["resultat"] = stats_ok()
    (tmp_path / "cache.json").write_text(json.dumps(cache))
    s = signal("m1", "Pescara", "Spezia")
    s["competition"], s["url_match"] = COMP, URL.format("pescara-spezia")
    dossier = str(tmp_path / "archive_test")
    for genere in ("2026-09-27 01:00 UTC", "2026-09-26 21:00 UTC"):          # le 2e est plus ancien : ignoré
        (tmp_path / "precalcul.json").write_text(json.dumps({"genere_le": genere, "signaux": [s]}))
        adt.archive_depuis_fichiers(str(tmp_path / "precalcul.json"), str(tmp_path / "cache.json"), dossier)
    d = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))
    assert d["m1"]["run"]["pris_le"] == "2026-09-27T01:00:00Z"


# --- point d'entrée nocturne (appelé par enregistre_scores_historique.py) ------------------------------------------

def test_execution_nocturne(tmp_path):
    cache = _cache("pescara", "spezia")
    for e in cache.values():
        e["resultat"] = stats_ok()
    (tmp_path / "cache.json").write_text(json.dumps(cache))
    s = signal("m1", "Pescara", "Spezia", heure="10:00")
    s["competition"], s["url_match"] = COMP, URL.format("pescara-spezia")
    (tmp_path / "precalcul.json").write_text(json.dumps({"genere_le": "2026-09-27 01:00 UTC", "signaux": [s]}))
    (tmp_path / "hist.json").write_text(json.dumps([{"date": "2026-09-27", "matchs": [{"match_id": "m1", "score": "1-1"}]}]))
    dossier = str(tmp_path / "data" / "archive_test")
    b = adt.execution_nocturne(str(tmp_path / "precalcul.json"), str(tmp_path / "cache.json"), dossier,
                               str(tmp_path / "hist.json"), maintenant=t(27, 12))
    assert b["avant_match"]["testables"] == 1
    assert b["scores"]["scores_ecrits"] == 1                  # coup d'envoi 09:00 UTC le 27/09, passé à 12:00 UTC
    assert b["archive"]["testables_avec_score"] == 1


def test_execution_nocturne_sans_precalcul(tmp_path):
    b = adt.execution_nocturne(str(tmp_path / "absent.json"), str(tmp_path / "c.json"), str(tmp_path / "d"),
                               str(tmp_path / "h.json"))
    assert "absent" in b["avant_match"] and b["archive"]["matchs"] == 0


def test_dossier_par_defaut_est_commite_par_le_workflow():
    assert adt.DOSSIER.replace("\\", "/") == "data/archive_test"


# --- données Football-Data (assemblage lu par contrat_moteur) -------------------------------------------------------

def fd(date, bm=1, be=0, dom=True, **extra):
    base = {"date": date, "domicile": dom, "adversaire": "X", "buts_marques": bm, "buts_encaisses": be,
            "buts_marques_mi_temps": 1, "buts_encaisses_mi_temps": 0, "tirs": 12, "tirs_concedes": 8,
            "tirs_cadres": 5, "tirs_cadres_concedes": 2, "corners": 6, "corners_concedes": 3,
            "cartons_jaunes": 2, "cartons_rouges": 0, "xg": None, "xg_concede": None,
            "source": "football-data", "provisoire": False, "saison": "2627", "url_match": None}
    base.update(extra)
    return base


def doc_assemblage(*equipes):
    return {"version_contrat": 1, "version": "1.0.0", "genere_le": "2026-09-26 23:57 UTC", "saison_football_data": "2627",
            "regle": "test", "bilan": {}, "equipes": list(equipes)}


def eq_fd(slug, matchs, comp="italie : série c girone a"):
    return {"cle_cache": f"https://www.matchendirect.fr/equipe/{slug}_abc123.html||{comp}", "competition": comp,
            "couverte_par_football_data": True, "division_football_data": "I3", "nom_football_data": slug.title(),
            "nom_matchendirect": slug.title(), "matchs": matchs}


@pytest.mark.parametrize("date_equipe", ["2026-09-26", "2026-09-01", "2026-08-10"])
def test_match_complet_d_avant_garde_en_entier(date_equipe):
    gardes, apres, inval = adt.matchs_complets_avant([fd(date_equipe)], "2026-09-27")
    assert len(gardes) == 1 and apres == 0 and inval == 0
    assert gardes[0]["corners"] == 6 and gardes[0]["buts_marques_mi_temps"] == 1 and gardes[0]["tirs_cadres"] == 5


@pytest.mark.parametrize("brut,retire,invalide", [
    (fd("2026-09-27"), 1, 0),                 # jour du match
    (fd("2026-10-02"), 1, 0),                 # après
    (fd(None), 0, 1),                         # sans date
])
def test_match_complet_du_jour_apres_ou_sans_date_retire(brut, retire, invalide):
    gardes, apres, inval = adt.matchs_complets_avant([brut], "2026-09-27")
    assert gardes == [] and apres == retire and inval == invalide


def test_match_complet_est_une_copie():
    source = [fd("2026-09-20")]
    gardes, _, _ = adt.matchs_complets_avant(source, "2026-09-27")
    gardes[0]["corners"] = 99
    assert source[0]["corners"] == 6


URL_EQ = "https://www.matchendirect.fr/equipe/{}_abc123.html"


def test_equipe_assemblage_ok_compte_les_donnees():
    doc = doc_assemblage(eq_fd("pescara", [fd("2026-09-06"), fd("2026-09-20", corners=None), fd("2026-09-27")]))
    b = adt.equipe_assemblage(doc, URL_EQ.format("pescara"), COMP, "2026-09-27")
    assert b["statut"] == "OK" and b["couverte_par_football_data"] is True
    assert len(b["matchs"]) == 2 and b["matchs_retires_apres_date"] == 1
    assert b["nb_football_data"] == 2 and b["nb_avec_mi_temps"] == 2 and b["nb_avec_corners"] == 1


@pytest.mark.parametrize("doc,url,statut", [
    (None, URL_EQ.format("pescara"), "ASSEMBLAGE_INDISPONIBLE"),
    (doc_assemblage(eq_fd("spezia", [])), URL_EQ.format("pescara"), "ABSENTE"),     # équipe absente
    (doc_assemblage(eq_fd("pescara", [])), None, "ABSENTE"),                       # adresse inconnue
])
def test_equipe_assemblage_non_disponible(doc, url, statut):
    assert adt.equipe_assemblage(doc, url, COMP, "2026-09-27")["statut"] == statut


def test_equipe_assemblage_autre_competition_jamais():
    doc = doc_assemblage(eq_fd("pescara", [fd("2026-09-06")], comp="italie : série b"))
    assert adt.equipe_assemblage(doc, URL_EQ.format("pescara"), COMP, "2026-09-27")["statut"] == "ABSENTE"


def test_charge_assemblage_valide(tmp_path):
    f = tmp_path / "equipes.json"
    f.write_text(json.dumps(doc_assemblage(eq_fd("pescara", [fd("2026-09-06")]))))
    etat = adt.charge_assemblage_sur(str(f))
    assert etat["statut"] == "OK" and etat["doc"]["version_contrat"] == 1


@pytest.mark.parametrize("contenu,debut", [
    (None, "ASSEMBLAGE_ABSENT"),                                                      # fichier absent
    ({"version_contrat": 99, "equipes": []}, "ASSEMBLAGE_REFUSE"),                    # contrat rompu
    ("pas du json {", "ASSEMBLAGE_REFUSE"),                                           # fichier illisible
])
def test_charge_assemblage_jamais_d_exception(tmp_path, contenu, debut):
    f = tmp_path / "equipes.json"
    if contenu is not None:
        f.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu))
    etat = adt.charge_assemblage_sur(str(f))
    assert etat["doc"] is None and etat["statut"].startswith(debut)


def test_archive_avec_football_data_bout_en_bout(tmp_path):
    cache = _cache("pescara", "spezia")
    for e in cache.values():
        e["resultat"] = stats_ok()
    (tmp_path / "cache.json").write_text(json.dumps(cache))
    (tmp_path / "equipes.json").write_text(json.dumps(doc_assemblage(
        eq_fd("pescara", [fd("2026-09-06"), fd("2026-09-20")]),
        eq_fd("spezia", [fd("2026-09-13", dom=False)]))))
    s = signal("m1", "Pescara", "Spezia")
    s["competition"], s["url_match"] = COMP, URL.format("pescara-spezia")
    (tmp_path / "precalcul.json").write_text(json.dumps({"genere_le": "2026-09-27 01:00 UTC", "signaux": [s]}))
    dossier = str(tmp_path / "data" / "archive_test")
    b = adt.archive_depuis_fichiers(str(tmp_path / "precalcul.json"), str(tmp_path / "cache.json"), dossier,
                                    fichier_assemblage=str(tmp_path / "equipes.json"))
    assert b["avec_football_data"] == 1
    e = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))["m1"]
    assert e["schema_version"] == 2 and e["donnees_football_data"] is True
    assert e["assemblage"]["genere_le"] == "2026-09-26 23:57 UTC"
    assert e["assemblage"]["equipe_ext"]["matchs"][0]["corners"] == 6
    assert adt.bilan_archive(dossier)["avec_football_data"] == 1


def test_archive_sans_assemblage_ecrit_quand_meme(tmp_path):
    cache = _cache("pescara", "spezia")
    for e in cache.values():
        e["resultat"] = stats_ok()
    (tmp_path / "cache.json").write_text(json.dumps(cache))
    s = signal("m1", "Pescara", "Spezia")
    s["competition"], s["url_match"] = COMP, URL.format("pescara-spezia")
    (tmp_path / "precalcul.json").write_text(json.dumps({"genere_le": "2026-09-27 01:00 UTC", "signaux": [s]}))
    dossier = str(tmp_path / "archive_test")
    b = adt.archive_depuis_fichiers(str(tmp_path / "precalcul.json"), str(tmp_path / "cache.json"), dossier,
                                    fichier_assemblage=str(tmp_path / "absent.json"))
    e = adt.charge_fichier(os.path.join(dossier, "2026-09-27.json.gz"))["m1"]
    assert b["testables"] == 1 and e["testable"] is True
    assert e["assemblage"]["statut"] == "ASSEMBLAGE_ABSENT" and e["donnees_football_data"] is False
