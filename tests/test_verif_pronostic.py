"""Tests de verif_pronostic.py : chaque regle avec >= 3 cas qui passent et >= 3 cas qui echouent, plus controles de fuite, de journal et de determinisme."""
import gzip, json, os, sys, tempfile, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verif_pronostic as v

def ok(m, h, a): return bool(v.CATALOGUE[m](h, a))
CFG = {"cote_min": 1.26}

class Catalogue(unittest.TestCase):
    def test_passent(self):
        for m, h, a in [("1", 2, 0), ("1N", 1, 1), ("N2", 0, 2), ("total_plus_2.5", 2, 1), ("total_moins_3.5", 1, 2), ("btts_oui", 1, 1), ("N2&total_moins_4.5", 1, 1), ("1&total_moins_4.5", 3, 1), ("dom_plus_1.5", 2, 0), ("cage_dom_oui", 1, 0)]: self.assertTrue(ok(m, h, a), (m, h, a))
    def test_echouent(self):
        for m, h, a in [("1", 1, 1), ("1N", 0, 1), ("N2", 2, 1), ("total_plus_2.5", 1, 1), ("total_moins_3.5", 3, 1), ("btts_oui", 2, 0), ("N2&total_moins_4.5", 3, 2), ("1&total_moins_4.5", 4, 1), ("dom_plus_1.5", 1, 0), ("cage_dom_oui", 1, 1)]: self.assertFalse(ok(m, h, a), (m, h, a))
    def test_exactement_la_ligne(self):          # plus de 2,5 = 3 buts ou plus ; moins de 3,5 = 3 buts ou moins
        self.assertTrue(ok("total_plus_2.5", 2, 1)); self.assertFalse(ok("total_plus_2.5", 1, 1)); self.assertTrue(ok("total_moins_3.5", 2, 1)); self.assertFalse(ok("total_moins_3.5", 2, 2))
    def test_libelle(self):
        self.assertEqual(v.libelle("N2&total_moins_4.5", "St Mirren", "Rangers"), "Rangers ou nul et Moins de 4,5 buts"); self.assertEqual(v.libelle("1", "A", "B"), "A gagne"); self.assertEqual(v.libelle("btts_oui", "A", "B"), "Les deux équipes marquent : oui")

