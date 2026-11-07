import datetime, json, os, pytest
import derniers_onglets as do, integration_calibration as ic, pouvoir_predictif as pp

R = ic.RACINE
D = do.construire()
FLUX = {m["match_id"]: m for m in ic.lire_flux((datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=do.FENETRE_JOURS)).isoformat(), None, tous=True)}
COUVERTS = [i for i in D["matchs"] if i in FLUX]
SANS = [i for i, m in FLUX.items() if not (m.get("division") and m.get("fd_dom") and m.get("fd_ext"))]

def test_donnees_presentes(): assert len(COUVERTS) >= 3 and len(SANS) >= 3

# ---- 3+ matchs couverts : chaque ligne est un VRAI match de l'historique, strictement avant le match, du bon cote
@pytest.mark.parametrize("k", range(3))
def test_lignes_reelles_et_avant_le_match(k):
    i = COUVERTS[k * (len(COUVERTS) // 3)]; m = FLUX[i]; d = D["matchs"][i]; H = ic.historique(m["division"]); jour = m["date"]
    index = {(datetime.date.fromordinal(h[0]).isoformat(), h[2], h[3]): (h[4], h[5]) for h in H}
    for cle, equipe, dom in (("dom", m["fd_dom"], True), ("ext", m["fd_ext"], False), ("dom_ext", m["fd_dom"], False), ("ext_dom", m["fd_ext"], True)):
        for date, adv, mq, enc in d[cle]:
            assert date < jour
            cle_h = (date, equipe, adv) if dom else (date, adv, equipe)
            assert cle_h in index and index[cle_h] == ((mq, enc) if dom else (enc, mq))
    for date, domflag, mq, enc in d["h2h"]:
        assert date < jour and len(d["h2h"]) <= 10
        a, b = (m["fd_dom"], m["fd_ext"]) if domflag == 1 else (m["fd_ext"], m["fd_dom"])
        assert index[(date, a, b)] == ((mq, enc) if domflag == 1 else (enc, mq))

# ---- 3+ matchs non couverts : aucune entree, rien d'invente
@pytest.mark.parametrize("k", range(3))
def test_match_non_couvert_sans_entree(k): assert SANS[k * (len(SANS) // 3)] not in D["matchs"]

def test_sortie_deterministe_hors_horodatage():
    a, b = do.construire(), do.construire(); a.pop("genere_le"); b.pop("genere_le"); assert a == b

# ---- pages : le module est charge AVANT le script du moteur, sur chaque page concernee, et pas sur la page Europe (aucune donnee couverte)
PAGES = {"pronostics_omega": "archetype_omega", "pronostics_gamma": "archetype_gamma", "pronostics_dc": "archetype_dc", "pronostics_mixte": "archetype_mixte", "pronostics_v": "archetype_v",
         "pronostics_v2r": "archetype_v2r", "pronostics_v3": "archetype_v3", "archetype": "archetype", "pronostics_comportement": "archetype_comportement"}
@pytest.mark.parametrize("page,js", sorted(PAGES.items()))
def test_page_charge_le_module_avant_le_moteur(page, js):
    s = open(os.path.join(R, page + ".html"), encoding="utf-8").read()
    assert "af-derniers-onglets.css" in s and s.index("af-derniers-onglets.js") < s.index(js + ".js")
    assert "afAttend" in open(os.path.join(R, js + ".js"), encoding="utf-8").read()
def test_page_europe_inchangee(): assert "af-derniers-onglets" not in open(os.path.join(R, "pronostics_europe.html"), encoding="utf-8").read()
