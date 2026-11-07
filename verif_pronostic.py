"""Verification d'un pronostic par les resultats REELS des deux equipes (methode « logigramme »).
Pour un pari donne sur A (domicile) - B (exterieur) :
  1. garde-fous : cote >= config/verif_pronostic.json (regle de l'utilisateur), assez de matchs de la saison des deux cotes ;
  2. collecte : matchs de A A DOMICILE et matchs de B A L'EXTERIEUR, cette saison, strictement avant le match ;
  3. le pari est une condition sur le score (home, away) : on compte combien de fois elle s'est produite dans chaque echantillon (kA/nA, kB/nB) ;
  4. indicateur = frequence du plus faible des deux cotes (« les deux cotes d'accord ») ou frequence groupee : choisi par marche sur les donnees ;
  5. l'indicateur est CALIBRE sur l'historique reel Football-Data (sans fuite) : taux de reussite observe dans des situations semblables (regression isotonique) ;
  6. verdict par intervalle de Wilson (95 %) du taux observe, ancre au point « plus souvent reussi que rate » (50 %) ;
  7. un marche dont l'indicateur n'a pas prouve son pouvoir (gain > 0 et z > 1,645 sur une saison jamais utilisee pour regler) est declare SANS SIGNAL ;
  8. marches alternatifs du meme match : memes calculs, cote >= minimum, classes par borne basse.
Aucune constante inventee : la cote minimale vient de l'utilisateur, les seuils (indicateur, nombre minimal de matchs) sont choisis sur les donnees passees, l'ancre 50 % est la definition de « plus souvent reussi que rate »."""
import datetime, glob, gzip, json, math, os, sys
import numpy as np

RACINE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(RACINE, "config", "verif_pronostic.json")
DOSSIER = os.path.join(RACINE, "data", "verif_pronostics")
CALIB = os.path.join(DOSSIER, "calibration.json")
FLUX = os.path.join(RACINE, "data", "archive_test")
Z = 1.645            # seuil unilateral a 95 % deja exige par le protocole du depot
Z95 = 1.96
CAP = 10             # buts au-dela de CAP : sans effet sur aucun marche (seuils <= 5,5)
NMIN = 3                           # plus petit echantillon par cote pour lequel un indicateur existe ; le bruit des petits echantillons est traite par le lissage ci-dessous
M_GRILLE = [0, 2, 4, 8, 16]         # lissage de la frequence vers le taux de base du marche (pseudo-matchs), choisi sur les donnees
SCORES = ["min", "pool"]
SAISON_VALID, SAISON_TEST = "2425", "2526"
SAISONS = ["2122", "2223", "2324", "2425", "2526"]

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

def pav(x, y, w):
    """Regression isotonique (croissante) ponderee. x trie croissant. -> liste de blocs [lo, hi, taux, poids]."""
    B = []
    for xi, yi, wi in zip(x, y, w):
        B.append([xi, xi, yi * wi, wi])
        while len(B) > 1 and B[-2][2] / B[-2][3] >= B[-1][2] / B[-1][3]:
            b = B.pop(); B[-1] = [B[-1][0], b[1], B[-1][2] + b[2], B[-1][3] + b[3]]
    return [[b[0], b[1], b[2] / b[3], b[3]] for b in B]

def _taux(blocs, s, base):
    """Taux calibre pour un indicateur s : bloc dont l'intervalle contient s (sinon bloc le plus proche)."""
    if not blocs: return base, 0
    for b in blocs:
        if s <= b[1]: return b[2], b[3]
    return blocs[-1][2], blocs[-1][3]

def _perte(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))

def _ajuste(s, y, _=0):
    """Blocs isotoniques d'un echantillon (indicateur s, resultat y)."""
    u = np.unique(s); ws = np.array([(s == v).sum() for v in u], dtype=float); ys = np.array([y[s == v].mean() for v in u])
    return pav(list(u), list(ys), list(ws))

