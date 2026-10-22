"""Onglet « Meilleures sélections » (22/10/2026) : critères = indice, pourcentage et étoiles AFFICHÉS + résultats réels ;
recalibrage hebdomadaire automatique ; absence de fuite du futur."""
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


def pari(i, moteur="V3", pct=85, indice=4, sur=4, etoiles=2, gagne=1, marche="under_2_5", mid=None, version=None):
    p = {"moteur": moteur, "date": jour(i), "marche": marche, "pct": pct, "indice": indice, "sur": sur, "etoiles": etoiles, "gagne": gagne}
    if mid is not None:
        p["match_id"] = mid
    if version is not None:
        p["version"] = version
    return p


def serie(taux, n_jours=28, par_jour=4, graine=1, depart=0, **kw):
    """Paris synthétiques ; `taux` = nombre ou fonction du jour."""
    r = random.Random(graine)
    out = []
    for d in range(depart, depart + n_jours):
        t = taux(d) if callable(taux) else taux
        for _ in range(par_jour):
            out.append(pari(d, gagne=int(r.random() < t), **kw))
    return out


def fond(taux=0.45, moteur="V3", n_jours=28, graine=99):
    """Les AUTRES paris du moteur (pourcentage bas, indice bas) : ils fixent la référence."""
    return serie(taux, n_jours=n_jours, moteur=moteur, graine=graine, pct=55, indice=0, etoiles=1, marche="over_2_5")


def retenues(paris):
    return {g["moteur"]: g for g in regles.calibrer(paris)["groupes"]}


# ───────────── valeurs de la structure ─────────────
def test_structure():
    assert regles.nb_tests_possibles() == 5 * 5 * 3 + 5 * 5 * 4 == 175
    c = regles.calibrer([])
    assert c["m_tests"] == 175 and c["seuil_confirme"] == pytest.approx(0.05 / 175) and c["seuil_observation"] == pytest.approx(1 / 175)


