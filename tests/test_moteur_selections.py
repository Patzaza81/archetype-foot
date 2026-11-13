"""Tests du moteur « selections » : historique au même lieu (sans fuite) et verdict à la manière d'Analyse Verdict. Chaque règle : >= 3 cas qui passent et >= 3 cas qui échouent."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_selections import donnees, verdict

CFG = {"cote_min": 1.26, "nmin": 4, "fenetre_jours": 1825, "officiels_seulement": True}
Q = donnees.QUALIF


def mt(date, dom, ext, hs, as_, comp=Q, neutre=False):
    return {"date": date, "domicile": dom, "exterieur": ext, "buts_dom": hs, "buts_ext": as_, "competition": comp, "neutre": neutre}


def serie(equipe, role, scores, debut="2026-01-01", comp=Q):
    """Matchs de `equipe` dans le rôle donné ; scores = [(buts marqués par l'équipe, buts encaissés)]. Adversaires distincts, un match par semaine."""
    out = []
    for i, (mq, en) in enumerate(scores):
        d = (__import__("datetime").date.fromisoformat(debut) + __import__("datetime").timedelta(days=7 * i)).isoformat()
        out.append(mt(d, equipe, f"Adv{role}{i}", mq, en, comp) if role == "dom" else mt(d, f"Adv{role}{i}", equipe, en, mq, comp))
    return out


MATCH = {"date": "2027-10-10", "domicile": "Alpha", "exterieur": "Beta", "neutre": False}


def hist_dominant():
    """Alpha gagne tous ses matchs à domicile, Beta perd tous les siens à l'extérieur."""
    return donnees.Historique(serie("Alpha", "dom", [(3, 0), (2, 0), (4, 1), (2, 1), (3, 0)]) + serie("Beta", "ext", [(0, 2), (1, 3), (0, 1), (1, 2), (0, 3)]))


class MemeLieu(unittest.TestCase):
    def setUp(self): self.H = donnees.Historique(serie("Alpha", "dom", [(1, 0)] * 5, "2026-01-01"))
    def test_passent(self):
        self.assertEqual(len(self.H.meme_lieu("Alpha", "dom", "2027-01-01", 1825, True)), 5)                        # tous les matchs dans la fenêtre
        self.assertEqual(len(self.H.meme_lieu("Alpha", "dom", "2026-01-23", 1825, True)), 4)                       # strictement avant la date : le 5e match (29/01) n'est pas vu
        self.assertEqual(self.H.meme_lieu("Alpha", "dom", "2027-01-01", 1825, True)[0], (1, 0))                    # (marqués, encaissés)
    def test_echouent(self):
        self.assertEqual(self.H.meme_lieu("Alpha", "dom", "2026-01-01", 1825, True), [])                           # le jour même : pas de fuite
        self.assertEqual(self.H.meme_lieu("Alpha", "ext", "2027-01-01", 1825, True), [])                           # mauvais rôle
        self.assertEqual(self.H.meme_lieu("Alpha", "dom", "2032-06-01", 365, True), [])                            # hors fenêtre
        self.assertEqual(self.H.meme_lieu("Inconnu", "dom", "2027-01-01", 1825, True), [])                         # équipe absente
    def test_neutre_exclu(self):
        H = donnees.Historique([mt("2026-01-01", "Alpha", "B", 1, 0, neutre=True), mt("2026-01-08", "C", "Alpha", 1, 0, neutre=True), mt("2026-01-15", "Alpha", "D", 2, 0)])
        self.assertEqual(H.meme_lieu("Alpha", "dom", "2027-01-01", 1825, True), [(2, 0)]); self.assertEqual(H.meme_lieu("Alpha", "ext", "2027-01-01", 1825, True), [])
    def test_amicaux(self):
        H = donnees.Historique(serie("Alpha", "dom", [(1, 0)] * 3, comp="Friendly") + serie("Alpha", "dom", [(2, 0)] * 2, "2026-03-01"))
        self.assertEqual(len(H.meme_lieu("Alpha", "dom", "2027-01-01", 1825, True)), 2); self.assertEqual(len(H.meme_lieu("Alpha", "dom", "2027-01-01", 1825, False)), 5)
    def test_avantage(self):
        H = donnees.Historique([mt("2026-01-01", "A", "B", 3, 1), mt("2026-01-08", "C", "D", 2, 2), mt("2026-01-15", "E", "F", 1, 0, comp="Friendly")])
        self.assertAlmostEqual(H.avantage("2027-01-01", 1825), 1.0)                                                # (3+2 - 1+2) / 2 = 1, l'amical n'entre pas
        self.assertEqual(H.avantage("2026-01-01", 1825), 0.0)                                                      # aucun match avant : 0


class Verdict(unittest.TestCase):
    def test_tient(self):
        H = hist_dominant()
        for m in ("1", "1N", "total_plus_1.5"):
            r = verdict.constat(H, MATCH, m, None, CFG); self.assertEqual(r["verdict"], "TIENT", m)
        self.assertEqual(verdict.constat(H, MATCH, "1", None, CFG)["A"]["reussi"], 5)
    def test_ne_tient_pas(self):
        H = hist_dominant()
        for m in ("2", "N2", "btts_oui"):
            self.assertEqual(verdict.constat(H, MATCH, m, None, CFG)["verdict"], "NE TIENT PAS", m)
    def test_avec_reserve(self):
        H = donnees.Historique(serie("Gamma", "dom", [(1, 1), (2, 1), (1, 2), (2, 2), (3, 0)]) + serie("Delta", "ext", [(0, 2), (0, 3), (0, 1), (1, 2), (0, 1)]))
        r = verdict.constat(H, {**MATCH, "domicile": "Gamma", "exterieur": "Delta"}, "btts_oui", None, CFG)
        self.assertEqual((r["A"]["reussi"], r["B"]["reussi"], r["verdict"]), (4, 1, "TIENT AVEC RÉSERVE"))
    def test_attaque_contre_defense_remonte_d_un_cran(self):
        H = donnees.Historique(serie("Eps", "dom", [(0, 0), (0, 0), (0, 0), (4, 2), (3, 3)]) + serie("Zeta", "ext", [(0, 0), (0, 0), (0, 0), (3, 3), (2, 4)]))
        r = verdict.constat(H, {**MATCH, "domicile": "Eps", "exterieur": "Zeta"}, "total_plus_1.5", None, CFG)
        self.assertEqual((r["A"]["reussi"], r["B"]["reussi"]), (2, 2)); self.assertEqual(r["verdict"], "TIENT AVEC RÉSERVE")     # les fréquences disaient NE TIENT PAS (2 sur 5), les buts attendus (2,4) confirment
    def test_non_evaluable(self):
        H = donnees.Historique(serie("Alpha", "dom", [(1, 0)] * 3) + serie("Beta", "ext", [(0, 1)] * 5))
        self.assertEqual(verdict.constat(H, MATCH, "1", None, CFG)["verdict"], "NON ÉVALUABLE")                                 # 3 matchs à domicile : moins de 4
        H2 = donnees.Historique(serie("Alpha", "dom", [(1, 0)] * 5) + serie("Beta", "ext", [(0, 1)] * 3))
        self.assertEqual(verdict.constat(H2, MATCH, "1", None, CFG)["verdict"], "NON ÉVALUABLE")                                # 3 matchs à l'extérieur
        self.assertEqual(verdict.constat(hist_dominant(), {**MATCH, "neutre": True}, "1", None, CFG)["verdict"], "NON ÉVALUABLE")  # terrain neutre
        self.assertEqual(verdict.constat(donnees.Historique([]), MATCH, "1", None, CFG)["verdict"], "NON ÉVALUABLE")             # aucune donnée
    def test_cote_minimale(self):
        H = hist_dominant()
        for c in (1.0, 1.2, 1.25):
            self.assertEqual(verdict.constat(H, MATCH, "1", c, CFG)["verdict"], "REFUSÉ", c)
        for c in (1.26, 1.5, 3.0): self.assertEqual(verdict.constat(H, MATCH, "1", c, CFG)["verdict"], "TIENT", c)
    def test_pas_de_fuite_du_match_lui_meme(self):
        H = donnees.Historique(serie("Alpha", "dom", [(3, 0), (2, 0), (4, 1), (2, 1)]) + serie("Beta", "ext", [(0, 2), (1, 3), (0, 1), (1, 2)]) + [mt("2027-10-10", "Alpha", "Beta", 0, 5)])
        r = verdict.constat(H, MATCH, "1", None, CFG); self.assertEqual((r["verdict"], r["A"]["n"]), ("TIENT", 4))         # le résultat du jour n'entre pas dans l'échantillon


class Paris(unittest.TestCase):
    def test_sans_cotes_aucune_cote(self):
        R = verdict.paris(hist_dominant(), MATCH, None, CFG)
        self.assertTrue(R and all(r["cote"] is None for r in R)); self.assertEqual(R[0]["verdict"], "TIENT")
        self.assertEqual([r["verdict"] for r in R], sorted((r["verdict"] for r in R), key=verdict.ORDRE.index))             # classés du plus fiable au moins fiable
    def test_avec_cotes_betpawa(self):
        cotes = {"1x2": {"1": 1.20, "N": 5.0, "2": 8.0}, "double_chance": {"1N": 1.05}, "over_under_1.5": {"plus": 1.30, "moins": 3.2}}
        R = verdict.paris(hist_dominant(), MATCH, cotes, CFG)
        self.assertEqual({r["marche"] for r in R}, {"total_plus_1.5"})                                                          # 1 (1,20) et 1N (1,05) sont sous 1,26 ; les autres ne tiennent pas
        self.assertEqual(R[0]["cote"], 1.30)
    def test_deterministe(self):
        self.assertEqual(verdict.paris(hist_dominant(), MATCH, None, CFG), verdict.paris(hist_dominant(), MATCH, None, CFG))


class Config(unittest.TestCase):
    def test_config_livree(self):
        c = verdict.config(); self.assertEqual((c["cote_min"], c["nmin"]), (1.26, 4)); self.assertIn(c["fenetre_jours"], (365, 730, 1095, 1460, 1825, 2190)); self.assertIsInstance(c["officiels_seulement"], bool)



class TestCompetitionsOfficielles(unittest.TestCase):
    def test_officielles(self):
        from moteur_selections.competitions import est_selection_officielle as f
        for c in ("Europe : Ligue des Nations de l'UEFA Ligue A Groupe 1",
                  "Amérique du Nord : Ligue des Nations de la CONCACAF Quarts de Finale",
                  "Afrique : Coupe d'Afrique des Nations Groupe A",
                  "Afrique : Coupe des Nations Qualification Groupe C",
                  "Asie : Championnat SAFF Demi-Finale",
                  "Europe : Qualifications Coupe du Monde Groupe C",
                  "Europe :\n   Ligue des Nations de l'UEFA Ligue C Groupe 2"):
            self.assertTrue(f(c), c)

    def test_exclues(self):
        from moteur_selections.competitions import est_selection_officielle as f
        for c in ("Monde : Matchs Amicaux Internationaux", "Monde : Matchs Amicaux U21",
                  "Afrique : Afrique U23 Coupe des nations Qualification 2nd Round",
                  "Afrique : Ligue des Champions Féminine de la CAF Finale",
                  "France : Ligue 1", "Europe : Ligue des Champions Phase de Ligue",
                  "Amérique du Sud : Copa Libertadores",
                  "Afrique du Sud : Diski Challenge",
                  "Monde : Matchs Amicaux Non-FIFA"):
            self.assertFalse(f(c), c)


class TestCollecte(unittest.TestCase):
    def test_collecte_ne_garde_que_les_selections(self):
        import json, tempfile, os
        from moteur_selections.collecte import collecte
        ms = [
            {"match_id": "a", "domicile": "Ghana", "exterieur": "Somalie", "date": "2026-11-12", "competition": "Afrique :\n   Coupe des Nations Qualification Groupe A"},
            {"match_id": "a", "domicile": "Ghana", "exterieur": "Somalie", "date": "2026-11-12", "competition": "Afrique : Coupe des Nations Qualification Groupe A"},
            {"match_id": "b", "domicile": "X", "exterieur": "Y", "competition": "Monde : Matchs Amicaux Internationaux"},
            {"match_id": "c", "domicile": "PSG", "exterieur": "OM", "competition": "France : Ligue 1"},
        ]
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "matchs_du_jour.json"), "w") as f:
                json.dump(ms, f)
            r = collecte(d)
        self.assertEqual([m["match_id"] for m in r], ["a"])
        self.assertEqual(r[0]["competition"], "Afrique : Coupe des Nations Qualification Groupe A")


class TestPronostics(unittest.TestCase):
    def test_sans_cote_ou_equipe_inconnue_aucun_pari(self):
        from moteur_selections.pronostics import calcule
        m = {"match_id": "x", "date": "2026-11-13", "domicile": "Atlantide", "exterieur": "France", "competition": "Europe : Ligue des Nations de l'UEFA", "heure_cameroun": "20:00"}
        self.assertEqual(calcule([m], None, {"x": {"1x2": {"1": 2.0}}}, {}), [])        # équipe inconnue
        self.assertEqual(calcule([{**m, "domicile": "Espagne"}], None, {}, {}), [])      # pas de cote

    def test_noms_traduits_existent(self):
        from moteur_selections import noms
        self.assertEqual(noms.FR_EN["Pays-Bas"], "Netherlands"); self.assertEqual(noms.FR_EN["Irlande"], "Republic of Ireland")

    def test_heure_utc(self):
        from moteur_selections.pronostics import _utc
        self.assertEqual(_utc("2026-11-13", "20:45"), "2026-11-13T19:45:00Z"); self.assertIsNone(_utc("2026-11-13", None))

if __name__ == "__main__":
    unittest.main()
