"""Enquête assemblage du 01/11/2026 : contrôles d'intégrité (3 cas qui passent, 3 qui échouent par règle), cas réel de la Série B, reproductibilité."""
from __future__ import annotations

import copy
import json
import types
from pathlib import Path

import pytest

import assemblage_equipes as AE
import controle_assemblage as C
from moteur_dc import donnees as D

RACINE = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "assemblage_serie_b_2026-11-01.json").read_text(encoding="utf-8"))


def _eq(nom, matchs, comp="x : ligue"):
    return {"cle_cache": f"https://www.matchendirect.fr/equipe/{nom}_abcdefghijklmnopqrstu.html||{comp}", "competition": comp, "nom_matchendirect": nom.title(), "matchs": matchs}


def _m(date, dom, adv, g, c):
    return {"date": date, "domicile": dom, "adversaire": adv, "buts_marques": g, "buts_encaisses": c}


def strict():
    """Variante proposée du chargeur : un alias n'est rattaché que si l'autre équipe NOMME explicitement la nôtre (jamais sur « adversaire aussi inconnu »)."""
    src = (RACINE / "moteur_dc" / "donnees.py").read_text(encoding="utf-8")
    nouveau = src.replace("(o2 == t or not res2)", "(o2 == t)")
    assert nouveau != src
    mod = types.ModuleType("dc_strict")
    mod.__package__, mod.__file__ = "moteur_dc", str(RACINE / "moteur_dc" / "donnees.py")
    exec(compile(nouveau, "dc_strict", "exec"), mod.__dict__)
    return mod.Ligues


# --- 1. auto-rencontre brute ------------------------------------------------------------------------------------------
def test_auto_rencontre_brute_passe_et_echoue():
    ok = {"equipes": [_eq("cerro", [_m("2026-05-01", True, "Cerro Largo", 1, 0)]), _eq("virtus", [_m("2026-05-01", False, "Arezzo", 0, 1)]),
                      _eq("arezzo", [_m("2026-05-01", True, "Virtus Entella", 1, 0)])]}
    assert C.auto_rencontres_brutes(ok) == []
    assert C.auto_rencontres_brutes({"equipes": [_eq("pise", [])]}) == []
    assert C.auto_rencontres_brutes({"equipes": [_eq("yangon-city", [_m("2026-10-11", True, "Yangon", 1, 0)])]}) == []
    for adv in ("Cerro", "CERRO", "cerro"):
        r = C.auto_rencontres_brutes({"equipes": [_eq("cerro", [_m("2026-05-29", True, adv, 2, 0)])]})
        assert len(r) == 1 and r[0]["date"] == "2026-05-29"


# --- 2. doublons -------------------------------------------------------------------------------------------------------
def test_doublon_dans_la_liste_d_une_equipe():
    base = [_m("2026-05-01", True, "B", 1, 0), _m("2026-05-08", False, "C", 0, 0)]
    assert C.doublons_par_equipe({"equipes": [_eq("a", base)]}) == []
    assert C.doublons_par_equipe({"equipes": [_eq("a", base + [_m("2026-05-01", True, "B", 2, 0)])]}) == []          # autre score : autre match
    assert C.doublons_par_equipe({"equipes": [_eq("a", base + [_m("2026-05-01", False, "B", 1, 0)])]}) == []         # autre lieu
    for extra in ([_m("2026-05-01", True, "B", 1, 0)], [_m("2026-05-08", False, "c", 0, 0)], [_m("2026-05-01", True, "B", 1, 0)] * 2):
        r = C.doublons_par_equipe({"equipes": [_eq("a", base + extra)]})
        assert r and r[0]["fois"] >= 2


