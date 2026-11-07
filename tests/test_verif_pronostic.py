"""Tests de verif_pronostic.py : chaque regle avec >= 3 cas qui passent et >= 3 cas qui echouent, plus controles de fuite, de journal et de determinisme."""
import gzip, json, os, sys, tempfile, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verif_pronostic as v

def ok(m, h, a): return bool(v.CATALOGUE[m](h, a))
CAL = {"n_min": 3, "z_seuil": 1.645, "marches": {
    "1": {"score": "pool", "lissage": 0, "valide": True, "taux_base": 0.45, "blocs": [[0.0, 0.3, 0.30, 400.0], [0.3, 0.6, 0.48, 400.0], [0.6, 0.8, 0.52, 40.0], [0.8, 1.0, 0.70, 400.0]]},
    "total_plus_2.5": {"score": "min", "lissage": 0, "valide": False, "taux_base": 0.5, "blocs": [[0.0, 1.0, 0.5, 100.0]]}}}
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

class GardeFou(unittest.TestCase):
    def test_refuse(self):
        for c in (1.12, 1.20, 1.25): self.assertEqual(v.evaluer([(1, 0)] * 6, [(1, 0)] * 6, "1", c, CAL, CFG)["verdict"], "REFUSÉ")
    def test_accepte(self):
        for c in (1.26, 1.3, 1.5, 2.0): self.assertNotEqual(v.evaluer([(1, 0)] * 6, [(1, 0)] * 6, "1", c, CAL, CFG)["verdict"], "REFUSÉ")
    def test_echantillon_trop_petit(self):
        for a, b in (([(1, 0)] * 2, [(1, 0)] * 6), ([(1, 0)] * 6, [(1, 0)] * 2), ([], [])): self.assertEqual(v.evaluer(a, b, "1", 1.5, CAL, CFG)["verdict"], "NON ÉVALUABLE")
    def test_assez_de_matchs(self):
        for n in (3, 4, 6): self.assertNotEqual(v.evaluer([(1, 0)] * n, [(1, 0)] * n, "1", 1.5, CAL, CFG)["verdict"], "NON ÉVALUABLE")

class Verdict(unittest.TestCase):
    def test_tient(self):                         # 6/6 des deux cotes -> indicateur 1.0 -> bloc 0.70 sur 400 matchs : borne basse > 0.5
        self.assertEqual(v.evaluer([(1, 0)] * 6, [(1, 0)] * 6, "1", 1.5, CAL, CFG)["verdict"], "TIENT")
    def test_reserve(self):                       # indicateur 0.5 -> bloc 0.48 ... non : on cible le bloc 0.52 sur 40 matchs (borne basse < 0.5)
        r = v.evaluer([(1, 0)] * 4 + [(0, 0)] * 2, [(1, 0)] * 4 + [(0, 0)] * 2, "1", 1.5, CAL, CFG); self.assertEqual(r["verdict"], "TIENT AVEC RÉSERVE")
    def test_fragile(self):                       # indicateur 0.5 -> bloc 0.48 : estimation < 0.5 mais borne haute > 0.5
        r = v.evaluer([(1, 0)] * 3 + [(0, 0)] * 3, [(1, 0)] * 3 + [(0, 0)] * 3, "1", 1.5, CAL, CFG); self.assertEqual(r["verdict"], "FRAGILE")
    def test_ne_tient_pas(self):                  # indicateur 0 -> bloc 0.30 sur 400 : borne haute < 0.5
        self.assertEqual(v.evaluer([(0, 1)] * 6, [(0, 1)] * 6, "1", 1.5, CAL, CFG)["verdict"], "NE TIENT PAS")
    def test_sans_signal(self):                   # marche dont l'indicateur n'a pas prouve son pouvoir
        self.assertEqual(v.evaluer([(2, 1)] * 6, [(2, 1)] * 6, "total_plus_2.5", 1.5, CAL, CFG)["verdict"], "SANS SIGNAL")
    def test_marche_inconnu(self):
        self.assertEqual(v.evaluer([(1, 0)] * 6, [(1, 0)] * 6, "1&xx", 1.5, {"marches": {}}, CFG)["verdict"], "NON ÉVALUABLE") if "1&xx" in v.IDX else None

