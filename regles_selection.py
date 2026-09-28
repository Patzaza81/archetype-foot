# -*- coding: utf-8 -*-
"""
RÈGLE DU DOUBLE CONTRÔLE — TRÈS IMPORTANTE (décidée le 26/09/2026)
===================================================================

À utiliser OBLIGATOIREMENT par tout nouveau moteur de sélection d'Archetype Foot.
Voir docs/REGLE_DOUBLE_CONTROLE.md pour l'explication complète et l'origine.

Un pari n'est retenu que s'il passe DEUX contrôles, sinon il est écarté :

  1. CONTRÔLE SAISON, DANS LES DEUX SENS
     - l'équipe à domicile est jugée sur SES matchs à domicile,
     - l'équipe à l'extérieur est jugée sur SES matchs à l'extérieur,
     - et les deux sur leur saison complète.
     Une victoire ne se justifie jamais par la seule faiblesse de l'adversaire :
     il faut aussi prouver que l'équipe choisie sait gagner.

  2. CONTRÔLE FORME RÉCENTE
     - les 6 derniers matchs de chaque équipe (tous lieux),
     - et les 3 derniers matchs au même lieu.
     Cas d'origine : Real Salt Lake – New England (26/09/2026), « les deux équipes
     marquent » validé sur la saison (RSL marque dans 75 % de ses matchs à domicile)
     alors que RSL n'avait marqué que dans 2 de ses 6 derniers matchs.

Ce module ne fait AUCUNE collecte : il reçoit les résultats déjà collectés
(Football-Data d'abord, Matchendirect en complément) et rend un verdict.

Format d'un match : {"date": "AAAA-MM-JJ", "lieu": "D" ou "E", "bm": buts marqués, "be": buts encaissés}
(bm / be sont vus du côté de l'équipe dont c'est la liste).
"""

VERSION_REGLE = "1.2.0"

MIN_MATCHS_LIEU = 3       # en dessous : pari écarté (échantillon trop petit)
MIN_MATCHS_RECENTS = 5    # en dessous : pari écarté
NB_RECENTS = 6
NB_RECENTS_LIEU = 3

MARCHES_COUVERTS = (
    "1X2 - 1", "1X2 - 2",
    "Double chance - 1X", "Double chance - X2",
    "Moins de 2.5 buts", "Moins de 3.5 buts",
    "Plus de 2.5 buts", "Plus de 3.5 buts",
    "BTTS - oui",
    # AJOUT version 1.2.0 (28/09/2026, décision de Patrick : « étendre la règle du 26/09 avec des seuils pour chaque
    # marché »). Seuils écrits À L'AVANCE, par analogie avec ceux de la 1.0.0, jamais ajustés sur des résultats.
    "Double chance - 12", "BTTS - non", "Plus de 1.5 buts", "Moins de 4.5 buts",
    "Handicap domicile -1.5", "Handicap domicile +1.5", "Handicap extérieur -1.5", "Handicap extérieur +1.5",
    "Buts domicile - plus de 0.5", "Buts domicile - plus de 1.5", "Buts domicile - moins de 0.5",
    "Buts domicile - moins de 1.5", "Buts domicile - moins de 2.5",
    "Buts extérieur - plus de 0.5", "Buts extérieur - plus de 1.5", "Buts extérieur - moins de 0.5",
    "Buts extérieur - moins de 1.5", "Buts extérieur - moins de 2.5",
)

