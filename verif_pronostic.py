"""Verification d'un pronostic par les resultats REELS des deux equipes (methode « logigramme »), simple et lisible.

Pour un pari sur A (domicile) - B (exterieur) :
  1. cote du pari >= config/verif_pronostic.json (1,26, regle de l'utilisateur) et au moins 4 matchs de la saison de chaque cote, AU MEME LIEU (A a domicile, B a l'exterieur) : moins de 4 -> rejete ;
  2. on prend les matchs de A A DOMICILE et ceux de B A L'EXTERIEUR, cette saison, avant le match ;
  3. on compte combien de fois le pari serait passe dans chacun : si c'est plus souvent passe que rate des DEUX cotes -> TIENT ; d'un seul cote -> TIENT AVEC RESERVE ; sinon NE TIENT PAS ;
  4. buts attendus de chaque equipe = moyenne de ce que son attaque marque et de ce que la defense adverse encaisse (avantage du terrain du championnat remis) ;
     meme calcul avec le xG de toute la saison, compare a la moyenne du championnat ;
  5. si l'attaque contre la defense confirme (buts et xG) alors que les frequences disent non, le verdict remonte d'un cran ; si le xG contredit, il baisse d'un cran ;
  6. verdicts geles AVANT le coup d'envoi (journal infalsifiable) puis bilan chaque soir sur les resultats reels.
Aucune constante inventee : la cote minimale vient de l'utilisateur, les moyennes viennent des matchs du championnat.
Commandes : geler | bilan | page | coupon <fichier.json> [jour] | analyse <domicile> <exterieur> [jour]
"""
import datetime, glob, gzip, json, math, os, sys
import numpy as np

RACINE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(RACINE, "config", "verif_pronostic.json")
DOSSIER = os.path.join(RACINE, "data", "verif_pronostics")
FLUX = os.path.join(RACINE, "data", "archive_test")
Z95 = 1.96
CAP = 10             # buts au-dela de CAP : sans effet sur aucun marche (seuils <= 5,5)
NMIN = 4                           # regle de l'utilisateur (07/11) : au moins 4 matchs au meme lieu pour chaque equipe, sinon pari rejete ; sert aussi de minimum pour lire le xG

# ---------------------------------------------------------------- catalogue des marches (condition sur le score home/away)
def _catalogue():
    C = {}
    r1 = {"1": lambda h, a: h > a, "N": lambda h, a: h == a, "2": lambda h, a: h < a}
    dc = {"1N": lambda h, a: h >= a, "N2": lambda h, a: h <= a, "12": lambda h, a: h != a}
    base = {**r1, **dc}
    for k, f in base.items(): C[k] = f
    for L in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5):
        C[f"total_plus_{L}"] = (lambda L: lambda h, a: h + a > L)(L); C[f"total_moins_{L}"] = (lambda L: lambda h, a: h + a < L)(L)
    C["btts_oui"] = lambda h, a: h > 0 and a > 0; C["btts_non"] = lambda h, a: not (h > 0 and a > 0)
    for L in (0.5, 1.5, 2.5):
        C[f"dom_plus_{L}"] = (lambda L: lambda h, a: h > L)(L); C[f"dom_moins_{L}"] = (lambda L: lambda h, a: h < L)(L)
        C[f"ext_plus_{L}"] = (lambda L: lambda h, a: a > L)(L); C[f"ext_moins_{L}"] = (lambda L: lambda h, a: a < L)(L)
    C["cage_dom_oui"] = lambda h, a: a == 0; C["cage_dom_non"] = lambda h, a: a > 0
    C["cage_ext_oui"] = lambda h, a: h == 0; C["cage_ext_non"] = lambda h, a: h > 0
    for k, f in base.items():
        for L in (1.5, 2.5, 3.5, 4.5):
            C[f"{k}&total_plus_{L}"] = (lambda f, L: lambda h, a: f(h, a) and h + a > L)(f, L)
            C[f"{k}&total_moins_{L}"] = (lambda f, L: lambda h, a: f(h, a) and h + a < L)(f, L)
        C[f"{k}&btts_oui"] = (lambda f: lambda h, a: f(h, a) and h > 0 and a > 0)(f)
        C[f"{k}&btts_non"] = (lambda f: lambda h, a: f(h, a) and not (h > 0 and a > 0))(f)
    return C

CATALOGUE = _catalogue()
NOMS = sorted(CATALOGUE)
IDX = {n: i for i, n in enumerate(NOMS)}
TABLE = np.array([[[CATALOGUE[n](h, a) for n in NOMS] for a in range(CAP + 1)] for h in range(CAP + 1)], dtype=np.float32)   # (h, a, marche)

