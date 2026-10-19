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
