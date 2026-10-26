"""Tickets alpha côté pipeline (25/10/2026) : palier 2, gel avant les matchs, résultats, bilan, et mêmes choix que la page."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_serie import palier2 as P2
from alpha_serie import tickets as T

RACINE = Path(__file__).resolve().parent.parent
JOUR = "2026-10-25"


def equipe(lieu_dom, buts):
    """buts : liste de (marqués, encaissés) au lieu demandé, avant JOUR."""
    return {"matchs": [{"date": f"2026-09-{i + 1:02d}", "domicile": lieu_dom, "buts_marques": m, "buts_encaisses": e} for i, (m, e) in enumerate(buts)]}


COTES = {"over_under_domicile_2.5": {"moins": 1.53, "plus": 2.40}}


# --- Palier 2 : 3 cas retenus, 3 cas écartés ----------------------------------------------------------------------------
def test_palier2_retenu():
    s = P2.selections(equipe(True, [(1, 0)] * 5), equipe(False, [(0, 1)] * 5), JOUR, COTES)        # 1 but attendu : P(≤2) ≈ 0,92
    assert s and s[0]["cle"] == ["over_under_domicile_2.5", "moins"] and s[0]["avantage"] > 0.10
    assert s[0]["domicile_au_plus_2"] == [5, 5] and s[0]["exterieur_encaisse_au_plus_2"] == [5, 5]
    assert P2.selections(equipe(True, [(2, 1)] * 10), equipe(False, [(1, 1)] * 10), JOUR, {"over_under_domicile_2.5": {"moins": 1.40}})
    assert P2.p_au_plus(1.0, 2) == pytest.approx(0.919698, abs=1e-6)


def test_palier2_ecarte():
    assert P2.selections(equipe(True, [(1, 0)] * 4), equipe(False, [(0, 1)] * 5), JOUR, COTES) == []          # 4 matchs seulement
    assert P2.selections(equipe(True, [(4, 0)] * 5), equipe(False, [(0, 3)] * 5), JOUR, COTES) == []          # beaucoup de buts attendus
    assert P2.selections(equipe(True, [(1, 0)] * 5), equipe(False, [(0, 1)] * 5), JOUR, {}) == []             # pas de cote : rien


# --- Gel, résultats, bilan ------------------------------------------------------------------------------------------------
def pari(marche, cote, valeur, cle, conf=(9, 12)):
    return {"marche": marche, "cote": cote, "valeur": valeur, "cle": cle, "explication": {"domicile": list(conf), "exterieur": list(conf)}}


def match(mid, heure, equipes=None, buts=None, palier2=None):
    return {"match_id": mid, "date": JOUR, "heure": heure, "statut": "analyse", "domicile": f"D{mid}", "exterieur": f"E{mid}", "competition": "Test",
            "n_domicile": 7, "n_exterieur": 7, "onglets": {"buts": buts or [], "equipes": equipes or [], "calibrees": []}, "palier2": palier2 or []}


PAGE = [match("a", "13:00", equipes=[pari("Pas de nul (12)", 1.30, 0.93, ["double_chance", "12"])]),
        match("b", "15:00", buts=[pari("Moins de 3,5 buts", 1.35, 0.93, ["over_under_3.5", "moins"])]),
        match("c", "17:30", palier2=[{"cle": ["over_under_domicile_2.5", "moins"], "marche": "Moins de 2,5 buts du domicile", "cote": 1.53, "avantage": 0.2}])]


def test_gel_regles_bilan(tmp_path):
    j = tmp_path / "t.jsonl"
    nuit = datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)
    assert T.geler(PAGE, nuit, j) == 1 and T.geler(PAGE, nuit, j) == 0                  # jamais regelé
    archive = [{"match_id": "a", "score_final": {"buts_dom": 2, "buts_ext": 1}}, {"match_id": "b", "score_final": {"buts_dom": 1, "buts_ext": 1}}]
    assert T.regler(archive, j) == 0                                                    # match c sans score : rien n'est réglé
    archive.append({"match_id": "c", "score_final": {"buts_dom": 3, "buts_ext": 0}})
    assert T.regler(archive, j) == 1
    b = T.bilan(j)
    assert b["palier1"] == {"tickets": 1, "gagnes": 1, "paris": 2, "paris_gagnes": 2, "rendement_par_ticket": pytest.approx(1.30 * 1.35 - 1, abs=1e-4)}
    assert b["palier3"]["gagnes"] == 0 and b["palier3"]["paris"] == 1                   # 3 buts du domicile : perdu
    assert b["palier2"]["tickets"] == 0                                                 # 2 admissibles, tous deux au palier 1


def test_aucun_gel_a_posteriori(tmp_path):
    j = tmp_path / "t.jsonl"
    assert T.geler(PAGE, datetime(2026, 10, 25, 12, 30, tzinfo=timezone.utc), j) == 0     # 13:30 à Douala : le match de 13:00 a commencé
    assert T.geler([], datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc), j) == 0


def test_gel_du_lendemain_si_le_pipeline_finit_avant_minuit(tmp_path):
    j = tmp_path / "t.jsonl"
    assert T.geler(PAGE, datetime(2026, 10, 24, 21, 30, tzinfo=timezone.utc), j) == 1     # 22:30 à Douala le 24 : on gèle le 25
    assert json.loads(j.read_text().splitlines()[0])["jour"] == JOUR
    assert T.geler(PAGE, datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc), j) == 0      # 01:45 le 25 : déjà gelé, jamais regelé
    k = tmp_path / "k.jsonl"
    assert T.geler(PAGE, datetime(2026, 10, 24, 20, 30, tzinfo=timezone.utc), k) == 0     # 21:30 le 24 : jour = 24, aucun match ce jour-là


# --- Mêmes choix que la page (af-alpha-tickets.js) -------------------------------------------------------------------------
PARITE = [("12:30", 1.30, 0.93, (9, 12)), ("13:15", 1.28, 0.93, (10, 12)), ("14:00", 1.35, 0.81, (5, 6)), ("15:00", 1.29, 0.81, (5, 6)),
          ("16:00", 1.40, 0.79, (9, 9)), ("18:30", 1.25, 1.0, (3, 4)), ("20:00", 1.29, 1.0, (9, 12)), ("22:30", 1.28, 0.86, (11, 12)),
          ("11:00", 1.33, 0.90, (10, 12)), ("12:00", 1.26, 0.88, (9, 12)), ("13:45", 1.31, 0.85, (8, 10)), ("17:00", 1.27, 0.84, (9, 11)),
          ("19:00", 1.32, 0.83, (7, 9)), ("21:00", 1.30, 0.82, (8, 10)), ("23:15", 1.29, 0.95, (11, 12)), ("10:30", 1.36, 0.92, (10, 12)),
          ("09:30", 1.30, 0.99, (12, 12))]                                        # 09:30 : hors de la journée de 10 h à minuit


def _page_parite():
    return [match(f"m{i:02d}", h, equipes=[pari("Pas de nul (12)", c, v, ["double_chance", "12"], conf)]) for i, (h, c, v, conf) in enumerate(PARITE)]


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_meme_ticket_que_la_page():
    page = _page_parite()
    code = ("const T = require(process.argv[1]); const d = JSON.parse(process.argv[2]); const a = T.analyse(d, '%s');"
            "const f = (l) => l.map((s) => s.match_id + '|' + s.categorie); console.log(JSON.stringify([f(a.palier1), f(a.palier2)]));" % JOUR)
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-tickets.js"), json.dumps({"matchs": page})], capture_output=True, text=True, check=True)
    t = T.du_jour(page, JOUR)
    assert json.loads(r.stdout) == [[f"{c['match_id']}|{c['categorie']}" for c in t[p]] for p in ("palier1", "palier2")]


# --- Palier 2 = les 10 meilleurs restants : 3 règles qui tiennent, 3 cas qui doivent être écartés -------------------------------
def test_palier2_dix_meilleurs_restants():
    t = T.du_jour(_page_parite(), JOUR)
    p1, p2 = {c["match_id"] for c in t["palier1"]}, [c["match_id"] for c in t["palier2"]]
    assert len(t["palier1"]) == 7 and len(p2) == 8                       # 15 admissibles en journée : 7 au palier 1, 8 restent (moins de 10)
    assert not p1 & set(p2) and len(set(p2)) == len(p2)                  # aucun match du palier 1, un pari par match
    v = [c["valeur"] for c in t["palier2"]]
    assert v == sorted(v, reverse=True)                                  # classés du meilleur au moins bon
    assert "m16" not in p2 and "m04" not in p2                           # 09:30 : hors journée ; 79 % : sous le seuil (rien n'est assoupli)
    plein = [match(f"x{i:02d}", f"{10 + i // 2}:{'00' if i % 2 == 0 else '30'}", equipes=[pari("Pas de nul (12)", 1.30, 0.90, ["double_chance", "12"])]) for i in range(28)]
    assert len(T.du_jour(plein, JOUR)["palier2"]) == T.PALIER2_MAX == 10  # jamais plus de 10


# --- Page d'accueil : 3 tickets par rang de classement (25/10/2026) -----------------------------------------------------------
def _ids(t, f):
    return [c["match_id"] for c in t[f]]


def test_trois_tickets_accueil_par_classement():
    cles = [["double_chance", "12"], ["over_under_3.5", "moins"], ["over_under_1.5", "plus"]]
    page = [match(f"x{i:02d}", f"{10 + i // 3}:{(i % 3) * 15:02d}", equipes=[pari("p", 1.30, 0.99 - i / 1000, cles[i % 3])]) for i in range(36)]
    page.append(match("deux", "12:05", equipes=[pari("p", 1.30, 0.995, cles[0])], buts=[pari("q", 1.30, 0.994, cles[1])]))
    page.append(match("tot", "09:00", equipes=[pari("p", 1.30, 1.0, cles[2])]))               # avant 10 h : jamais
    t = T.du_jour(page, JOUR)
    ids = [i for f in T.FAMILLES for i in _ids(t, f)]
    assert [len(t[f]) for f in T.FAMILLES] == [10, 10, 10] and len(ids) == len(set(ids))      # 3 × 10, un match une seule fois
    assert _ids(t, "accueil_1")[0] == "deux" and "tot" not in ids                             # meilleur classé en tête ; 09:00 exclu
    assert ids == ["deux"] + [f"x{i:02d}" for i in range(29)]                                 # strictement dans l'ordre du classement
    v = [c["valeur"] for f in T.FAMILLES for c in t[f]]
    assert v == sorted(v, reverse=True)


def test_accueil_jamais_force():
    page = [match(f"y{i}", "15:00", equipes=[pari("p", 1.30, 0.95, ["double_chance", "12"])]) for i in range(12)]
    page.append(match("bas", "15:00", equipes=[pari("p", 1.30, 0.79, ["double_chance", "12"])]))   # 79 % : écarté
    page.append(match("ko", "15:00", equipes=[pari("p", 1.20, 0.99, ["double_chance", "12"])]))    # cote 1,20 : écartée
    t = T.du_jour(page, JOUR)
    assert [len(t[f]) for f in T.FAMILLES] == [10, 2, 0]
    assert "bas" not in _ids(t, "accueil_2") and "ko" not in _ids(t, "accueil_1")


def test_accueil_affiche_le_gel(tmp_path):
    j, sortie = tmp_path / "t.jsonl", tmp_path / "acc.json"
    nuit = datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)
    T.geler(PAGE, nuit, j)
    d = T.ecrire_accueil(PAGE + [match("tard", "14:00", equipes=[pari("Pas de nul (12)", 1.40, 0.99, ["double_chance", "12"])])], nuit, j, sortie)
    assert d["gele"] and json.loads(sortie.read_text())["jour"] == JOUR
    res = next(t for t in d["tickets"] if t["cle"] == "accueil_1")
    assert [c["match_id"] for c in res["selection"]] == ["a", "b"] and res["cote_totale"] == pytest.approx(1.30 * 1.35)   # le match ajouté après le gel n'y est pas
    html = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "data/alpha_serie/tickets_accueil.json" in html and "data/tickets.json" not in html


# --- Ticket recommandé : cote totale 5 au plus (règle de Patrick, 25/10/2026) ------------------------------------------------
def _rec(cotes):
    page = [match(f"r{i}", f"{12 + i}:00", equipes=[pari("p", c, 0.99 - i / 1000, ["double_chance", "12"])]) for i, c in enumerate(cotes)]
    return [(c["match_id"], c["cote"]) for c in T.du_jour(page, JOUR)["accueil_recommande"]]


def test_ticket_recommande_cote_5_maximum():
    assert [m for m, _ in _rec([1.30, 1.30, 1.30, 1.30, 1.30, 1.30, 1.30])] == ["r0", "r1", "r2", "r3", "r4", "r5"]   # 1,3^6 = 4,83
    assert [m for m, _ in _rec([2.0, 2.5, 1.25])] == ["r0", "r1"]                                                  # 5,00 pile : gardé
    assert [m for m, _ in _rec([1.25, 1.25, 1.25])] == ["r0", "r1", "r2"]                                          # moins de 5 : tout


def test_ticket_recommande_ne_depasse_jamais_ni_ne_saute():
    assert [m for m, _ in _rec([1.30, 1.30, 1.30, 1.30, 1.30, 1.30, 1.30, 1.25])] == ["r0", "r1", "r2", "r3", "r4", "r5"]  # stop à r6
    assert _rec([5.5, 1.25]) == []                                         # le mieux classé dépasse seul : pas de ticket, pas de saut
    assert [m for m, _ in _rec([2.0, 2.6, 1.25])] == ["r0"]                # 5,20 : on s'arrête, r2 n'est pas pris à la place


# --- « Plus de 1,5 » à chances maximales : entre automatiquement dans le ticket du jour et se reconnaît (26/10/2026) --------------------
CLE15 = ["over_under_1.5", "plus"]


def match15(mid, heure, total, cote=1.30, valeur=0.70, equipes=None, cle=None):
    """Match dont le « Plus de 1,5 » d'alpha a un total attendu `total` (valeur 70 % : sous le seuil des autres paris, donc jamais admissible seul)."""
    m = match(mid, heure, buts=[pari("Plus de 1,5 buts", cote, valeur, cle or CLE15)], equipes=equipes)
    m["niveaux"] = {"dom": total / 2, "ext": total / 2, "total": total, "d": 0.0}
    return m


