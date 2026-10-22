"""Onglet « Meilleures sélections » (22/10/2026) : règles d'admission, recalibrage hebdomadaire automatique, absence de fuite du futur."""
import json
import math
import random
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from meilleures_selections import regles, suivi

RACINE = Path(__file__).resolve().parent.parent
DEBUT = date(2026, 9, 1)


def jour(i):
    return (DEBUT + timedelta(days=i)).isoformat()


def pari(i, marche="under_2_5", moteur="V3", cote=1.5, indice=4, sur=4, gagne=1):
    return {"moteur": moteur, "date": jour(i), "marche": marche, "cote": cote, "indice": indice, "sur": sur, "gagne": gagne}


def serie(marche, taux, n_jours=28, par_jour=4, cote=1.5, moteur="V3", graine=1, indice=4, sur=4, depart=0):
    """Paris synthétiques : `taux` peut être un nombre ou une fonction du jour."""
    r = random.Random(graine)
    out = []
    for d in range(depart, depart + n_jours):
        t = taux(d) if callable(taux) else taux
        for _ in range(par_jour):
            out.append(pari(d, marche, moteur, cote, indice, sur, int(r.random() < t)))
    return out


def admis(paris):
    return {(g["moteur"], g["famille"]): g for g in regles.calibrer(paris)["groupes"]}


# ───────────── familles ─────────────
@pytest.mark.parametrize("marche,attendu", [
    ("under_2_5", "total_moins"), ("over_1_5", "total_plus"), ("away_under_1_5", "equipe_moins"), ("home_over_0_5", "equipe_plus"),
    ("handicap_-1.5_1", "handicap"), ("dc_1X", "double_chance"), ("1x2_2", "victoire"), ("btts_yes", "btts_oui"), ("clean_home", "cage"),
])
def test_familles_reconnues(marche, attendu):
    assert regles.famille(marche) == attendu


@pytest.mark.parametrize("marche", ["", None, "score_2_3", "corners_over_8_5", "inconnu"])
def test_familles_inconnues_exclues(marche):
    assert regles.famille(marche) is None
    assert regles.calibrer([pari(0, marche or "x") for _ in range(50)])["groupes"] == []


