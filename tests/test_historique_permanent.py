"""Historique permanent : l'assemblage du jour ne garde que les equipes a venir ; les blocs des autres sont conserves."""
import historique_permanent as HP

def bloc(cle, ms, fd=False): return {"cle_cache": cle, "competition": "bulgarie : parva liga", "couverte_par_football_data": fd, "matchs": ms}
M1 = {"date": "2026-10-11", "domicile": True, "adversaire": "Dunav", "buts_marques": 2, "buts_encaisses": 3}
M2 = {"date": "2026-11-06", "domicile": False, "adversaire": "Loko", "buts_marques": 1, "buts_encaisses": 1}

# doivent reussir
def test_equipe_absente_du_jour_est_conservee_et_rendue(tmp_path):
    f = str(tmp_path / "a.json"); HP.archiver({"equipes": [bloc("S", [M1]), bloc("D", [M1])]}, f)
    HP.archiver({"equipes": [bloc("D", [M1, M2])]}, f)                      # S n'a plus de match a venir
    r = HP.completer({"equipes": [bloc("D", [M1, M2])]}, f); cles = {x["cle_cache"]: x for x in r["equipes"]}
    assert set(cles) == {"S", "D"} and cles["S"]["hors_fenetre"] and "hors_fenetre" not in cles["D"]
def test_bloc_du_jour_remplace_l_ancien(tmp_path):
    f = str(tmp_path / "a.json"); HP.archiver({"equipes": [bloc("D", [M1])]}, f); HP.archiver({"equipes": [bloc("D", [M1, M2])]}, f)
    assert len(HP.lire(f)["D"]["matchs"]) == 2
def test_archivage_idempotent(tmp_path):
    f = str(tmp_path / "a.json"); d = {"equipes": [bloc("D", [M1])]}; HP.archiver(d, f); a = open(f).read(); assert HP.archiver(d, f) == (1, 0) and open(f).read() == a
def test_ligues_retrouve_le_match_perdu(tmp_path):
    import moteur_dc.donnees as D
    A = {"equipes": [{**bloc("https://www.matchendirect.fr/equipe/a_abcdefghij.html||bulgarie : parva liga", [M1]), "nom_matchendirect": "A"},
                     {**bloc("https://www.matchendirect.fr/equipe/b_abcdefghij.html||bulgarie : parva liga", [{**M1, "domicile": False, "adversaire": "A", "buts_marques": 3, "buts_encaisses": 2}]), "nom_matchendirect": "Dunav"}]}
    f = str(tmp_path / "a.json"); HP.archiver(A, f)
    jour = {"equipes": [{**A["equipes"][0], "matchs": []}]}                  # le jour : seule A reste, sans match connu
    assert len(D.Ligues(HP.completer(jour, f)).matchs["bulgarie : parva liga"]) == 1

# doivent echouer (rejetes)
def test_championnat_couvert_par_football_data_non_archive(tmp_path):
    f = str(tmp_path / "a.json"); HP.archiver({"equipes": [bloc("FD", [M1], fd=True)]}, f); assert HP.lire(f) == {}
def test_bloc_sans_match_ou_sans_cle_non_archive(tmp_path):
    f = str(tmp_path / "a.json"); HP.archiver({"equipes": [bloc("V", []), bloc("", [M1])]}, f); assert HP.lire(f) == {}
def test_fichier_absent_ou_casse_donne_vide(tmp_path):
    f = tmp_path / "a.json"; assert HP.lire(str(f)) == {}; f.write_text("{pas du json"); assert HP.lire(str(f)) == {} and HP.completer({"equipes": []}, str(f)) == {"equipes": []}