def _predire_blocs(blocs, s, base):
    out = np.empty(len(s))
    hi = np.array([b[1] for b in blocs]); tx = np.array([b[2] for b in blocs])
    i = np.minimum(np.searchsorted(hi, s, side="left"), len(blocs) - 1)
    return tx[i] if len(blocs) else np.full(len(s), base)

# ---------------------------------------------------------------- calibration sur l'historique reel (Football-Data, sans fuite)
def lignes_historique(codes=None):
    """Pour chaque match historique : saison, nA, nB, kA, kB (vecteurs par marche), y (vecteur). Echantillons = matchs de la MEME saison strictement anterieurs."""
    import pouvoir_predictif as pp
    cfg = json.load(open(os.path.join(RACINE, "data", "calibration_p1", "config_calibration.json"), encoding="utf-8"))
    L = {"saison": [], "nA": [], "nB": [], "kA": [], "kB": [], "y": []}
    for code in (codes or sorted(cfg["competitions"])):
        M = pp.charger(code)
        if not M: continue
        H = {}; Aw = {}                     # (saison, equipe) -> [somme vecteur, n]
        i = 0
        while i < len(M):
            j = i
            while j < len(M) and M[j][0] == M[i][0]: j += 1      # matchs d'un meme jour : predits avant toute mise a jour
            for d, s, dom, ext, bd, ba in M[i:j]:
                ha = H.get((s, dom)); aw = Aw.get((s, ext)); y = TABLE[min(bd, CAP), min(ba, CAP)]
                if ha and aw:
                    L["saison"].append(s); L["nA"].append(ha[1]); L["nB"].append(aw[1]); L["kA"].append(ha[0].copy()); L["kB"].append(aw[0].copy()); L["y"].append(y)
            for d, s, dom, ext, bd, ba in M[i:j]:
                v = TABLE[min(bd, CAP), min(ba, CAP)]
                h = H.setdefault((s, dom), [np.zeros(len(NOMS), dtype=np.float32), 0]); h[0] += v; h[1] += 1
                a = Aw.setdefault((s, ext), [np.zeros(len(NOMS), dtype=np.float32), 0]); a[0] += v; a[1] += 1
            i = j
    return {"saison": np.array(L["saison"]), "nA": np.array(L["nA"]), "nB": np.array(L["nB"]), "kA": np.array(L["kA"]), "kB": np.array(L["kB"]), "y": np.array(L["y"])}

def indicateur(kA, nA, kB, nB, score, m=0, base=0.5):
    """Frequence lissee (m pseudo-matchs au taux de base) : plus faible des deux cotes (min) ou frequence groupee (pool)."""
    fa, fb = (kA + m * base) / np.maximum(nA + m, 1), (kB + m * base) / np.maximum(nB + m, 1)
    return np.minimum(fa, fb) if score == "min" else (kA + kB + 2 * m * base) / np.maximum(nA + nB + 2 * m, 1)

