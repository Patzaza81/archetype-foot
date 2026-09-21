"""Récupération automatique des scores du jeu d'évaluation (21/09/2026), site simulé."""
import datetime
import json
import os

import pytest

import evaluation_moteur as ev
import evaluation_scores as es

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORIQUE = os.path.join(RACINE, "evaluation", "snapshot_historique_moteur_v2_6_9.json")
AUJ = datetime.date(2026, 9, 22)


def snap(tmp_path, matchs):
    p = tmp_path / "snapshot_test.json"
    p.write_text(json.dumps({"matchs": [{"id": i, "date": d, "domicile": a, "exterieur": b} for i, d, a, b in matchs]}), encoding="utf-8")
    return str(p)


class Site:
    """Faux site des résultats : pages par date, scores par (dom, ext), et pages en échec."""
    def __init__(self, pages, echecs=()):
        self.pages, self.echecs, self.requetes = pages, set(echecs), []

    def fetch(self, url):
        self.requetes.append(url)
        if url in self.echecs:
            raise ConnectionError("réseau")
        return url, None

    def parse(self, html, max_matchs, date_label):
        return self.pages[date_label]


def trouve(page, dom, ext):
    for m in page:
        if m["domicile"] == dom and m["exterieur"] == ext:
            return m["score"] if m.get("heure") == "TER" and m.get("score") else None
    return None


def lance(tmp_path, matchs, site, **kw):
    chemin = snap(tmp_path, matchs)
    r = es.recupere_scores(chemin, chemin_sortie=str(tmp_path / "scores.json"), aujourdhui=AUJ, fetch=site.fetch, parse=site.parse,
                           url_de_date=lambda d: d.isoformat(), trouve=trouve, **kw)
    return r, json.load(open(tmp_path / "scores.json", encoding="utf-8"))["scores"]


def test_recupere_les_scores_des_matchs_termines(tmp_path):
    site = Site({"2026-09-20": [{"domicile": "A", "exterieur": "B", "score": "2-1", "heure": "TER"}, {"domicile": "C", "exterieur": "D", "score": "0-0", "heure": "TER"}]})
    r, s = lance(tmp_path, [("1", "2026-09-20", "A", "B"), ("2", "2026-09-20", "C", "D")], site)
    assert r["nouveaux"] == 2 and r["restants"] == 0 and (s["1"]["buts_dom"], s["1"]["buts_ext"]) == (2, 1) and (s["2"]["buts_dom"], s["2"]["buts_ext"]) == (0, 0)
    assert site.requetes == ["2026-09-20"]                                          # UNE requête par date


@pytest.mark.parametrize("statut", ["20:45", "REP", "45'", "MT", ""])
def test_un_match_non_termine_reste_restant_jamais_un_score_partiel(tmp_path, statut):
    site = Site({"2026-09-20": [{"domicile": "A", "exterieur": "B", "score": "1-0", "heure": statut}]})
    r, s = lance(tmp_path, [("1", "2026-09-20", "A", "B")], site)
    assert r["nouveaux"] == 0 and r["restants"] == 1 and s == {}


def test_un_match_absent_de_la_page_reste_restant(tmp_path):
    r, s = lance(tmp_path, [("1", "2026-09-20", "A", "B")], Site({"2026-09-20": [{"domicile": "X", "exterieur": "Y", "score": "1-0", "heure": "TER"}]}))
    assert r["restants"] == 1 and s == {}


def test_le_jour_pas_termine_n_est_jamais_interroge(tmp_path):
    site = Site({"2026-09-20": []})
    r, _ = lance(tmp_path, [("1", "2026-09-22", "A", "B"), ("2", "2026-09-23", "C", "D")], site)      # aujourd'hui et demain
    assert r["jour_pas_termine"] == 2 and site.requetes == []


