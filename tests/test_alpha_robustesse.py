"""Tests de la couche de robustesse de l'alpha (cahier des charges du 23/10/2026)."""
from alpha_serie import robustesse as R


def _grille(cle):
    for c, _, p, z in R.catalogue():
        if c == cle:
            return R.grilles(p, z)
    raise KeyError(cle)


def test_juste_au_seuil_plus_1_5():
    passe, solide = _grille(("over_under_1.5", "plus"))
    assert solide[2][1] and solide[3][0] and solide[2][2]          # 3 buts et plus : solide
    assert not solide[1][1] and not solide[2][0] and not solide[0][2]  # 2 buts pile : juste au seuil
    assert not passe[1][0]


def test_juste_double_chance_et_victoire():
    _, solide = _grille(("double_chance", "1N"))
    assert solide[1][0] and solide[2][0] and solide[3][1]          # victoire du domicile : solide
    assert not solide[0][0] and not solide[1][1] and not solide[2][2]  # passe grâce au nul : juste
    _, sv = _grille(("1x2", "1"))
    assert sv[2][0] and sv[3][1] and sv[4][2]
    assert not sv[1][0] and not sv[2][1] and not sv[3][2]          # gagné d'un seul but : juste


def test_marches_zero_but_exemptes():
    _, solide = _grille(("btts", "Non"))
    assert solide[0][0] and solide[3][0] and solide[0][2]
    assert not solide[1][1] and not solide[2][1] and not solide[1][3]


def test_defavorable_pire_des_quatre_coins():
    passe, solide = _grille(("over_under_1.5", "plus"))
    # (A, C, B, D) : domicile marque 3 / extérieur encaisse 2 ; extérieur marque 1 / domicile encaisse 1 -> coins (2..3, 1..1) : 3 et 4 buts
    assert R.lecture_paire((3, 2, 1, 1), passe, solide) == (1, 1)
    # coin le plus fermé (1, 0) : 1 but -> le défavorable tombe, l'habituel (2, 1) passe
    assert R.lecture_paire((2, 1, 1, 0), passe, solide) == (0, 1)
    assert R.lecture_paire((0, 0, 0, 0), passe, solide) == (0, 0)


def test_combo_juste_si_une_jambe_juste():
    _, solide = _grille(("combo", "1N+plus_1.5"))
    assert solide[3][0] and solide[2][1] and solide[4][1]          # aucune jambe ne tombe avec un but de plus ou de moins
    assert not solide[3][3]                                        # nul : jambe 1N juste
    assert not solide[2][0] and not solide[1][1]                   # 2 buts pile : jambe total juste


def test_wilson_et_effectif_minimum():
    assert R.wilson_bas(16, 16) >= R.SEUIL_WILSON
    assert R.wilson_bas(9, 9) < R.SEUIL_WILSON                     # un petit groupe parfait ne suffit pas (seuil 72 %)
    assert R.wilson_bas(0, 0) == 0.0


def test_verdict_stabilite_table_gelee():
    passe, solide = _grille(("over_under_1.5", "plus"))
    prs = [(3, 3, 2, 2)] * 4
    cle = ("over_under_1.5", "plus")
    ok = {"retenu": True}
    cel = {R.cle_cellule(cle, 4, 4, 4): ok, R.cle_cellule(cle, 3, 3, 3): ok}
    assert R.verdict(prs, cle, passe, solide, cel)["statut"] == "retenu"
    cel_instable = {R.cle_cellule(cle, 4, 4, 4): ok, R.cle_cellule(cle, 3, 3, 3): {"retenu": False}}
    assert R.verdict(prs, cle, passe, solide, cel_instable)["statut"] == "instable"
    assert R.verdict(prs, cle, passe, solide, {})["statut"] == "abstention"
    assert R.verdict(prs[:3], cle, passe, solide, cel)["statut"] == "exclu"


# --- Version 2 (23/10/2026) : seuil 72 %, combos par jambes, calibrage par marché et intervalle de cote --------------
def test_combo_avec_jambe_zero_but_garde_son_exemption():
    _, solide = _grille(("combo", "1N+btts_non"))
    assert solide[1][0] and solide[3][0] and solide[5][0]          # BTTS non exempté ; 1N tient même avec un but de moins (nul)
    assert not solide[0][0] and not solide[1][1] and not solide[0][1]  # 0-0 : 1N juste ; 1-1 et 0-1 ne passent pas