def test_palier_gele_identique_partout():
    conf = json.loads((RACINE / "data" / "alpha_serie" / "plus15_chances_max.json").read_text(encoding="utf-8"))
    assert T.palier_plus15() == conf["palier_total_attendu"] == 3.4
    assert conf["controle"]["wilson_bas"] >= 0.80 and conf["reglage"]["wilson_bas"] >= 0.80          # règle : borne basse >= 1/1,25 aux deux périodes
    if shutil.which("node"):
        r = subprocess.run(["node", "-e", "const T=require(process.argv[1]);console.log(JSON.stringify([T.REGLES.plus15TotalMin,T.REGLES.plus15Taux,T.REGLES.plus15Matchs]))",
                            str(RACINE / "af-alpha-tickets.js")], capture_output=True, text=True, check=True)
        assert json.loads(r.stdout) == [3.4, round(conf["tous"]["reussite"], 2), conf["tous"]["matchs"]]


def test_plus15_max_entre_dans_tous_les_tickets_et_est_marque():
    page = [match15("pm", "16:00", 3.8), match("a", "13:00", equipes=[pari("Pas de nul (12)", 1.30, 0.99, ["double_chance", "12"])])]
    t = T.du_jour(page, JOUR)
    p1 = {c["match_id"]: c for c in t["palier1"]}
    assert "pm" in p1 and p1["pm"]["chances_max"] is True and p1["pm"]["total_attendu"] == 3.8 and p1["pm"]["categorie"] == "plus15"   # ticket du jour
    assert t["accueil_1"][0]["match_id"] == "pm" and t["accueil_1"][0]["chances_max"] is True                                   # prioritaire : en tête de l'accueil
    assert "pm" in [c["match_id"] for c in t["accueil_recommande"]]
    assert p1["a"].get("chances_max") is None                                                                                    # les autres paris ne sont pas marqués