# --- 3. incohérence croisée -------------------------------------------------------------------------------------------
def test_incoherence_croisee_scores_non_inverses():
    def doc(sa, sb):
        return {"equipes": [_eq("alpha", [_m("2026-05-01", True, "Beta", *sa)]), _eq("beta", [_m("2026-05-01", False, "Alpha", *sb)])]}
    assert C.incoherences_croisees(doc((2, 1), (1, 2))) == []
    assert C.incoherences_croisees(doc((0, 0), (0, 0))) == []
    assert C.incoherences_croisees({"equipes": [_eq("alpha", [_m("2026-05-01", True, "Gamma", 2, 1)])]}) == []        # l'autre n'est pas dans le cache
    for sa, sb in (((2, 1), (2, 1)), ((3, 0), (1, 1)), ((1, 1), (0, 2))):
        assert len(C.incoherences_croisees(doc(sa, sb))) >= 1


# --- 4. volumes, couverture, bilan ----------------------------------------------------------------------------------------
def test_comparaison_des_volumes_et_championnats_passes_a_zero():
    av = {"a": {"equipes": 10, "identites": 10, "matchs": 50}, "b": {"equipes": 4, "identites": 4, "matchs": 20}, "c": {"equipes": 3, "identites": 3, "matchs": 9}}
    r = C.comparer_volumes(av, av)
    assert r["passes_a_zero"] == [] and r["perdent_des_equipes"] == [] and r["total_avant"] == r["total_apres"] == 79
    ap = {"a": {"equipes": 10, "identites": 10, "matchs": 50}, "b": {"equipes": 0, "identites": 0, "matchs": 0}, "c": {"equipes": 2, "identites": 2, "matchs": 4}}
    r = C.comparer_volumes(av, ap)
    assert r["passes_a_zero"] == ["b"] and set(r["perdent_des_equipes"]) == {"b", "c"} and r["total_apres"] == 54
    assert C.comparer_volumes(av, {})["passes_a_zero"] == ["a", "b", "c"]
    assert C.comparer_volumes({}, av)["passes_a_zero"] == []


def test_championnat_attendu_sans_match_et_controle_global():
    doc = {"equipes": [_eq("a", [_m("2026-05-01", True, "B", 1, 0)], "x : l1"), _eq("b", [_m("2026-05-01", False, "A", 0, 1)], "x : l1")]}
    assert C.manquants(doc, {"x : l1"}) == []
    assert C.manquants(doc, set()) == []
    assert C.manquants(doc, {"x : l1", "y : l2"}) == ["y : l2"]
    assert C.manquants(doc, {"z : l3", "y : l2"}) == ["y : l2", "z : l3"]
    assert C.controler(doc, {"x : l1"})["ok"]
    r = C.controler(doc, {"x : l1", "y : l2"})
    assert not r["ok"] and r["violations"]["championnats_attendus_sans_match"] == 1
    sale = copy.deepcopy(doc)
    sale["equipes"][0]["matchs"].append(_m("2026-05-01", True, "B", 1, 0))
    assert not C.controler(sale)["ok"]                                                                              # doublon bloquant


def test_la_verification_bloque_le_pipeline(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"equipes": [_eq("a", [_m("2026-05-01", True, "B", 1, 0)]), _eq("b", [_m("2026-05-01", False, "A", 0, 1)])]}), encoding="utf-8")
    assert C.main(["--assemblage", str(ok), "--verifier"]) == 0
    mauvais = tmp_path / "mauvais.json"
    mauvais.write_text(json.dumps({"equipes": [_eq("a", [_m("2026-05-01", True, "A", 1, 0)])]}), encoding="utf-8")
    assert C.main(["--assemblage", str(mauvais), "--verifier"]) == 1
    assert C.main(["--assemblage", str(mauvais)]) == 0                                                              # sans --verifier : information seulement


