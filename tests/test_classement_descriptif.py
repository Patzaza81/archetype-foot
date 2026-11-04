import json, os, shutil, sys, tempfile, unittest
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import classement_descriptif as cd
import inventaire_football_data as inv
import importlib.util
_spec = importlib.util.spec_from_file_location("fixtures_inventaire", os.path.join(RACINE, "tests", "test_inventaire_football_data.py"))
_fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fx)
fabriquer, ecrire, CFG, EU_HDR, ligne_eu = _fx.fabriquer, _fx.ecrire, _fx.CFG, _fx.EU_HDR, _fx.ligne_eu


def construire(tmp, verifs=None):
    fabriquer(tmp)
    os.makedirs(os.path.join(tmp, "config"), exist_ok=True)
    shutil.copy(os.path.join(RACINE, "config", "inventaire_regles.json"), os.path.join(tmp, "config"))
    assert inv.main(["--racine", tmp]) == 0
    if verifs is not None:
        ecrire(os.path.join(tmp, "data/inventaire/verifications_completude.json"), json.dumps({"verifications": verifs}))
    assert cd.main(["--racine", tmp]) in (0, 1)
    return json.load(open(os.path.join(tmp, "data/inventaire/classement_descriptif.json"), encoding="utf-8"))


class Classement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_38_profils_sans_verification_non_verifiee(self):
        r = construire(self.tmp)
        self.assertEqual(len(r["competitions"]), 38)
        for c in r["competitions"].values():
            self.assertTrue(all(v == "COMPLETUDE_NON_VERIFIEE" for v in c["completude_par_saison"].values()))
            self.assertFalse(c["comparable_sans_reserve"])

    def test_verification_concordante(self):
        v = [{"competition": "F1", "saison": s, "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"]} for s in CFG["saisons"]]
        r = construire(self.tmp, v)
        self.assertTrue(r["competitions"]["F1"]["comparable_sans_reserve"])
        self.assertFalse(r["competitions"]["E0"]["comparable_sans_reserve"])

    def test_verification_divergente(self):
        v = [{"competition": "F1", "saison": "2122", "equipes_attendues": 20, "matchs_attendus": 380, "preuves": ["x"]}]
        r = construire(self.tmp, v)
        self.assertEqual(r["competitions"]["F1"]["completude_par_saison"]["2122"], "COMPLETUDE_INCOHERENTE")

    def test_trois_dimensions_separees_sans_score_global(self):
        r = construire(self.tmp)
        c = r["competitions"]["F1"]
        for k in ("volume", "couverture", "fiabilite"):
            self.assertIn(k, c)
        self.assertNotIn("score", json.dumps(c).lower().replace("avec_score", ""))

    def test_structure_ecart_detecte(self):
        p = os.path.join(self.tmp, "x.csv")
        ecrire(p, EU_HDR + "\n" + ligne_eu("F1", "10/09/2021", "A", "B") + "\n" + ligne_eu("F1", "11/09/2021", "A", "B") + "\n")
        s = cd.structure_saison(p)["F1"]
        self.assertEqual((s["structure"], s["paires_manquantes"], s["paires_en_double"]), ("ECART_STRUCTURE", 1, 1))
        ecrire(p, EU_HDR + "\n" + ligne_eu("F1", "10/09/2021", "A", "B") + "\n" + ligne_eu("F1", "11/09/2021", "B", "A") + "\n")
        self.assertEqual(cd.structure_saison(p)["F1"]["structure"], "ALLER_RETOUR_COMPLET")

    def test_editions_non_melangees(self):
        p = os.path.join(self.tmp, "x.csv")
        ecrire(p, "Country,League,Season,Date,Time,Home,Away,HG,AG,Res\nX,Copa,2025,01/02/2025,,A,B,1,0,H\nX,Liga,2025,02/02/2025,,A,B,1,0,H\n")
        self.assertEqual(sorted(cd.structure_saison(p)), ["Copa", "Liga"])


    def test_statut_archive_distinct_de_la_completude(self):
        base = {"competition": "F1", "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"]}
        sig = [{"code": "MATCH_ARCHIVE_MANQUANT", "matchs_documentes_absents": 1, "niveau_preuve": "match_par_match", "perimetre": "implique_un_club_de_la_ligue", "detail": "d"}]
        v = []
        for i, s in enumerate(CFG["saisons"]):
            e = dict(base, saison=s)
            if i == 0:
                e["signalements_archive"] = sig
            elif i == 1:
                e["signalements_archive"] = []
            v.append(e)
        r = construire(self.tmp, v)
        f1 = r["competitions"]["F1"]
        a = [f1["archive_par_saison"][s] for s in CFG["saisons"]]
        self.assertEqual(a[0], "MATCH_ARCHIVE_MANQUANT")
        self.assertEqual(a[1], "ARCHIVE_COMPLETE_EXAMINEE")
        self.assertTrue(all(x == "ARCHIVE_NON_EXAMINEE" for x in a[2:]))
        self.assertTrue(all(st == "COMPLETUDE_VERIFIEE" for st in f1["completude_par_saison"].values()))
        self.assertTrue(f1["comparable_sans_reserve"])
        self.assertFalse(f1["comparable_archive_sans_reserve"])
        self.assertEqual(list(f1["signalements_archive"]), [CFG["saisons"][0]])

    def test_sans_cle_signalements_rien_n_est_affirme(self):
        v = [{"competition": "F1", "saison": s, "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"]} for s in CFG["saisons"]]
        r = construire(self.tmp, v)
        self.assertTrue(all(x == "ARCHIVE_NON_EXAMINEE" for x in r["competitions"]["F1"]["archive_par_saison"].values()))
        self.assertFalse(r["competitions"]["F1"]["comparable_archive_sans_reserve"])


if __name__ == "__main__":
    unittest.main()
