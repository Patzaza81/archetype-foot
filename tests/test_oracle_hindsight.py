"""Tests du système tricheur d'évaluation (oracle_hindsight) : données synthétiques, aucun fichier lu."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import oracle_hindsight as O  # noqa: E402


def pari(mid, marche, cote, gagne, date="2026-10-01"):
    return {"match_id": mid, "date": date, "marche": marche, "cote": cote, "resultat": 1 if gagne else -1,
            "profit": (cote - 1) if gagne else -1.0}


B = (1.30, 1.60)


def test_dans_bande_cas_qui_passent():
    assert O.dans_bande(pari("a", "x", 1.30, True), B)      # borne basse incluse
    assert O.dans_bande(pari("a", "x", 1.45, True), B)
    assert O.dans_bande(pari("a", "x", 1.599, True), B)


def test_dans_bande_cas_qui_echouent():
    assert not O.dans_bande(pari("a", "x", 1.60, True), B)  # borne haute exclue
    assert not O.dans_bande(pari("a", "x", 1.29, True), B)
    assert not O.dans_bande(pari("a", "x", 2.50, True), B)


def test_choix_oracle_prend_le_gagnant_de_cote_max_dans_la_bande():
    L = [pari("m", "A", 1.35, True), pari("m", "B", 1.55, True), pari("m", "C", 1.58, False), pari("m", "D", 2.2, True)]
    assert O.choix_oracle(L, B)["marche"] == "B"            # C perd, D hors bande
    assert O.choix_oracle([pari("m", "A", 1.4, True)], B)["marche"] == "A"
    assert O.choix_oracle([pari("m", "A", 1.4, True), pari("m", "Z", 1.4, True)], B)["marche"] == "Z"  # égalité : ordre fixe


def test_choix_oracle_aucun_gagnant():
    assert O.choix_oracle([pari("m", "A", 1.4, False)], B) is None             # perd
    assert O.choix_oracle([pari("m", "A", 2.0, True)], B) is None              # gagne mais hors bande
    assert O.choix_oracle([], B) is None


def test_plafond_et_hasard_valeurs_exactes():
    P = [pari("m1", "A", 1.5, True), pari("m1", "B", 1.4, False), pari("m2", "A", 1.5, False), pari("m2", "B", 1.4, False)]
    o = O.plafond(P, B)
    assert o["matchs_eligibles"] == 2 and o["matchs_avec_gagnant"] == 1
    assert abs(o["roi"] - ((0.5 - 1) / 2)) < 1e-12
    h = O.hasard(P, B)
    assert h["paris"] == 4 and abs(h["reussite"] - 0.25) < 1e-12 and abs(h["roi"] - (0.5 - 3) / 4) < 1e-12


def test_evalue_detecte_la_fuite():
    P = [pari(f"m{i}", "A", 1.5, True) for i in range(25)] + [pari(f"m{i}", "B", 1.4, False) for i in range(25)]
    parfait = [p for p in P if p["resultat"] == 1]
    e = O.evalue(parfait, P, B)
    assert e["fuite_suspecte"] is True and abs(e["capture"] - 1.0) < 1e-9
    nul = [p for p in P if p["resultat"] == -1]
    assert O.evalue(nul, P, B)["fuite_suspecte"] is False
    assert O.evalue(nul, P, B)["capture"] < 0               # pire que le hasard


def test_tickets_gagnants_sont_gagnants_et_sans_match_repete():
    P = []
    for i in range(12):
        P += [pari(f"m{i}", "A", 1.4, True), pari(f"m{i}", "B", 1.5, False)]
    T = O.tickets_gagnants(P, B, 3, 4, graine=1)
    assert len(T) == 3
    vus = [p["match_id"] for t in T for p in t]
    assert len(vus) == len(set(vus)) == 12
    assert all(p["resultat"] == 1 for t in T for p in t)
    assert O.tickets_gagnants(P, B, 3, 4, graine=1) == T     # reproductible


def test_tickets_gagnants_manque_de_matchs():
    P = [pari(f"m{i}", "A", 1.4, True) for i in range(5)]
    assert len(O.tickets_gagnants(P, B, 3, 4)) == 1          # 5 matchs -> un seul ticket de 4
    assert O.tickets_gagnants([pari("m", "A", 2.0, True)], B, 2, 1) == []   # rien dans la bande
    assert O.tickets_gagnants([], B, 2, 1) == []