# --- 5. cas réel : Série B du 01/11/2026 --------------------------------------------------------------------------------
def test_serie_b_reelle_chargeur_actuel_fabrique_virtus_contre_virtus():
    L = D.Ligues(FIXTURE)
    lg = "italie : série b"
    auto = [m for m in L.matchs[lg] if m["dom"] == m["ext"]]
    assert len(FIXTURE["equipes"]) == 14                                                    # l'assemblage brut n'a que 14 clubs de Série B sur 20
    assert len(auto) == 1 and auto[0]["date"] == "2026-09-19" and "virtus" in auto[0]["dom"]    # défaut démontré, non corrigé dans le moteur
    assert len({m[k] for m in L.matchs[lg] for k in ("dom", "ext")}) == 18                   # Cremonese et Mantova absorbés par d'autres clubs


def test_serie_b_reelle_chargeur_strict_garde_les_20_clubs_sans_auto_rencontre():
    L = strict()(FIXTURE)
    lg = "italie : série b"
    ms = L.matchs[lg]
    assert [m for m in ms if m["dom"] == m["ext"]] == []
    ident = {m[k] for m in ms for k in ("dom", "ext")}
    assert len(ident) == 20                                                                 # les 20 clubs de la Série B
    assert any("cremonese" in str(L.noms.get(i, i)).lower() for i in ident) and any("mantova" in str(L.noms.get(i, i)).lower() for i in ident)
    clefs = [(m["date"], frozenset((m["dom"], m["ext"]))) for m in ms]
    assert len(clefs) == len(set(clefs))                                                    # aucun doublon de rencontre
    cles_cache = [x["cle_cache"] for x in FIXTURE["equipes"]]
    assert len({L.equipe(k) for k in cles_cache}) == len(cles_cache)                        # aucune identité de club du cache fusionnée avec une autre


# --- 6. non-régression sur tous les championnats (assemblage commité) ---------------------------------------------------
def test_chargeur_strict_ne_perd_aucun_match_et_ne_cree_aucune_auto_rencontre():
    doc = json.loads((RACINE / "data" / "assemblage" / "equipes.json").read_text(encoding="utf-8"))
    cur, str_ = D.Ligues(doc), strict()(doc)
    brut = len(C.auto_rencontres_brutes(doc))
    tot = lambda L: sum(len(v) for v in L.matchs.values())
    auto = lambda L: sum(1 for v in L.matchs.values() for m in v if m["dom"] == m["ext"])
    assert tot(str_) >= tot(cur)
    assert auto(str_) <= auto(cur) and auto(str_) <= brut                                   # il ne reste que les erreurs de la source
    for lg, v in cur.matchs.items():                                                          # championnat par championnat : jamais moins de matchs
        assert len(str_.matchs.get(lg, [])) >= len(v), lg
    cles = [x["cle_cache"] for x in doc["equipes"]]
    assert len({str_.equipe(k) for k in cles}) == len({cur.equipe(k) for k in cles}) == len(cles)   # identités des clubs du cache conservées


# --- 7. reproductibilité -----------------------------------------------------------------------------------------------------
def test_assemblage_reproductible_a_partir_des_memes_entrees():
    cache = json.loads((RACINE / "cache_equipes_saison.json").read_text(encoding="utf-8"))
    corr = json.loads((RACINE / "data" / "correspondances" / "equipes.json").read_text(encoding="utf-8"))["divisions"]
    a1, b1 = AE.assemble(cache, [], corr)
    a2, b2 = AE.assemble(copy.deepcopy(cache), [], copy.deepcopy(corr))
    assert json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True) and b1 == b2
    fd = [{"date": "2026-10-01", "home_team": "A", "away_team": "B", "full_time_home_goals": 1, "full_time_away_goals": 0, "competition_code": "X", "season": "2026-27"}]
    med = [{"date": AE._date("2026-10-01"), "domicile": "A", "exterieur": "B", "competition": "x", "buts": (1, 0)}]
    assert AE.construit_correspondances(fd, med) == AE.construit_correspondances(fd, med)
    assert len(a1) == len(cache)                                                              # une entrée du cache = une équipe assemblée, rien de perdu ici