# Seuils (ne pas modifier sans validation sur données réelles et sans mettre à jour la doc)
SEUILS = {
    "victoire": {"victoires_lieu_min": 0.50, "pts_par_match_min": 1.60, "buts_marques_lieu_min": 1.4,
                 "adv_victoires_lieu_max": 0.34, "adv_buts_encaisses_lieu_min": 1.2,
                 "recent_victoires_min": 3, "recent_defaites_max": 2, "adv_recent_victoires_max": 2},
    "double_chance": {"invaincu_lieu_min": 0.70, "pts_par_match_min": 1.45, "adv_victoires_lieu_max": 0.40,
                      "recent_invaincu_min": 4, "adv_recent_victoires_max": 3},
    "moins_2_5": {"lieu_min": 0.60, "saison_min": 0.55, "buts_attendus_max": 2.3, "recent_min": 4},
    "moins_3_5": {"lieu_min": 0.75, "buts_attendus_max": 2.7, "recent_min": 4},
    "plus_2_5": {"lieu_min": 0.60, "saison_min": 0.55, "buts_attendus_min": 2.9,
                 "recent_min_chacun": 3, "recent_min_total": 7},
    "plus_3_5": {"lieu_min": 0.50, "buts_attendus_min": 3.4, "recent_min_chacun": 3, "recent_min_total": 7},
    # --- version 1.2.0 ---
    "dc_12": {"nuls_lieu_max": 0.20, "nuls_saison_max": 0.25, "recent_nuls_max": 1},
    "btts_non": {"btts_lieu_max": 0.40, "buts_attendus_faible_max": 1.1, "recent_btts_max": 2},
    "plus_1_5": {"lieu_min": 0.75, "saison_min": 0.70, "buts_attendus_min": 2.4, "recent_min": 4},
    "moins_4_5": {"lieu_min": 0.85, "buts_attendus_max": 3.2, "recent_min": 5},
    # handicap -1,5 : gagner par 2 buts ou plus ; +1,5 : ne pas perdre par 2 buts ou plus
    "handicap_moins_1_5": {"large_victoire_lieu_min": 0.40, "pts_par_match_min": 1.8,
                           "adv_large_defaite_lieu_min": 0.35, "ecart_attendu_min": 1.0,
                           "recent_larges_victoires_min": 2, "adv_recent_larges_defaites_min": 2},
    "handicap_plus_1_5": {"large_defaite_lieu_max": 0.15, "adv_large_victoire_lieu_max": 0.20,
                          "ecart_attendu_max": 0.5, "recent_larges_defaites_max": 1,
                          "adv_recent_larges_victoires_max": 2},
    # buts d'une équipe : part des matchs de l'équipe à son lieu au-dessus/en dessous de la ligne, part des matchs de
    # l'adversaire à son lieu où il encaisse au-dessus/en dessous, buts attendus de l'équipe, forme récente (sur 6).
    "equipe": {
        ("plus", 0.5): {"eq": 0.80, "adv": 0.70, "saison": 0.75, "attendu": 1.2, "recent": 5, "recent_adv": 4},
        ("plus", 1.5): {"eq": 0.60, "adv": 0.50, "saison": 0.50, "attendu": 1.9, "recent": 3, "recent_adv": 3},
        ("moins", 0.5): {"eq": 0.50, "adv": 0.50, "saison": 0.40, "attendu": 0.6, "recent": 3, "recent_adv": 3},
        ("moins", 1.5): {"eq": 0.70, "adv": 0.65, "saison": 0.65, "attendu": 1.0, "recent": 4, "recent_adv": 4},
        ("moins", 2.5): {"eq": 0.85, "adv": 0.80, "saison": 0.80, "attendu": 1.6, "recent": 5, "recent_adv": 5},
    },
    "btts": {"marque_lieu_min": 0.70, "encaisse_lieu_min": 0.60, "btts_lieu_min": 0.55, "buts_attendus_min": 1.0,
             "recent_marque_min": 4, "recent_encaisse_min": 4, "recent_lieu_marque_min": 2},
}


# ---------------------------------------------------------------------------
# Statistiques de base
# ---------------------------------------------------------------------------
def _tries(matchs):
    return sorted(matchs, key=lambda m: m.get("date") or "")


def stats(matchs):
    """Statistiques d'une liste de matchs (vus du côté de l'équipe). None si liste vide."""
    n = len(matchs)
    if n == 0:
        return None

    def part(cond):
        return sum(1 for m in matchs if cond(m)) / n

    return {
        "n": n,
        "victoires": part(lambda m: m["bm"] > m["be"]),
        "nuls": part(lambda m: m["bm"] == m["be"]),
        "defaites": part(lambda m: m["bm"] < m["be"]),
        "pts_par_match": sum(3 if m["bm"] > m["be"] else 1 if m["bm"] == m["be"] else 0 for m in matchs) / n,
        "buts_marques": sum(m["bm"] for m in matchs) / n,
        "buts_encaisses": sum(m["be"] for m in matchs) / n,
        "plus_2_5": part(lambda m: m["bm"] + m["be"] > 2),
        "plus_3_5": part(lambda m: m["bm"] + m["be"] > 3),
        "plus_1_5": part(lambda m: m["bm"] + m["be"] > 1),
        "moins_4_5": part(lambda m: m["bm"] + m["be"] < 5),
        "larges_victoires": part(lambda m: m["bm"] - m["be"] >= 2),
        "larges_defaites": part(lambda m: m["be"] - m["bm"] >= 2),
        "moins_2_5": part(lambda m: m["bm"] + m["be"] < 3),
        "moins_3_5": part(lambda m: m["bm"] + m["be"] < 4),
        "btts": part(lambda m: m["bm"] > 0 and m["be"] > 0),
        "marque": part(lambda m: m["bm"] > 0),
        "encaisse": part(lambda m: m["be"] > 0),
    }