def test_quatre_coins_egal_coin_du_marche_pour_les_marches_monotones():
    """Réponse au contrôle externe : pour un marché qui ne fait que monter ou descendre avec les buts de chaque équipe,
    exiger les 4 coins revient exactement à exiger le coin défavorable propre au marché."""
    coins = {("over_under_1.5", "plus"): (0, 0), ("over_under_3.5", "moins"): (1, 1), ("1x2", "1"): (0, 1),
             ("double_chance", "N2"): (1, 0), ("over_under_domicile_1.5", "plus"): (0, 0), ("btts", "Oui"): (0, 0)}
    for cle, (ih, ia) in coins.items():
        passe, solide = _grille(cle)
        for A in range(5):
            for Cc in range(5):
                for B in range(5):
                    for D in range(5):
                        hs, as_ = (min(A, Cc), max(A, Cc)), (min(B, D), max(B, D))
                        quatre = all(solide[h][a] for h in hs for a in as_)
                        un = solide[hs[ih]][as_[ia]]
                        assert quatre == un, (cle, A, Cc, B, D)


def test_archive_sans_doublon():
    from alpha_serie.robustesse import charger_archive_archetype
    ms = charger_archive_archetype()
    assert len({m["id"] for m in ms}) == len(ms)
    assert len({(m["jour"], m["domicile"], m["exterieur"]) for m in ms}) == len(ms)
    from alpha_serie import coeur
    for m in ms[:200]:                                           # anti-fuite : la série lue s'arrête avant le jour du match
        hm, _ = coeur.serie_lieu(m["dom"], True, m["jour"])
        assert len(hm) <= 7


# --- Calibrage par famille (24/10/2026) : aucun taux commun, combos autonomes, grosses cotes sans plafond ---------
def _l(nom, jour, gagne, cote, d=1.0, h=1.0, cle=("x", "y"), **kw):
    return {"marche": nom, "jour": jour, "gagne": bool(gagne), "cote": cote, "def": d, "hab": h, "cle": cle, "famille": R.famille(cle), **kw}


JOURS = [f"2026-10-{i:02d}" for i in range(1, 21)]


def test_familles_separees():
    assert R.famille(("over_under_2.5", "plus")) == "totaux"
    assert R.famille(("over_under_domicile_1.5", "plus")) == "buts par équipe" and R.famille(("cages_inviolees_domicile", "oui")) == "buts par équipe"
    assert R.famille(("btts", "Oui")) == "BTTS" and R.famille(("1x2", "N")) == "1N2" and R.famille(("double_chance", "12")) == "double chance"
    assert R.famille(("handicap_-1.5", "domicile")) == "handicaps" and R.famille(("combo", "1N+plus_1.5")) == "combos"
    assert R.famille(("multigoals", "1-3")) == "multigoals" and R.famille(("multiscores", "Match nul")) == "multiscores"


def test_voies_sans_plafond():
    assert R.voie(1.25) == "A" and R.voie(1.38) == "A" and R.voie(1.39) == "B" and R.voie(25.0) == "B"
    assert R.voie(1.24) is None and R.voie(None, ("combo", "1N+plus_1.5")) == "sans_cote"


def test_combo_retenu_par_ses_criteres_sous_le_seuil_des_simples():
    """Combo à 45 % avec filtre contre 25 % sans : retenu, alors qu'aucun marché simple ne passerait 72 %."""
    L = []
    for j in JOURS:
        L += [_l("C", j, k < 9, None, cle=("combo", "1N+moins_3.5"), def_fragile=1.0, hab_fragile=1.0) for k in range(20)]   # 45 %
        L += [_l("C", j, k < 1, None, cle=("combo", "1N+moins_3.5"), def_fragile=0.0, hab_fragile=0.0) for k in range(20)]   # 5 %
    r = R.calibrer_marche_voie(L, "sans_cote")
    assert r is not None and r["axes"] == "jambe la plus fragile" and r["valeur"] == 0.45 and r["valeur"] < 0.72
    assert len(R.appliquer([_l("C", "2026-10-21", 0, None, cle=("combo", "1N+moins_3.5"), def_fragile=1.0, hab_fragile=1.0)], {("C", "sans_cote"): r})) == 1


