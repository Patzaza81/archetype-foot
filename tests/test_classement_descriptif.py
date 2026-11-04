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

    def test_statuts_archive_distincts_et_perimetre(self):
        base = {"competition": "F1", "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"]}
        def g(code, niveau="match_par_match"):
            return {"code": code, "matchs_documentes_absents": 1, "niveau_preuve": niveau, "perimetre": "implique_un_club_de_la_ligue", "detail": "d"}
        etendu = {"saison_reguliere": "paires_completes_verifiees", "phases_finales": "individuelle", "matchs_additionnels": "examines"}
        partiel = {"saison_reguliere": "comptes_par_equipe_et_total", "phases_finales": "individuelle", "matchs_additionnels": "non_examines"}
        par = [
            {"signalements_archive": [g("MATCH_ARCHIVE_MANQUANT")]},
            {"signalements_archive": [g("PHASE_EXCLUE_NON_DETAILLEE", "existence_seulement")]},
            {"signalements_archive": [g("MATCH_ATTRIBUE_NON_JOUE")]},
            {"signalements_archive": [g("MATCH_ATTRIBUE_NON_JOUE"), g("MATCH_ARCHIVE_MANQUANT")]},
            {"signalements_archive": [], "perimetre_examen": partiel},
        ]
        v = [dict(base, saison=s, **(par[i] if i < len(par) else {})) for i, s in enumerate(CFG["saisons"])]
        r = construire(self.tmp, v)
        f1 = r["competitions"]["F1"]
        a = [f1["archive_par_saison"][s] for s in CFG["saisons"]]
        attendu = ["MATCH_ARCHIVE_MANQUANT", "PHASE_EXCLUE_NON_DETAILLEE", "MATCH_ATTRIBUE_NON_JOUE", "MATCH_ARCHIVE_MANQUANT", "ARCHIVE_COMPLETE_PERIMETRE_PARTIEL"]
        self.assertEqual(a[:len(attendu)], attendu[:len(a)])
        self.assertTrue(all(st == "COMPLETUDE_VERIFIEE" for st in f1["completude_par_saison"].values()))
        self.assertTrue(f1["comparable_sans_reserve"])
        self.assertFalse(f1["comparable_archive_sans_reserve"])

    def test_score_attribue_divergent_distinct_d_un_match_absent(self):
        base = {"competition": "F1", "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"]}
        def g(code):
            return {"code": code, "matchs_documentes_absents": 0, "niveau_preuve": "match_par_match", "perimetre": "implique_un_club_de_la_ligue", "detail": "d"}
        par = [[g("SCORE_ATTRIBUE_DIVERGENT")], [g("SCORE_ATTRIBUE_DIVERGENT"), g("MATCH_ATTRIBUE_NON_JOUE")],
               [g("SCORE_ATTRIBUE_DIVERGENT"), g("MATCH_ARCHIVE_MANQUANT")], [g("SCORE_ATTRIBUE_DIVERGENT"), g("PHASE_EXCLUE_NON_DETAILLEE")], [g("MATCH_ATTRIBUE_NON_JOUE")]]
        v = [dict(base, saison=s, signalements_archive=par[i]) for i, s in enumerate(CFG["saisons"])]
        a = [construire(self.tmp, v)["competitions"]["F1"]["archive_par_saison"][s] for s in CFG["saisons"]]
        self.assertEqual(a, ["SCORE_ATTRIBUE_DIVERGENT", "SCORE_ATTRIBUE_DIVERGENT", "MATCH_ARCHIVE_MANQUANT", "PHASE_EXCLUE_NON_DETAILLEE", "MATCH_ATTRIBUE_NON_JOUE"])

    def test_perimetre_etendu_exige_les_trois_conditions(self):
        base = {"competition": "F1", "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"], "signalements_archive": []}
        etendu = {"saison_reguliere": "paires_completes_verifiees", "phases_finales": "aucune_phase_documentee", "matchs_additionnels": "examines"}
        v = [dict(base, saison=s, perimetre_examen=dict(etendu)) for s in CFG["saisons"]]
        r = construire(self.tmp, v)
        self.assertTrue(all(x == "ARCHIVE_COMPLETE_PERIMETRE_ETENDU" for x in r["competitions"]["F1"]["archive_par_saison"].values()))
        self.assertTrue(r["competitions"]["F1"]["comparable_archive_sans_reserve"])
        for cle, val in (("phases_finales", "total_seulement"), ("saison_reguliere", "comptes_par_equipe_et_total"), ("matchs_additionnels", "non_examines")):
            v2 = [dict(base, saison=s, perimetre_examen=dict(etendu, **{cle: val})) for s in CFG["saisons"]]
            import shutil as _sh
            _sh.rmtree(self.tmp); self.tmp = tempfile.mkdtemp()
            r2 = construire(self.tmp, v2)
            self.assertTrue(all(x == "ARCHIVE_COMPLETE_PERIMETRE_PARTIEL" for x in r2["competitions"]["F1"]["archive_par_saison"].values()), cle)
            self.assertFalse(r2["competitions"]["F1"]["comparable_archive_sans_reserve"])

    def test_sans_cle_signalements_rien_n_est_affirme(self):
        v = [{"competition": "F1", "saison": s, "equipes_attendues": 2, "matchs_attendus": 2, "preuves": ["x"]} for s in CFG["saisons"]]
        r = construire(self.tmp, v)
        self.assertTrue(all(x == "ARCHIVE_NON_EXAMINEE" for x in r["competitions"]["F1"]["archive_par_saison"].values()))
        self.assertFalse(r["competitions"]["F1"]["comparable_archive_sans_reserve"])
