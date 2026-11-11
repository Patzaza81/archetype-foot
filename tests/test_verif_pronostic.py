"""Tests de verif_pronostic.py : chaque regle avec >= 3 cas qui passent et >= 3 cas qui echouent, plus controles de fuite, de journal et de determinisme."""
import gzip, json, os, sys, tempfile, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verif_pronostic as v

def ok(m, h, a): return bool(v.CATALOGUE[m](h, a))
CFG = {"cote_min": 1.26, "sans_regles": True}      # la methode de base ; les regles par marche ont leurs tests dans test_verif_regles.py
CFG_REGLES = {"cote_min": 1.26}

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
        self.assertEqual(v.constat(MATCH([(3, 2)] * 5, [(2, 3)] * 5), "total_plus_2.5", 1.5, CFG)["verdict"], "TIENT")
        self.assertEqual(v.constat(MATCH([(1, 1)] * 4, [(1, 1)] * 4), "btts_oui", 1.5, CFG)["verdict"], "TIENT")
    def test_reserve(self):                        # d'un seul cote le pari passe plus souvent que rate
        self.assertEqual(v.constat(MATCH([(2, 0)] * 6, [(1, 1)] * 6), "1", 1.5, CFG)["verdict"], "TIENT AVEC RÉSERVE")
        self.assertEqual(v.constat(MATCH([(0, 0)] * 6, [(0, 2)] * 6), "1", 1.5, CFG)["verdict"], "TIENT AVEC RÉSERVE")
    def test_regle_de_marche_dans_constat(self):   # meme match, meme pari : sans regle RESERVE ; avec la regle « 1 » (xG du domicile trop bas) un cran de moins ; marche sans regle : inchange
        m = MATCH([(0, 0)] * 6, [(0, 2)] * 6)
        self.assertEqual(v.constat(m, "1", 1.5, CFG)["verdict"], "TIENT AVEC RÉSERVE")
        r = v.constat(m, "1", 1.5, CFG_REGLES); self.assertEqual(r["verdict"], "NE TIENT PAS"); self.assertFalse(r["regle"]["remplie"])
        self.assertEqual(v.constat(m, "total_moins_2.5", 1.5, CFG_REGLES)["verdict"], v.constat(m, "total_moins_2.5", 1.5, CFG)["verdict"])
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
        self.assertIn("1N&total_moins_4.5", m); self.assertTrue(all(r["verdict"] == "TIENT" and r["cote"] >= 1.26 for r in R))
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
        r = v.xg_attendus(self.S(8, 2.0, 1.0, 8, 2.0, 1.0), self.S(8, 1.0, 2.0, 8, 1.0, 2.0), {}); self.assertEqual(r[2], "xG"); self.assertEqual(r[:2], (2.0, 1.0))
    def test_estime_avec_la_meme_formule(self):    # xG estimes fournis (valeurs deja remplies par saison_complete) : meme moyenne attaque / defense adverse
        r = v.xg_attendus(self.S(6, 1.5, 1.5, 0, 1.4, 1.4), self.S(6, 1.5, 1.5, 0, 1.0, 1.0), {}); self.assertEqual(r[2], "estimé"); self.assertAlmostEqual(r[0], 1.2); self.assertAlmostEqual(r[1], 1.2)
        r = v.xg_attendus(self.S(5, 3.0, 0.5, 2, 2.4, 0.9), self.S(5, 1.0, 2.0, 0, 1.2, 1.7), {}); self.assertEqual(r[2], "estimé"); self.assertAlmostEqual(r[0], (2.4 + 1.7) / 2)
        r = v.xg_attendus(self.S(4, 1.0, 1.0, 0, 1.0, 1.0), self.S(4, 1.0, 1.0, 0, 1.0, 1.0), {}); self.assertEqual(r[2], "estimé")
    def test_rien_si_pas_assez_de_matchs_ou_pas_d_estimation(self):
        for A, B in [(self.S(3, 1.0, 1.0, 0, 1.0, 1.0), self.S(6, 1.0, 1.0, 0, 1.0, 1.0)), (self.S(6, 1.0, 1.0), self.S(6, 1.0, 1.0)), (self.S(6, 1.0, 1.0, 0, 1.0, 1.0), self.S(2, 1.0, 1.0, 0, 1.0, 1.0)), (self.S(0, None, None), self.S(0, None, None))]:
            self.assertEqual(v.xg_attendus(A, B, {}), (None, None, None))
    def test_modele_appris_sur_football_data(self):
        mo = v.modele_xg(); self.assertIsNotNone(mo); self.assertGreater(mo["equipes"], 50); self.assertGreater(mo["cree"]["b"], 0); self.assertGreater(mo["concede"]["b"], 0); self.assertGreater(mo["cree"]["r"], 0.5)
    def test_estimation_croissante_avec_les_buts(self):
        for lo, hi in [(0.5, 1.0), (1.0, 2.0), (1.5, 3.0)]:
            self.assertLess(v.xg_estime(lo, "cree"), v.xg_estime(hi, "cree")); self.assertLess(v.xg_estime(lo, "concede"), v.xg_estime(hi, "concede"))
        self.assertIsNone(v.xg_estime(None, "cree"))
    def test_saison_complete_remplit_l_estimation_seulement_sans_xg(self):
        sans = MATCH([(1, 1)] * 5, [(2, 0)] * 5); SA = v.saison_complete(sans, "equipe_dom"); self.assertTrue(SA["xg_est"]); self.assertAlmostEqual(SA["xg_cree"], v.xg_estime(1.0, "cree"))
        avec = MATCH([(1, 1)] * 5, [(2, 0)] * 5)
        for m in avec["assemblage"]["equipe_dom"]["matchs"]: m["xg"] = 2.0; m["xg_concede"] = 0.5
        SA = v.saison_complete(avec, "equipe_dom"); self.assertFalse(SA["xg_est"]); self.assertAlmostEqual(SA["xg_cree"], 2.0)
        peu = MATCH([(1, 1)] * 3, [(2, 0)] * 3); self.assertFalse(v.saison_complete(peu, "equipe_dom")["xg_est"])
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