def test_plus15_max_prioritaire_sur_le_meilleur_pari_du_meme_match():
    m = match15("pm", "16:00", 3.6, equipes=[pari("Pas de nul (12)", 1.30, 0.99, ["double_chance", "12"])])        # le match a aussi un pari admissible à 99 %
    t = T.du_jour([m], JOUR)
    assert [c["categorie"] for c in t["palier1"]] == ["plus15"] and len(t["palier2"]) == 0                              # un pari par match : le « chances maximales »


def test_plus15_max_ecarte_si_sous_le_palier_sans_cote_ou_hors_horaire():
    assert T.du_jour([match15("p1", "16:00", 3.39)], JOUR)["palier1"] == []                                             # 3,39 < 3,4
    assert T.du_jour([match15("p2", "16:00", 4.5, cote=None)], JOUR)["palier1"] == []                                   # cote absente : jamais proposé
    assert T.du_jour([match15("p3", "16:00", 4.5, cote=1.249)], JOUR)["palier1"] == []                                  # cote < 1,25 (minimum de tous les marchés)
    assert T.du_jour([match15("p4", "09:30", 4.5)], JOUR)["palier1"] == []                                              # avant 10 h
    assert T.du_jour([match15("p5", "16:00", 4.5, cle=["over_under_2.5", "plus"])], JOUR)["palier1"] == []             # autre marché que +1,5
    inactif = T.palier_plus15(Path("/inexistant/plus15.json"))
    assert inactif is None                                                                                              # fichier absent : fonction désactivée


