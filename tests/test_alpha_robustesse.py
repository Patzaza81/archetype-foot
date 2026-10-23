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


# --- Correction méthodologique (24/10/2026) : deux voies, aucun plafond de cote, verdicts séparés ------------------
def _l(nom, jour, gagne, cote, d=1.0, h=1.0, cle=("x", "y")):
    return {"marche": nom, "jour": jour, "gagne": bool(gagne), "cote": cote, "def": d, "hab": h, "cle": cle}


def test_voies_sans_plafond_et_cote_minimale():
    assert R.voie(1.25) == "A" and R.voie(1.38) == "A"
    assert R.voie(1.39) == "B" and R.voie(4.5) == "B" and R.voie(25.0) == "B"     # aucune limite haute
    assert R.voie(1.24) is None and R.voie(1.10) is None                          # sous la cote minimale de Patrick
    assert R.voie(None, ("combo", "1N+plus_1.5")) == "sans_cote"
    assert R.voie(None, ("1x2", "1")) is None                                     # marché simple sans cote pour ce match : écarté


def test_grosse_cote_admissible_n_est_pas_rejetee_pour_sa_valeur():
    jours = [f"2026-10-{i:02d}" for i in range(1, 21)]
    L = [_l("V", j, k == 0, 3.6) for j in jours for k in range(3)]                 # 1 sur 3 à 3,6 : gain positif dans chaque moitié
    r = R.calibrer_marche_voie(L, "B")
    assert r is not None and r["gain_net"] > 0
    pris = R.appliquer([_l("V", "2026-10-21", 0, 6.0)], {("V", "B"): r})
    assert len(pris) == 1 and pris[0]["voie"] == "B"                              # une cote de 6,0 passe : la valeur de la cote ne rejette rien


def test_appliquer_ne_lit_jamais_l_issue():
    regles = {("M", "A"): {"part_defavorable_min": 0.5, "part_habituelle_min": 0.5}}
    jour = [_l("M", "2026-10-21", 1, 1.30, 0.6, 0.6), _l("M", "2026-10-21", 1, 1.30, 0.2, 0.9)]
    a = [x["def"] for x in R.appliquer(jour, regles)]
    for x in jour:
        x["gagne"] = not x["gagne"]
    assert [x["def"] for x in R.appliquer(jour, regles)] == a == [0.6]


def test_regle_choisie_par_objectif_pas_par_volume():
    jours = [f"2026-10-{i:02d}" for i in range(1, 21)]
    L = []
    for j in jours:
        L += [_l("M", j, 1, 1.30, 1.0, 1.0)] * 4                                  # filtré : 100 %
        L += [_l("M", j, k < 3, 1.30, 0.0, 0.0) for k in range(5)]                # non filtré : 60 %
    r = R.calibrer_marche_voie(L, "A")
    assert r["filtre_scenarios"] and r["paris"] == 80 and r["reussite"] == 1.0   # pas la règle « tout prendre » (180 paris)


def test_filtre_sans_apport_non_retenu():
    jours = [f"2026-10-{i:02d}" for i in range(1, 21)]
    L = [_l("M", j, k < 8, 1.30, 1.0 if k % 2 else 0.0, 1.0) for j in jours for k in range(10)]  # 80 % avec ou sans filtre
    r = R.calibrer_marche_voie(L, "A")
    assert r is not None and not r["filtre_scenarios"]


def test_juger_voie_a_valide_rejette_exploratoire():
    def oos(gs, v="A", cote=1.30):
        return [{**_l("M", f"2026-10-{10 + i // 20:02d}", g, cote), "voie": v} for i, g in enumerate(gs)]
    ref = [_l("M", f"2026-10-{10 + i:02d}", k < 6, 1.30) for i in range(4) for k in range(10)]   # sans filtre : 60 %
    assert R.juger(oos([1, 1, 1, 1, 0] * 12), ref)["A"]["M"]["statut"] == "validé"
    assert R.juger(oos([1] * 30), ref)["A"]["M"]["statut"] == "exploratoire"
    assert R.juger(oos([1, 0] * 30), ref)["A"]["M"]["statut"] == "rejeté"                         # 50 %
    v = R.juger(oos([1] * 30 + [1, 0] * 15), ref)["A"]["M"]
    assert v["statut"] == "rejeté" and "incohérent" in v["raison"]


def test_juger_voie_b_separee():
    def oos(gs, cote):
        return [{**_l("M", f"2026-10-{10 + i // 20:02d}", g, cote), "voie": "B"} for i, g in enumerate(gs)]
    ref = [_l("M", "2026-10-10", 0, 3.0)]
    assert R.juger(oos([1, 0, 0] * 20, 3.6), ref)["B"]["M"]["statut"] == "opportunité démontrée"   # 33 % à 3,6 : gagnant
    assert R.juger(oos([1, 0, 0, 0] * 15, 3.6), ref)["B"]["M"]["statut"] == "rejeté"               # 25 % à 3,6 : perdant
    assert R.juger(oos([1, 0, 0] * 10, 3.6), ref)["B"]["M"]["statut"] == "exploratoire"
    assert R.juger(oos([1, 0, 0] * 20, 3.6), ref)["A"] == {}                                        # jamais mélangé avec la voie A


def test_cotes_anterieures_au_coup_d_envoi():
    ms = R.charger_archive_archetype()
    assert all(m["cotes_prises_le"] < m["coup_d_envoi_utc"] for m in ms)


def test_multigoals_et_multiscores_hors_couche():
    assert R.HORS_COUCHE == {"multigoals", "multiscores"}