def calibrer(D=None):
    """Choisit pour chaque marche (indicateur, lissage) sur 2122-2324 evalue en 2425 (memes matchs pour toutes les options), teste en 2526 (jamais utilisee pour regler), puis ajuste sur toutes les saisons."""
    D = D or lignes_historique(); s_ = D["saison"]; nm = np.minimum(D["nA"], D["nB"]); res = {"description": __doc__.split("\n")[0], "z_seuil": Z, "n_min": NMIN, "marches": {},
        "periodes": {"reglage": "2122-2324", "validation": SAISON_VALID, "test": SAISON_TEST}, "nb_matchs_historiques": int(len(s_))}
    ok = nm >= NMIN; tr = ok & np.isin(s_, ["2122", "2223", "2324"]); va = ok & (s_ == SAISON_VALID); te = ok & (s_ == SAISON_TEST)
    for n in NOMS:
        k = IDX[n]; y = D["y"][:, k]; best = None; base_tr = float(y[tr].mean())
        for sc in SCORES:
            for m in M_GRILLE:
                ind = indicateur(D["kA"][:, k], D["nA"], D["kB"][:, k], D["nB"], sc, m, base_tr)
                blocs = _ajuste(ind[tr], y[tr], 0); p = _predire_blocs(blocs, ind[va], base_tr)
                g = _perte(base_tr, y[va]) - _perte(p, y[va]); gm = float(g.mean()); z = gm / (g.std(ddof=1) / math.sqrt(len(g))) if g.std() > 0 else 0.0
                if best is None or gm > best[0]: best = (gm, float(z), sc, m)
        gm, z, sc, m = best; base_t = float(y[tr | va].mean()); ind = indicateur(D["kA"][:, k], D["nA"], D["kB"][:, k], D["nB"], sc, m, base_t)
        blocs_t = _ajuste(ind[tr | va], y[tr | va], 0); p_t = _predire_blocs(blocs_t, ind[te], base_t)
        g = _perte(base_t, y[te]) - _perte(p_t, y[te]); gt = float(g.mean()); zt = float(gt / (g.std(ddof=1) / math.sqrt(len(g)))) if g.std() > 0 else 0.0
        valide = bool(gm > 0 and z > Z and gt > 0 and zt > Z)
        base_f = float(y[ok].mean()); ind = indicateur(D["kA"][:, k], D["nA"], D["kB"][:, k], D["nB"], sc, m, base_f); blocs = _ajuste(ind[ok], y[ok], 0)
        res["marches"][n] = {"score": sc, "lissage": m, "valide": valide, "taux_base": base_f, "n_ajuste": int(ok.sum()),
                             "validation": {"gain_logloss": gm, "z": z, "n": int(va.sum())}, "test": {"gain_logloss": gt, "z": zt, "n": int(te.sum())},
                             "blocs": [[float(x[0]), float(x[1]), float(x[2]), float(x[3])] for x in blocs]}
    return res