# ───────────── test statistique exact et borne ─────────────
def somme_directe(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


@pytest.mark.parametrize("k,n,p", [(3, 3, 0.7), (0, 5, 0.4), (7, 10, 0.5), (40, 50, 0.698), (45, 65, 0.612), (1, 1, 0.9)])
def test_queue_binomiale_exacte(k, n, p):
    assert regles.queue_binomiale(k, n, p) == pytest.approx(somme_directe(k, n, p), rel=1e-9)


def hyper_directe(g, n, K, N):
    return sum(math.comb(K, i) * math.comb(N - K, n - i) for i in range(g, min(n, K) + 1)) / math.comb(N, n)


@pytest.mark.parametrize("g,n,K,N", [(8, 10, 12, 30), (3, 3, 10, 20), (0, 5, 9, 20), (20, 25, 30, 60), (5, 5, 5, 40), (2, 12, 3, 15)])
def test_test_de_fisher_exact(g, n, K, N):
    assert regles.queue_hypergeometrique(g, n, K, N) == pytest.approx(hyper_directe(g, n, K, N), rel=1e-9)


def test_borne_basse_de_wilson():
    assert regles.borne_basse(0, 0) == 0.0
    assert regles.borne_basse(50, 100) == pytest.approx(0.4038, abs=1e-3)      # valeur de référence de l'intervalle de Wilson à 95 %
    assert regles.borne_basse(100, 200) > regles.borne_basse(50, 100)           # plus de paris, borne plus haute
    assert regles.borne_basse(9, 10) < regles.borne_basse(90, 100)


# ───────────── règle : cas qui DOIVENT passer ─────────────
def test_passe_une_combinaison_tres_reussie_et_stable():
    g = retenues(serie(0.92) + fond())["V3"]
    assert g["statut"] == "confirme" and g["reussite"] > 0.85


def test_passe_aussi_pour_v2_et_retient_les_bons_criteres():
    # seuls les paris à pourcentage >= 80 réussissent : la règle retenue doit exiger au moins 70 %
    haut = serie(0.93, moteur="V2", pct=85, etoiles=3)
    bas = serie(0.40, moteur="V2", pct=65, etoiles=3, graine=7, marche="over_2_5")
    g = retenues(haut + bas)["V2"]
    assert g["statut"] == "confirme" and g["pct_min"] >= 70


def test_la_regle_suit_l_indice_affiche():
    bon = serie(0.92, indice=4)
    mauvais = serie(0.40, indice=1, graine=5, marche="over_2_5") + serie(0.45, indice=2, graine=6, marche="over_1_5")
    g = retenues(bon + mauvais)["V3"]
    assert g["indice_min"] >= 0.5


def test_la_regle_suit_les_etoiles_affichees():
    bon = serie(0.93, etoiles=3)
    mauvais = serie(0.40, etoiles=1, graine=5, marche="over_2_5")
    g = retenues(bon + mauvais)["V3"]
    assert g["etoiles_min"] >= 2


def test_la_reference_est_celle_du_meme_moteur():
    # V3 réussit 9 fois sur 10 PARTOUT (séries exactes, sans hasard) : aucune combinaison n'est meilleure que les autres paris du moteur.
    # Le même profil côté V2, dont les autres paris réussissent moins, est retenu.
    exact = lambda k, taux_dix: (k % 10) < taux_dix
    v3 = [pari(i // 4, gagne=int(exact(i, 9))) for i in range(112)] + [pari(i // 4, gagne=int(exact(i, 9)), pct=55, indice=0, etoiles=1, marche="over_2_5") for i in range(112)]
    assert "V3" not in retenues(v3)
    v2 = [pari(i // 4, "V2", gagne=int(exact(i, 9))) for i in range(112)] + [pari(i // 4, "V2", gagne=int(exact(i, 4)), pct=55, indice=0, etoiles=1, marche="over_2_5") for i in range(112)]
    assert "V2" in retenues(v2)


# ───────────── règle : cas qui DOIVENT échouer ─────────────
def test_echoue_tout_gagne_mais_trop_peu_de_paris():
    assert "V3" not in retenues([pari(i, gagne=1) for i in range(3)] + fond())


def test_echoue_resultat_egal_aux_autres_paris():
    assert "V3" not in retenues(serie(0.5) + fond(0.5))


def test_echoue_reussi_seulement_dans_une_moitie():
    assert "V3" not in retenues(serie(lambda d: 0.97 if d < 14 else 0.30) + fond())
    assert "V3" not in retenues(serie(lambda d: 0.30 if d < 14 else 0.97) + fond())


def test_echoue_perdant():
    assert "V3" not in retenues(serie(0.30) + fond())


def test_echoue_un_seul_jour_de_donnees():
    un_jour = [pari(0, gagne=1) for _ in range(40)] + [pari(0, gagne=0, pct=55, indice=0, etoiles=1, marche="over_2_5") for _ in range(40)]
    assert retenues(un_jour) == {}


def test_cotes_et_rendement_ignores():
    a = [{**p, "cote": 1.2} for p in serie(0.92) + fond()]
    b = [{**p, "cote": 9.0} for p in serie(0.92) + fond()]
    cle = lambda c: [(g["moteur"], g["indice_min"], g["pct_min"], g["etoiles_min"], g["n"]) for g in regles.calibrer(c)["groupes"]]
    assert cle(a) == cle(b)


# ───────────── recalibrage hebdomadaire ─────────────
def test_recalibrage_du_calendrier():
    assert regles.recalibrage_du([], "2026-10-22") is True
    h = [{"calibre_le": "2026-10-15"}]
    assert regles.recalibrage_du(h, "2026-10-21") is False
    assert regles.recalibrage_du(h, "2026-10-22") is True
    assert regles.recalibrage_du(h, "2026-11-30") is True
    assert regles.recalibrage_du([{"calibre_le": "2026-10-01"}, {"calibre_le": "2026-10-20"}], "2026-10-26") is False


def test_la_regle_change_toute_seule_quand_les_donnees_changent():
    """Jusqu'au jour 30 ce sont les paris à indice 4 qui réussissent ; ensuite ce sont ceux à indice 1. La règle suit, sans aucune main."""
    haut = serie(lambda d: 0.95 if d < 30 else 0.30, n_jours=60, indice=4, graine=3)
    bas = serie(lambda d: 0.30 if d < 30 else 0.95, n_jours=60, indice=1, graine=4, marche="over_2_5")
    tout = haut + bas
    g30 = regles.photographie(tout, jour(30))["groupes"]
    assert g30 and g30[0]["indice_min"] >= 0.5                      # au jour 30 : indice élevé
    g60 = regles.photographie(tout, jour(60))["groupes"]
    assert [(g["indice_min"], g["n"]) for g in g60] != [(g["indice_min"], g["n"]) for g in g30]    # la règle a changé


def test_construire_ne_recalibre_qu_une_fois_par_semaine():
    paris = serie(0.9) + fond()
    h1, _ = suivi.construire(jour(30), paris, [], [])
    h2, s2 = suivi.construire(jour(31), paris, [], h1)
    assert len(h2) == 1 and s2["recalibre_aujourdhui"] is False
    h3, s3 = suivi.construire(jour(37), paris, [], h2)
    assert len(h3) == 2 and s3["recalibre_aujourdhui"] is True and s3["prochain_recalibrage"] == jour(44)


# ───────────── pas de fuite du futur ─────────────
def test_le_calibrage_du_jour_J_ignore_les_paris_du_jour_J_et_apres():
    base = serie(0.9, n_jours=20) + fond(n_jours=20)
    avant = regles.photographie(base, jour(20))
    futur = base + [pari(20 + i % 5, gagne=0) for i in range(500)]
    apres = regles.photographie(futur, jour(20))
    assert avant["groupes"] == apres["groupes"] and avant["nb_paris"] == apres["nb_paris"]


def test_bilan_hors_echantillon_par_moteur_apres_le_choix():
    paris = serie(0.9, n_jours=40, graine=5) + fond(n_jours=40)
    hist = [regles.photographie(paris, jour(14)), regles.photographie(paris, jour(28))]
    b = regles.bilan_hors_echantillon(paris, hist)
    assert set(b) == {"V3"} and 0 < b["V3"]["n"] <= len([p for p in paris if p["date"] >= jour(14)])
    assert regles.bilan_hors_echantillon([p for p in paris if p["date"] < jour(14)], hist) == {}      # rien avant le 1er instantané
    assert regles.bilan_historique(paris, hist[-1]["groupes"])["V3"]["n"] > 0


# ───────────── classement du jour ─────────────
def test_classer_filtre_sur_la_regle_et_trie_par_indicateurs_affiches():
    regle_v3 = {"moteur": "V3", "indice_min": 0.75, "pct_min": 80, "etoiles_min": 2, "statut": "confirme", "n": 50, "gagnes": 40,
                "reussite": .8, "borne_basse": .7, "p": 0.001}
    regle_v2 = {"moteur": "V2", "indice_min": 0.0, "pct_min": 70, "etoiles_min": 1, "statut": "observation", "n": 90, "gagnes": 60,
                "reussite": .66, "borne_basse": .6, "p": 0.03}
    base = {"marche": "under_2_5"}
    sel = [
        {**base, "moteur": "V3", "pct": 82, "indice": 3, "sur": 4, "etoiles": 2},        # passe
        {**base, "moteur": "V3", "pct": 88, "indice": 4, "sur": 4, "etoiles": 3},        # passe, meilleur pourcentage
        {**base, "moteur": "V3", "pct": 79, "indice": 4, "sur": 4, "etoiles": 3},        # pourcentage trop bas
        {**base, "moteur": "V3", "pct": 90, "indice": 2, "sur": 4, "etoiles": 3},        # indice trop bas
        {**base, "moteur": "V3", "pct": 90, "indice": 4, "sur": 4, "etoiles": 1},        # étoiles insuffisantes
        {**base, "moteur": "V2", "pct": 75, "indice": 0, "sur": 4, "etoiles": 1},        # passe (observation)
        {**base, "moteur": "V2", "pct": 65, "indice": 4, "sur": 4, "etoiles": 3},        # pourcentage trop bas
        {**base, "moteur": "V3", "pct": 95, "indice": None, "sur": None, "etoiles": 3},  # sans indice
    ]
    out = regles.classer(sel, [regle_v3, regle_v2])
    assert [(x["moteur"], x["pct"]) for x in out] == [("V3", 88), ("V3", 82), ("V2", 75)]
    assert [x["rang"] for x in out] == [1, 2, 3]


# ───────────── version du moteur V2 et un pari par match ─────────────
def test_version_courante_et_filtre():
    paris = [pari(0, "V2", version="2.6.9"), pari(5, "V2", version="2.6.9"), pari(4, "V2", version="2.6.10"), pari(9, "V2", version="2.6.10")]
    assert regles.version_courante(paris) == "2.6.10"
    v3, sans = pari(3), pari(2, "V2")
    gardes = regles.garde_version_courante(paris[:2] + [pari(6, "V2", version="2.6.10"), v3, sans])
    assert [p.get("version") for p in gardes if p["moteur"] == "V2" and p.get("version")] == ["2.6.10"]
    assert v3 in gardes and sans in gardes
    assert regles.garde_version_courante([pari(i, "V2") for i in range(5)]) == [pari(i, "V2") for i in range(5)]


def test_un_pari_par_match_garde_le_meilleur_pourcentage():
    a, b = pari(0, mid="M1", marche="over_1_5", pct=60), pari(0, mid="M1", marche="over_2_5", pct=80)
    assert regles.un_pari_par_match_et_famille([a, b]) == [b]


def test_un_pari_par_match_ne_fusionne_pas_ce_qui_est_different():
    lots = [
        [pari(0, mid="M1", marche="over_1_5"), pari(0, mid="M2", marche="over_1_5")],                          # 2 matchs
        [pari(0, mid="M1", marche="over_1_5"), pari(0, mid="M1", marche="under_3_5")],                         # 2 familles
        [pari(0, "V2", mid="M1", marche="over_1_5"), pari(0, "V3", mid="M1", marche="over_1_5")],              # 2 moteurs
        [pari(0), pari(0)],                                                                                    # pas d'identifiant
    ]
    for lot in lots:
        assert len(regles.un_pari_par_match_et_famille(lot)) == 2


def test_la_deduplication_est_deterministe():
    a, b = pari(0, mid="M1", marche="over_1_5", pct=70, gagne=1), pari(0, mid="M1", marche="over_2_5", pct=70, gagne=0)
    assert regles.un_pari_par_match_et_famille([a, b]) == regles.un_pari_par_match_et_famille([b, a])


def test_calibrer_compte_un_pari_par_match():
    paris = [pari(m % 28, "V2", mid=f"M{m}", marche=ligne, pct=90 - 10 * k, gagne=int(m % 10 != 0))
             for m in range(40) for k, ligne in enumerate(("over_0_5", "over_1_5", "over_2_5"))]
    assert regles.calibrer(paris)["nb_paris"] == 40


# ───────────── garde-fou statistique ─────────────
def test_faux_positifs_rares_sans_aucun_avantage():
    r = random.Random(11)
    faux_confirmes = 0
    essais = 30
    for _ in range(essais):
        paris = []
        for d in range(28):
            for _ in range(8):
                paris.append(pari(d, "V2", pct=r.choice((55, 65, 75, 85, 95)), indice=r.randint(0, 4), etoiles=r.randint(1, 3),
                                  gagne=int(r.random() < 0.55)))                # aucun lien entre les indicateurs et le résultat
        faux_confirmes += len([g for g in regles.calibrer(paris)["groupes"] if g["statut"] == "confirme"])
    assert faux_confirmes / essais <= 1.0


# ───────────── données réelles du dépôt (si présentes) ─────────────
def test_chargement_reel_coherent():
    donnees = pytest.importorskip("meilleures_selections.donnees")
    if not (RACINE / "data" / "archive_test").exists():
        pytest.skip("archive absente")
    paris = donnees.paris_resolus(str(RACINE / "data/archive_test"), str(RACINE / "data/v3/journal"))
    assert paris and {p["moteur"] for p in paris} <= {"V2", "V3"}
    assert all(p["gagne"] in (0, 1) and isinstance(p["pct"], int) and p["etoiles"] in (1, 2, 3, 4) for p in paris)
    assert all(p["etoiles"] <= 3 for p in paris if p["moteur"] == "V2")
    c = regles.calibrer(regles.garde_version_courante(paris))
    assert c["m_tests"] == 175 and all(g["statut"] in ("confirme", "observation") for g in c["groupes"])


def test_pourcentage_affiche_arrondi_comme_le_site():
    donnees = pytest.importorskip("meilleures_selections.donnees")
    assert [donnees.pct_affiche(x) for x in (0.7349, 0.735, 0.7351, 0.8, 0.9999)] == [73, 74, 74, 80, 100]
    assert donnees.pct_affiche(None) is None and donnees.pct_affiche("x") is None
    assert [donnees.etoiles_v3(n) for n in (3, 4, 5, 7, 8, 9, 10, 12)] == [1, 1, 2, 2, 3, 3, 4, 4]


# ───────────── pages et pipeline ─────────────
@pytest.mark.parametrize("page,moteur,js", [("archetype.html", "V2", "archetype.js"), ("pronostics_v3.html", "V3", "archetype_v3.js")])
def test_pages_branchees(page, moteur, js):
    h = (RACINE / page).read_text(encoding="utf-8")
    assert f'class="ax-page af-fond af-v{moteur[1]}"' in h
    assert re.search(r"af-meilleures\.css\?v=\d", h)
    assert h.index(js) < h.index("af-date-navigation.js") < h.index("meilleures_selections.js")


def test_js_ne_touche_pas_aux_cartes_du_filtre_de_dates_et_n_affiche_ni_cote_ni_rendement():
    js = (RACINE / "meilleures_selections.js").read_text(encoding="utf-8")
    assert "ax-carte" not in js and "<table" not in js
    assert not re.search(r"cote|rendement|misés", js, re.I)


def test_css_limite_a_la_page():
    css = re.sub(r"/\*.*?\*/", "", (RACINE / "af-meilleures.css").read_text(encoding="utf-8"), flags=re.S)
    for sel in re.findall(r"^([^{}@\n][^{}]*)\{", css, flags=re.M):
        assert all(s.strip().startswith("body.ax-page") for s in sel.split(",")), sel


def test_workflow_apres_les_scores_et_avant_la_publication():
    w = (RACINE / ".github/workflows/pipeline.yml").read_text(encoding="utf-8")
    i = w.index("python evaluation_scores.py")
    j = w.index("python -m meilleures_selections.suivi pipeline")
    k = w.index("Commit et push du résultat")
    assert i < j < k and "continue-on-error: true" in w[j:j + 200]


def test_sortie_json_complete():
    paris = serie(0.9, n_jours=30) + fond(n_jours=30)
    sel = [{"moteur": "V3", "match_id": "m", "date": jour(30), "heure": "10:00", "competition": "X", "domicile": "A", "exterieur": "B",
            "marche": "under_2_5", "pct": 88, "indice": 4, "sur": 4, "etoiles": 2}]
    _, s = suivi.construire(jour(30), paris, sel, [])
    json.dumps(s)
    for cle in ("calibre_le", "prochain_recalibrage", "groupes", "hors_echantillon", "bilan_historique", "rejeu", "selections", "m_tests", "seuil_confirme", "seuil_observation"):
        assert cle in s
    assert len(s["selections"]) == 1 and s["selections"][0]["rang"] == 1