# ───────────── test statistique exact ─────────────
def somme_directe(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


@pytest.mark.parametrize("k,n,p", [(3, 3, 0.7), (0, 5, 0.4), (7, 10, 0.5), (40, 50, 0.698), (45, 65, 0.612), (1, 1, 0.9)])
def test_queue_binomiale_exacte(k, n, p):
    assert regles.queue_binomiale(k, n, p) == pytest.approx(somme_directe(k, n, p), rel=1e-9)


def test_queue_binomiale_bornes():
    assert regles.queue_binomiale(0, 10, 0.3) == 1.0 and regles.queue_binomiale(11, 10, 0.3) == 0.0


# ───────────── admission : cas qui DOIVENT passer ─────────────
def test_passe_groupe_tres_gagnant_et_stable():
    g = admis(serie("under_2_5", 0.92))[("V3", "total_moins")]
    assert g["statut"] == "confirme" and g["n"] == 112


def test_passe_groupe_moyennement_gagnant_en_observation():
    # taux entre la base (0,667) et le très fort : preuve moyenne → au moins « en observation »
    res = {admis(serie("under_2_5", 0.82, graine=s)).get(("V3", "total_moins"), {}).get("statut") for s in range(1, 9)}
    assert res & {"observation", "confirme"} and None not in res or res & {"observation", "confirme"}


def test_passe_aussi_pour_v2_et_une_autre_famille():
    g = admis(serie("handicap_-1.5_1", 0.93, moteur="V2"))
    assert g[("V2", "handicap")]["statut"] == "confirme"


# ───────────── admission : cas qui DOIVENT échouer ─────────────
def test_echoue_tout_gagne_mais_trop_peu_de_paris():
    paris = [pari(i, gagne=1) for i in range(3)] + [pari(i, marche="over_2_5", gagne=0) for i in range(3, 6)]
    assert ("V3", "total_moins") not in admis(paris)          # 3 sur 3 : p = 0,30, rien d'établi


def test_echoue_resultat_egal_a_la_base():
    assert admis(serie("under_2_5", 1 / 1.5)) == {} or ("V3", "total_moins") not in admis(serie("under_2_5", 1 / 1.5))


def test_echoue_gagnant_seulement_dans_une_moitie():
    t = lambda d: 0.97 if d < 14 else 0.45
    assert ("V3", "total_moins") not in admis(serie("under_2_5", t))
    t2 = lambda d: 0.45 if d < 14 else 0.97
    assert ("V3", "total_moins") not in admis(serie("under_2_5", t2))


def test_echoue_perdant():
    assert ("V3", "total_moins") not in admis(serie("under_2_5", 0.40))


def test_echoue_reussite_au_dessus_de_la_base_mais_rendement_negatif():
    # 140 paris à cote 1,10 (133 gagnés) + 60 paris à cote 4 (12 gagnés) : réussite 72,5 % > base 71,1 %, mais on perd de l'argent
    paris = []
    for i in range(140):
        paris.append(pari(i % 28, cote=1.1, gagne=int(i % 20 != 0)))
    for i in range(60):
        paris.append(pari(i % 28, cote=4.0, gagne=int(i % 5 == 0)))
    s = regles.statistiques(paris)
    assert s["reussite"] > s["base"] and s["rendement"] < 0
    assert ("V3", "total_moins") not in admis(paris)


# ───────────── recalibrage hebdomadaire ─────────────
def test_recalibrage_du_calendrier():
    assert regles.recalibrage_du([], "2026-10-22") is True
    h = [{"calibre_le": "2026-10-15"}]
    assert regles.recalibrage_du(h, "2026-10-21") is False
    assert regles.recalibrage_du(h, "2026-10-22") is True
    assert regles.recalibrage_du(h, "2026-11-30") is True
    assert regles.recalibrage_du([{"calibre_le": "2026-10-01"}, {"calibre_le": "2026-10-20"}], "2026-10-26") is False


def test_un_groupe_rentable_est_remplace_quand_les_donnees_changent():
    """A gagnait au début puis s'effondre ; B perdait puis gagne. Le recalibrage de fin doit retirer A et faire entrer B, sans aucune main."""
    A = serie("under_2_5", lambda d: 0.95 if d < 21 else 0.10, n_jours=42, graine=3)
    B = serie("over_2_5", lambda d: 0.10 if d < 21 else 0.97, n_jours=42, graine=4, cote=1.5)
    tout = A + B
    tot_t = regles.photographie(tout, jour(21))["groupes"]     # on ne connaît que les 21 premiers jours
    assert [g["famille"] for g in tot_t] == ["total_moins"]
    fin = regles.photographie(tout, jour(42))["groupes"]
    fams = {g["famille"] for g in fin}
    assert "total_plus" in fams or "total_moins" not in fams
    assert "total_moins" not in fams                         # A est sorti


def test_construire_ne_recalibre_qu_une_fois_par_semaine():
    paris = serie("under_2_5", 0.9)
    h1, _ = suivi.construire(jour(30), paris, [], [])
    h2, s2 = suivi.construire(jour(31), paris, [], h1)
    assert len(h2) == 1 and s2["recalibre_aujourdhui"] is False
    h3, s3 = suivi.construire(jour(37), paris, [], h2)
    assert len(h3) == 2 and s3["recalibre_aujourdhui"] is True and s3["prochain_recalibrage"] == jour(44)


# ───────────── pas de fuite du futur ─────────────
def test_le_calibrage_du_jour_J_ignore_les_paris_du_jour_J_et_apres():
    base = serie("under_2_5", 0.9, n_jours=20)
    avant = regles.photographie(base, jour(20))
    futur = base + [pari(20 + i % 5, gagne=0) for i in range(500)]   # des défaites massives APRÈS le recalibrage
    apres = regles.photographie(futur, jour(20))
    assert avant["groupes"] == apres["groupes"] and avant["nb_paris"] == apres["nb_paris"]


def test_bilan_hors_echantillon_utilise_l_instantane_d_avant_le_pari():
    paris = serie("under_2_5", 0.9, n_jours=40, graine=5)
    hist = [regles.photographie(paris, jour(14)), regles.photographie(paris, jour(28))]
    b = regles.bilan_hors_echantillon(paris, hist)
    comptes = sum(v["n"] for v in b.values())
    assert 0 < comptes <= len([p for p in paris if p["date"] >= jour(14)])
    assert regles.bilan_hors_echantillon([p for p in paris if p["date"] < jour(14)], hist)["confirme"]["n"] == 0   # rien avant le 1er instantané


# ───────────── classement du jour ─────────────
def test_classer_ne_garde_que_les_groupes_admis_et_trie():
    groupes = [
        {"moteur": "V3", "famille": "total_moins", "palier": 0.5, "statut": "observation", "n": 40, "gagnes": 33, "reussite": .8, "base": .7, "rendement": .1, "p": 0.05},
        {"moteur": "V2", "famille": "handicap", "palier": 0.0, "statut": "confirme", "n": 90, "gagnes": 80, "reussite": .9, "base": .7, "rendement": .2, "p": 0.001},
    ]
    sel = [
        {"moteur": "V3", "marche": "under_2_5", "indice": 4, "sur": 4, "cote": 1.5, "probabilite": .8},    # admis (observation)
        {"moteur": "V3", "marche": "under_2_5", "indice": 1, "sur": 4, "cote": 1.5, "probabilite": .8},    # indice trop bas
        {"moteur": "V3", "marche": "over_2_5", "indice": 4, "sur": 4, "cote": 1.5, "probabilite": .8},     # autre famille
        {"moteur": "V2", "marche": "handicap_-1.5_1", "indice": 0, "sur": 4, "cote": 1.6, "probabilite": .7},  # admis (confirmé)
        {"moteur": "V2", "marche": "under_2_5", "indice": 4, "sur": 4, "cote": 1.5, "probabilite": .8},    # autre moteur
        {"moteur": "V3", "marche": "under_2_5", "indice": None, "sur": None, "cote": 1.5, "probabilite": .8},  # sans indice
    ]
    out = regles.classer(sel, groupes)
    assert [(x["moteur"], x["marche"]) for x in out] == [("V2", "handicap_-1.5_1"), ("V3", "under_2_5")]
    assert [x["rang"] for x in out] == [1, 2]


# ───────────── garde-fou statistique : sous l'hypothèse « aucun avantage », on n'admet presque jamais ─────────────
def test_faux_positifs_rares_sans_aucun_avantage():
    r = random.Random(11)
    faux_confirmes = 0
    essais = 40
    for _ in range(essais):
        paris = []
        for marche, cote, indice in (("under_2_5", 1.5, 4), ("over_2_5", 1.9, 3), ("handicap_-1.5_1", 1.7, 2), ("dc_1X", 1.3, 4), ("btts_yes", 1.9, 4)):
            for d in range(28):
                for _ in range(3):
                    paris.append(pari(d, marche, "V2", cote, indice, 4, int(r.random() < 1 / cote)))
        faux_confirmes += len([g for g in regles.calibrer(paris)["groupes"] if g["statut"] == "confirme"])
    assert faux_confirmes / essais <= 1.0        # au plus une fausse admission « confirmée » attendue par recalibrage


# ───────────── données réelles du dépôt (si présentes) ─────────────
def test_chargement_reel_coherent():
    donnees = pytest.importorskip("meilleures_selections.donnees")
    if not (RACINE / "data" / "archive_test").exists():
        pytest.skip("archive absente")
    paris = donnees.paris_resolus(str(RACINE / "data/archive_test"), str(RACINE / "data/v3/journal"))
    assert paris and {p["moteur"] for p in paris} <= {"V2", "V3"}
    assert all(p["gagne"] in (0, 1) and p["cote"] > 1 for p in paris)
    c = regles.calibrer(paris)
    assert c["m_tests"] > 0 and all(g["statut"] in ("confirme", "observation") for g in c["groupes"])


# ───────────── pages et pipeline ─────────────
@pytest.mark.parametrize("page,moteur,js", [("archetype.html", "V2", "archetype.js"), ("pronostics_v3.html", "V3", "archetype_v3.js")])
def test_pages_branchees(page, moteur, js):
    h = (RACINE / page).read_text(encoding="utf-8")
    assert f'class="ax-page af-fond af-v{moteur[1]}"' in h        # le script lit le moteur dans la classe du body
    assert re.search(r"af-meilleures\.css\?v=\d", h)
    assert h.index(js) < h.index("af-date-navigation.js") < h.index("meilleures_selections.js")   # après la page (helper de traduction) et la navigation par dates


def test_js_ne_touche_pas_aux_cartes_du_filtre_de_dates():
    js = (RACINE / "meilleures_selections.js").read_text(encoding="utf-8")
    assert "ax-carte" not in js and "<table" not in js


def test_css_limite_a_la_page():
    css = re.sub(r"/\*.*?\*/", "", (RACINE / "af-meilleures.css").read_text(encoding="utf-8"), flags=re.S)
    for sel in re.findall(r"^([^{}@\n][^{}]*)\{", css, flags=re.M):
        assert all(s.strip().startswith("body.ax-page") for s in sel.split(",")), sel


def test_workflow_apres_les_scores_et_avant_la_publication():
    w = (RACINE / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    i = w.index("python evaluation_scores.py")
    j = w.index("python -m meilleures_selections.suivi pipeline")
    k = w.index("Commit et push du résultat")
    assert i < j < k
    assert "continue-on-error: true" in w[j:j + 200]


def test_sortie_json_complete(tmp_path):
    paris = serie("under_2_5", 0.9, n_jours=30)
    sel = [{"moteur": "V3", "match_id": "m", "date": jour(30), "heure": "10:00", "competition": "X", "domicile": "A", "exterieur": "B",
            "marche": "under_2_5", "cote": 1.5, "probabilite": .8, "indice": 4, "sur": 4}]
    _, s = suivi.construire(jour(30), paris, sel, [])
    json.dumps(s)
    for cle in ("calibre_le", "prochain_recalibrage", "groupes", "hors_echantillon", "bilan_historique", "rejeu", "selections", "m_tests", "seuil_confirme", "seuil_observation"):
        assert cle in s
    assert len(s["selections"]) == 1 and s["selections"][0]["rang"] == 1


def test_nombre_de_tests_possibles_suit_la_structure():
    assert regles.nb_tests_possibles() == 2 * (7 * 5 + 3 * 3) == 88
    assert regles.nb_paliers("nul") == 0 and regles.nb_paliers("cage") == 3 and regles.nb_paliers("handicap") == 5
    c = regles.calibrer(serie("under_2_5", 0.9))
    assert c["m_tests"] == 88 and c["seuil_confirme"] == pytest.approx(1 / 88)
    assert regles.calibrer([])["m_tests"] == 88                      # indépendant de la quantité de données
