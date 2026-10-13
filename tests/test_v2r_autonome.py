"""Tests de l'autonomie v2r : règles figées, choix de pari, carnet, exécution de bout en bout (données synthétiques)."""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import carnet as K, execution as X, pronostics as P, regles as R  # noqa: E402

UTC = datetime.timezone.utc
HIST = [dict(domicile=i % 2 == 0, buts_marques=2, buts_encaisses=1, date=f"2026-09-{10 + i:02d}") for i in range(6)]


def match(mid, date, h=2, a=2, cotes=None, kickoff=None, hd=None):
    return dict(id=mid, date=date, ligue="L1", h=h, a=a, cotes=cotes if cotes is not None else {"BTTS - oui": 1.9},
                dom="A", ext="B", kickoff=kickoff, hd=HIST if hd is None else hd, he=HIST)


def joues(n=12):
    return [match(f"j{i}", f"2026-10-{1 + i:02d}") for i in range(n)]


# ---- règles
def test_entraine_garde_la_cellule_gagnante_et_exclut_le_futur():
    r = R.entraine(joues(12), "2026-10-13")
    assert r["entraine_sur"] == 12 and len(r["cellules"]) == 1 and r["cellules"][0]["lib"] == "BTTS - oui"
    assert R.entraine(joues(12), "2026-10-05")["entraine_sur"] == 4          # seuls les matchs avant la date
    assert R.entraine(joues(12), "2026-10-01") is None                        # rien avant
    assert R.entraine(joues(9), "2026-10-13")["cellules"] == []               # < 10 paris


def test_doit_reentrainer_cas_qui_passent():
    r = dict(cree_le="2026-10-12")
    assert R.doit_reentrainer(datetime.date(2026, 10, 13), None)
    assert R.doit_reentrainer(datetime.date(2026, 10, 19), r)                 # lundi, 7 jours
    assert R.doit_reentrainer(datetime.date(2026, 10, 19), dict(cree_le="2026-10-13"))   # lundi, 6 jours


def test_doit_reentrainer_cas_qui_echouent():
    r = dict(cree_le="2026-10-12")
    assert not R.doit_reentrainer(datetime.date(2026, 10, 14), r)             # mercredi
    assert not R.doit_reentrainer(datetime.date(2026, 10, 18), r)             # dimanche
    assert not R.doit_reentrainer(datetime.date(2026, 10, 19), dict(cree_le="2026-10-16"))   # lundi mais 3 jours


def test_regles_jamais_ecrasees():
    with tempfile.TemporaryDirectory() as d:
        r = R.entraine(joues(), "2026-10-13")
        R.ecrit(r, d)
        try:
            R.ecrit(r, d)
            assert False
        except FileExistsError:
            pass
        assert R.derniere(d)["version"] == "2026-10-13" and R.derniere(os.path.join(d, "vide")) is None


# ---- choix de pari
def regles_test():
    return R.entraine(joues(), "2026-10-13")


