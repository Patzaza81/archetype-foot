"""Audit des identités : un alias rattaché doit être prouvé par l'identifiant du match (url_match), pas par le nom ni par le score."""
import json

import pytest

import audit_identites as A
from moteur_dc import donnees as D

LG = "pays : ligue"
ID = "a" * 25


def eq(nom, matchs):
    return {"cle_cache": f"https://www.matchendirect.fr/equipe/{nom.lower()}_{'z' * 25}.html||{LG}", "competition": LG, "nom_matchendirect": nom, "matchs": matchs}


def m(adv, dom, gm, gc, url=None, date="2026-10-01"):
    return {"date": date, "adversaire": adv, "domicile": dom, "buts_marques": gm, "buts_encaisses": gc, "url_match": url}


def url(i):
    return f"/live-score/x-y_{i}.html"


def doc(a_matchs, foo_matchs):
    return {"equipes": [eq("Alpha", a_matchs), eq("Foo", foo_matchs)]}


def cle(nom):
    return f"https://www.matchendirect.fr/equipe/{nom.lower()}_{'z' * 25}.html||{LG}"


# --- cas où la preuve existe (3) ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("score", [(2, 1), (0, 0), (3, 3)])
def test_alias_prouve_par_le_meme_identifiant_de_match(score):
    d = doc([m("Foo 2", True, *score, url(ID))], [m("Alpha", False, score[1], score[0], url(ID))])
    p = A.preuves_par_identifiant(d)
    assert set(p[(LG, D.norm("Foo 2"))]) == {cle("Foo")}
    r = A.auditer(d)
    assert r["alias_rattaches"] == 1 and r["prouves_par_identifiant"] == 1 and not r["sans_preuve_d_identifiant"]


# --- cas où la preuve manque (3) ---------------------------------------------------------------------------------------
def test_memes_noms_et_scores_mais_identifiants_differents_ne_prouvent_rien():
    d = doc([m("Foo 2", True, 2, 1, url(ID))], [m("Alpha", False, 1, 2, url("b" * 25))])
    assert not A.preuves_par_identifiant(d)
    r = A.auditer(d)
    assert r["alias_rattaches"] == 1 and r["prouves_par_identifiant"] == 0 and len(r["sans_preuve_d_identifiant"]) == 1


def test_sans_url_match_la_preuve_est_absente():
    d = doc([m("Foo 2", True, 2, 1, None)], [m("Alpha", False, 1, 2, None)])
    assert not A.preuves_par_identifiant(d)
    assert len(A.auditer(d)["sans_preuve_d_identifiant"]) == 1


def test_un_alias_prouve_pour_un_autre_club_est_un_desaccord():
    # un chargeur fautif rattacherait « Foo 2 » à Foo alors que l'identifiant du match désigne Beta
    class _UF:
        def trouve(self, x):
            return cle("Foo") if x == f"?{LG}|{D.norm('Foo 2')}" else x

    class Fautif:
        _uf = _UF()

    a = [m("Foo 2", True, 2, 1, url(ID))]
    foo = [m("Alpha", False, 1, 2, url("c" * 25), date="2026-10-02")]
    beta = [m("Alpha", False, 1, 2, url(ID))]
    d = {"equipes": [eq("Alpha", a), eq("Foo", foo), eq("Beta", beta)]}
    assert set(A.preuves_par_identifiant(d)[(LG, D.norm("Foo 2"))]) == {cle("Beta")}
    r = A.auditer(d, Fautif())
    assert r["alias_rattaches"] == 1 and len(r["contredits_par_identifiant"]) == 1 and r["prouves_par_identifiant"] == 0
    # et le vrai chargeur, sur les mêmes données, rattache bien à Beta
    assert A.auditer(d)["prouves_par_identifiant"] == 1


def test_identifiant_extrait_de_l_adresse():
    assert A.id_match("/live-score/a-b_9vc5rqfvidznnj4fz2nyuo55g.html") == "9vc5rqfvidznnj4fz2nyuo55g"
    assert A.id_match("/live-score/a-b.html") is None and A.id_match(None) is None


# --- données réelles -----------------------------------------------------------------------------------------------------
@pytest.mark.donnees_du_jour
def test_assemblage_courant_aucun_alias_rattache_sans_preuve_d_identifiant():
    if not D.ASSEMBLAGE.exists():
        pytest.skip("assemblage absent")
    r = A.auditer(json.loads(D.ASSEMBLAGE.read_text(encoding="utf-8")))
    assert not r["sans_preuve_d_identifiant"] and not r["contredits_par_identifiant"], r