def _compte(matchs, cond):
    return sum(1 for m in matchs if cond(m))


def _pct(x):
    return f"{x:.0%}"


def _dec(x, d):
    """Nombre à virgule, à la française (CORRECTIF 28/09/2026 : « 1.71 » affiché sur la page V3)."""
    return f"{x:.{d}f}".replace(".", ",")


def _nb(k, mot):
    """« 0 victoire », « 1 victoire », « 2 victoires » (CORRECTIF 28/09/2026 : « 1 victoires »)."""
    return f"{k} {mot}{'s' if k > 1 else ''}"


class _Controle:
    def __init__(self):
        self.ok = True
        self.raisons = []

    def exige(self, condition, texte):
        self.raisons.append(("✓ " if condition else "✗ ") + texte)
        if not condition:
            self.ok = False

    def resultat(self):
        return {"ok": self.ok, "raisons": self.raisons}


# ---------------------------------------------------------------------------
# Contrôle 1 : saison, dans les deux sens
# ---------------------------------------------------------------------------
def controle_saison(marche, matchs_dom, matchs_ext, nom_dom="Domicile", nom_ext="Extérieur"):
    c = _Controle()
    dom_lieu = stats([m for m in matchs_dom if m["lieu"] == "D"])
    ext_lieu = stats([m for m in matchs_ext if m["lieu"] == "E"])
    dom_tout, ext_tout = stats(matchs_dom), stats(matchs_ext)
    if not dom_lieu or not ext_lieu or dom_lieu["n"] < MIN_MATCHS_LIEU or ext_lieu["n"] < MIN_MATCHS_LIEU:
        c.exige(False, f"échantillon trop petit (moins de {MIN_MATCHS_LIEU} matchs au même lieu)")
        return c.resultat()
    # buts attendus : attaque de l'un croisée avec la défense de l'autre, chacun à son lieu
    att_dom = (dom_lieu["buts_marques"] + ext_lieu["buts_encaisses"]) / 2
    att_ext = (ext_lieu["buts_marques"] + dom_lieu["buts_encaisses"]) / 2
    total = att_dom + att_ext

    if marche in ("1X2 - 1", "1X2 - 2"):
        s = SEUILS["victoire"]
        if marche == "1X2 - 1":
            eq, adv, eq_tout, n_eq, n_adv = dom_lieu, ext_lieu, dom_tout, nom_dom, nom_ext
        else:
            eq, adv, eq_tout, n_eq, n_adv = ext_lieu, dom_lieu, ext_tout, nom_ext, nom_dom
        # compétence de l'équipe choisie
        c.exige(eq["victoires"] >= s["victoires_lieu_min"], f"{n_eq} gagne {_pct(eq['victoires'])} de ses matchs à ce lieu ({eq['n']})")
        c.exige(eq_tout["pts_par_match"] >= s["pts_par_match_min"], f"{n_eq} prend {_dec(eq_tout['pts_par_match'], 2)} pt/match sur la saison")
        c.exige(eq["buts_marques"] >= s["buts_marques_lieu_min"], f"{n_eq} marque {_dec(eq['buts_marques'], 1)} but/match à ce lieu")
        # faiblesse de l'adversaire
        c.exige(adv["victoires"] <= s["adv_victoires_lieu_max"], f"{n_adv} gagne {_pct(adv['victoires'])} à son lieu ({adv['n']})")
        c.exige(adv["buts_encaisses"] >= s["adv_buts_encaisses_lieu_min"], f"{n_adv} encaisse {_dec(adv['buts_encaisses'], 1)} but/match à son lieu")

    elif marche in ("Double chance - 1X", "Double chance - X2"):
        s = SEUILS["double_chance"]
        if marche == "Double chance - 1X":
            eq, adv, eq_tout, n_eq, n_adv = dom_lieu, ext_lieu, dom_tout, nom_dom, nom_ext
        else:
            eq, adv, eq_tout, n_eq, n_adv = ext_lieu, dom_lieu, ext_tout, nom_ext, nom_dom
        c.exige(eq["victoires"] + eq["nuls"] >= s["invaincu_lieu_min"], f"{n_eq} invaincu {_pct(eq['victoires'] + eq['nuls'])} à ce lieu ({eq['n']})")
        c.exige(eq_tout["pts_par_match"] >= s["pts_par_match_min"], f"{n_eq} prend {_dec(eq_tout['pts_par_match'], 2)} pt/match sur la saison")
        c.exige(adv["victoires"] <= s["adv_victoires_lieu_max"], f"{n_adv} gagne {_pct(adv['victoires'])} à son lieu")
        c.exige(eq["buts_marques"] >= adv["buts_marques"], f"{n_eq} marque {_dec(eq['buts_marques'], 1)} contre {_dec(adv['buts_marques'], 1)} pour {n_adv}, chacun à son lieu")

    elif marche == "Moins de 2.5 buts":
        s = SEUILS["moins_2_5"]
        c.exige(dom_lieu["moins_2_5"] >= s["lieu_min"], f"{nom_dom} à domicile : {_pct(dom_lieu['moins_2_5'])} de matchs à -2,5")
        c.exige(ext_lieu["moins_2_5"] >= s["lieu_min"], f"{nom_ext} à l'extérieur : {_pct(ext_lieu['moins_2_5'])} de matchs à -2,5")
        c.exige(dom_tout["moins_2_5"] >= s["saison_min"] and ext_tout["moins_2_5"] >= s["saison_min"],
                f"saison complète -2,5 : {_pct(dom_tout['moins_2_5'])} / {_pct(ext_tout['moins_2_5'])}")
        c.exige(total <= s["buts_attendus_max"], f"total attendu (moyennes simples) : {_dec(total, 2)} buts")

    elif marche == "Moins de 3.5 buts":
        s = SEUILS["moins_3_5"]
        c.exige(dom_lieu["moins_3_5"] >= s["lieu_min"] and ext_lieu["moins_3_5"] >= s["lieu_min"],
                f"-3,5 chacun à son lieu : {_pct(dom_lieu['moins_3_5'])} / {_pct(ext_lieu['moins_3_5'])}")
        c.exige(total <= s["buts_attendus_max"], f"total attendu (moyennes simples) : {_dec(total, 2)} buts")

    elif marche == "Plus de 2.5 buts":
        s = SEUILS["plus_2_5"]
        c.exige(dom_lieu["plus_2_5"] >= s["lieu_min"], f"{nom_dom} à domicile : {_pct(dom_lieu['plus_2_5'])} de matchs à +2,5")
        c.exige(ext_lieu["plus_2_5"] >= s["lieu_min"], f"{nom_ext} à l'extérieur : {_pct(ext_lieu['plus_2_5'])} de matchs à +2,5")
        c.exige(dom_tout["plus_2_5"] >= s["saison_min"] and ext_tout["plus_2_5"] >= s["saison_min"],
                f"saison complète +2,5 : {_pct(dom_tout['plus_2_5'])} / {_pct(ext_tout['plus_2_5'])}")
        c.exige(total >= s["buts_attendus_min"], f"total attendu (moyennes simples) : {_dec(total, 2)} buts")

    elif marche == "Plus de 3.5 buts":
        s = SEUILS["plus_3_5"]
        c.exige(dom_lieu["plus_3_5"] >= s["lieu_min"] and ext_lieu["plus_3_5"] >= s["lieu_min"],
                f"+3,5 chacun à son lieu : {_pct(dom_lieu['plus_3_5'])} / {_pct(ext_lieu['plus_3_5'])}")
        c.exige(total >= s["buts_attendus_min"], f"total attendu (moyennes simples) : {_dec(total, 2)} buts")

    elif marche == "BTTS - oui":
        s = SEUILS["btts"]
        c.exige(dom_lieu["marque"] >= s["marque_lieu_min"] and ext_lieu["marque"] >= s["marque_lieu_min"],
                f"marquent chacun à son lieu : {_pct(dom_lieu['marque'])} / {_pct(ext_lieu['marque'])}")
        c.exige(dom_lieu["encaisse"] >= s["encaisse_lieu_min"] and ext_lieu["encaisse"] >= s["encaisse_lieu_min"],
                f"encaissent chacun à son lieu : {_pct(dom_lieu['encaisse'])} / {_pct(ext_lieu['encaisse'])}")
        c.exige(dom_lieu["btts"] >= s["btts_lieu_min"] and ext_lieu["btts"] >= s["btts_lieu_min"],
                f"les deux marquent, chacun à son lieu : {_pct(dom_lieu['btts'])} / {_pct(ext_lieu['btts'])}")
        c.exige(min(att_dom, att_ext) >= s["buts_attendus_min"], f"buts attendus de chaque côté (moyennes simples) : {_dec(att_dom, 2)} / {_dec(att_ext, 2)}")

    # ------------------------------------------------------------------ version 1.2.0
    elif marche == "Double chance - 12":
        s = SEUILS["dc_12"]
        c.exige(dom_lieu["nuls"] <= s["nuls_lieu_max"] and ext_lieu["nuls"] <= s["nuls_lieu_max"],
                f"nuls chacun à son lieu : {_pct(dom_lieu['nuls'])} / {_pct(ext_lieu['nuls'])}")
        c.exige(dom_tout["nuls"] <= s["nuls_saison_max"] and ext_tout["nuls"] <= s["nuls_saison_max"],
                f"nuls sur la saison : {_pct(dom_tout['nuls'])} / {_pct(ext_tout['nuls'])}")

    elif marche == "BTTS - non":
        s = SEUILS["btts_non"]
        c.exige(dom_lieu["btts"] <= s["btts_lieu_max"] and ext_lieu["btts"] <= s["btts_lieu_max"],
                f"les deux marquent, chacun à son lieu : {_pct(dom_lieu['btts'])} / {_pct(ext_lieu['btts'])}")
        c.exige(min(att_dom, att_ext) <= s["buts_attendus_faible_max"],
                f"buts attendus du côté le plus faible (moyennes simples) : {_dec(min(att_dom, att_ext), 2)}")

    elif marche == "Plus de 1.5 buts":
        s = SEUILS["plus_1_5"]
        c.exige(dom_lieu["plus_1_5"] >= s["lieu_min"] and ext_lieu["plus_1_5"] >= s["lieu_min"],
                f"+1,5 chacun à son lieu : {_pct(dom_lieu['plus_1_5'])} / {_pct(ext_lieu['plus_1_5'])}")
        c.exige(dom_tout["plus_1_5"] >= s["saison_min"] and ext_tout["plus_1_5"] >= s["saison_min"],
                f"saison complète +1,5 : {_pct(dom_tout['plus_1_5'])} / {_pct(ext_tout['plus_1_5'])}")
        c.exige(total >= s["buts_attendus_min"], f"total attendu (moyennes simples) : {_dec(total, 2)} buts")

    elif marche == "Moins de 4.5 buts":
        s = SEUILS["moins_4_5"]
        c.exige(dom_lieu["moins_4_5"] >= s["lieu_min"] and ext_lieu["moins_4_5"] >= s["lieu_min"],
                f"-4,5 chacun à son lieu : {_pct(dom_lieu['moins_4_5'])} / {_pct(ext_lieu['moins_4_5'])}")
        c.exige(total <= s["buts_attendus_max"], f"total attendu (moyennes simples) : {_dec(total, 2)} buts")

    elif marche.startswith("Handicap "):
        domicile = marche.startswith("Handicap domicile")
        eq, adv, eq_tout = (dom_lieu, ext_lieu, dom_tout) if domicile else (ext_lieu, dom_lieu, ext_tout)
        n_eq, n_adv = (nom_dom, nom_ext) if domicile else (nom_ext, nom_dom)
        ecart = (att_dom - att_ext) if domicile else (att_ext - att_dom)
        if marche.endswith("-1.5"):
            s = SEUILS["handicap_moins_1_5"]
            c.exige(eq["larges_victoires"] >= s["large_victoire_lieu_min"],
                    f"{n_eq} gagne par 2 buts ou plus dans {_pct(eq['larges_victoires'])} de ses matchs à ce lieu")
            c.exige(eq_tout["pts_par_match"] >= s["pts_par_match_min"],
                    f"{n_eq} prend {_dec(eq_tout['pts_par_match'], 2)} pt/match sur la saison")
            c.exige(adv["larges_defaites"] >= s["adv_large_defaite_lieu_min"],
                    f"{n_adv} perd par 2 buts ou plus dans {_pct(adv['larges_defaites'])} de ses matchs à son lieu")
            c.exige(ecart >= s["ecart_attendu_min"], f"écart de buts attendu (moyennes simples) : {_dec(ecart, 2)}")
        else:
            s = SEUILS["handicap_plus_1_5"]
            c.exige(eq["larges_defaites"] <= s["large_defaite_lieu_max"],
                    f"{n_eq} perd par 2 buts ou plus dans {_pct(eq['larges_defaites'])} de ses matchs à ce lieu")
            c.exige(adv["larges_victoires"] <= s["adv_large_victoire_lieu_max"],
                    f"{n_adv} gagne par 2 buts ou plus dans {_pct(adv['larges_victoires'])} de ses matchs à son lieu")
            c.exige(-ecart <= s["ecart_attendu_max"],
                    f"écart de buts attendu en faveur de {n_adv} (moyennes simples) : {_dec(-ecart, 2)}")

    elif marche.startswith("Buts "):
        domicile, sens, ligne = _lit_marche_equipe(marche)
        s = SEUILS["equipe"][(sens, ligne)]
        eq_l = [m for m in matchs_dom if m["lieu"] == "D"] if domicile else [m for m in matchs_ext if m["lieu"] == "E"]
        adv_l = [m for m in matchs_ext if m["lieu"] == "E"] if domicile else [m for m in matchs_dom if m["lieu"] == "D"]
        eq_t = matchs_dom if domicile else matchs_ext
        n_eq, n_adv = (nom_dom, nom_ext) if domicile else (nom_ext, nom_dom)
        att = att_dom if domicile else att_ext
        cond = (lambda b: b > ligne) if sens == "plus" else (lambda b: b < ligne)
        mot = f"{'plus' if sens == 'plus' else 'moins'} de {_dec(ligne, 1)} but{'s' if ligne > 2 else ''}"
        p_eq = _compte(eq_l, lambda m: cond(m["bm"])) / len(eq_l)
        p_adv = _compte(adv_l, lambda m: cond(m["be"])) / len(adv_l)
        p_sai = _compte(eq_t, lambda m: cond(m["bm"])) / len(eq_t)
        c.exige(p_eq >= s["eq"], f"{n_eq} marque {mot} dans {_pct(p_eq)} de ses matchs à ce lieu")
        c.exige(p_adv >= s["adv"], f"{n_adv} encaisse {mot} dans {_pct(p_adv)} de ses matchs à son lieu")
        c.exige(p_sai >= s["saison"], f"{n_eq} marque {mot} dans {_pct(p_sai)} de ses matchs de la saison")
        c.exige(att >= s["attendu"] if sens == "plus" else att <= s["attendu"],
                f"buts attendus de {n_eq} (moyennes simples) : {_dec(att, 2)}")

    else:
        c.exige(False, f"marché « {marche} » non couvert par la règle : pari écarté")
    return c.resultat()