# ---------------------------------------------------------------- selections gelees (Top 20 et onglet Regles) et page sur 7 jours — donnees fabriquees
import pytest
def _pari(marche, cote, taux, verdict="TIENT", regle=False):
    p = {"marche": marche, "cote": cote, "taux": taux, "verdict": verdict}
    if regle: p["regle"] = True
    return p

def _match(mid, ko, paris, statut="a_venir"):
    G = {"buts": [], "equipes": [], "victoire": [], "combos": []}
    for p in paris: G[v.groupe(p["marche"])].append(p)
    return {"match_id": mid, "date": ko[:10], "coup_d_envoi_utc": ko, "statut": statut, "domicile": "A" + mid, "exterieur": "B" + mid, "paris": G}

class TestTop20:
    def test_cote_minimale_1_34(self):               # 3 cas refuses (1,26 / 1,30 / 1,33) et 3 acceptes (1,34 / 1,40 / 2,00)
        for c in (1.26, 1.30, 1.33): assert v.top20_page({"matchs": [_match("m", "2026-11-20T18:00:00Z", [_pari("1N", c, 0.9)])]}) == {}
        for c in (1.34, 1.40, 2.00): assert "m" in v.top20_page({"matchs": [_match("m", "2026-11-20T18:00:00Z", [_pari("1N", c, 0.9)])]})
    def test_note_la_plus_prudente(self):            # reussite 90 % a 2,00 (cote : 50 %) passe APRES reussite 70 % a 1,40 (cote : 71 %)
        d = {"matchs": [_match("a", "2026-11-20T18:00:00Z", [_pari("1", 2.00, 0.9)]), _match("b", "2026-11-20T19:00:00Z", [_pari("1N", 1.40, 0.7)])]}
        T = v.top20_page(d); assert T["b"]["rang"] == 1 and T["a"]["rang"] == 2
    def test_un_pari_par_match_et_20_par_jour(self):
        d = {"matchs": [_match(f"m{i:02d}", "2026-11-20T18:00:00Z", [_pari("1N", 1.40, 0.5 + i / 100), _pari("total_plus_1.5", 1.36, 0.4)]) for i in range(25)]}
        T = v.top20_page(d); assert len(T) == 20 and all(t["pari"]["marche"] == "1N" for t in T.values()) and T["m24"]["rang"] == 1 and "m04" not in T
    def test_jour_du_cameroun(self):                 # 23h30 UTC le 20 = le 21 au Cameroun : classe avec les matchs du 21
        d = {"matchs": [_match("soir", "2026-11-20T23:30:00Z", [_pari("1N", 1.40, 0.6)])] + [_match(f"m{i:02d}", "2026-11-21T15:00:00Z", [_pari("1N", 1.40, 0.7)]) for i in range(20)]}
        assert "soir" not in v.top20_page(d)