def cotes_betpawa(c):
    """Cotes du flux Betpawa -> {nom de marche du catalogue: cote}."""
    out = {}
    if not c: return out
    def put(n, v):
        if n in CATALOGUE and isinstance(v, (int, float)) and v > 1: out[n] = float(v)
    for k, v in (c.get("1x2") or {}).items(): put(k, v)
    for k, v in (c.get("double_chance") or {}).items(): put(k, v)
    for L in ("0.5", "1.5", "2.5", "3.5", "4.5", "5.5"):
        for s, v in (c.get(f"over_under_{L}") or {}).items(): put(f"total_{'plus' if s == 'plus' else 'moins'}_{L}", v)
    for s, v in (c.get("btts") or {}).items(): put("btts_oui" if s.lower() == "oui" else "btts_non", v)
    for L in ("0.5", "1.5", "2.5"):
        for p, cle in (("dom", "domicile"), ("ext", "exterieur")):
            for s, v in (c.get(f"over_under_{cle}_{L}") or {}).items(): put(f"{p}_{'plus' if s == 'plus' else 'moins'}_{L}", v)
    for p, cle in (("dom", "domicile"), ("ext", "exterieur")):
        for s, v in (c.get(f"cages_inviolees_{cle}") or {}).items(): put(f"cage_{p}_{'oui' if s == 'oui' else 'non'}", v)
    for L in ("1.5", "2.5", "3.5", "4.5"):
        for k, v in (c.get(f"dc_total_{L}") or {}).items():
            if v and "|" in k: g, s = k.split("|"); put(f"{g}&total_{s}_{L}", v)
        for k, v in (c.get(f"1x2_total_{L}") or {}).items():
            if v and "|" in k: g, s = k.split("|"); put(f"{g}&total_{s}_{L}", v)
    for typ in ("dc_btts", "1x2_btts"):
        for k, v in (c.get(typ) or {}).items():
            if v and "|" in k: g, s = k.split("|"); put(f"{g}&btts_{'oui' if s.lower() == 'oui' else 'non'}", v)
    return out

def libelle(n, dom, ext):
    """Libelle lisible d'un marche du catalogue."""
    def v(x):
        return {"1": f"{dom} gagne", "N": "Match nul", "2": f"{ext} gagne", "1N": f"{dom} ou nul", "N2": f"{ext} ou nul", "12": "Pas de match nul"}[x]
    def L(x): return x.replace(".", ",")
    if "&" in n:
        g, r = n.split("&", 1); return v(g) + " et " + libelle(r, dom, ext)
    if n in ("1", "N", "2", "1N", "N2", "12"): return v(n)
    p = n.split("_")
    if p[0] == "total": return ("Plus de " if p[1] == "plus" else "Moins de ") + L(p[2]) + " buts"
    if p[0] == "btts": return "Les deux équipes marquent : " + ("oui" if p[1] == "oui" else "non")
    if p[0] in ("dom", "ext"): return (dom if p[0] == "dom" else ext) + (" marque plus de " if p[1] == "plus" else " marque moins de ") + L(p[2]) + " buts"
    if p[0] == "cage": return ("Cage inviolée " + (dom if p[1] == "dom" else ext) + ": ") + p[2]
    return n

def config():
    return json.load(open(CONFIG, encoding="utf-8"))

# ---------------------------------------------------------------- statistiques
def wilson(k, n, z=Z95):
    if n <= 0: return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)

# ---------------------------------------------------------------- echantillons d'un match a venir
def trouver(nom_dom, nom_ext, jours=None):
    """Retrouve un match du flux commun par fragments de noms. -> dict du flux (le plus recent fichier qui le porte)."""
    res = None
    for f in sorted(glob.glob(os.path.join(FLUX, "*.json.gz"))):
        if jours and os.path.basename(f)[:10] not in jours: continue
        for x in json.load(gzip.open(f)).values():
            if nom_dom.lower() in (x.get("domicile") or "").lower() and nom_ext.lower() in (x.get("exterieur") or "").lower(): res = x
    return res

# ---------------------------------------------------------------- constat simple (buts reels + xG du championnat), sans calibration
def _moy(L):
    L = [v for v in L if v is not None]
    return (sum(L) / len(L), len(L)) if L else (None, 0)

def _attendus(A, B, cle_a, cle_b):
    """Buts attendus de A et de B : moyenne de ce que l'attaque de l'un marque et de ce que la defense de l'autre concede (memes champs pour buts et xG)."""
    p = lambda u, w: None if u is None or w is None else (u + w) / 2
    return p(A[cle_a[0]], B[cle_b[1]]), p(B[cle_b[0]], A[cle_a[1]])

def _ligne(valeur, X, sens):
    """Ligne de buts X.5 : True si la valeur attendue passe franchement (il faut un nombre entier de buts), False si elle est du mauvais cote de la ligne, 'limite' entre les deux."""
    if sens == "plus": return True if valeur >= X + 0.5 else False if valeur < X else "limite"
    return True if valeur <= X - 0.5 else False if valeur > X else "limite"

def _lecture(marche, la, lb, avantage=0.0):
    """Le marche est-il confirme par les buts attendus (la = domicile, lb = exterieur) ? True / False / 'limite' (juste sous ou juste sur la ligne) / None (non lisible). Chaque element du marche est lu a part."""
    if la is None or lb is None: return None
    la, lb = la + avantage / 2, lb - avantage / 2     # xG de toute la saison = domicile et exterieur melanges : on remet l'avantage du terrain du championnat (total inchange)
    reps = []
    for el in marche.split("&"):
        if el in ("1", "2"): reps.append(la > lb if el == "1" else lb > la)
        elif el == "1N": reps.append(la >= lb)
        elif el == "N2": reps.append(lb >= la)
        elif el.startswith("total_"): _, sens, X = el.split("_"); reps.append(_ligne(la + lb, float(X), sens))
        elif el.startswith(("dom_", "ext_")): q, sens, X = el.split("_"); reps.append(_ligne(la if q == "dom" else lb, float(X), sens))
        elif el == "btts_oui": reps.append(min(la, lb) >= 1.0)
        elif el == "btts_non": reps.append(min(la, lb) < 1.0)
        elif el in ("cage_dom_oui", "cage_ext_oui"): reps.append((lb if el == "cage_dom_oui" else la) < 0.5)
        elif el in ("cage_dom_non", "cage_ext_non"): reps.append((lb if el == "cage_dom_non" else la) >= 0.5)
        else: return None
    if any(r is False for r in reps): return False
    return "limite" if any(r == "limite" for r in reps) else True