def _lit_marche_equipe(marche):
    """« Buts domicile - plus de 1.5 » -> (True, "plus", 1.5)."""
    qui, reste = marche[len("Buts "):].split(" - ")
    sens, ligne = reste.split(" de ")
    return qui == "domicile", sens, float(ligne)


# ---------------------------------------------------------------------------
# Contrôle 2 : forme récente
# ---------------------------------------------------------------------------
def controle_recent(marche, matchs_dom, matchs_ext, nom_dom="Domicile", nom_ext="Extérieur"):
    c = _Controle()
    d6 = _tries(matchs_dom)[-NB_RECENTS:]
    e6 = _tries(matchs_ext)[-NB_RECENTS:]
    d3 = [m for m in _tries(matchs_dom) if m["lieu"] == "D"][-NB_RECENTS_LIEU:]
    e3 = [m for m in _tries(matchs_ext) if m["lieu"] == "E"][-NB_RECENTS_LIEU:]
    if len(d6) < MIN_MATCHS_RECENTS or len(e6) < MIN_MATCHS_RECENTS:
        c.exige(False, f"moins de {MIN_MATCHS_RECENTS} matchs récents")
        return c.resultat()

    if marche in ("1X2 - 1", "1X2 - 2"):
        s = SEUILS["victoire"]
        eq, adv, n_eq, n_adv = (d6, e6, nom_dom, nom_ext) if marche == "1X2 - 1" else (e6, d6, nom_ext, nom_dom)
        v = _compte(eq, lambda m: m["bm"] > m["be"])
        d = _compte(eq, lambda m: m["bm"] < m["be"])
        va = _compte(adv, lambda m: m["bm"] > m["be"])
        c.exige(v >= s["recent_victoires_min"] and d <= s["recent_defaites_max"], f"{n_eq} sur ses 6 derniers : {_nb(v, 'victoire')}, {_nb(d, 'défaite')}")
        c.exige(va <= s["adv_recent_victoires_max"], f"{n_adv} sur ses 6 derniers : {_nb(va, 'victoire')}")

    elif marche in ("Double chance - 1X", "Double chance - X2"):
        s = SEUILS["double_chance"]
        eq, adv, n_eq, n_adv = (d6, e6, nom_dom, nom_ext) if marche == "Double chance - 1X" else (e6, d6, nom_ext, nom_dom)
        inv = _compte(eq, lambda m: m["bm"] >= m["be"])
        va = _compte(adv, lambda m: m["bm"] > m["be"])
        c.exige(inv >= s["recent_invaincu_min"], f"{n_eq} invaincu {inv} fois sur ses 6 derniers")
        c.exige(va <= s["adv_recent_victoires_max"], f"{n_adv} : {_nb(va, 'victoire')} sur ses 6 derniers")

    elif marche in ("Moins de 2.5 buts", "Moins de 3.5 buts"):
        ligne = 2 if marche == "Moins de 2.5 buts" else 3
        mini = SEUILS["moins_2_5" if ligne == 2 else "moins_3_5"]["recent_min"]
        a = _compte(d6, lambda m: m["bm"] + m["be"] <= ligne)
        b = _compte(e6, lambda m: m["bm"] + m["be"] <= ligne)
        c.exige(a >= mini and b >= mini, f"sous la ligne sur les 6 derniers : {a} ({nom_dom}) / {b} ({nom_ext})")

    elif marche in ("Plus de 2.5 buts", "Plus de 3.5 buts"):
        ligne = 2 if marche == "Plus de 2.5 buts" else 3
        s = SEUILS["plus_2_5" if ligne == 2 else "plus_3_5"]
        a = _compte(d6, lambda m: m["bm"] + m["be"] > ligne)
        b = _compte(e6, lambda m: m["bm"] + m["be"] > ligne)
        c.exige(a >= s["recent_min_chacun"] and b >= s["recent_min_chacun"] and a + b >= s["recent_min_total"],
                f"au-dessus de la ligne sur les 6 derniers : {a} ({nom_dom}) / {b} ({nom_ext})")

    elif marche == "BTTS - oui":
        s = SEUILS["btts"]
        md, me = _compte(d6, lambda m: m["bm"] > 0), _compte(e6, lambda m: m["bm"] > 0)
        ed, ee = _compte(d6, lambda m: m["be"] > 0), _compte(e6, lambda m: m["be"] > 0)
        ld, le = _compte(d3, lambda m: m["bm"] > 0), _compte(e3, lambda m: m["bm"] > 0)
        c.exige(md >= s["recent_marque_min"] and me >= s["recent_marque_min"], f"marquent sur les 6 derniers : {md} / {me}")
        c.exige(ed >= s["recent_encaisse_min"] and ee >= s["recent_encaisse_min"], f"encaissent sur les 6 derniers : {ed} / {ee}")
        c.exige(ld >= s["recent_lieu_marque_min"] and le >= s["recent_lieu_marque_min"], f"marquent sur les 3 derniers au même lieu : {ld} / {le}")

    # ------------------------------------------------------------------ version 1.2.0
    elif marche == "Double chance - 12":
        s = SEUILS["dc_12"]
        a = _compte(d6, lambda m: m["bm"] == m["be"])
        b = _compte(e6, lambda m: m["bm"] == m["be"])
        c.exige(a <= s["recent_nuls_max"] and b <= s["recent_nuls_max"],
                f"nuls sur les 6 derniers : {a} ({nom_dom}) / {b} ({nom_ext})")

    elif marche == "BTTS - non":
        s = SEUILS["btts_non"]
        a = _compte(d6, lambda m: m["bm"] > 0 and m["be"] > 0)
        b = _compte(e6, lambda m: m["bm"] > 0 and m["be"] > 0)
        c.exige(a <= s["recent_btts_max"] and b <= s["recent_btts_max"],
                f"les deux ont marqué sur les 6 derniers : {a} ({nom_dom}) / {b} ({nom_ext})")

    elif marche in ("Plus de 1.5 buts", "Moins de 4.5 buts"):
        plus = marche == "Plus de 1.5 buts"
        mini = SEUILS["plus_1_5" if plus else "moins_4_5"]["recent_min"]
        cond = (lambda m: m["bm"] + m["be"] > 1) if plus else (lambda m: m["bm"] + m["be"] < 5)
        a, b = _compte(d6, cond), _compte(e6, cond)
        c.exige(a >= mini and b >= mini,
                f"{'au-dessus' if plus else 'sous'} de la ligne sur les 6 derniers : {a} ({nom_dom}) / {b} ({nom_ext})")

    elif marche.startswith("Handicap "):
        domicile = marche.startswith("Handicap domicile")
        eq, adv, n_eq, n_adv = (d6, e6, nom_dom, nom_ext) if domicile else (e6, d6, nom_ext, nom_dom)
        lv = _compte(eq, lambda m: m["bm"] - m["be"] >= 2)
        ld = _compte(eq, lambda m: m["be"] - m["bm"] >= 2)
        adv_lv = _compte(adv, lambda m: m["bm"] - m["be"] >= 2)
        adv_ld = _compte(adv, lambda m: m["be"] - m["bm"] >= 2)
        if marche.endswith("-1.5"):
            s = SEUILS["handicap_moins_1_5"]
            c.exige(lv >= s["recent_larges_victoires_min"],
                    f"{n_eq} : {_nb(lv, 'victoire')} par 2 buts ou plus sur ses 6 derniers")
            c.exige(adv_ld >= s["adv_recent_larges_defaites_min"],
                    f"{n_adv} : {_nb(adv_ld, 'défaite')} par 2 buts ou plus sur ses 6 derniers")
        else:
            s = SEUILS["handicap_plus_1_5"]
            c.exige(ld <= s["recent_larges_defaites_max"],
                    f"{n_eq} : {_nb(ld, 'défaite')} par 2 buts ou plus sur ses 6 derniers")
            c.exige(adv_lv <= s["adv_recent_larges_victoires_max"],
                    f"{n_adv} : {_nb(adv_lv, 'victoire')} par 2 buts ou plus sur ses 6 derniers")

    elif marche.startswith("Buts "):
        domicile, sens, ligne = _lit_marche_equipe(marche)
        s = SEUILS["equipe"][(sens, ligne)]
        eq, adv, n_eq, n_adv = (d6, e6, nom_dom, nom_ext) if domicile else (e6, d6, nom_ext, nom_dom)
        cond = (lambda b: b > ligne) if sens == "plus" else (lambda b: b < ligne)
        a = _compte(eq, lambda m: cond(m["bm"]))
        b = _compte(adv, lambda m: cond(m["be"]))
        mot = f"{'plus' if sens == 'plus' else 'moins'} de {_dec(ligne, 1)} but{'s' if ligne > 2 else ''}"
        c.exige(a >= s["recent"], f"{n_eq} marque {mot} dans {a} de ses 6 derniers")
        c.exige(b >= s["recent_adv"], f"{n_adv} encaisse {mot} dans {b} de ses 6 derniers")

    else:
        c.exige(False, f"marché « {marche} » non couvert par la règle : pari écarté")
    return c.resultat()