def test_un_echec_reseau_ne_bloque_pas_les_autres_dates(tmp_path):
    site = Site({"2026-09-19": [{"domicile": "A", "exterieur": "B", "score": "3-0", "heure": "TER"}],
                 "2026-09-20": []}, echecs=["2026-09-20"])
    r, s = lance(tmp_path, [("1", "2026-09-19", "A", "B"), ("2", "2026-09-20", "C", "D")], site)
    assert r["dates_en_echec"] == ["2026-09-20"] and r["nouveaux"] == 1 and r["restants"] == 1 and list(s) == ["1"]


def test_idempotent_les_scores_trouves_sont_conserves_et_ne_sont_plus_redemandes(tmp_path):
    site = Site({"2026-09-20": [{"domicile": "A", "exterieur": "B", "score": "2-1", "heure": "TER"}]})
    matchs = [("1", "2026-09-20", "A", "B")]
    lance(tmp_path, matchs, site)
    site2 = Site({"2026-09-20": [{"domicile": "A", "exterieur": "B", "score": "9-9", "heure": "TER"}]})     # le site « change d'avis » : ignoré
    r, s = lance(tmp_path, matchs, site2)
    assert r["deja_connus"] == 1 and r["nouveaux"] == 0 and site2.requetes == [] and (s["1"]["buts_dom"], s["1"]["buts_ext"]) == (2, 1)


def test_un_score_mal_forme_est_ignore_sans_planter(tmp_path):
    site = Site({"2026-09-20": [{"domicile": "A", "exterieur": "B", "score": "n/a", "heure": "TER"}]})
    r, s = lance(tmp_path, [("1", "2026-09-20", "A", "B")], site)
    assert r["restants"] == 1 and s == {}


def test_chemin_des_scores():
    assert es.chemin_scores("evaluation/snapshot_historique_moteur_v2_6_9.json") == os.path.join("evaluation", "scores_historique_moteur_v2_6_9.json")


def test_le_workflow_recupere_les_scores_et_les_publie():
    txt = open(os.path.join(RACINE, ".github", "workflows", "pipeline.yml"), encoding="utf-8").read()
    assert "run: python evaluation_scores.py" in txt and "[ -d evaluation ] && git add evaluation/" in txt


# ─────────── le jeu d'évaluation historique ───────────
def test_le_snapshot_historique_est_intact_et_reproductible():
    import branchement_moteur as bm
    import moteur_v2_6_9 as moteur
    assert ev.integrite(HISTORIQUE) is True
    snap_h = json.load(open(HISTORIQUE, encoding="utf-8"))
    assert snap_h["nb_matchs"] == len(snap_h["matchs"]) > 400
    for m in snap_h["matchs"]:
        assert m["date"] <= "2026-09-20" and m["donnees_du_run"]["heure_utc"] < f"{m['date']}T24"      # données antérieures au match
        t = datetime.datetime.strptime(m["donnees_du_run"]["heure_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
        res = moteur.analyser_match(m["entree_moteur"], m["entree_moteur"]["date_match"], t)
        assert sorted((bm.nom_canonique(l["marche"]), round(l["proba_modele"], 9)) for l in res["inventaire"]) == sorted((l["marche"], round(l["probabilite"], 9)) for l in m["inventaire"])
        assert min(m["effectifs"].values()) >= bm.MIN_MATCHS_PAR_LIEU                                   # règle des 2 matchs respectée


def test_l_outil_lit_le_fichier_de_scores(tmp_path, capsys):
    snap_h = json.load(open(HISTORIQUE, encoding="utf-8"))
    ids = [m["id"] for m in snap_h["matchs"][:40]]
    f = tmp_path / "scores.json"
    f.write_text(json.dumps({"scores": {i: {"buts_dom": k % 4, "buts_ext": (k * 3) % 3} for k, i in enumerate(ids)}}), encoding="utf-8")
    assert ev.main([HISTORIQUE, str(f)]) == 0
    sortie = capsys.readouterr().out
    assert "40 matchs avec résultat sur" in sortie and "INTACT" in sortie
