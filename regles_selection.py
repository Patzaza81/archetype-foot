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

VERSION_REGLE = "1.1.0"

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
        c.exige(eq_tout["pts_par_match"] >= s["pts_par_match_min"], f"{n_eq} prend {eq_tout['pts_par_match']:.2f} pt/match sur la saison")
        c.exige(eq["buts_marques"] >= s["buts_marques_lieu_min"], f"{n_eq} marque {eq['buts_marques']:.1f} but/match à ce lieu")
        # faiblesse de l'adversaire
        c.exige(adv["victoires"] <= s["adv_victoires_lieu_max"], f"{n_adv} gagne {_pct(adv['victoires'])} à son lieu ({adv['n']})")
        c.exige(adv["buts_encaisses"] >= s["adv_buts_encaisses_lieu_min"], f"{n_adv} encaisse {adv['buts_encaisses']:.1f} but/match à son lieu")

    elif marche in ("Double chance - 1X", "Double chance - X2"):
        s = SEUILS["double_chance"]
        if marche == "Double chance - 1X":
            eq, adv, eq_tout, n_eq, n_adv = dom_lieu, ext_lieu, dom_tout, nom_dom, nom_ext
        else:
            eq, adv, eq_tout, n_eq, n_adv = ext_lieu, dom_lieu, ext_tout, nom_ext, nom_dom
        c.exige(eq["victoires"] + eq["nuls"] >= s["invaincu_lieu_min"], f"{n_eq} invaincu {_pct(eq['victoires'] + eq['nuls'])} à ce lieu ({eq['n']})")
        c.exige(eq_tout["pts_par_match"] >= s["pts_par_match_min"], f"{n_eq} prend {eq_tout['pts_par_match']:.2f} pt/match sur la saison")
        c.exige(adv["victoires"] <= s["adv_victoires_lieu_max"], f"{n_adv} gagne {_pct(adv['victoires'])} à son lieu")
        c.exige(eq["buts_marques"] >= adv["buts_marques"], f"{n_eq} marque {eq['buts_marques']:.1f} contre {adv['buts_marques']:.1f} pour {n_adv}, chacun à son lieu")

    elif marche == "Moins de 2.5 buts":
        s = SEUILS["moins_2_5"]
        c.exige(dom_lieu["moins_2_5"] >= s["lieu_min"], f"{nom_dom} à domicile : {_pct(dom_lieu['moins_2_5'])} de matchs à -2,5")
        c.exige(ext_lieu["moins_2_5"] >= s["lieu_min"], f"{nom_ext} à l'extérieur : {_pct(ext_lieu['moins_2_5'])} de matchs à -2,5")
        c.exige(dom_tout["moins_2_5"] >= s["saison_min"] and ext_tout["moins_2_5"] >= s["saison_min"],
                f"saison complète -2,5 : {_pct(dom_tout['moins_2_5'])} / {_pct(ext_tout['moins_2_5'])}")
        c.exige(total <= s["buts_attendus_max"], f"buts attendus {total:.2f}")

    elif marche == "Moins de 3.5 buts":
        s = SEUILS["moins_3_5"]
        c.exige(dom_lieu["moins_3_5"] >= s["lieu_min"] and ext_lieu["moins_3_5"] >= s["lieu_min"],
                f"-3,5 chacun à son lieu : {_pct(dom_lieu['moins_3_5'])} / {_pct(ext_lieu['moins_3_5'])}")
        c.exige(total <= s["buts_attendus_max"], f"buts attendus {total:.2f}")

    elif marche == "Plus de 2.5 buts":
        s = SEUILS["plus_2_5"]
        c.exige(dom_lieu["plus_2_5"] >= s["lieu_min"], f"{nom_dom} à domicile : {_pct(dom_lieu['plus_2_5'])} de matchs à +2,5")
        c.exige(ext_lieu["plus_2_5"] >= s["lieu_min"], f"{nom_ext} à l'extérieur : {_pct(ext_lieu['plus_2_5'])} de matchs à +2,5")
        c.exige(dom_tout["plus_2_5"] >= s["saison_min"] and ext_tout["plus_2_5"] >= s["saison_min"],
                f"saison complète +2,5 : {_pct(dom_tout['plus_2_5'])} / {_pct(ext_tout['plus_2_5'])}")
        c.exige(total >= s["buts_attendus_min"], f"buts attendus {total:.2f}")

    elif marche == "Plus de 3.5 buts":
        s = SEUILS["plus_3_5"]
        c.exige(dom_lieu["plus_3_5"] >= s["lieu_min"] and ext_lieu["plus_3_5"] >= s["lieu_min"],
                f"+3,5 chacun à son lieu : {_pct(dom_lieu['plus_3_5'])} / {_pct(ext_lieu['plus_3_5'])}")
        c.exige(total >= s["buts_attendus_min"], f"buts attendus {total:.2f}")

    elif marche == "BTTS - oui":
        s = SEUILS["btts"]
        c.exige(dom_lieu["marque"] >= s["marque_lieu_min"] and ext_lieu["marque"] >= s["marque_lieu_min"],
                f"marquent chacun à son lieu : {_pct(dom_lieu['marque'])} / {_pct(ext_lieu['marque'])}")
        c.exige(dom_lieu["encaisse"] >= s["encaisse_lieu_min"] and ext_lieu["encaisse"] >= s["encaisse_lieu_min"],
                f"encaissent chacun à son lieu : {_pct(dom_lieu['encaisse'])} / {_pct(ext_lieu['encaisse'])}")
        c.exige(dom_lieu["btts"] >= s["btts_lieu_min"] and ext_lieu["btts"] >= s["btts_lieu_min"],
                f"les deux marquent, chacun à son lieu : {_pct(dom_lieu['btts'])} / {_pct(ext_lieu['btts'])}")
        c.exige(min(att_dom, att_ext) >= s["buts_attendus_min"], f"buts attendus de chaque côté {att_dom:.2f} / {att_ext:.2f}")

    else:
        c.exige(False, f"marché « {marche} » non couvert par la règle : pari écarté")
    return c.resultat()


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
        c.exige(v >= s["recent_victoires_min"] and d <= s["recent_defaites_max"], f"{n_eq} sur ses 6 derniers : {v} victoires, {d} défaites")
        c.exige(va <= s["adv_recent_victoires_max"], f"{n_adv} sur ses 6 derniers : {va} victoires")

    elif marche in ("Double chance - 1X", "Double chance - X2"):
        s = SEUILS["double_chance"]
        eq, adv, n_eq, n_adv = (d6, e6, nom_dom, nom_ext) if marche == "Double chance - 1X" else (e6, d6, nom_ext, nom_dom)
        inv = _compte(eq, lambda m: m["bm"] >= m["be"])
        va = _compte(adv, lambda m: m["bm"] > m["be"])
        c.exige(inv >= s["recent_invaincu_min"], f"{n_eq} invaincu {inv} fois sur ses 6 derniers")
        c.exige(va <= s["adv_recent_victoires_max"], f"{n_adv} : {va} victoires sur ses 6 derniers")

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