# ---------------------------------------------------------------------------
# Pari « limite » (AJOUT 26/09/2026, version 1.1.0)
# ---------------------------------------------------------------------------
# Règle d'usage : dans un combiné, un pari limite est EXCLU dès qu'un autre pari propre (retenu, non limite)
# est disponible. Un pari est limite s'il passe sans aucune marge : l'adversaire a déjà atteint le maximum
# autorisé de victoires récentes. Seuls les matchs de la MÊME compétition comptent (jamais les coupes).
def est_limite(resultat):
    """resultat : sortie de double_controle."""
    return bool(resultat.get("limite"))


def choisir_pour_combine(resultats):
    """resultats : liste de sorties de double_controle (une par pari candidat).
    Garde les paris retenus ; écarte les paris limites dès qu'au moins un pari propre (retenu, non limite) existe."""
    retenus = [r for r in resultats if r["retenu"]]
    propres = [r for r in retenus if not r["limite"]]
    return propres if propres else retenus


# ---------------------------------------------------------------------------
# Point d'entrée unique
# ---------------------------------------------------------------------------
def double_controle(marche, matchs_dom, matchs_ext, nom_dom="Domicile", nom_ext="Extérieur"):
    """Verdict final. Le pari n'est retenu que si les DEUX contrôles passent.

    matchs_dom : matchs de la saison en cours de l'équipe qui reçoit, dans la MÊME compétition que le match analysé
                 (domicile et extérieur). Jamais de matchs de coupe ou d'une autre compétition.
    matchs_ext : idem pour l'équipe qui se déplace.
    Renvoie {"retenu", "limite", "marge_nulle", "saison", "recent", "version_regle"}.
    """
    saison = controle_saison(marche, matchs_dom, matchs_ext, nom_dom, nom_ext)
    recent = controle_recent(marche, matchs_dom, matchs_ext, nom_dom, nom_ext)
    marge_nulle = _marge_nulle(marche, matchs_dom, matchs_ext)
    retenu = saison["ok"] and recent["ok"]
    return {"retenu": retenu, "limite": retenu and marge_nulle, "marge_nulle": marge_nulle, "saison": saison, "recent": recent, "version_regle": VERSION_REGLE}


def _marge_nulle(marche, matchs_dom, matchs_ext):
    """Vrai si l'adversaire est exactement au maximum autorisé de victoires récentes (victoire ou double chance)."""
    d6 = _tries(matchs_dom)[-NB_RECENTS:]
    e6 = _tries(matchs_ext)[-NB_RECENTS:]
    victoires = lambda L: _compte(L, lambda m: m["bm"] > m["be"])
    if marche in ("1X2 - 1", "Double chance - 1X"):
        adv = e6
    elif marche in ("1X2 - 2", "Double chance - X2"):
        adv = d6
    else:
        return False
    maxi = SEUILS["victoire"]["adv_recent_victoires_max"] if marche.startswith("1X2") else SEUILS["double_chance"]["adv_recent_victoires_max"]
    return victoires(adv) == maxi