def de_la_saison(m, saison):
    """Match de la saison en cours : etiquete comme tel (Football-Data) ou sans etiquette (Matchendirect : le flux ne garde que la saison en cours pour ces championnats)."""
    return m.get("saison") == saison or (m.get("saison") is None and m.get("source") == "matchendirect")

_CHAMP = {}
_MODELE = {}
def modele_xg():
    """xG des equipes SANS xG : on apprend sur les equipes Football-Data (saison en cours, au moins NMIN matchs avec xG) comment leur xG moyen suit leurs buts moyens
    (droite des moindres carres : xG cree = a + b x buts marques ; xG concede = a + b x buts encaisses). Football-Data ne publie pas de formule : on copie son echelle. -> dict ou None."""
    if "m" in _MODELE: return _MODELE["m"]
    T, vus = {}, set()
    for f in sorted(glob.glob(os.path.join(FLUX, "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            saison = (x.get("assemblage") or {}).get("saison_football_data")
            for eq, nom in (("equipe_dom", x.get("domicile")), ("equipe_ext", x.get("exterieur"))):
                for m in ((x.get("assemblage") or {}).get(eq) or {}).get("matchs") or []:
                    if m.get("source") != "football-data" or m.get("saison") != saison or m.get("xg") is None or m.get("xg_concede") is None or (nom, m.get("date")) in vus: continue
                    vus.add((nom, m.get("date"))); T.setdefault(nom, []).append((m["buts_marques"], m["buts_encaisses"], m["xg"], m["xg_concede"]))
    P = np.array([np.mean(t, axis=0) for t in T.values() if len(t) >= NMIN])
    if len(P) < 10: _MODELE["m"] = None; return None
    def droite(i, j):
        b, a = np.polyfit(P[:, i], P[:, j], 1); return {"a": float(a), "b": float(b), "r": float(np.corrcoef(P[:, i], P[:, j])[0, 1])}
    _MODELE["m"] = {"cree": droite(0, 2), "concede": droite(1, 3), "equipes": int(len(P))}; return _MODELE["m"]

def xg_estime(buts, cote):
    mo = modele_xg(); return None if mo is None or buts is None else mo[cote]["a"] + mo[cote]["b"] * buts

def xg_attendus(SA, SB, champ):
    """Buts attendus de chaque equipe d'apres le xG de la saison (meme formule dans les deux cas : moyenne de ce que l'attaque cree et de ce que la defense adverse concede).
    xG reel si les deux equipes en ont (NMIN matchs) ; sinon xG ESTIME par la droite apprise sur Football-Data a partir des buts de la saison (Matchendirect). -> (domicile, exterieur, source) ; source = 'xG', 'estimé' ou None."""
    if min(SA["n_xg"], SB["n_xg"]) >= NMIN: return (*_attendus(SA, SB, ("xg_cree", "xg_concede"), ("xg_cree", "xg_concede")), "xG")
    if min(SA["n"], SB["n"]) >= NMIN and None not in (SA["xg_cree"], SA["xg_concede"], SB["xg_cree"], SB["xg_concede"]): return (*_attendus(SA, SB, ("xg_cree", "xg_concede"), ("xg_cree", "xg_concede")), "estimé")
    return None, None, None

def _ajuster(verdict, lect_b, lect_x):
    """Verdict des frequences, corrige par la comparaison attaque / defense (buts attendus et xG).
    - NE TIENT PAS remonte a TIENT AVEC RÉSERVE si les buts attendus ET le xG (quand il existe) confirment : l'attaque contre la defense dit oui meme si les frequences disent non.
    - Un xG qui contredit fait baisser d'un cran ; un xG a la limite de la ligne empeche TIENT."""
    if verdict == "NE TIENT PAS" and lect_b is True and lect_x in (True, None): return "TIENT AVEC RÉSERVE"
    if lect_x is False and verdict in ("TIENT", "TIENT AVEC RÉSERVE"): return "TIENT AVEC RÉSERVE" if verdict == "TIENT" else "NE TIENT PAS"
    if lect_x == "limite" and verdict == "TIENT": return "TIENT AVEC RÉSERVE"
    return verdict

def moyenne_championnat(competition, saison):
    """Moyenne du championnat (par equipe et par match, saison en cours) : buts marques et xG, lue sur tous les matchs des equipes de ce championnat dans le flux."""
    if (competition, saison) in _CHAMP: return _CHAMP[(competition, saison)]
    B, X, BD, BE, vus = [], [], [], [], set()
    for f in sorted(glob.glob(os.path.join(FLUX, "*.json.gz"))):
        for y in json.load(gzip.open(f)).values():
            if y.get("competition") != competition: continue
            for eq, nom in (("equipe_dom", y.get("domicile")), ("equipe_ext", y.get("exterieur"))):
                for m in ((y.get("assemblage") or {}).get(eq) or {}).get("matchs") or []:
                    cle = (nom, m.get("date"))
                    if cle in vus or not de_la_saison(m, saison) or m.get("buts_marques") is None: continue
                    vus.add(cle); B.append(m["buts_marques"]); (BD if m.get("domicile") else BE).append(m["buts_marques"])
                    if m.get("xg") is not None: X.append(m["xg"])
    mo = lambda L: sum(L) / len(L) if L else None
    r = {"buts": mo(B), "buts_dom": mo(BD), "buts_ext": mo(BE), "avantage_dom": (mo(BD) - mo(BE)) if BD and BE else 0.0, "n": len(B), "xg": (sum(X) / len(X)) if X else None, "n_xg": len(X)}
    r["xg_est"] = (r["xg"] is None and r["buts"] is not None and xg_estime(r["buts"], "cree") is not None); r["xg"] = r["xg"] if r["xg"] is not None else (xg_estime(r["buts"], "cree") if r["buts"] is not None else None)
    _CHAMP[(competition, saison)] = r; return r

def saison_complete(x, eq):
    """Toute la saison en cours (domicile et exterieur), avant le match : moyennes buts et xG, comme dans la comparaison avec les xG du championnat."""
    a = x.get("assemblage") or {}; saison = a.get("saison_football_data")
    M = [m for m in (a.get(eq) or {}).get("matchs") or [] if m.get("date") and m["date"] < x["date"] and de_la_saison(m, saison) and m.get("buts_marques") is not None]
    g = lambda c: _moy([m.get(c) for m in M])
    (bm, n), (be, _), (xc, nx), (xd, _) = g("buts_marques"), g("buts_encaisses"), g("xg"), g("xg_concede")
    est = nx < NMIN and n >= NMIN
    if est: xc, xd = xg_estime(bm, "cree"), xg_estime(be, "concede")
    return {"n": n, "buts_marques": bm, "buts_encaisses": be, "xg_cree": xc, "xg_concede": xd, "n_xg": nx, "xg_est": bool(est and xc is not None),
            "ecart_xg": None if xc is None or xd is None else xc - xd, "surperformance": None if est or xc is None or bm is None else bm - xc}

def constat(x, marche, cote=None, cfg=None):
    """Constat lisible : ce que chaque equipe a fait dans le role du match (A a domicile, B a l'exterieur), saison en cours, avant le match.
    Pour chaque equipe : buts marques / encaisses et xG cree / concede (moyennes), et combien de fois le pari serait passe.
    Regle : le pari tient si, des deux cotes, il serait passe plus souvent que rate ; reserve si d'un seul cote ; ne tient pas sinon.
    Le xG signale une tendance cachee : xG cree > buts marques = attaque qui peut mieux faire ; xG concede > buts encaisses = defense chanceuse."""
    cfg = cfg or config(); a = x.get("assemblage") or {}; saison = a.get("saison_football_data"); jour = x["date"]
    if cote is not None and cote < cfg["cote_min"]: return {"verdict": "REFUSÉ", "phrase": f"Cote {cote} sous le minimum {cfg['cote_min']}."}
    def pris(eq, dom):
        M = [m for m in (a.get(eq) or {}).get("matchs") or [] if m.get("domicile") is dom and m.get("date") and m["date"] < jour and m.get("buts_marques") is not None and m.get("buts_encaisses") is not None]
        S = [m for m in M if m.get("saison") == saison] if saison else M
        return S if S or not saison else M
    k = IDX[marche]; res = {}
    for cle, eq, dom in (("A", "equipe_dom", True), ("B", "equipe_ext", False)):
        M = pris(eq, dom); n = len(M)
        # orientation (home, away) : pour B a l'exterieur, home = son adversaire
        sc = [(m["buts_marques"], m["buts_encaisses"]) if dom else (m["buts_encaisses"], m["buts_marques"]) for m in M]
        ok_ = sum(1 for h, aw in sc if TABLE[min(h, CAP), min(aw, CAP), k])
        gm, _ = _moy([m["buts_marques"] for m in M]); ge, _ = _moy([m["buts_encaisses"] for m in M])
        xm, nx = _moy([m.get("xg") for m in M]); xe, _ = _moy([m.get("xg_concede") for m in M])
        res[cle] = {"n": n, "reussi": ok_, "buts_marques": gm, "buts_encaisses": ge, "xg_cree": xm, "xg_concede": xe, "n_xg": nx}
    A, B = res["A"], res["B"]
    d_, e_ = x["domicile"], x["exterieur"]
    if A["n"] < NMIN or B["n"] < NMIN: return {"verdict": "NON ÉVALUABLE", "phrase": f"Rejeté : moins de {NMIN} matchs au même lieu ({d_} à domicile {A['n']}, {e_} à l'extérieur {B['n']}).", "A": A, "B": B}
    pa, pb = A["reussi"] / A["n"] > 0.5, B["reussi"] / B["n"] > 0.5
    verdict = "TIENT" if pa and pb else "TIENT AVEC RÉSERVE" if pa or pb else "NE TIENT PAS"
    f = lambda v: "?" if v is None else f"{v:.1f}"
    def tendance(e, nom):
        t = []
        if e["n_xg"] >= NMIN:
            if e["xg_cree"] is not None and e["buts_marques"] is not None and e["xg_cree"] - e["buts_marques"] >= 0.3: t.append(f"{nom} crée plus qu'il ne marque (xG {f(e['xg_cree'])} pour {f(e['buts_marques'])} buts)")
            if e["xg_concede"] is not None and e["buts_encaisses"] is not None and e["xg_concede"] - e["buts_encaisses"] >= 0.3: t.append(f"défense de {nom} chanceuse (xG concédé {f(e['xg_concede'])} pour {f(e['buts_encaisses'])} encaissés)")
        return t
    tend = tendance(A, x["domicile"]) + tendance(B, x["exterieur"])
    bm = _attendus(A, B, ("buts_marques", "buts_encaisses"), ("buts_marques", "buts_encaisses")); lect_b = None
    SA, SB = saison_complete(x, "equipe_dom"), saison_complete(x, "equipe_ext")   # xG sur toute la saison : l'echantillon domicile/exterieur seul est trop petit
    champ = moyenne_championnat(x.get("competition"), a.get("saison_football_data")); xa = xg_attendus(SA, SB, champ)[:2]; src = xg_attendus(SA, SB, champ)[2]
    lect_x = _lecture(marche, *xa, champ["avantage_dom"]); lect_b = _lecture(marche, *bm, champ["avantage_dom"])
    ordre = ["NE TIENT PAS", "TIENT AVEC RÉSERVE", "TIENT"]
    verdict = _ajuster(verdict, lect_b, lect_x)
    nom_xg = "xG estimé" if src == "estimé" else "xG"
    lecture_xg = {None: "xG indisponible (trop peu de matchs)" if xa[0] is None else f"pari non lisible avec le {nom_xg}", True: f"le {nom_xg} confirme", False: f"le {nom_xg} contredit", "limite": f"le {nom_xg} est à la limite de la ligne"}[lect_x]
    phrase = (f"{x['domicile']} à domicile : {f(A['buts_marques'])} buts marqués, {f(A['buts_encaisses'])} encaissés (xG {f(A['xg_cree'])}/{f(A['xg_concede'])}), pari passé {A['reussi']} fois sur {A['n']}. "
              f"{x['exterieur']} à l'extérieur : {f(B['buts_marques'])} marqués, {f(B['buts_encaisses'])} encaissés (xG {f(B['xg_cree'])}/{f(B['xg_concede'])}), pari passé {B['reussi']} fois sur {B['n']}.")
    ch = lambda e: ("?" if e["xg_cree"] is None else f"xG {e['xg_cree']:.2f} créés / {e['xg_concede']:.2f} concédés (écart {e['ecart_xg']:+.2f}), buts {f(e['buts_marques'])} / {f(e['buts_encaisses'])}")
    phrase += f" Saison entière (xG) : {x['domicile']} {ch(SA)} ; {x['exterieur']} {ch(SB)}. Moyenne du championnat : {f(champ['buts'])} but par équipe et par match."
    return {"verdict": verdict, "force": (A["reussi"] / A["n"] + B["reussi"] / B["n"]) / 2, "libelle": libelle(marche, x["domicile"], x["exterieur"]), "cote": cote, "phrase": phrase, "tendances_xg": tend, "buts_attendus": bm, "xg_attendus": xa, "xg_source": src, "lecture_xg": lecture_xg, "saison_A": SA, "saison_B": SB, "championnat": champ, "A": A, "B": B}


# ---------------------------------------------------------------- journal gele (verdicts figes AVANT le coup d'envoi) et bilan sur resultats reels
JOURNAL = os.path.join(DOSSIER, "journal.jsonl"); BILAN = os.path.join(DOSSIER, "bilan.json")
import hashlib

def _empreinte(prec, rec):
    return hashlib.sha256((prec + json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()

def lire_journal(chemin=JOURNAL):
    return [json.loads(l) for l in open(chemin, encoding="utf-8") if l.strip()] if os.path.exists(chemin) else []

def verifier_journal(chemin=JOURNAL):
    """Chaine d'empreintes intacte ET chaque ligne gelee avant son coup d'envoi. -> liste d'anomalies (vide = intact)."""
    anom, prec = [], ""
    for i, r in enumerate(lire_journal(chemin)):
        e = r.get("empreinte"); corps = {k: v for k, v in r.items() if k != "empreinte"}
        if e != _empreinte(prec, corps): anom.append((i, r.get("match_id"), "empreinte"))
        if not r.get("coup_d_envoi_utc") or not r["gele_le"] < r["coup_d_envoi_utc"]: anom.append((i, r.get("match_id"), "gele apres le coup d envoi"))
        prec = e or ""
    return anom

def matchs_a_venir(jour_min, maintenant, flux=FLUX):
    """Matchs du flux commun sans score, coup d'envoi futur, avec cotes Betpawa. -> dict du flux."""
    res = {}
    for f in sorted(glob.glob(os.path.join(flux, "*.json.gz"))):
        if os.path.basename(f)[:10] < jour_min: continue
        for x in json.load(gzip.open(f)).values():
            if (x.get("score") or {}).get("buts_dom") is not None: continue
            if not x.get("coup_d_envoi_utc") or x["coup_d_envoi_utc"] <= maintenant or not x.get("cotes_betpawa"): continue
            res[x["match_id"]] = x
    return list(res.values())

ORDRE = ["TIENT", "TIENT AVEC RÉSERVE", "NE TIENT PAS", "NON ÉVALUABLE", "REFUSÉ"]

def choix_a_geler(x, cfg, n=2):
    """Pour un match : les n paris qui tiennent le mieux ET les n qui tiennent le moins bien, parmi les marches Betpawa a cote >= minimum (pour que le bilan puisse comparer les deux)."""
    E = []
    for m, c in cotes_betpawa(x["cotes_betpawa"]).items():
        r = constat(x, m, c, cfg)
        if r["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE", "NE TIENT PAS"): E.append((ORDRE.index(r["verdict"]), -r["force"], m, c, r["verdict"]))
    E.sort(); haut, bas = E[:n], [e for e in E[-n:] if e not in E[:n]]
    return [{"marche": e[2], "cote": e[3], "verdict": e[4], "force": round(-e[1], 4)} for e in haut + bas]

def geler(jour=None, maintenant=None, chemin=JOURNAL, flux=FLUX, cfg=None):
    """Ajoute au journal (jamais reecrit) les verdicts des matchs a venir, avant leur coup d'envoi. -> nb de lignes ajoutees."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); jour = jour or maintenant[:10]
    cfg = cfg or config(); os.makedirs(os.path.dirname(chemin), exist_ok=True)
    ex = lire_journal(chemin); deja = {(r["match_id"], r["marche"]) for r in ex}; prec = ex[-1]["empreinte"] if ex else ""; n = 0
    with open(chemin, "a", encoding="utf-8") as f:
        for x in matchs_a_venir(jour, maintenant, flux):
            for e in choix_a_geler(x, cfg):
                if (x["match_id"], e["marche"]) in deja: continue
                rec = {"match_id": x["match_id"], "date": x["date"], "coup_d_envoi_utc": x["coup_d_envoi_utc"], "gele_le": maintenant, **e}
                prec = _empreinte(prec, rec); f.write(json.dumps({**rec, "empreinte": prec}, ensure_ascii=False, separators=(",", ":")) + "\n"); n += 1
    return n

def bilan(chemin=JOURNAL, flux=FLUX):
    """Taux de reussite REEL par verdict (matchs termines du journal gele). Refuse si le journal est altere."""
    anom = verifier_journal(chemin)
    if anom: raise RuntimeError(f"journal gele non intact : {anom[:3]}")
    import p1_page_donnees as pd
    S = pd.scores(flux); par = {}
    for r in lire_journal(chemin):
        sc = S.get(r["match_id"])
        if sc is None: continue
        y = bool(TABLE[min(sc["buts_dom"], CAP), min(sc["buts_ext"], CAP), IDX[r["marche"]]]); g = par.setdefault(r["verdict"], {"n": 0, "reussis": 0}); g["n"] += 1; g["reussis"] += y
    out = {}
    for v, g in par.items():
        lo, hi = wilson(g["reussis"], g["n"]); out[v] = {"paris": g["n"], "reussis": g["reussis"], "taux_reel": g["reussis"] / g["n"], "borne_basse": lo, "borne_haute": hi}
    return {"description": "Taux de reussite reel par verdict, sur les paris gelés avant le coup d'envoi (matchs termines).", "derniere_empreinte": (lire_journal(chemin) or [{}])[-1].get("empreinte"), "par_verdict": out}

def ecrire_bilan(b=None, chemin=BILAN):
    b = b or bilan(); os.makedirs(os.path.dirname(chemin), exist_ok=True); json.dump(b, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True); return b

def evaluer_coupon(picks, jour=None):
    """picks : [{'dom': 'Galatasaray', 'ext': 'Amed', 'marche': '1', 'cote': 1.41}] -> constats classes du plus tenace au moins tenace."""
    cfg = config(); out = []
    for p in picks:
        x = trouver(p["dom"], p["ext"], [jour] if jour else None)
        if not x: out.append({**p, "verdict": "NON ÉVALUABLE", "phrase": "Match absent du flux commun : échantillons à fournir à la main.", "force": 0}); continue
        r = constat(x, p["marche"], p.get("cote"), cfg); out.append({**p, **r, "heure": x.get("heure_cameroun"), "repli": repli_combo(x, p["marche"], p.get("cote"), cfg)})
    out.sort(key=lambda e: (ORDRE.index(e["verdict"]), -(e.get("force") or 0))); return out

def alternatives(x, cfg=None, exclure=None, n=3):
    """Autres paris du meme match qui tiennent (TIENT puis TIENT AVEC RÉSERVE), cote >= minimum, classes du plus au moins tenace."""
    cfg = cfg or config(); R = []
    for m, c in cotes_betpawa(x.get("cotes_betpawa") or {}).items():
        if m == exclure: continue
        r = constat(x, m, c, cfg)
        if r["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE"): R.append({"marche": m, **r})
    R.sort(key=lambda e: (ORDRE.index(e["verdict"]), -e["force"])); return R[:n]

def analyse(x, cfg=None):
    """Presentation complete d'UN match, comme dans nos echanges : tableau des equipes (xG, buts, ecart, moyenne du championnat), tous les paris Betpawa qui passent les filtres
    (cote >= minimum, assez de matchs, TIENT ou TIENT AVEC RÉSERVE) du plus fiable au moins fiable, constats, classement. -> texte (Markdown)."""
    cfg = cfg or config(); d, e = x["domicile"], x["exterieur"]; SA, SB = saison_complete(x, "equipe_dom"), saison_complete(x, "equipe_ext")
    champ = moyenne_championnat(x.get("competition"), (x.get("assemblage") or {}).get("saison_football_data"))
    est = lambda S, k: ("non disponible" if S[k] is None else ("≈ " if S["xg_est"] else "") + f"{S[k]:.2f}".replace(".", ","))
    f = lambda u, k=2: "non disponible" if u is None else f"{u:.{k}f}".replace(".", ","); sg = lambda u: "non disponible" if u is None else f"{u:+.2f}".replace(".", ",")
    L = [f"**{d} – {e}** ({x.get('competition', '')}, {x.get('heure_cameroun', '')} heure du Cameroun). Saison entière, sans séparer domicile et extérieur : {SA['n']} matchs pour {d}, {SB['n']} pour {e}.", "",
         f"| | {d} | {e} | Moyenne du championnat |", "|---|---|---|---|",
         f"| xG créés par match | {est(SA, 'xg_cree')} | {est(SB, 'xg_cree')} | {f(champ['xg'])}{' ≈' if champ['xg_est'] else ''} |", f"| xG concédés par match | {est(SA, 'xg_concede')} | {est(SB, 'xg_concede')} | non indiqué |",
         f"| Buts marqués par match | {f(SA['buts_marques'], 1)} | {f(SB['buts_marques'], 1)} | {f(champ['buts'], 1)} |", f"| Buts encaissés par match | {f(SA['buts_encaisses'], 1)} | {f(SB['buts_encaisses'], 1)} | {f(champ['buts'], 1)} |",
         f"| Écart xG (créés moins concédés) | **{'≈ ' if SA['xg_est'] else ''}{sg(SA['ecart_xg'])}** | **{'≈ ' if SB['xg_est'] else ''}{sg(SB['ecart_xg'])}** | |", ""]
    xa = xg_attendus(SA, SB, champ); mo = modele_xg()
    if "estimé" in (xa[2], ) or SA["xg_est"] or SB["xg_est"] or champ["xg_est"]:
        L += ["≈ = xG estimé (le xG manque) : formule apprise sur " + (f"{mo['equipes']} équipes Football-Data (xG créé = {f(mo['cree']['a'])} + {f(mo['cree']['b'])} × buts marqués ; xG concédé = {f(mo['concede']['a'])} + {f(mo['concede']['b'])} × buts encaissés)" if mo else "les équipes Football-Data") + ", appliquée aux buts de la saison (Matchendirect).", ""]
    R = []
    for m, c in cotes_betpawa(x.get("cotes_betpawa") or {}).items():
        r = constat(x, m, c, cfg)
        if r["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE"): R.append({"marche": m, **r})
    R.sort(key=lambda r: (ORDRE.index(r["verdict"]), -r["force"]))
    L += ["**Tous les paris qui passent les filtres, du plus fiable au moins fiable**", "", "| # | Pari | Cote | Résultats | xG | Verdict |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(R, 1):
        xa = r["xg_attendus"]; av = champ["avantage_dom"]; att = "" if xa[0] is None else f" ({f(xa[0] + av / 2, 1)} – {f(xa[1] - av / 2, 1)} buts attendus, terrain compris)"; lec = r["lecture_xg"]; lec = lec[0].upper() + lec[1:]
        L.append(f"| {i} | {r['libelle']} | {str(r['cote']).replace('.', ',')} | {r['A']['reussi']} sur {r['A']['n']} et {r['B']['reussi']} sur {r['B']['n']} | {lec}{att} | **{r['verdict'].capitalize()}** |")
    if not R: L.append("| | Aucun pari ne passe les filtres | | | | |")
    L += ["", "**Constats**"]
    for nom, S in ((d, SA), (e, SB)):
        if S["surperformance"] is not None: L.append(f"- **{nom}** marque {f(S['buts_marques'], 1)} buts par match pour {f(S['xg_cree'])} xG, soit {f(abs(S['surperformance']), 2)} de {'plus' if S['surperformance'] >= 0 else 'moins'} qu'attendu ; il encaisse {f(S['buts_encaisses'], 1)} pour {f(S['xg_concede'])} xG concédé.")
    L += ["", f"Le xG vient de la saison en cours ; cote minimale {str(cfg['cote_min']).replace('.', ',')}."]
    return "\n".join(L)

COMBOS = ("1N&total_plus_", "1N&total_moins_", "N2&total_plus_", "N2&total_moins_", "12&total_plus_", "12&total_moins_")

def repli_combo(x, marche, cote, cfg=None, n=3):
    """Regle de l'utilisateur (07/11) : un pari sous la cote minimale mais TRES SOLIDE (verdict TIENT sans tenir compte de la cote) est remplace par ses combos
    double chance + plus de buts / double chance + moins de buts, retenus seulement s'ils passent tous les filtres (cote >= minimum, verdict TIENT). -> liste, du plus au moins fiable."""
    cfg = cfg or config()
    if cote is None or cote >= cfg["cote_min"]: return []
    base = constat(x, marche, None, cfg)
    if base["verdict"] != "TIENT": return []
    R = []
    for m, c in cotes_betpawa(x.get("cotes_betpawa") or {}).items():
        if not m.startswith(COMBOS) or c < cfg["cote_min"]: continue
        r = constat(x, m, c, cfg)
        if r["verdict"] == "TIENT": R.append({"marche": m, **r})
    R.sort(key=lambda r: -r["force"]); return R[:n]

# ---------------------------------------------------------------- page dediee (data/verif_pronostics/page_verif.json)
PAGE = os.path.join(DOSSIER, "page_verif.json")
NB_DERNIERS = 10

def groupe(marche):
    """Famille du pari : marches de buts / marches d'equipes / combos."""
    if "&" in marche: return "combos"
    return "buts" if marche.startswith(("total_", "btts_")) else "equipes"

def derniers_matchs(x):
    """Historique des deux equipes (saison en cours, avant le match), du plus recent au plus ancien : A a domicile, A a l'exterieur, B a l'exterieur, B a domicile, face-a-face."""
    a = x.get("assemblage") or {}; saison = a.get("saison_football_data")
    def liste(eq, dom, nb=NB_DERNIERS, tous=False):
        M = [m for m in (a.get(eq) or {}).get("matchs") or [] if m.get("date") and m["date"] < x["date"] and m.get("buts_marques") is not None and m.get("buts_encaisses") is not None and (tous or (m.get("domicile") is dom and de_la_saison(m, saison)))]
        M.sort(key=lambda m: m["date"], reverse=True); return M if tous else M[:nb]
    f = lambda L: [{"date": m["date"], "adversaire": m.get("adversaire"), "marques": m["buts_marques"], "encaisses": m["buts_encaisses"]} for m in L]
    h2h = [m for m in liste("equipe_dom", None, tous=True) if m.get("adversaire") == x["exterieur"]][:NB_DERNIERS]
    return {"dom": f(liste("equipe_dom", True)), "dom_ext": f(liste("equipe_dom", False)), "ext": f(liste("equipe_ext", False)), "ext_dom": f(liste("equipe_ext", True)),
            "h2h": [{"date": m["date"], "domicile": m.get("domicile"), "marques": m["buts_marques"], "encaisses": m["buts_encaisses"]} for m in h2h]}

def fiche_match(x, maintenant, cfg):
    """Un match pour la page : tableau des equipes, xG (reel ou estime), paris qui passent les filtres classes par reussite observee decroissante dans chaque famille, historique."""
    SA, SB = saison_complete(x, "equipe_dom"), saison_complete(x, "equipe_ext"); champ = moyenne_championnat(x.get("competition"), (x.get("assemblage") or {}).get("saison_football_data"))
    xa = xg_attendus(SA, SB, champ); sc = (x.get("score") or {}); fini = sc.get("buts_dom") is not None and sc.get("buts_ext") is not None
    statut = "termine" if fini else "en_cours_ou_resultat_attendu" if (x.get("coup_d_envoi_utc") or "9") <= maintenant else "a_venir"
    G = {"buts": [], "equipes": [], "combos": []}
    for m, c in cotes_betpawa(x.get("cotes_betpawa") or {}).items():
        r = constat(x, m, c, cfg)
        if r["verdict"] not in ("TIENT", "TIENT AVEC RÉSERVE"): continue
        A, B = r["A"], r["B"]; taux = (A["reussi"] + B["reussi"]) / (A["n"] + B["n"])
        e = {"marche": m, "libelle": r["libelle"], "cote": c, "reussite_dom": [A["reussi"], A["n"]], "reussite_ext": [B["reussi"], B["n"]], "taux": round(taux, 4), "verdict": r["verdict"], "lecture_xg": r["lecture_xg"]}
        if fini: e["gagne"] = bool(TABLE[min(sc["buts_dom"], CAP), min(sc["buts_ext"], CAP), IDX[m]])
        G[groupe(m)].append(e)
    for L in G.values(): L.sort(key=lambda e: (-e["taux"], ORDRE.index(e["verdict"]), -(e["reussite_dom"][1] + e["reussite_ext"][1])))
    arr = lambda u: None if u is None else round(u, 3)
    av = champ["avantage_dom"]
    return {"match_id": x["match_id"], "date": x["date"], "coup_d_envoi_utc": x.get("coup_d_envoi_utc"), "competition": x.get("competition"), "domicile": x["domicile"], "exterieur": x["exterieur"], "statut": statut,
            "resultat": {"buts_dom": sc["buts_dom"], "buts_ext": sc["buts_ext"]} if fini else None,
            "xg_source": xa[2], "buts_attendus": None if xa[0] is None else [arr(xa[0] + av / 2), arr(xa[1] - av / 2)],
            "equipes": {"dom": {k: arr(SA[k]) if isinstance(SA[k], float) else SA[k] for k in ("n", "buts_marques", "buts_encaisses", "xg_cree", "xg_concede", "ecart_xg", "surperformance", "n_xg", "xg_est")},
                        "ext": {k: arr(SB[k]) if isinstance(SB[k], float) else SB[k] for k in ("n", "buts_marques", "buts_encaisses", "xg_cree", "xg_concede", "ecart_xg", "surperformance", "n_xg", "xg_est")},
                        "championnat": {"buts": arr(champ["buts"]), "xg": arr(champ["xg"]), "xg_est": champ["xg_est"], "avantage_dom": arr(av), "matchs": champ["n"]}},
            "paris": G, "derniers_matchs": derniers_matchs(x)}

def page_donnees(jours_passes=0, maintenant=None, flux=FLUX, cfg=None):
    """Toutes les fiches (matchs a partir de J - jours_passes, avec cotes et au moins un pari qui passe les filtres). Deterministe, aucune valeur inventee."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); cfg = cfg or config()
    depuis = (datetime.date.fromisoformat(maintenant[:10]) - datetime.timedelta(days=jours_passes)).isoformat(); M = []
    for f in sorted(glob.glob(os.path.join(flux, "*.json.gz"))):
        if os.path.basename(f)[:10] < depuis: continue
        for x in json.load(gzip.open(f)).values():
            if not x.get("cotes_betpawa"): continue
            fm = fiche_match(x, maintenant, cfg)
            if any(fm["paris"].values()): M.append(fm)
    M.sort(key=lambda m: (m["coup_d_envoi_utc"] or "", m["domicile"]))
    try: b = bilan()
    except RuntimeError as err: b = {"erreur": str(err), "par_verdict": {}}
    return {"genere_le": maintenant, "cote_min": cfg["cote_min"], "minimum_matchs_meme_lieu": NMIN, "modele_xg": modele_xg(), "bilan": b.get("par_verdict", {}), "nb_matchs": len(M), "matchs": M}

def ecrire_page(d=None, chemin=PAGE):
    d = d or page_donnees(); os.makedirs(os.path.dirname(chemin), exist_ok=True)
    json.dump(d, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":")); return d

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "geler":
        print(json.dumps({"lignes_ajoutees": geler(), "anomalies": verifier_journal()}, ensure_ascii=False))
    elif cmd == "bilan":
        b = ecrire_bilan(); print(json.dumps({k: {x: round(y, 3) if isinstance(y, float) else y for x, y in v.items()} for k, v in b["par_verdict"].items()}, ensure_ascii=False))
    elif cmd == "page":
        d = ecrire_page(); print(json.dumps({"matchs": d["nb_matchs"], "octets": os.path.getsize(PAGE)}, ensure_ascii=False))
    elif cmd == "analyse":
        x = trouver(sys.argv[2], sys.argv[3], [sys.argv[4]] if len(sys.argv) > 4 else None); print(analyse(x) if x else "Match absent du flux commun.")
    elif cmd == "coupon":
        for e in evaluer_coupon(json.load(open(sys.argv[2], encoding="utf-8")), sys.argv[3] if len(sys.argv) > 3 else None):
            print(f"{e['verdict']} | {e.get('libelle', e.get('marche'))} {e.get('cote')} | {e['phrase']}")
            for r in e.get("repli") or []: print(f"   RETENU (repli combo) : {r['libelle']} {r['cote']} | {r['verdict']}")
    else: print(__doc__)