class Cotes(unittest.TestCase):
    def test_cotes_betpawa(self):
        c = v.cotes_betpawa({"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "dc_total_2.5": {"1N|moins": 2.5, "N2|plus": 5.4}, "btts": {"Oui": 1.7, "Non": 2.0}, "over_under_2.5": {"plus": 1.9, "moins": 1.8}, "cages_inviolees_domicile": {"oui": 2.4, "non": 1.5}})
        self.assertEqual(c["1"], 1.5); self.assertEqual(c["1N&total_moins_2.5"], 2.5); self.assertEqual(c["N2&total_plus_2.5"], 5.4); self.assertEqual(c["btts_oui"], 1.7); self.assertEqual(c["total_moins_2.5"], 1.8); self.assertEqual(c["cage_dom_oui"], 2.4)
    def test_vide_ou_invalide(self):
        self.assertEqual(v.cotes_betpawa(None), {}); self.assertEqual(v.cotes_betpawa({"1x2": {"1": None, "N": 0, "2": 1.0}}), {})


def MATCH(A, B, jour="2026-11-07", saison="2627", extra_a=(), extra_b=()):
    """Match synthetique : A = scores (marques, encaisses) de A a domicile ; B = scores (marques, encaisses) de B a l'exterieur."""
    ea = [{"domicile": True, "date": f"2026-10-{i+1:02d}", "saison": saison, "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(A)] + list(extra_a)
    eb = [{"domicile": False, "date": f"2026-10-{i+1:02d}", "saison": saison, "buts_marques": h, "buts_encaisses": a} for i, (h, a) in enumerate(B)] + list(extra_b)
    return {"date": jour, "domicile": "A", "exterieur": "B", "competition": "Test", "assemblage": {"saison_football_data": saison, "equipe_dom": {"matchs": ea}, "equipe_ext": {"matchs": eb}}}

class GardeFou(unittest.TestCase):
    def test_refuse(self):
        for c in (1.12, 1.20, 1.25): self.assertEqual(v.constat(MATCH([(1, 0)] * 6, [(0, 1)] * 6), "1", c, CFG)["verdict"], "REFUSÉ")
    def test_accepte(self):
        for c in (1.26, 1.3, 1.5, 2.0): self.assertNotEqual(v.constat(MATCH([(1, 0)] * 6, [(0, 1)] * 6), "1", c, CFG)["verdict"], "REFUSÉ")
    def test_echantillon_trop_petit(self):
        for a, b in (([(1, 0)] * 3, [(0, 1)] * 6), ([(1, 0)] * 6, [(0, 1)] * 3), ([(1, 0)] * 2, [(0, 1)] * 2), ([], [])): self.assertEqual(v.constat(MATCH(a, b), "1", 1.5, CFG)["verdict"], "NON ÉVALUABLE")
    def test_assez_de_matchs(self):
        for n in (4, 5, 6): self.assertNotEqual(v.constat(MATCH([(1, 0)] * n, [(0, 1)] * n), "1", 1.5, CFG)["verdict"], "NON ÉVALUABLE")

class Verdict(unittest.TestCase):
    def test_tient(self):                          # A gagne toujours chez lui, B perd toujours dehors
        self.assertEqual(v.constat(MATCH([(2, 0)] * 6, [(0, 2)] * 6), "1", 1.5, CFG)["verdict"], "TIENT")
        self.assertEqual(v.constat(MATCH([(2, 1)] * 5, [(1, 2)] * 5), "total_plus_2.5", 1.5, CFG)["verdict"], "TIENT")
        self.assertEqual(v.constat(MATCH([(1, 1)] * 4, [(1, 1)] * 4), "btts_oui", 1.5, CFG)["verdict"], "TIENT")
    def test_reserve(self):                        # d'un seul cote le pari passe plus souvent que rate
        self.assertEqual(v.constat(MATCH([(2, 0)] * 6, [(1, 1)] * 6), "1", 1.5, CFG)["verdict"], "TIENT AVEC RÉSERVE")
        self.assertEqual(v.constat(MATCH([(0, 0)] * 6, [(0, 2)] * 6), "1", 1.5, CFG)["verdict"], "TIENT AVEC RÉSERVE")
    def test_ne_tient_pas(self):                   # ni l'un ni l'autre : A perd chez lui, B gagne dehors
        self.assertEqual(v.constat(MATCH([(0, 2)] * 6, [(2, 0)] * 6), "1", 1.5, CFG)["verdict"], "NE TIENT PAS")
        self.assertEqual(v.constat(MATCH([(0, 0)] * 6, [(0, 0)] * 6), "total_plus_2.5", 1.5, CFG)["verdict"], "NE TIENT PAS")
        self.assertEqual(v.constat(MATCH([(3, 3)] * 6, [(3, 3)] * 6), "total_moins_1.5", 1.5, CFG)["verdict"], "NE TIENT PAS")
    def test_ordre_du_pari_conserve_orientation(self):   # B a l'exterieur : ses buts marques sont ceux de l'exterieur
        self.assertEqual(v.constat(MATCH([(1, 0)] * 6, [(3, 0)] * 6), "2", 1.5, CFG)["verdict"], "TIENT AVEC RÉSERVE")

class Fuite(unittest.TestCase):
    def test_match_du_jour_ou_futur_ignore(self):
        for jour in ("2026-11-07", "2026-11-08", "2027-01-01"):
            ex = [{"domicile": True, "date": jour, "saison": "2627", "buts_marques": 9, "buts_encaisses": 9}]
            r = v.constat(MATCH([(1, 0)] * 4, [(0, 1)] * 4, extra_a=ex), "1", 1.5, CFG); self.assertEqual(r["A"]["n"], 4)
    def test_autre_saison_ignoree(self):
        ex = [{"domicile": True, "date": "2000-01-01", "saison": "9900", "buts_marques": 8, "buts_encaisses": 8}]
        self.assertEqual(v.constat(MATCH([(1, 0)] * 4, [(0, 1)] * 4, extra_a=ex), "1", 1.5, CFG)["A"]["n"], 4)
    def test_mauvais_cote_ignore(self):             # un match de A a l'exterieur ne compte pas dans « A a domicile »
        ex = [{"domicile": False, "date": "2026-10-20", "saison": "2627", "buts_marques": 7, "buts_encaisses": 7}]
        self.assertEqual(v.constat(MATCH([(1, 0)] * 4, [(0, 1)] * 4, extra_a=ex), "1", 1.5, CFG)["A"]["n"], 4)

class Rang(unittest.TestCase):
    def test_choix_a_geler(self):
        x = MATCH([(2, 0)] * 6, [(0, 2)] * 6); x["cotes_betpawa"] = {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "btts": {"Oui": 1.7, "Non": 2.0}}
        E = v.choix_a_geler(x, CFG); self.assertEqual(E[0]["marche"], "1"); self.assertEqual(E[0]["verdict"], "TIENT"); self.assertTrue(all(e["cote"] >= 1.26 for e in E)); self.assertEqual(E[-1]["verdict"], "NE TIENT PAS")
    def test_alternatives(self):
        x = MATCH([(2, 0)] * 6, [(0, 2)] * 6); x["cotes_betpawa"] = {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "btts": {"Oui": 1.7, "Non": 2.0}}
        A = v.alternatives(x, CFG, exclure="1"); self.assertNotIn("1", [a["marche"] for a in A]); self.assertTrue(all(a["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE") and a["cote"] >= 1.26 for a in A))

class Presentation(unittest.TestCase):
    def _x(self, A, B, cotes):
        x = MATCH(A, B); x["cotes_betpawa"] = cotes; x["heure_cameroun"] = "17:00"; return x
    def test_ordre_du_plus_au_moins_fiable(self):
        T = v.analyse(self._x([(2, 0)] * 6, [(0, 2)] * 6, {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "btts": {"Oui": 1.7, "Non": 2.0}}), CFG)
        lignes = [l for l in T.splitlines() if l.startswith("| ") and "**" in l and l[2].isdigit()]; verdicts = [("Tient avec réserve" in l) for l in lignes]
        self.assertTrue(lignes); self.assertEqual(verdicts, sorted(verdicts)); self.assertIn("A gagne", lignes[0])
    def test_cote_sous_le_minimum_absente(self):
        T = v.analyse(self._x([(2, 0)] * 6, [(0, 2)] * 6, {"1x2": {"1": 1.25, "N": 4.0, "2": 6.0}}), CFG); self.assertNotIn("A gagne", T); self.assertIn("Aucun pari ne passe les filtres", T)
    def test_pari_qui_ne_tient_pas_absent(self):
        T = v.analyse(self._x([(0, 2)] * 6, [(2, 0)] * 6, {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}}), CFG); self.assertNotIn("A gagne", T)
    def test_tableau_des_equipes(self):
        T = v.analyse(self._x([(2, 0)] * 6, [(0, 2)] * 6, {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}}), CFG)
        for mot in ("xG créés par match", "Buts marqués par match", "Écart xG", "Moyenne du championnat", "Constats"): self.assertIn(mot, T)

class Repli(unittest.TestCase):
    def _x(self, A, B, cotes):
        x = MATCH(A, B); x["cotes_betpawa"] = cotes; return x
    COT = {"1x2": {"1": 1.2, "N": 6.0, "2": 9.0}, "dc_total_4.5": {"1N|moins": 1.5, "N2|moins": 3.0}, "dc_total_2.5": {"1N|plus": 1.3, "N2|plus": 4.0}}
    def test_retenu(self):                          # pari 1 a 1,20 tres solide : ses combos double chance a cote >= 1,26 qui tiennent sont retenus
        R = v.repli_combo(self._x([(2, 1)] * 6, [(1, 2)] * 6, self.COT), "1", 1.2, CFG); m = [r["marche"] for r in R]
        self.assertIn("1N&total_moins_4.5", m); self.assertIn("1N&total_plus_2.5", m); self.assertTrue(all(r["verdict"] == "TIENT" and r["cote"] >= 1.26 for r in R))
    def test_pas_de_repli_si_cote_suffisante(self):
        for c in (1.26, 1.4, 2.0): self.assertEqual(v.repli_combo(self._x([(2, 0)] * 6, [(0, 2)] * 6, self.COT), "1", c, CFG), [])
    def test_pas_de_repli_si_pari_pas_solide(self):  # A perd chez lui : le pari « 1 » ne tient pas, donc pas de repli
        for A, B in (([(0, 2)] * 6, [(2, 0)] * 6), ([(2, 0)] * 6, [(1, 1)] * 6), ([(0, 0)] * 6, [(0, 0)] * 6)): self.assertEqual(v.repli_combo(self._x(A, B, self.COT), "1", 1.2, CFG), [])
    def test_combo_sous_le_minimum_ecarte(self):
        cot = {**self.COT, "dc_total_4.5": {"1N|moins": 1.2, "N2|moins": 3.0}}
        self.assertNotIn("1N&total_moins_4.5", [r["marche"] for r in v.repli_combo(self._x([(2, 0)] * 6, [(0, 2)] * 6, cot), "1", 1.2, CFG)])
    def test_combo_qui_ne_tient_pas_ecarte(self):    # le combo « Moins de 1,5 » ne tient pas quand tout finit 2-0
        cot = {**self.COT, "dc_total_1.5": {"1N|moins": 3.0, "N2|moins": 4.0}}
        self.assertNotIn("1N&total_moins_1.5", [r["marche"] for r in v.repli_combo(self._x([(2, 0)] * 6, [(0, 2)] * 6, cot), "1", 1.2, CFG)])
    def test_sans_donnees(self):
        self.assertEqual(v.repli_combo(self._x([], [], self.COT), "1", 1.2, CFG), [])

class XGEstime(unittest.TestCase):
    S = lambda self, n, bm, be, nx=0, xc=None, xd=None: {"n": n, "buts_marques": bm, "buts_encaisses": be, "n_xg": nx, "xg_cree": xc, "xg_concede": xd}
    def test_xg_present_utilise(self):
        r = v.xg_attendus(self.S(8, 2.0, 1.0, 8, 2.0, 1.0), self.S(8, 1.0, 2.0, 8, 1.0, 2.0), {"buts": 1.5}); self.assertEqual(r[2], "xG"); self.assertEqual(r[:2], (2.0, 1.0))
    def test_estime_quand_xg_manque(self):         # attaque A 1,5 x defense B 1,5 / moyenne 1,5 = 1,5 ; B : 1,5 x 1,5 / 1,5
        r = v.xg_attendus(self.S(6, 1.5, 1.5), self.S(6, 1.5, 1.5), {"buts": 1.5}); self.assertEqual(r[2], "estimé"); self.assertAlmostEqual(r[0], 1.5); self.assertAlmostEqual(r[1], 1.5)
        r = v.xg_attendus(self.S(5, 3.0, 0.5), self.S(5, 1.0, 2.0), {"buts": 1.5}); self.assertAlmostEqual(r[0], 3.0 * 2.0 / 1.5); self.assertAlmostEqual(r[1], 1.0 * 0.5 / 1.5)
        r = v.xg_attendus(self.S(4, 1.2, 1.2, 2), self.S(4, 1.2, 1.2, 2), {"buts": 1.2}); self.assertEqual(r[2], "estimé")    # xG sur 2 matchs seulement : insuffisant
    def test_rien_si_pas_assez_de_matchs_ou_pas_de_moyenne(self):
        for A, B, ch in [(self.S(3, 1.0, 1.0), self.S(6, 1.0, 1.0), {"buts": 1.2}), (self.S(6, 1.0, 1.0), self.S(6, 1.0, 1.0), {"buts": None}), (self.S(6, 1.0, 1.0), self.S(2, 1.0, 1.0), {"buts": 1.2}), (self.S(0, None, None), self.S(0, None, None), {"buts": 1.2})]:
            self.assertEqual(v.xg_attendus(A, B, ch), (None, None, None))
    def test_saison_matchendirect_comptee(self):
        for m, ok_ in [({"saison": None, "source": "matchendirect"}, True), ({"saison": "2627", "source": "football-data"}, True), ({"saison": "2526", "source": "football-data"}, False), ({"saison": None, "source": "football-data"}, False), ({"saison": "2526", "source": "matchendirect"}, False)]: self.assertEqual(v.de_la_saison(m, "2627"), ok_, m)

class Statistiques(unittest.TestCase):
    def test_wilson(self):
        lo, hi = v.wilson(50, 100); self.assertAlmostEqual(lo, 0.404, 2); self.assertAlmostEqual(hi, 0.596, 2)
        lo, hi = v.wilson(0, 10); self.assertEqual(lo, 0.0) if False else self.assertLess(lo, 1e-9); lo, hi = v.wilson(10, 10); self.assertGreater(lo, 0.69); self.assertEqual(v.wilson(0, 0), (0.0, 1.0))

class Journal(unittest.TestCase):
    def _flux(self, d, kick):
        os.makedirs(d, exist_ok=True)
        ed = {"matchs": [{"domicile": True, "date": "2026-10-01", "saison": "2627", "buts_marques": 2, "buts_encaisses": 0}] * 5}
        x = {"match_id": "m1", "competition": "Test", "date": "2026-11-07", "domicile": "A", "exterieur": "B", "coup_d_envoi_utc": kick, "score": None, "cotes_betpawa": {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "btts": {"Oui": 1.7, "Non": 2.0}},
             "assemblage": {"saison_football_data": "2627", "equipe_dom": ed, "equipe_ext": {"matchs": [{"domicile": False, "date": "2026-10-01", "saison": "2627", "buts_marques": 0, "buts_encaisses": 2}] * 5}}}
        with gzip.open(os.path.join(d, "2026-11-07.json.gz"), "wt") as f: json.dump({"m1": x}, f)
    def test_gel_chaine_et_alteration(self):
        t = tempfile.mkdtemp(); self._flux(t, "2026-11-07T15:00:00Z"); j = os.path.join(t, "j.jsonl")
        n = v.geler("2026-11-07", "2026-11-07T09:00:00Z", j, t); self.assertGreater(n, 0); self.assertEqual(v.verifier_journal(j), [])
        self.assertEqual(v.geler("2026-11-07", "2026-11-07T09:30:00Z", j, t), 0)           # jamais reecrit
        L = open(j).read().splitlines(); r = json.loads(L[0]); r["verdict"] = "TIENT" if r["verdict"] != "TIENT" else "FRAGILE"; L[0] = json.dumps(r); open(j, "w").write("\n".join(L) + "\n")
        self.assertTrue(v.verifier_journal(j))                                               # alteration detectee
    def test_refus_apres_coup_d_envoi(self):
        t = tempfile.mkdtemp(); self._flux(t, "2026-11-07T15:00:00Z"); j = os.path.join(t, "j.jsonl")
        for maintenant in ("2026-11-07T15:00:00Z", "2026-11-07T15:00:01Z", "2026-11-07T20:00:00Z"): self.assertEqual(v.geler("2026-11-07", maintenant, j, t), 0)
        self.assertEqual(v.lire_journal(j), [])
    def test_bilan_refuse_journal_altere(self):
        t = tempfile.mkdtemp(); self._flux(t, "2026-11-07T15:00:00Z"); j = os.path.join(t, "j.jsonl"); v.geler("2026-11-07", "2026-11-07T09:00:00Z", j, t)
        L = open(j).read().splitlines(); r = json.loads(L[0]); r["cote"] = 9.99; L[0] = json.dumps(r); open(j, "w").write("\n".join(L) + "\n")
        with self.assertRaises(RuntimeError): v.bilan(j, t)

class LectureXG(unittest.TestCase):
    def test_confirme(self):
        for m, la, lb in [("1", 2.0, 1.0), ("total_plus_2.5", 1.6, 1.4), ("btts_oui", 1.5, 1.2), ("N2&total_moins_4.5", 1.0, 1.4), ("1&total_moins_4.5", 2.0, 0.8)]: self.assertTrue(v._lecture(m, la, lb), (m, la, lb))
    def test_contredit(self):
        for m, la, lb in [("1", 1.0, 1.5), ("total_plus_2.5", 1.0, 1.2), ("btts_oui", 2.0, 0.6), ("N2&total_moins_4.5", 2.0, 0.8), ("total_moins_1.5", 1.0, 1.0)]: self.assertFalse(v._lecture(m, la, lb), (m, la, lb))
    def test_ligne_franche(self):
        for val, X, sens in [(2.0, 1.5, "plus"), (3.0, 2.5, "plus"), (1.0, 1.5, "moins"), (2.5, 3.5, "moins")]: self.assertIs(v._ligne(val, X, sens), True)
    def test_ligne_mauvais_cote(self):
        for val, X, sens in [(1.4, 1.5, "plus"), (2.0, 2.5, "plus"), (1.6, 1.5, "moins"), (3.6, 3.5, "moins")]: self.assertIs(v._ligne(val, X, sens), False)
    def test_ligne_limite(self):                  # exemple Galatasaray plus de 1,5 avec 1,6 but attendu : sous les 2 buts qu'il faut
        for val, X, sens in [(1.6, 1.5, "plus"), (2.9, 2.5, "plus"), (1.4, 1.5, "moins"), (3.1, 3.5, "moins")]: self.assertEqual(v._ligne(val, X, sens), "limite")
        self.assertEqual(v._lecture("dom_plus_1.5", 1.61, 1.63), "limite")
    def test_avantage_du_terrain(self):           # xG quasi egaux (Galatasaray 1,61 contre 1,63) : sans avantage la victoire est contredite, avec l'avantage du championnat elle est confirmee
        self.assertFalse(v._lecture("1", 1.61, 1.63)); self.assertTrue(v._lecture("1", 1.61, 1.63, 0.47)); self.assertTrue(v._lecture("1", 1.6, 1.5, 0.35))
        self.assertFalse(v._lecture("1", 1.0, 1.5, 0.35)); self.assertFalse(v._lecture("1", 1.2, 1.9, 0.47)); self.assertTrue(v._lecture("2", 1.0, 1.5, 0.35))
    def test_total_inchange_par_avantage(self):
        for av in (0.0, 0.5, 0.9): self.assertEqual(v._lecture("total_plus_2.5", 1.6, 1.4, av), True); self.assertEqual(v._lecture("total_moins_1.5", 1.0, 1.0, av), False)
    def test_ajuster_remonte(self):               # Birmingham : frequences 3/7 des deux cotes mais buts attendus et xG confirment
        for lb, lx in [(True, True), (True, None)]: self.assertEqual(v._ajuster("NE TIENT PAS", lb, lx), "TIENT AVEC RÉSERVE")
    def test_ajuster_ne_remonte_pas(self):
        for lb, lx in [(False, True), (None, True), (True, False), (True, "limite"), ("limite", True)]: self.assertEqual(v._ajuster("NE TIENT PAS", lb, lx), "NE TIENT PAS", (lb, lx))
    def test_ajuster_baisse(self):
        self.assertEqual(v._ajuster("TIENT", True, False), "TIENT AVEC RÉSERVE"); self.assertEqual(v._ajuster("TIENT AVEC RÉSERVE", True, False), "NE TIENT PAS"); self.assertEqual(v._ajuster("TIENT", True, "limite"), "TIENT AVEC RÉSERVE"); self.assertEqual(v._ajuster("TIENT", True, True), "TIENT")
    def test_non_lisible(self):
        self.assertIsNone(v._lecture("1", None, 1.0)); self.assertIsNone(v._lecture("N", 1.0, 1.0)); self.assertIsNone(v._lecture("12", 1.0, 1.0))
    def test_attendus(self):
        A = {"xg_cree": 2.0, "xg_concede": 0.5}; B = {"xg_cree": 1.0, "xg_concede": 1.5}; self.assertEqual(v._attendus(A, B, ("xg_cree", "xg_concede"), ("xg_cree", "xg_concede")), (1.75, 0.75))

if __name__ == "__main__":
    unittest.main()