class TestGelSelections:
    def _d(self, extra=()):
        return {"genere_le": "2026-11-20T10:00:00Z", "matchs": [_match("m1", "2026-11-20T18:00:00Z", [_pari("1N", 1.40, 0.8, regle=True), _pari("total_plus_1.5", 1.36, 0.7)]),
                                                                _match("m2", "2026-11-20T18:00:00Z", [_pari("total_plus_2.5", 1.30, 0.8)]),                       # sous 1,34 et sans regle : dans aucune selection
                                                                _match("m3", "2026-11-20T09:00:00Z", [_pari("1N", 1.40, 0.8, regle=True)], "en_cours_ou_resultat_attendu"), *extra]}
    def test_gel_seulement_avant_le_coup_d_envoi(self, tmp_path):
        j = str(tmp_path / "sel.jsonl")
        assert v.geler_selections(self._d(), chemin=j) == 2                                   # m1 : top20 + regles ; m2 : rien ; m3 : deja commence
        L = v.lire_journal(j); assert {(r["match_id"], r["selection"]) for r in L} == {("m1", "top20"), ("m1", "regles")} and v.verifier_journal(j) == []
        assert v.geler_selections(self._d(), chemin=j) == 0                                   # rien n'a change : aucune ligne
        assert v.geler_selections(self._d(), maintenant="2026-11-20T18:30:00Z", chemin=j) == 0   # apres le coup d'envoi : plus aucun gel
    def test_sortie_d_une_selection_enregistree(self, tmp_path):
        j = str(tmp_path / "sel.jsonl"); v.geler_selections(self._d(), chemin=j)
        d = self._d(); d["matchs"][0] = _match("m1", "2026-11-20T18:00:00Z", [_pari("total_plus_1.5", 1.30, 0.7)]); d["genere_le"] = "2026-11-20T12:00:00Z"
        assert v.geler_selections(d, chemin=j) == 2                                           # m1 sort du Top 20 et des Regles : deux listes vides ecrites
        assert [r["paris"] for r in v.lire_journal(j)[-2:]] == [[], []]
    def test_bilan_reel_sur_le_dernier_etat(self, tmp_path, monkeypatch):
        import p1_page_donnees
        j = str(tmp_path / "sel.jsonl"); v.geler_selections(self._d(), chemin=j)
        monkeypatch.setattr(p1_page_donnees, "scores", lambda flux: {"m1": {"buts_dom": 2, "buts_ext": 0}})
        b = v.bilan_selections(j)
        assert b["top20"] == {"paris": 1, "matchs": 1, "reussis": 1, "taux_reel": 1.0, "cote_moyenne": 1.4, "du": "2026-11-20", "au": "2026-11-20"} and b["regles"]["reussis"] == 1
        monkeypatch.setattr(p1_page_donnees, "scores", lambda flux: {"m1": {"buts_dom": 0, "buts_ext": 1}})
        assert v.bilan_selections(j)["top20"]["reussis"] == 0                                 # 0-1 : « 1N » perd
        monkeypatch.setattr(p1_page_donnees, "scores", lambda flux: {})
        assert v.bilan_selections(j) == {}                                                     # match pas termine : pas compte
    def test_journal_altere_refuse(self, tmp_path):
        j = str(tmp_path / "sel.jsonl"); v.geler_selections(self._d(), chemin=j)
        texte = open(j, encoding="utf-8").read().replace("1.4", "1.9", 1)                      # une cote modifiee apres coup
        open(j, "w", encoding="utf-8").write(texte)
        with pytest.raises(RuntimeError): v.bilan_selections(j)

def test_page_garde_sept_jours_et_meme_cote_que_la_page():
    import pathlib
    js = (pathlib.Path(v.RACINE) / "archetype_verif.js").read_text(encoding="utf-8")
    assert v.JOURS_PASSES_PAGE == 7 and f"const COTE_TOP = {v.COTE_TOP};" in js and "selectionsGelees(d)" in js
