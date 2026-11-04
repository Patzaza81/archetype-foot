import json, os, sys, tempfile, unittest, hashlib, shutil
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import inventaire_football_data as inv

CFG = inv.charger_config(os.path.join(RACINE, "config", "inventaire_regles.json"))
EU_HDR = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A"
EX_HDR = "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,,,"


def ligne_eu(code, d, h, a, hg=1, ag=0, extra=None):
    res = "H" if hg > ag else ("A" if hg < ag else "D")
    if hg == "":
        res = ""
    return f"{code},{d},15:00,{h},{a},{hg},{ag},{res},0,0,D,10,8,4,3,12,11,5,4,1,2,0,0,2.0,3.3,3.8"


def ecrire(chemin, texte):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    open(chemin, "w", encoding="utf-8").write(texte)


def fabriquer(racine, modif=None):
    snap = os.path.join(racine, CFG["chemins"]["snapshots"])
    for s in CFG["saisons"]:
        a = 2000 + int(s[:2])
        man_eu, man_ex = {"files": {}}, {"files": {}}
        ecrire(os.path.join(snap, s, "_SNAPSHOT_COMPLETE.json"), "{}")
        for code in CFG["competitions_europe"]:
            txt = EU_HDR + "\n" + "\n".join([ligne_eu(code, f"10/09/{a}", "Alpha FC", "Beta FC"),
                                             ligne_eu(code, f"17/09/{a}", "Beta FC", "Alpha FC", 2, 2)]) + "\n"
            p = os.path.join(snap, s, "raw", code + ".csv"); ecrire(p, txt)
            man_eu["files"][code] = {"sha256": inv.sha256_fichier(p), "rows": 2}
        for code in CFG["competitions_extra"]:
            lab = str(a)
            txt = EX_HDR + "\n" + f"X,Liga,{lab},10/09/{a},15:00,Alpha,Beta,1,0,H,2.0,3.0,4.0,,,\n"
            p = os.path.join(snap, s, "nouvelles_ligues", "raw", code + ".csv"); ecrire(p, txt)
            man_ex["files"][code] = {"sha256": inv.sha256_fichier(p), "rows": 1, "season_label": lab, "season_format": "civile"}
        ecrire(os.path.join(snap, s, "manifest.json"), json.dumps(man_eu))
        ecrire(os.path.join(snap, s, "nouvelles_ligues", "manifest.json"), json.dumps(man_ex))
    if modif:
        modif(snap)


