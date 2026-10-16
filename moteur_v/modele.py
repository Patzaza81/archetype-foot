"""Modèle de v : force des adversaires affrontés (Poisson), calcul simple de buts (marqués/encaissés au même lieu), écart de points,
écart de rang, choix du pronostic principal + rubrique « autres », fiabilité HONNÊTE par zone de cote.
Paramètres mesurés le 16/10/2026 sur 440 matchs de data/archive_test (28/09 au 14/10) : à réévaluer avec les carnets."""
import math
from collections import defaultdict

from .coeur import COTE_MIN, MIN_MATCHS
from .marches import cote_cote

PARAMETRES_VERSION = "2026-10-16"
PRIOR_FORCE = 3.0                       # matchs fictifs qui ramènent une force d'équipe vers 1 (peu de matchs = peu de confiance)
SEUIL_AUTRES = 0.70                     # score modèle minimal pour figurer dans « autres »
MAX_AUTRES = 5
VETO_POINTS = -0.30                     # écart de points par match / 3 défavorable au côté parié (1X2, double chance) -> alerte
VETO_RANG = -0.40                       # écart de rang normalisé défavorable au côté parié -> alerte
MIN_EQUIPES_CLASSEMENT = 8
MIN_MATCHS_POINTS = 3
# Fiabilité MESURÉE (réussite réelle du pari au plus fort score du modèle) par zone de cote. Le score du modèle lui-même est trop
# optimiste (74-79 % annoncés pour 54-75 % réels) : on affiche la fiabilité mesurée, jamais le score brut.
FIABILITE_ZONES = [(1.26, 1.37, 0.748, "SÛR"), (1.37, 1.49, 0.655, "MOYEN"), (1.49, 1.81, 0.543, "RISQUÉ")]


# ---------------------------------------------------------------- probabilités
def _pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)


def proba_marche(pred, lh, la, n=10):
    ph = [_pois(lh, k) for k in range(n + 1)]
    pa = [_pois(la, k) for k in range(n + 1)]
    return sum(ph[i] * pa[j] for i in range(n + 1) for j in range(n + 1) if pred(i, j))


def lambdas_simples(rh, ra):
    """Buts attendus par moyennes simples au même lieu : (marqués dom + encaissés ext)/2 et (marqués ext + encaissés dom)/2."""
    sH = sum(x[0] for x in rh) / len(rh)
    cH = sum(x[1] for x in rh) / len(rh)
    sA = sum(x[0] for x in ra) / len(ra)
    cA = sum(x[1] for x in ra) / len(ra)
    return max((sH + cA) / 2, .05), max((sA + cH) / 2, .05)


class Forces:
    """Force d'attaque / défense de chaque équipe, ajustée à la force des adversaires affrontés (Poisson multiplicatif, rétréci vers 1),
    ajustée sur tous les matchs archivés STRICTEMENT avant la date (aucune fuite). entrees = entrées de data/archive_test."""

    def __init__(self, entrees):
        M = {}
        for e in entrees:
            for t in ("equipe_dom", "equipe_ext"):
                q = e.get(t) or {}
                for m in q.get("matchs") or []:
                    if not (isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)):
                        continue
                    h, a = (q.get("nom"), m.get("adversaire")) if m.get("domicile") else (m.get("adversaire"), q.get("nom"))
                    g = (m["buts_marques"], m["buts_encaisses"]) if m.get("domicile") else (m["buts_encaisses"], m["buts_marques"])
                    M[(m["date"], h, a)] = g
        self.L = sorted((d, h, a, g[0], g[1]) for (d, h, a), g in M.items())
        self.cache = {}

    def ajuste(self, avant, it=60):
        if avant in self.cache:
            return self.cache[avant]
        ms = [x for x in self.L if x[0] < avant]
        if not ms:
            self.cache[avant] = ({}, {}, 1.0, 1.0)
            return self.cache[avant]
        mu = sum(x[3] + x[4] for x in ms) / (2 * len(ms))
        gam = 1.2
        att = defaultdict(lambda: 1.0)
        dfn = defaultdict(lambda: 1.0)
        for _ in range(it):
            na, da, nd, dd = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
            for d, h, a, gh, ga in ms:
                na[h] += gh; da[h] += mu * gam * dfn[a]; na[a] += ga; da[a] += mu * dfn[h]
                nd[a] += gh; dd[a] += mu * gam * att[h]; nd[h] += ga; dd[h] += mu * att[a]
            att = defaultdict(lambda: 1.0, {t: (na[t] + PRIOR_FORCE) / (da[t] + PRIOR_FORCE) for t in na})
            dfn = defaultdict(lambda: 1.0, {t: (nd[t] + PRIOR_FORCE) / (dd[t] + PRIOR_FORCE) for t in nd})
            gam = sum(x[3] for x in ms) / max(1e-9, sum(mu * att[x[1]] * dfn[x[2]] for x in ms))
        self.cache[avant] = (att, dfn, mu, gam)
        return self.cache[avant]

    def lambdas(self, date, dom, ext):
        """(lambda dom, lambda ext) ou None si une équipe n'a aucun match connu avant la date."""
        att, dfn, mu, gam = self.ajuste(date)
        if dom not in att or ext not in att:
            return None
        return mu * gam * att[dom] * dfn[ext], mu * att[ext] * dfn[dom]


