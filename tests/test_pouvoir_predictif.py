import os, sys, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pouvoir_predictif as pp

def _modifie(matchs, idx, bd, ba):
    m = list(matchs); d, s, h, a, _, _ = m[idx]; m[idx] = (d, s, h, a, bd, ba); return m

class Causalite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = pp.charger("E0")[:700]

    def test_futur_sans_effet_sur_le_passe(self):          # 3 familles: le futur ne change AUCUNE prediction anterieure
        t = 500; jour = self.m[t][0]
        avant = [i for i, x in enumerate(self.m) if x[0] < jour]
        futur = [(d, s, h, a, 9 - bd % 3, 7) if i >= t else (d, s, h, a, bd, ba) for i, (d, s, h, a, bd, ba) in enumerate(self.m)]
        for f in pp.FAMILLES:
            a = pp.predire(self.m, f, 10, 365)[avant]; b = pp.predire(futur, f, 10, 365)[avant]
            np.testing.assert_allclose(a, b, err_msg=f)

    def test_meme_journee_sans_effet(self):                 # le resultat d'un match ne change pas les predictions de sa propre journee
        t = 400; jour = self.m[t][0]; meme = [i for i, x in enumerate(self.m) if x[0] == jour]
        self.assertGreaterEqual(len(meme), 2)
        alt = _modifie(self.m, meme[0], 8, 0)
        for f in pp.FAMILLES:
            np.testing.assert_allclose(pp.predire(self.m, f, 10, None)[meme], pp.predire(alt, f, 10, None)[meme], err_msg=f)
        np.testing.assert_allclose(pp.reference(self.m)[meme], pp.reference(alt)[meme])

    def test_sensibilite_le_passe_change_la_prediction(self):   # cas qui DOIVENT differer (le test detecte bien un effet)
        t = 600; jour = self.m[t][0]; h = self.m[t][2]
        idx = [i for i, x in enumerate(self.m) if x[0] < jour and (x[2] == h or x[3] == h)][0]
        alt = _modifie(self.m, idx, 9, 9)
        for f in pp.FAMILLES:
            a = pp.predire(self.m, f, 2, None)[t]; b = pp.predire(alt, f, 2, None)[t]
            self.assertFalse(np.allclose(a, b), f)

    def test_choix_de_config_independant_de_la_saison_test(self):
        full = pp.charger("E0"); r0 = pp.analyser("E0", full)
        # on bouleverse tous les resultats de la derniere saison (2526): le choix pour 2223, 2324, 2425 doit rester identique
        alt = [(d, s, h, a, (bd + 3) % 5, (ba * 2 + 1) % 4) if s == "2526" else (d, s, h, a, bd, ba) for d, s, h, a, bd, ba in full]
        r1 = pp.analyser("E0", alt)
        for key, v in r0["resultats"].items():
            for s in ("2223", "2324", "2425"):
                self.assertEqual(v["config_retenue"][s], r1["resultats"][key]["config_retenue"][s], (key, s))
                self.assertEqual(v["gain_par_saison_test"][s], r1["resultats"][key]["gain_par_saison_test"][s], (key, s))

class Calculs(unittest.TestCase):
    def test_reference_frequence_expansive_laplace(self):
        m = [(1, "2122", "A", "B", 2, 0), (2, "2122", "C", "D", 1, 1), (3, "2122", "A", "C", 0, 3)]
        r = pp.reference(m)
        self.assertTrue(np.isnan(r[0]).all())
        np.testing.assert_allclose(r[1][:3], [(1 + 1) / 4, 1 / 4, 1 / 4])        # apres 1 match: 1 victoire dom
        self.assertAlmostEqual(r[1][4], (0 + 1) / 3)                              # o25: 2-0 = 2 buts, evenement faux: (0+1)/3
        np.testing.assert_allclose(r[2][:3], [(1 + 1) / 5, (1 + 1) / 5, 1 / 5])  # apres 2 matchs: dom 1, nul 1, ext 0

    def test_poisson_probabilites_coherentes(self):
        p = pp._probas_poisson(np.array([1.5, 0.3, 2.8]), np.array([1.1, 0.3, 0.5]))
        np.testing.assert_allclose(p[:, :3].sum(axis=1), 1.0, atol=1e-6)
        self.assertTrue((p[:, 3] >= p[:, 4]).all() and (p[:, 4] >= p[:, 5]).all())  # >=2 >= >=3 >= >=4
        p2 = pp._probas_poisson(np.array([1.2]), np.array([1.2])); self.assertAlmostEqual(p2[0, 0], p2[0, 2], places=9)

    def test_evenements(self):
        self.assertEqual(pp.evenements(2, 1), (True, False, False, True, True, False, True))
        self.assertEqual(pp.evenements(0, 0), (False, True, False, False, False, False, False))
        self.assertEqual(pp.evenements(0, 4), (False, False, True, True, True, True, False))

if __name__ == "__main__": unittest.main()
