"""Pari retenu par P1 pour un match: calcul pur, sans constante arbitraire.
Marches evalues = ceux dont P1 donne la probabilite (exactement, par somme ou complement des 7 evenements P1) ET dont la cote reelle est disponible (cotes_betpawa du flux). Un marche sans cote n'est pas evalue (rien d'invente).
Valeur d'un marche = probabilite P1 x cote - 1 (valeur > 0 : P1 juge la cote superieure a son prix juste). Pari retenu = parmi les marches a valeur > 0, celui de plus forte probabilite P1 ; aucun si aucun marche n'a de valeur > 0 (« aucun marche retenu » est un resultat valide).
Valeur selon P1 uniquement : P1 n'a pas demontre de gain face aux cotes ; ce n'est pas une garantie."""
M = [  # cle, libelle, (type, parametre), chemin de cote
    ("1", "Victoire {d}", "dom", ("1x2", "1")), ("N", "Match nul", "nul", ("1x2", "N")), ("2", "Victoire {e}", "ext", ("1x2", "2")),
    ("1N", "{d} ou match nul", "1N", ("double_chance", "1N")), ("N2", "Match nul ou {e}", "N2", ("double_chance", "N2")), ("12", "{d} ou {e} (pas de nul)", "12", ("double_chance", "12")),
    ("o15+", "Plus de 1,5 but", "o15", ("over_under_1.5", "plus")), ("o15-", "Moins de 1,5 but", "-o15", ("over_under_1.5", "moins")),
    ("o25+", "Plus de 2,5 buts", "o25", ("over_under_2.5", "plus")), ("o25-", "Moins de 2,5 buts", "-o25", ("over_under_2.5", "moins")),
    ("o35+", "Plus de 3,5 buts", "o35", ("over_under_3.5", "plus")), ("o35-", "Moins de 3,5 buts", "-o35", ("over_under_3.5", "moins")),
    ("btts+", "Les deux équipes marquent", "btts", ("btts", "Oui")), ("btts-", "Au moins une équipe ne marque pas", "-btts", ("btts", "Non"))]

def proba(p, t):
    if t in ("dom", "nul", "ext", "o15", "o25", "o35", "btts"): return p[t]
    if t == "1N": return p["dom"] + p["nul"]
    if t == "N2": return p["nul"] + p["ext"]
    if t == "12": return p["dom"] + p["ext"]
    return 1.0 - p[t[1:]]

def gagne(cle, d, e):
    t = d + e
    return {"1": d > e, "N": d == e, "2": d < e, "1N": d >= e, "N2": d <= e, "12": d != e, "o15+": t >= 2, "o15-": t < 2, "o25+": t >= 3, "o25-": t < 3, "o35+": t >= 4, "o35-": t < 4, "btts+": d > 0 and e > 0, "btts-": not (d > 0 and e > 0)}[cle]

def cotes_utiles(cotes_betpawa):
    """{cle: cote} pour les marches disponibles avec cote > 1 (sinon absents)."""
    out = {}
    for cle, _, _, (g, s) in M:
        v = ((cotes_betpawa or {}).get(g) or {}).get(s)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1: out[cle] = float(v)
    return out

def choisir(p, cotes, domicile="", exterieur=""):
    marches = []
    for cle, lib, t, _ in M:
        if cle not in cotes: continue
        q = proba(p, t); marches.append({"cle": cle, "libelle": lib.format(d=domicile, e=exterieur), "p1": q, "cote": cotes[cle], "valeur": q * cotes[cle] - 1})
    pos = [m for m in marches if m["valeur"] > 0]
    return {"retenu": max(pos, key=lambda m: m["p1"]) if pos else None, "marches": marches, "cotes_disponibles": len(marches)}