def test_proposer_cas_qui_passent():
    r = regles_test()
    p = P.proposer(match("n1", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z"), r)
    assert p["marche"] == "BTTS - oui" and p["cote"] == 1.9 and p["regles_version"] == "2026-10-13"
    assert P.proposer(match("n2", "2026-10-14", h=None, a=None, cotes={"BTTS - oui": 1.9, "BTTS - non": 1.9}), r)["marche"] == "BTTS - oui"
    assert P.proposer(match("n3", "2026-10-14", h=None, a=None, cotes={"BTTS - oui": 1.99}), r)


def test_proposer_cas_qui_echouent():
    r = regles_test()
    assert P.proposer(match("n", "2026-10-14", cotes={"BTTS - oui": 3.5}), r) is None       # autre tranche de cote
    assert P.proposer(match("n", "2026-10-14", cotes={"BTTS - non": 1.9}), r) is None       # autre marché
    assert P.proposer(match("n", "2026-10-14", cotes={"libellé inconnu": 1.9}), r) is None
    assert P.proposer(match("n", "2026-10-14", cotes={}), r) is None
    assert P.proposer(match("n", "2026-10-14", hd=[]), r) is None                            # pas d'historique
    r2 = dict(r, cellules=[])
    assert P.proposer(match("n", "2026-10-14"), r2) is None


# ---- carnet
def pick(mid="m", ko="2026-10-14T18:00:00Z", lib="BTTS - oui", cote=1.9):
    return dict(match_id=mid, coup_d_envoi_utc=ko, marche=lib, cote=cote)


def test_enregistre_avant_coup_d_envoi():
    now = datetime.datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
    c = {}
    assert K.enregistre(c, pick(), now) and c["m"]["fige"] is False
    assert K.enregistre(c, pick(cote=2.0), now) and c["m"]["cote"] == 2.0       # mise à jour permise avant le coup d'envoi
    assert K.enregistre({}, pick(ko="2026-10-14T12:00:01Z"), now)


def test_enregistre_refuse_apres_coup_d_envoi_ou_si_fige():
    now = datetime.datetime(2026, 10, 14, 18, 0, tzinfo=UTC)
    assert not K.enregistre({}, pick(), now)                                      # pile au coup d'envoi
    assert not K.enregistre({}, None, now)
    assert not K.enregistre({}, pick(ko=None), now)
    c = {"m": dict(pick(), fige=True)}
    assert not K.enregistre(c, pick(cote=5.0), datetime.datetime(2026, 10, 14, 10, 0, tzinfo=UTC)) and c["m"]["cote"] == 1.9


def ligne(lib="BTTS - oui", cote=1.9, fige=True):
    return dict(match_id="m", marche=lib, cote=cote, fige=fige, resultat=None, score=None, profit=None)


def test_regle_gagne_perd_rembourse():
    c = {"m": ligne()}
    assert K.regle(c, {"m": (2, 1)}) == 1 and c["m"]["resultat"] == "WIN" and abs(c["m"]["profit"] - 0.9) < 1e-9
    c = {"m": ligne()}
    K.regle(c, {"m": (1, 0)}); assert c["m"]["resultat"] == "LOSS" and c["m"]["profit"] == -1.0
    c = {"m": ligne("Handicap 0 - Domicile", 1.5)}
    K.regle(c, {"m": (1, 1)}); assert c["m"]["resultat"] == "PUSH" and c["m"]["profit"] == 0.0


def test_regle_une_seule_fois_et_seulement_si_fige():
    c = {"m": ligne()}
    K.regle(c, {"m": (2, 1)})
    assert K.regle(c, {"m": (0, 0)}) == 0 and c["m"]["score"] == [2, 1]           # jamais modifié
    c = {"m": ligne(fige=False)}
    assert K.regle(c, {"m": (2, 1)}) == 0 and c["m"]["resultat"] is None           # pas figé = pas réglé
    assert K.regle({"m": ligne()}, {}) == 0                                        # score inconnu


def test_statut():
    assert K.statut(299, (0.5, 0.9)) == "observation"
    assert K.statut(300, None) == "observation"
    assert K.statut(300, (0.01, 0.4)) == "actif"
    assert K.statut(500, (-0.05, 0.3)) == "non_rentable"
    assert K.statut(300, (0.0, 0.3)) == "non_rentable"                             # borne basse doit être > 0


# ---- bout en bout
def test_execution_de_bout_en_bout():
    with tempfile.TemporaryDirectory() as d:
        a_venir = match("n1", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z")
        t1 = datetime.datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
        s = X.execute(joues() + [a_venir], d, t1)
        assert s["regles_nouvelles"] and len(s["a_venir"]) == 1 and s["statut"] == "observation" and s["avertissement"]
        s = X.execute(joues() + [a_venir], d, t1)                                  # idempotent
        assert not s["regles_nouvelles"] and len(s["a_venir"]) == 1
        fini = dict(a_venir, h=2, a=2)
        t2 = datetime.datetime(2026, 10, 14, 21, 0, tzinfo=UTC)
        s = X.execute(joues() + [fini], d, t2)
        assert s["regles_reglees_aujourdhui"] == 1 and s["bilan"]["regles"] == 1 and s["bilan"]["roi"] == 0.9
        assert s["a_venir"] == []
        s = X.execute(joues() + [dict(fini, h=0, a=0)], d, t2)                     # score "corrigé" ignoré
        assert s["bilan"]["roi"] == 0.9 and s["regles_reglees_aujourdhui"] == 0


def test_execution_pari_apres_coup_d_envoi_jamais_enregistre():
    with tempfile.TemporaryDirectory() as d:
        tard = match("n1", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z")
        s = X.execute(joues() + [tard], d, datetime.datetime(2026, 10, 14, 19, 0, tzinfo=UTC))
        assert s["a_venir"] == [] and s["bilan"]["regles"] == 0