class Unitaires(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def analyser(self, lignes, hdr=EU_HDR, annees=None):
        p = os.path.join(self.tmp, "x.csv"); ecrire(p, hdr + "\n" + "\n".join(lignes) + "\n")
        return inv.analyser_fichier(p, CFG, annees)

    def test_lignes_mesurees_vs_avec_score(self):
        an, _ = self.analyser([ligne_eu("F2", "10/09/2021", "A", "B"), ligne_eu("F2", "11/09/2021", "C", "D", "", "")])
        self.assertEqual((an["lignes_total"], an["lignes_avec_score"]), (2, 1))

    def test_colonne_absente_vs_presente_vide(self):
        an, _ = self.analyser(["X,Liga,2025,10/09/2025,15:00,A,B,1,0,H,,,,,,"], hdr=EX_HDR)
        self.assertEqual(inv.etat_colonne(an, "PSCH", CFG), "presente_vide")
        self.assertEqual(inv.etat_colonne(an, "HS", CFG), "absente")
        self.assertEqual(inv.etat_colonne(an, "FTHG", CFG), "complete")

    def test_alias_extras(self):
        an, _ = self.analyser(["X,Liga,2025,10/09/2025,15:00,A,B,3,1,H,,,,,,"], hdr=EX_HDR)
        self.assertEqual(an["colonnes_canoniques"]["FTHG"], "HG")

    def test_doublon_multi_criteres(self):
        l1 = ligne_eu("F2", "10/09/2021", "A", "B"); l2 = ligne_eu("F2", "24/09/2021", "A", "B")
        _, an = self.analyser([l1, l2])
        self.assertIn("doublon_probable_equipes_score_cotes", [x["type"] for x in an])
        _, an = self.analyser([l1, l1])
        t = [x["type"] for x in an]
        self.assertIn("doublon_ligne_exacte", t); self.assertIn("doublon_cle_date_equipes", t)

    def test_incoherences(self):
        mauvais = ligne_eu("F2", "10/09/2021", "A", "B").replace(",H,0,0,D,", ",A,0,0,D,")
        _, an = self.analyser([mauvais])
        self.assertIn("FTR_incoherent", [x["type"] for x in an])

    def test_date_hors_saison_annee_civile_vs_saison(self):
        _, an = self.analyser([ligne_eu("F2", "10/09/2019", "A", "B")], annees=(2021, 2022))
        self.assertIn("date_hors_saison", [x["type"] for x in an])
        self.assertEqual(inv._annees("2526", {"season_format": "civile"}, "extras"), (2025, 2025))
        self.assertEqual(inv._annees("2526", {"season_format": "a_cheval"}, "extras"), (2025, 2026))

    def test_changement_nom_candidat_sans_fusion(self):
        r = inv.candidats_changement_de_nom({"Racing Club"}, {"Racing Club Lens", "Zeta"}, 4)
        self.assertEqual(r, [["Racing Club", "Racing Club Lens"]])
        self.assertEqual(inv.candidats_changement_de_nom({"Alpha"}, {"Zeta"}, 4), [])

    def test_editions_non_fusionnees(self):
        an, _ = self.analyser(["X,Copa,2025,10/09/2025,15:00,A,B,1,0,H,,,,,,", "X,Liga,2025,17/09/2025,15:00,C,D,1,1,D,,,,,,"], hdr=EX_HDR)
        self.assertEqual(sorted(an["editions"]), ["Copa", "Liga"])


class Valeurs(unittest.TestCase):
    def setUp(self):
        self.C = inv.Cfg(CFG)

    def v(self, col, val):
        canon = col
        return self.C.classer_valeur(col, canon, val)

    def test_valides(self):
        for col, val in (("B365AHH", "0.56"), ("AvgCAHA", "0.6"), ("B365H", "1.01"), ("BMGMCH", "2.5"), ("HS", "12"), ("P>2.5", "1.9")):
            self.assertEqual(self.v(col, val), (True, None), (col, val))

    def test_invalides(self):
        casse = {("B365AHH", "0"): "code_remplissage", ("B365CH", "#"): "code_remplissage", ("1XBH", "1xBet"): "code_remplissage",
                 ("USAH", "x"): "code_remplissage", ("B365H", "0.9"): "erreur_donnee", ("B365H", "0"): "code_remplissage",
                 ("HS", "2.5"): "erreur_donnee", ("HS", "-1"): "erreur_donnee", ("B365AHH", "-0.3"): "erreur_donnee"}
        for (col, val), cat in casse.items():
            self.assertEqual(self.v(col, val), (False, cat), (col, val))

    def test_manquantes_comptees(self):
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, "x.csv")
            l1 = ligne_eu("F2", "10/09/2021", "A", "B")
            l2 = ligne_eu("F2", "11/09/2021", "C", "D").replace(",10,8,4,3,", ",,8,4,3,")
            ecrire(p, EU_HDR + "\n" + l1 + "\n" + l2 + "\n")
            an, _ = inv.analyser_fichier(p, CFG)
            st = an["editions"]["F2"]["colonnes"]["HS"]
            self.assertEqual((st["valides_joues"], st["manquantes_joues"]), (1, 1))
        finally:
            shutil.rmtree(tmp)


class Statuts(unittest.TestCase):
    def cel(self, taux_ok, joues=10, coh=None):
        ed = {"colonnes": {"HS": {"valides_joues": taux_ok}, "AS": {"valides_joues": taux_ok}},
              "coherence": coh or {k: {"evaluees": 0, "violations": 0} for k in ("FTR_vs_buts", "mt_inferieur_ft", "cadres_inf_tirs", "HTR_vs_buts_mt")}}
        return {"colonnes": ["HS", "AS"], "colonnes_canoniques": {}, "lignes_avec_score": joues, "editions": {"e": ed}}

    def eval(self, ok):
        cells = [(s, self.cel(ok)) for s in CFG["saisons"]]
        return inv.evaluer_capacite("tirs", CFG["capacites"]["tirs"], cells, CFG)["statut"]

    def test_confirmee(self): self.assertEqual(self.eval(10), "CAPACITE_CONFIRMEE")
    def test_limitee(self): self.assertEqual(self.eval(9), "CAPACITE_LIMITEE")
    def test_inexploitable(self): self.assertEqual(self.eval(0), "CAPACITE_INEXPLOITABLE")

    def test_saison_manquante_limitee(self):
        cells = [(s, self.cel(10)) for s in CFG["saisons"][:4]] + [("2526", None)]
        self.assertEqual(inv.evaluer_capacite("tirs", CFG["capacites"]["tirs"], cells, CFG)["statut"], "CAPACITE_LIMITEE")