def test_plus15_max_gele_regle_et_suivi(tmp_path):
    j = tmp_path / "t.jsonl"
    page = [match15("pm", "16:00", 3.8), match15("qm", "17:30", 4.1)]
    assert T.geler(page, datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc), j) == 1
    gele = json.loads(j.read_text().splitlines()[0])
    assert all(c["chances_max"] for c in gele["palier1"]) and gele["accueil_1"][0]["total_attendu"] in (3.8, 4.1)
    archive = [{"match_id": "pm", "score_final": {"buts_dom": 1, "buts_ext": 1}}, {"match_id": "qm", "score_final": {"buts_dom": 1, "buts_ext": 0}}]
    assert T.regler(archive, j) == 1
    assert T.bilan(j)["plus15_max"] == {"paris": 2, "gagnes": 1, "reussite": 0.5}                                         # 1-0 : un seul but, perdu


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_plus15_max_meme_ticket_que_la_page():
    page = _page_parite() + [match15("pm1", "12:10", 3.9), match15("pm2", "12:40", 3.5), match15("pm3", "19:20", 4.2), match15("pn", "15:30", 3.2)]
    code = ("const T = require(process.argv[1]); const d = JSON.parse(process.argv[2]); const a = T.analyse(d, '%s');"
            "const f = (l) => l.map((s) => s.match_id + '|' + s.categorie); console.log(JSON.stringify([f(a.palier1), f(a.palier2)]));" % JOUR)
    r = subprocess.run(["node", "-e", code, str(RACINE / "af-alpha-tickets.js"), json.dumps({"matchs": page})], capture_output=True, text=True, check=True)
    t = T.du_jour(page, JOUR)
    assert json.loads(r.stdout) == [[f"{c['match_id']}|{c['categorie']}" for c in t[p]] for p in ("palier1", "palier2")]
    assert {"pm1|plus15", "pm3|plus15"} <= {f"{c['match_id']}|{c['categorie']}" for c in t["palier1"]}                    # prioritaires dans leur créneau


def test_plus15_cote_minimale_1_25_comme_les_autres():
    assert [c["categorie"] for c in T.du_jour([match15("p", "16:00", 3.8, cote=1.25)], JOUR)["palier1"]] == ["plus15"]   # 1,25 : retenu
    for cote in (1.22, 1.23, 1.249):                                                                                      # l'essai à 1,22 est retiré
        assert T.du_jour([match15("p", "16:00", 3.8, cote=cote)], JOUR)["palier1"] == []
    sous_palier = match15("q", "16:00", 3.0, cote=1.23, valeur=0.95)
    assert T.du_jour([sous_palier], JOUR)["palier1"] == []                                                                # +1,5 ordinaire à 1,23 : écarté aussi