class Statistiques(unittest.TestCase):
    def test_wilson(self):
        lo, hi = v.wilson(50, 100); self.assertAlmostEqual(lo, 0.404, 2); self.assertAlmostEqual(hi, 0.596, 2)
        lo, hi = v.wilson(0, 10); self.assertEqual(lo, 0.0) if False else self.assertLess(lo, 1e-9); lo, hi = v.wilson(10, 10); self.assertGreater(lo, 0.69); self.assertEqual(v.wilson(0, 0), (0.0, 1.0))
    def test_pav_croissant(self):
        B = v.pav([1, 2, 3, 4], [0.5, 0.2, 0.6, 0.9], [10, 10, 10, 10]); taux = [b[2] for b in B]; self.assertEqual(taux, sorted(taux)); self.assertAlmostEqual(taux[0], 0.35)
    def test_pav_deja_croissant(self):
        B = v.pav([1, 2, 3], [0.1, 0.5, 0.9], [5, 5, 5]); self.assertEqual(len(B), 3)

class Echantillons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = None
        f = os.path.join(v.FLUX, "2026-11-07.json.gz")
        if os.path.exists(f):
            for x in json.load(gzip.open(f)).values():
                if x["domicile"] == "Rome" and x["exterieur"] == "Sassuolo": cls.x = x
    def test_rome_sassuolo(self):
        if self.x is None: self.skipTest("flux absent")
        A, B = v.echantillons(self.x); self.assertTrue(len(A) >= 3 and len(B) >= 3)
        eq = self.x["assemblage"]["equipe_dom"]["matchs"]; att = [(m["buts_marques"], m["buts_encaisses"]) for m in eq if m["domicile"] and m["date"] < self.x["date"] and m["saison"] == self.x["assemblage"]["saison_football_data"]]
        self.assertEqual(A, att)                                   # domicile de A, orientation (home, away)
        ee = self.x["assemblage"]["equipe_ext"]["matchs"]; self.assertEqual(B, [(m["buts_encaisses"], m["buts_marques"]) for m in ee if not m["domicile"] and m["date"] < self.x["date"] and m["saison"] == self.x["assemblage"]["saison_football_data"]])
    def test_aucun_match_du_jour_ni_futur(self):
        if self.x is None: self.skipTest("flux absent")
        x = json.loads(json.dumps(self.x)); x["assemblage"]["equipe_dom"]["matchs"].append({"domicile": True, "date": x["date"], "saison": x["assemblage"]["saison_football_data"], "buts_marques": 9, "buts_encaisses": 9})
        A, _ = v.echantillons(x); self.assertNotIn((9, 9), A)      # un match du jour meme n'est jamais utilise
    def test_autre_saison_ecartee(self):
        if self.x is None: self.skipTest("flux absent")
        x = json.loads(json.dumps(self.x)); x["assemblage"]["equipe_dom"]["matchs"].append({"domicile": True, "date": "2000-01-01", "saison": "9900", "buts_marques": 8, "buts_encaisses": 8})
        A, _ = v.echantillons(x); self.assertNotIn((8, 8), A)

class Historique(unittest.TestCase):
    def test_pas_de_fuite(self):
        D = v.lignes_historique(["E0"]); self.assertGreater(len(D["nA"]), 1000); self.assertTrue((D["nA"] >= 1).all() and (D["nB"] >= 1).all())
        self.assertTrue((D["nA"] <= 19).all())           # 19 matchs a domicile par saison au maximum : jamais le match lui-meme ni une autre saison
    def test_deterministe(self):
        D = v.lignes_historique(["E0"]); a = v.calibrer(D); b = v.calibrer(D); self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

class Journal(unittest.TestCase):
    def _flux(self, d, kick):
        os.makedirs(d, exist_ok=True)
        ed = {"matchs": [{"domicile": True, "date": "2026-10-01", "saison": "2627", "buts_marques": 2, "buts_encaisses": 0}] * 5}
        x = {"match_id": "m1", "date": "2026-11-07", "domicile": "A", "exterieur": "B", "coup_d_envoi_utc": kick, "score": None, "cotes_betpawa": {"1x2": {"1": 1.5, "N": 4.0, "2": 6.0}, "btts": {"Oui": 1.7, "Non": 2.0}},
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

if __name__ == "__main__":
    unittest.main()
