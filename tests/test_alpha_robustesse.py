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


def test_intervalle_gagnant():
    from alpha_serie.robustesse import _meilleur_intervalle
    pts = [(1.30, 1)] * 20 + [(1.60, 0)] * 10
    assert _meilleur_intervalle(sorted(pts))[:2] == (1.30, 1.30)     # la zone perdante est laissée dehors
    pts = [(1.30, 1)] * 15 + [(1.40, 1)] * 15 + [(1.50, 1)] * 5
    assert _meilleur_intervalle(sorted(pts))[:3] == (1.30, 1.50, 35)  # tout passe : le plus large
    assert _meilleur_intervalle(sorted([(1.30, 1)] * 30 + [(1.32, 0)] * 2))[2] == 32  # deux pertes au milieu : gardées si la barre tient
    assert _meilleur_intervalle([(1.30, 1)] * 9) is None               # trop peu de paris : 9 sur 9 ne passe pas la borne Wilson
    assert _meilleur_intervalle(sorted([(1.30, 1), (1.30, 0)] * 20)) is None   # 50 % : jamais retenu
    assert _meilleur_intervalle([]) is None


def test_archive_sans_doublon():
    from alpha_serie.robustesse import charger_archive_archetype
    ms = charger_archive_archetype()
    assert len({m["id"] for m in ms}) == len(ms)
    assert len({(m["jour"], m["domicile"], m["exterieur"]) for m in ms}) == len(ms)
    from alpha_serie import coeur
    for m in ms[:200]:                                           # anti-fuite : la série lue s'arrête avant le jour du match
        hm, _ = coeur.serie_lieu(m["dom"], True, m["jour"])
        assert len(hm) <= 7


# --- Protocole final (24/10/2026) : validation chronologique répétée, verdict hors échantillon ----------------------
def _paris(nom, gagnes_par_jour):
    out = []
    for i, gs in enumerate(gagnes_par_jour):
        out += [{"marche": nom, "jour": f"2026-10-{10 + i:02d}", "gagne": bool(g), "cote": 1.30} for g in gs]
    return out


def _base(nom, taux, jours=4, n=100):
    return [{"marche": nom, "jour": f"2026-10-{10 + i:02d}", "gagne": k < taux * n} for i in range(jours) for k in range(n)]


def test_juger_valide_quand_tout_tient():
    paris = _paris("M", [[1] * 20 + [0] * 5, [1] * 20 + [0] * 5, [1] * 20 + [0] * 5])
    v = R.juger(paris, _base("M", 0.60))
    assert v["M"]["statut"] == "validé" and v["M"]["paris"] == 75


def test_juger_exploratoire_sous_50_paris():
    v = R.juger(_paris("M", [[1] * 20, [1] * 20]), _base("M", 0.5))
    assert v["M"]["statut"] == "exploratoire"


def test_juger_rejette_sous_72_ou_incoherent_ou_sans_gain():
    assert R.juger(_paris("M", [[1] * 35 + [0] * 25]), _base("M", 0.5))["M"]["statut"] == "rejeté"             # 58 %
    v = R.juger(_paris("M", [[1] * 30, [1] * 15 + [0] * 15]), _base("M", 0.5))["M"]                              # 100 % puis 50 %
    assert v["statut"] == "rejeté" and "incohérent" in v["raison"]
    v = R.juger(_paris("M", [[1] * 40 + [0] * 10, [1] * 40 + [0] * 10]), _base("M", 0.85))["M"]                  # 80 % < base 85 %
    assert v["statut"] == "rejeté" and "gain" in v["raison"]


def test_multigoals_et_multiscores_hors_couche():
    assert R.HORS_COUCHE == {"multigoals", "multiscores"}