class Bout_en_bout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def lancer(self):
        os.makedirs(os.path.join(self.tmp, "config"), exist_ok=True)
        shutil.copy(os.path.join(RACINE, "config", "inventaire_regles.json"), os.path.join(self.tmp, "config"))
        return inv.main(["--racine", self.tmp])

    def sortie(self, nom):
        return json.load(open(os.path.join(self.tmp, "data", "inventaire", nom), encoding="utf-8"))

    def test_38_competitions_5_saisons(self):
        fabriquer(self.tmp)
        self.assertEqual(self.lancer(), 0)
        m = self.sortie("manifest_global.json")
        self.assertEqual(len(m["competitions"]), 38)
        for c in m["competitions"].values():
            self.assertEqual(len(c["saisons"]), 5)
            self.assertTrue(all(s["presente"] for s in c["saisons"].values()))
        p = self.sortie("profils_capacite.json")
        self.assertEqual(len(p["competitions"]), 38)
        self.assertEqual(p["competitions"]["F1"]["capacites"]["resultat_final"]["statut"], "CAPACITE_CONFIRMEE")
        self.assertEqual(p["competitions"]["ARG"]["capacites"]["tirs"]["statut"], "CAPACITE_INEXPLOITABLE")
        self.assertEqual(p["competitions"]["ARG"]["capacites"]["resultat_final"]["statut"], "CAPACITE_CONFIRMEE")

    def test_reproductible(self):
        fabriquer(self.tmp)
        self.lancer(); a = open(os.path.join(self.tmp, "data/inventaire/manifest_global.json"), "rb").read()
        self.lancer(); b = open(os.path.join(self.tmp, "data/inventaire/manifest_global.json"), "rb").read()
        self.assertEqual(a, b)

    def test_archive_absente_bloque_publication(self):
        fabriquer(self.tmp, lambda snap: os.remove(os.path.join(snap, "2324", "raw", "F2.csv")))
        self.assertEqual(self.lancer(), 1)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data/inventaire/profils_capacite.json")))
        self.assertFalse(self.sortie("dernier_run.json")["publication"])

    def test_hash_different_du_manifest_bloque(self):
        def m(snap):
            p = os.path.join(snap, "2425", "raw", "E0.csv"); open(p, "a").write("\n")
            open(p, "a").write(ligne_eu("E0", "11/09/2024", "A", "B") + "\n")
        fabriquer(self.tmp, m)
        self.assertEqual(self.lancer(), 1)

    def test_archives_non_modifiees(self):
        fabriquer(self.tmp)
        snap = os.path.join(self.tmp, CFG["chemins"]["snapshots"])
        av = inv.empreinte_arbre(snap); self.lancer()
        self.assertEqual(av, inv.empreinte_arbre(snap))

    def test_complement_manuel_declare_sans_changer_statut(self):
        fabriquer(self.tmp)
        ecrire(os.path.join(self.tmp, "data/inventaire/complements_manuels.json"), json.dumps({"complements": [
            {"competition": "ARG", "saison": "2526", "colonnes": ["HS", "AS"], "source": "ref", "date_ajout": "2026-11-04"}]}))
        self.assertEqual(self.lancer(), 0)
        p = self.sortie("profils_capacite.json")["competitions"]["ARG"]
        self.assertEqual(len(p["complements_manuels"]), 1)
        self.assertEqual(p["capacites"]["tirs"]["statut"], "CAPACITE_INEXPLOITABLE")


class Recomptage(unittest.TestCase):
    def test_recomptage_sans_ecart_sur_donnees_fabriquees(self):
        import recomptage_independant as rc
        tmp = tempfile.mkdtemp()
        try:
            fabriquer(tmp)
            os.makedirs(os.path.join(tmp, "config")); shutil.copy(os.path.join(RACINE, "config", "inventaire_regles.json"), os.path.join(tmp, "config"))
            self.assertEqual(inv.main(["--racine", tmp]), 0)
            argv = ["--snapshots", os.path.join(tmp, CFG["chemins"]["snapshots"]), "--config", os.path.join(tmp, "config", "inventaire_regles.json"),
                    "--manifest", os.path.join(tmp, "data/inventaire/manifest_global.json"), "--sortie", os.path.join(tmp, "data/inventaire")]
            self.assertEqual(rc.main(argv), 0)
            # un ecart doit etre detecte si on falsifie le manifest
            mp = argv[argv.index("--manifest") + 1]
            m = json.load(open(mp, encoding="utf-8")); m["competitions"]["F1"]["saisons"]["2122"]["lignes_avec_score"] += 1
            json.dump(m, open(mp, "w", encoding="utf-8"))
            self.assertEqual(rc.main(argv), 1)
        finally:
            shutil.rmtree(tmp)


@unittest.skipUnless(os.environ.get("INVENTAIRE_DONNEES_REELLES") == "1", "donnees reelles non demandees")
class DonneesReelles(unittest.TestCase):
    def test_38_competitions_reelles(self):
        racine = os.environ.get("INVENTAIRE_RACINE", os.path.dirname(RACINE))
        cfg = CFG
        for s in cfg["saisons"]:
            for code in cfg["competitions_europe"]:
                self.assertTrue(os.path.exists(os.path.join(racine, cfg["chemins"]["snapshots"], s, "raw", code + ".csv")), (s, code))
            for code in cfg["competitions_extra"]:
                self.assertTrue(os.path.exists(os.path.join(racine, cfg["chemins"]["snapshots"], s, "nouvelles_ligues", "raw", code + ".csv")), (s, code))
        self.assertEqual(len(cfg["competitions_europe"]) + len(cfg["competitions_extra"]), 38)


if __name__ == "__main__":
    unittest.main()