# ---------------------------------------------------------------- points et classement (reconstruits sans fuite)
def points_par_match(hist, date):
    ms = [m for m in (hist or []) if isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)
          and str(m.get("date") or "") < date]
    if len(ms) < MIN_MATCHS_POINTS:
        return None
    pts = sum(3 if m["buts_marques"] > m["buts_encaisses"] else 1 if m["buts_marques"] == m["buts_encaisses"] else 0 for m in ms)
    return pts / len(ms)


def ecart_points(hd, he, date):
    """(points par match domicile - extérieur) / 3 ; positif = domicile devant. None si historique trop court."""
    h, a = points_par_match(hd, date), points_par_match(he, date)
    return None if h is None or a is None else (h - a) / 3.0


class Classements:
    """Classement reconstruit depuis les historiques archivés (points par match, puis différence de buts par match). Partiel :
    seules les équipes présentes dans l'archive y figurent. Il doit être remplacé par le vrai classement quand il sera archivé."""

    def __init__(self, entrees):
        self.t = defaultdict(dict)
        for e in entrees:
            for k in ("equipe_dom", "equipe_ext"):
                q = e.get(k) or {}
                if q.get("matchs"):
                    self.t[e.get("competition")][q.get("nom")] = q["matchs"]
        self.cache = {}

    def table(self, comp, d):
        if (comp, d) not in self.cache:
            T = []
            for n, ms in self.t[comp].items():
                ms = [m for m in ms if str(m.get("date") or "") < d and isinstance(m.get("buts_marques"), int)
                      and isinstance(m.get("buts_encaisses"), int)]
                if len(ms) < MIN_MATCHS_POINTS:
                    continue
                pts = sum(3 if m["buts_marques"] > m["buts_encaisses"] else 1 if m["buts_marques"] == m["buts_encaisses"] else 0 for m in ms)
                T.append((n, pts / len(ms), sum(m["buts_marques"] - m["buts_encaisses"] for m in ms) / len(ms)))
            T.sort(key=lambda t: (-t[1], -t[2]))
            self.cache[(comp, d)] = T
        return self.cache[(comp, d)]

    def ecart_rang(self, comp, date, dom, ext):
        """(rang extérieur - rang domicile) / nb équipes ; positif = domicile mieux classé. None si classement trop incomplet."""
        T = self.table(comp, date)
        noms = [t[0] for t in T]
        if len(T) < MIN_EQUIPES_CLASSEMENT or dom not in noms or ext not in noms:
            return None
        return (noms.index(ext) - noms.index(dom)) / len(T)


# ---------------------------------------------------------------- choix du pronostic
def zone_fiabilite(cote):
    for lo, hi, p, nom in FIABILITE_ZONES:
        if lo - 1e-9 <= cote < hi + (1e-9 if hi == FIABILITE_ZONES[-1][1] else 0):
            return p, nom
    return None, "NON CALIBRÉ"


def _signature(pred, n=8):
    return tuple(bool(pred(h, a)) for h in range(n) for a in range(n))


def proposer(cands, lam_force, lam_simple, seuil_autres=SEUIL_AUTRES, max_autres=MAX_AUTRES, cote_min=COTE_MIN):
    """PRONOSTIC PRINCIPAL (plus fort score du modèle ; la cote ne choisit pas) + rubrique AUTRES (pronostics aussi acceptables :
    score >= seuil_autres, cote >= cote_min, marché différent du principal et des autres déjà listés ; deux marchés qui gagnent
    exactement sur les mêmes scores sont fusionnés, ex. Handicap +0.5 domicile = Double chance 1X). None si une estimation manque."""
    if lam_force is None or lam_simple is None:
        return None
    liste = []
    for x in cands:
        if x["cote"] < cote_min - 1e-9:
            continue
        pm = (proba_marche(x["pred"], *lam_force) + proba_marche(x["pred"], *lam_simple)) / 2
        p, nom = zone_fiabilite(x["cote"])
        liste.append(dict(x, p_modele=pm, p_honnete=p, niveau=nom, sig=_signature(x["pred"])))
    if not liste:
        return None
    liste.sort(key=lambda d: (-round(d["p_modele"], 9), d["cote"]))
    principal = liste[0]
    vus = {principal["sig"]}
    autres = []
    for d in liste[1:]:
        if d["p_modele"] < seuil_autres - 1e-9 or d["sig"] in vus:
            continue
        vus.add(d["sig"])
        autres.append(d)
        if len(autres) >= max_autres:
            break
    return {"principal": principal, "autres": autres}


def alerte_contexte(marche, ep, er):
    """Alertes d'information (jamais un filtre) : le côté parié (1X2 / double chance) est très défavorisé aux points ou au rang."""
    c = cote_cote(marche)
    out = []
    if c != 0 and ep is not None and c * ep <= VETO_POINTS + 1e-9:
        out.append("côté parié très défavorisé aux points")
    if c != 0 and er is not None and c * er <= VETO_RANG + 1e-9:
        out.append("côté parié très mal classé")
    return out