def ecrire_calibration(res=None):
    res = res or calibrer(); os.makedirs(DOSSIER, exist_ok=True); json.dump(res, open(CALIB, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True); return res

def charger_calibration(chemin=CALIB):
    return json.load(open(chemin, encoding="utf-8"))

# ---------------------------------------------------------------- echantillons d'un match a venir
def echantillons(x):
    """Flux commun (un match) -> (liste des scores (home, away) des matchs de A a domicile, idem pour B a l'exterieur), saison en cours, strictement avant le match.
    Orientation home/away conservee : pour B a l'exterieur, home = adversaire de B."""
    a = x.get("assemblage") or {}; saison = a.get("saison_football_data"); jour = x["date"]
    def pris(eq, dom):
        M = [m for m in (a.get(eq) or {}).get("matchs") or [] if m.get("domicile") is dom and m.get("date") and m["date"] < jour and m.get("buts_marques") is not None and m.get("buts_encaisses") is not None]
        S = [m for m in M if m.get("saison") == saison] if saison else M
        return S if S or not saison else M
    A = [(m["buts_marques"], m["buts_encaisses"]) for m in pris("equipe_dom", True)]
    B = [(m["buts_encaisses"], m["buts_marques"]) for m in pris("equipe_ext", False)]
    return A, B

def _compte(S, k):
    return float(sum(TABLE[min(h, CAP), min(a, CAP), k] for h, a in S))

def evaluer(A, B, marche, cote=None, calib=None, cfg=None):
    """Evalue UN pari. A, B : echantillons (voir echantillons). -> dict (verdict, taux historique, intervalle, preuve)."""
    calib = calib or charger_calibration(); cfg = cfg or config(); k = IDX[marche]; r = {"marche": marche, "cote": cote, "nA": len(A), "nB": len(B)}
    if cote is not None and cote < cfg["cote_min"]: return {**r, "verdict": "REFUSÉ", "raison": f"cote {cote} < {cfg['cote_min']} (règle de l'utilisateur)"}
    c = calib["marches"].get(marche)
    if not c: return {**r, "verdict": "NON ÉVALUABLE", "raison": "marché sans calibration"}
    nmin = calib.get("n_min", NMIN)
    if min(len(A), len(B)) < nmin: return {**r, "verdict": "NON ÉVALUABLE", "raison": f"moins de {nmin} matchs d'un côté (A à domicile {len(A)}, B à l'extérieur {len(B)})"}
    kA, kB = _compte(A, k), _compte(B, k); r.update(kA=int(kA), kB=int(kB))
    s = float(indicateur(np.array(kA), np.array(len(A)), np.array(kB), np.array(len(B)), c["score"], c["lissage"], c["taux_base"])); r["indicateur"] = s
    taux, nb = _taux(c["blocs"], s, c["taux_base"]); lo, hi = wilson(taux * nb, nb); r.update(taux_historique=float(taux), n_historique=int(nb), borne_basse=lo, borne_haute=hi, taux_base=c["taux_base"])
    if not c["valide"]: return {**r, "verdict": "SANS SIGNAL", "raison": "l'indicateur n'a pas prouvé son pouvoir sur ce marché (gain > 0 et z > 1,645 sur 2425 puis 2526)"}
    if lo > 0.5: v = "TIENT"
    elif taux > 0.5: v = "TIENT AVEC RÉSERVE"
    elif hi > 0.5: v = "FRAGILE"
    else: v = "NE TIENT PAS"
    return {**r, "verdict": v}

def alternatives(x, calib=None, cfg=None, exclure=None, n=3):
    """Marches du meme match qui tiennent, cote >= minimum, classes par borne basse du taux historique."""
    calib = calib or charger_calibration(); cfg = cfg or config(); A, B = echantillons(x); cotes = cotes_betpawa(x.get("cotes_betpawa") or x.get("cotes")); R = []
    for m, c in cotes.items():
        if m == exclure or c < cfg["cote_min"]: continue
        e = evaluer(A, B, m, c, calib, cfg)
        if e["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE"): R.append(e)
    R.sort(key=lambda e: -e["borne_basse"]); return R[:n]

def trouver(nom_dom, nom_ext, jours=None):
    """Retrouve un match du flux commun par fragments de noms. -> dict du flux (le plus recent fichier qui le porte)."""
    res = None
    for f in sorted(glob.glob(os.path.join(FLUX, "*.json.gz"))):
        if jours and os.path.basename(f)[:10] not in jours: continue
        for x in json.load(gzip.open(f)).values():
            if nom_dom.lower() in (x.get("domicile") or "").lower() and nom_ext.lower() in (x.get("exterieur") or "").lower(): res = x
    return res

def evaluer_coupon(picks, jour=None):
    """picks : [{'dom': 'Galatasaray', 'ext': 'Amed', 'marche': '1', 'cote': 1.41}] -> liste d'evaluations triees du plus au moins tenace."""
    calib = charger_calibration(); cfg = config(); out = []
    for p in picks:
        x = trouver(p["dom"], p["ext"], [jour] if jour else None)
        if not x: out.append({**p, "verdict": "NON ÉVALUABLE", "raison": "match absent du flux commun"}); continue
        A, B = echantillons(x); e = evaluer(A, B, p["marche"], p.get("cote"), calib, cfg)
        out.append({**p, **e, "libelle": libelle(p["marche"], x["domicile"], x["exterieur"]), "heure": x.get("heure_cameroun")})
    ordre = {"TIENT": 0, "TIENT AVEC RÉSERVE": 1, "FRAGILE": 2, "NE TIENT PAS": 3, "SANS SIGNAL": 4, "NON ÉVALUABLE": 5, "REFUSÉ": 6}
    out.sort(key=lambda e: (ordre.get(e["verdict"], 9), -(e.get("borne_basse") or 0))); return out


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

_CHAMP = {}
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
                    if cle in vus or m.get("saison") != saison: continue
                    vus.add(cle); B.append(m["buts_marques"]); (BD if m.get("domicile") else BE).append(m["buts_marques"])
                    if m.get("xg") is not None: X.append(m["xg"])
    mo = lambda L: sum(L) / len(L) if L else None
    r = {"buts": mo(B), "buts_dom": mo(BD), "buts_ext": mo(BE), "avantage_dom": (mo(BD) - mo(BE)) if BD and BE else 0.0, "n": len(B), "xg": (sum(X) / len(X)) if X else None, "n_xg": len(X)}
    _CHAMP[(competition, saison)] = r; return r

def saison_complete(x, eq):
    """Toute la saison en cours (domicile et exterieur), avant le match : moyennes buts et xG, comme dans la comparaison avec les xG du championnat."""
    a = x.get("assemblage") or {}; saison = a.get("saison_football_data")
    M = [m for m in (a.get(eq) or {}).get("matchs") or [] if m.get("date") and m["date"] < x["date"] and m.get("saison") == saison and m.get("buts_marques") is not None]
    g = lambda c: _moy([m.get(c) for m in M])
    (bm, n), (be, _), (xc, nx), (xd, _) = g("buts_marques"), g("buts_encaisses"), g("xg"), g("xg_concede")
    return {"n": n, "buts_marques": bm, "buts_encaisses": be, "xg_cree": xc, "xg_concede": xd, "n_xg": nx,
            "ecart_xg": None if xc is None or xd is None else xc - xd, "surperformance": None if xc is None or bm is None else bm - xc}

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
    if A["n"] < NMIN or B["n"] < NMIN: return {"verdict": "NON ÉVALUABLE", "phrase": f"Pas assez de matchs ({A['n']} / {B['n']}).", "A": A, "B": B}
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
    xa = _attendus(SA, SB, ("xg_cree", "xg_concede"), ("xg_cree", "xg_concede")) if min(SA["n_xg"], SB["n_xg"]) >= NMIN else (None, None); champ = moyenne_championnat(x.get("competition"), a.get("saison_football_data")); lect_x = _lecture(marche, *xa, champ["avantage_dom"]); lect_b = _lecture(marche, *bm, champ["avantage_dom"])
    ordre = ["NE TIENT PAS", "TIENT AVEC RÉSERVE", "TIENT"]
    verdict = _ajuster(verdict, lect_b, lect_x)
    lecture_xg = {None: "xG indisponible pour une des deux équipes", True: "le xG confirme", False: "le xG contredit", "limite": "le xG est à la limite de la ligne"}[lect_x]
    phrase = (f"{x['domicile']} à domicile : {f(A['buts_marques'])} buts marqués, {f(A['buts_encaisses'])} encaissés (xG {f(A['xg_cree'])}/{f(A['xg_concede'])}), pari passé {A['reussi']} fois sur {A['n']}. "
              f"{x['exterieur']} à l'extérieur : {f(B['buts_marques'])} marqués, {f(B['buts_encaisses'])} encaissés (xG {f(B['xg_cree'])}/{f(B['xg_concede'])}), pari passé {B['reussi']} fois sur {B['n']}.")
    ch = lambda e: ("?" if e["xg_cree"] is None else f"xG {e['xg_cree']:.2f} créés / {e['xg_concede']:.2f} concédés (écart {e['ecart_xg']:+.2f}), buts {f(e['buts_marques'])} / {f(e['buts_encaisses'])}")
    phrase += f" Saison entière (xG) : {x['domicile']} {ch(SA)} ; {x['exterieur']} {ch(SB)}. Moyenne du championnat : {f(champ['buts'])} but par équipe et par match."
    return {"verdict": verdict, "libelle": libelle(marche, x["domicile"], x["exterieur"]), "cote": cote, "phrase": phrase, "tendances_xg": tend, "buts_attendus": bm, "xg_attendus": xa, "lecture_xg": lecture_xg, "saison_A": SA, "saison_B": SB, "championnat": champ, "A": A, "B": B}


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

def choix_a_geler(x, calib, cfg, n=2):
    """Pour un match : les n marches qui tiennent le mieux (borne basse) ET les n qui tiennent le moins bien parmi les marches evaluables a cote >= minimum."""
    A, B = echantillons(x); E = []
    for m, c in cotes_betpawa(x["cotes_betpawa"]).items():
        e = evaluer(A, B, m, c, calib, cfg)
        if "taux_historique" in e and e["verdict"] != "SANS SIGNAL": E.append(e)
    E.sort(key=lambda e: -e["borne_basse"]); return E[:n] + [e for e in E[-n:] if e not in E[:n]]

def geler(jour=None, maintenant=None, chemin=JOURNAL, flux=FLUX, calib=None, cfg=None):
    """Ajoute au journal (jamais reecrit) les verdicts des matchs a venir. -> nb de lignes ajoutees."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); jour = jour or maintenant[:10]
    calib = calib or charger_calibration(); cfg = cfg or config(); os.makedirs(os.path.dirname(chemin), exist_ok=True)
    ex = lire_journal(chemin); deja = {(r["match_id"], r["marche"]) for r in ex}; prec = ex[-1]["empreinte"] if ex else ""; n = 0
    with open(chemin, "a", encoding="utf-8") as f:
        for x in matchs_a_venir(jour, maintenant, flux):
            for e in choix_a_geler(x, calib, cfg):
                if (x["match_id"], e["marche"]) in deja: continue
                rec = {"match_id": x["match_id"], "date": x["date"], "coup_d_envoi_utc": x["coup_d_envoi_utc"], "gele_le": maintenant,
                       **{k: (round(e[k], 4) if isinstance(e[k], float) and k != "cote" else e[k]) for k in ("marche", "cote", "verdict", "taux_historique", "borne_basse")}}
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
        y = bool(TABLE[min(sc["buts_dom"], CAP), min(sc["buts_ext"], CAP), IDX[r["marche"]]]); g = par.setdefault(r["verdict"], {"n": 0, "reussis": 0, "p_annonce": 0.0}); g["n"] += 1; g["reussis"] += y; g["p_annonce"] += r["taux_historique"]
    out = {}
    for v, g in par.items():
        lo, hi = wilson(g["reussis"], g["n"]); out[v] = {"paris": g["n"], "reussis": g["reussis"], "taux_reel": g["reussis"] / g["n"], "borne_basse": lo, "borne_haute": hi, "taux_annonce_moyen": g["p_annonce"] / g["n"]}
    return {"description": "Taux de reussite reel par verdict, sur les paris gelés avant le coup d'envoi (matchs termines).", "derniere_empreinte": (lire_journal(chemin) or [{}])[-1].get("empreinte"), "par_verdict": out}

def ecrire_bilan(b=None, chemin=BILAN):
    b = b or bilan(); os.makedirs(os.path.dirname(chemin), exist_ok=True); json.dump(b, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True); return b

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "calibrer":
        r = ecrire_calibration(); v = [n for n, c in r["marches"].items() if c.get("valide")]
        print(json.dumps({"matchs_historiques": r["nb_matchs_historiques"], "marches": len(r["marches"]), "marches_valides": len(v)}, ensure_ascii=False))
    elif cmd == "geler":
        print(json.dumps({"lignes_ajoutees": geler(), "anomalies": verifier_journal()}, ensure_ascii=False))
    elif cmd == "bilan":
        b = ecrire_bilan(); print(json.dumps({k: {x: round(y, 3) if isinstance(y, float) else y for x, y in v.items()} for k, v in b["par_verdict"].items()}, ensure_ascii=False))
    elif cmd == "coupon":
        for e in evaluer_coupon(json.load(open(sys.argv[2], encoding="utf-8")), sys.argv[3] if len(sys.argv) > 3 else None): print(json.dumps(e, ensure_ascii=False))
    else: print(__doc__)
