"""Juges du super pronostic : chaque règle est testée sur 3 cas qui passent et 3 cas qui échouent."""
from matrice_scenarios import juges as J

SEUILS = {"q1_contrarien": 0.77, "q1_outsider": 0.85, "q99_ecart_cote": 0.17}


def cand(**k):
    base = {"j1": 0.9, "j4": 0.9, "valeur": 0.05, "cote": 1.5, "probabilite": 0.66, "p_calibree": 0.66, "ecart_cote": 0.0}
    base.update(k)
    return base


def juge(cands):
    J.juger_candidats(cands, SEUILS)
    return cands


def test_contrarien_passe():
    for j1 in (0.77, 0.9, 1.0):
        assert juge([cand(j1=j1)])[0]["juges"]["contrarien"]


def test_contrarien_echoue():
    for j1 in (0.0, 0.5, 0.76):
        assert not juge([cand(j1=j1)])[0]["juges"]["contrarien"]


def test_outsider_passe():
    for j4 in (0.85, 0.95, 1.0):
        assert juge([cand(j4=j4)])[0]["juges"]["outsider"]


def test_outsider_echoue():
    for j4 in (0.0, 0.6, 0.84):
        assert not juge([cand(j4=j4)])[0]["juges"]["outsider"]


def test_premiers_principes():
    for v in (0.01, 0.05, 0.3):
        assert juge([cand(valeur=v)])[0]["juges"]["premiers_principes"]
    for v in (0.0, -0.05, -0.4):
        assert not juge([cand(valeur=v)])[0]["juges"]["premiers_principes"]


def test_executant_cote_et_coherence():
    for c, e in ((1.26, 0.0), (1.5, 0.1), (3.0, 0.17)):
        assert juge([cand(cote=c, ecart_cote=e)])[0]["juges"]["executant"]
    for c, e in ((1.25, 0.0), (1.1, 0.0), (1.5, 0.3)):     # cote trop basse / cote incohérente avec la probabilité
        assert not juge([cand(cote=c, ecart_cote=e)])[0]["juges"]["executant"]


def test_expansionniste_domine():
    a, b = cand(probabilite=0.7, cote=1.6), cand(probabilite=0.6, cote=1.3)     # b est dominé par a (moins sûr ET moins payé)
    r = juge([a, b])
    assert r[0]["juges"]["expansionniste"] and not r[1]["juges"]["expansionniste"]


def test_dangereux_si_un_juge_cle_echoue():
    assert not juge([cand()])[0]["dangereux"]
    assert juge([cand(j1=0.1)])[0]["dangereux"]
    assert juge([cand(j4=0.1)])[0]["dangereux"]
    assert juge([cand(cote=1.1)])[0]["dangereux"]


def mj(buts="Match ouvert : beaucoup de buts (3,0 attendus)", btts=None, extremes=False, dc="12", cote_princ=1.28):
    t = [{"cle": "resultat", "court": "Match serré, pas de favori net", "texte": "Match équilibré : A 36 % · nul 26 % · B 38 %."}]
    if buts:
        t.append({"cle": "buts", "court": buts, "texte": "Match offensif : 3,0 buts attendus."})
    if btts:
        t.append({"cle": "deux_marquent", "court": btts, "texte": "Les deux équipes marquent souvent dans les séries croisées."})
    if extremes:
        t.append({"cle": "extremes", "texte": "Séries avec un score extrême."})
    return {"tendances": t, "selections": [{"role": "principal", "groupe": "over_under_1.5", "choix": "plus", "cote": cote_princ, "libelle": "Plus de 1,5 buts"},
                                          {"role": "tendance", "groupe": "double_chance", "choix": dc, "cote": 1.3, "libelle": "x"}]}


def combo(g, sel, cote, proba=0.6):
    return {"groupe": g, "selection": sel, "libelle": J.libelle_combine(g, sel), "famille": "combine", "cote": cote, "probabilite": proba, "combine": True}


def test_super_combine_match_ouvert_et_resultat_propose():
    r = J.super_pronostic({"candidats": [combo("dc_total_1.5", "12|plus", 1.62)]}, mj())
    assert r and r["type"] == "combine" and r["cote_combine"] == 1.62 and "Betpawa" in r["raison"]


def test_super_combine_match_ferme_moins_de_buts():
    r = J.super_pronostic({"candidats": [combo("dc_total_3.5", "1N|moins", 1.45), combo("dc_total_1.5", "1N|plus", 1.7)]},
                          mj(buts="Match fermé : peu de buts (2,2 attendus)", dc="1N"))
    assert r and r["jambes"][0]["selection"] == "1N|moins"


def test_super_rien_pas_de_nul_avec_match_ferme():
    assert J.super_pronostic({"candidats": [combo("dc_total_3.5", "12|moins", 1.8)]}, mj(buts="Match fermé : peu de buts (2,2 attendus)")) is None


def test_super_combine_les_deux_marquent():
    r = J.super_pronostic({"candidats": [combo("dc_btts", "12|Oui", 1.9)]}, mj(buts=None, btts="Les deux équipes marquent souvent"))
    assert r and r["jambes"][0]["groupe"] == "dc_btts"


def test_super_rien_sans_cote_combine_trouvee():
    assert J.super_pronostic({"candidats": []}, mj()) is None


def test_super_rien_si_le_combine_ne_paie_pas_plus_que_le_principal():
    assert J.super_pronostic({"candidats": [combo("dc_total_1.5", "12|plus", 1.4)]}, mj(cote_princ=1.5)) is None


def test_super_rien_si_les_buts_vont_a_l_inverse_de_la_page():
    assert J.super_pronostic({"candidats": [combo("dc_total_2.5", "12|moins", 1.8)]}, mj()) is None          # page : match ouvert
    assert J.super_pronostic({"candidats": [combo("dc_total_2.5", "12|plus", 1.8)]}, mj(buts="Match fermé : peu de buts (2,2 attendus)")) is None
    assert J.super_pronostic({"candidats": [combo("dc_total_2.5", "12|moins", 1.8)]}, mj(buts="Match fermé : peu de buts (2,2 attendus)", extremes=True)) is None   # extrême : 3,5 ou 4,5 seulement


def test_super_rien_si_le_resultat_n_est_pas_celui_de_la_page():
    assert J.super_pronostic({"candidats": [combo("dc_total_1.5", "1N|plus", 1.7)]}, mj(dc="12")) is None
