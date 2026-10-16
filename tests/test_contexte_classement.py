import unittest

from contexte_classement import extraire_zones_classement, enjeu_equipe


class TestContexteClassement(unittest.TestCase):
    def test_absence_de_legende_reste_indeterminee(self):
        html = """
        <table><tr><th>Pts</th><th>J</th><th>V</th><th>N</th><th>D</th><th>BP</th><th>BC</th><th>Diff</th></tr>
        <tr><td>1</td><td>20</td><td>8</td><td>6</td><td>2</td><td>0</td><td>18</td><td>5</td><td>13</td></tr></table>
        """
        resultat = extraire_zones_classement(html)
        self.assertEqual(resultat["statut"], "indetermine")
        self.assertEqual(enjeu_equipe(resultat, 1), {"statut": "indetermine", "zones": []})

    def test_zone_reliee_a_un_rang_par_classe_css(self):
        html = """
        <div class="legend-zone europe">Qualifications Ligue des Champions</div>
        <table>
          <tr class="europe"><td>1</td><td>Club A</td><td>20</td></tr>
          <tr><td>2</td><td>Club B</td><td>18</td></tr>
        </table>
        """
        resultat = extraire_zones_classement(html)
        self.assertEqual(resultat["statut"], "identifie")
        self.assertIn(1, resultat["zones"][0]["rangs"])
        self.assertEqual(enjeu_equipe(resultat, 1)["statut"], "identifie")

    def test_legend_sans_lien_de_couleur_ne_devine_pas_les_rangs(self):
        html = '<p>Relégation</p><table><tr><td>1</td><td>Club A</td></tr></table>'
        resultat = extraire_zones_classement(html)
        self.assertEqual(resultat["statut"], "indetermine")
        self.assertEqual(resultat["zones"][0]["rangs"], [])


if __name__ == "__main__":
    unittest.main()