def test_grosse_cote_non_rejetee_pour_son_montant():
    L = []
    for j in JOURS:
        L += [_l("V", j, k == 0, 4.0, 1.0, 1.0) for k in range(3)]          # filtré : 1 sur 3 à 4,0 -> rendement +33 %
        L += [_l("V", j, 0, 4.0, 0.0, 0.0) for _ in range(3)]               # non filtré : 0 sur 3
    r = R.calibrer_marche_voie(L, "B")
    assert r is not None and r["objectif"] == "rendement" and r["valeur"] > 0
    pris = R.appliquer([_l("V", "2026-10-21", 0, 9.5, 1.0, 1.0)], {("V", "B"): r})
    assert len(pris) == 1 and pris[0]["voie"] == "B"                           # une cote de 9,5 passe


def test_filtre_sans_amelioration_rejete():
    L = [_l("M", j, k < 8, 1.30, 1.0 if k % 2 else 0.0, 1.0 if k % 2 else 0.0) for j in JOURS for k in range(10)]   # 80 % avec ou sans filtre
    assert R.calibrer_marche_voie(L, "A") is None                                # le filtre n'apporte rien : aucune règle
    oos = [{**_l("M", f"2026-10-{21 + i % 4:02d}", i % 5 != 0, 1.30), "voie": "A"} for i in range(40)]   # 80 %
    ref = [_l("M", f"2026-10-{21 + i % 4:02d}", i % 10 != 0, 1.30) for i in range(80)]                   # 90 % sans filtre
    v = R.juger(oos, ref, {f"2026-10-{d}" for d in range(21, 25)})
    assert v[0]["statut"] == "rejeté" and "ne fait pas mieux" in v[0]["raison"]


def test_petit_effectif_parfait_pas_valide():
    oos = [{**_l("M", f"2026-10-{21 + i:02d}", 1, 1.30), "voie": "A"} for i in range(3)]
    ref = [_l("M", f"2026-10-{21 + i:02d}", k < 7, 1.30) for i in range(3) for k in range(10)]
    v = R.juger(oos, ref, {"2026-10-21", "2026-10-22", "2026-10-23"})[0]
    assert v["reussite"] == 1.0 and v["statut"] != "validé hors échantillon"     # 3 sur 3 ne prouve rien (borne de Wilson)


def test_validation_et_prometteur():
    jt = {f"2026-10-{d}" for d in range(21, 25)}
    ref = [_l("M", f"2026-10-{21 + i % 4:02d}", i % 2 == 0, 1.30) for i in range(400)]                   # 50 %
    oos = [{**_l("M", f"2026-10-{21 + i % 4:02d}", i % 10 < 9, 1.30), "voie": "A"} for i in range(200)]  # 90 %
    assert R.juger(oos, ref, jt)[0]["statut"] == "validé hors échantillon"
    oos = [{**_l("M", f"2026-10-{21 + i % 4:02d}", i % 5 < 3, 1.30), "voie": "A"} for i in range(20)]    # 60 % sur 20
    assert R.juger(oos, ref, jt)[0]["statut"] == "prometteur"


def test_appliquer_ne_lit_jamais_l_issue():
    regles = {("M", "A"): {"marge_defavorable": 0.5, "marge_habituelle": 0.5}}
    jour = [_l("M", "2026-10-21", 1, 1.30, 0.6, 0.6), _l("M", "2026-10-21", 1, 1.30, 0.2, 0.9)]
    a = [x["def"] for x in R.appliquer(jour, regles)]
    for x in jour:
        x["gagne"] = not x["gagne"]
    assert [x["def"] for x in R.appliquer(jour, regles)] == a == [0.6]


def test_cotes_anterieures_au_coup_d_envoi():
    ms = R.charger_archive_archetype()
    assert ms and all(m["cotes_prises_le"] < m["coup_d_envoi_utc"] for m in ms)


def test_marche_avant_n_apprend_que_sur_le_passe(monkeypatch):
    vus = []
    reel = R.calibrer
    monkeypatch.setattr(R, "calibrer", lambda L: (vus.append(max(x["jour"] for x in L)), reel(L))[1])
    lignes = [_l("M", j, 1, 1.30) for j in JOURS[:5]]
    R.marche_avant(lignes)
    assert vus == JOURS[:4]                                                      # le jour d appris est toujours strictement avant le jour testé
