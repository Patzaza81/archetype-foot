"""Pouvoir predictif des marches deduits des SCORES, par competition (etape 2, descriptive, sans cotes ni ROI).
Marches (evenements binaires): dom, nul, ext, o15 (>=2 buts), o25 (>=3), o35 (>=4), btts; plus le 1X2 multiclasse.
Referentiel: frequence historique de la competition (expansive, lissage de Laplace). Methodes: P1 (Poisson attaque/defense generales),
P2 (Poisson attaque/defense par lieu), F (frequences d'evenements propres a chaque equipe, par lieu).
Chronologie stricte: la prediction d'un match n'utilise que des matchs de dates STRICTEMENT anterieures (les matchs d'une meme date sont predits avant toute mise a jour).
Hyperparametres (force du lissage k, demi-vie de l'oubli) choisis par saison test uniquement sur les saisons ANTERIEURES (jamais sur la saison test).
Saisons test: 2223..2526 (au moins une saison anterieure). Archives en lecture seule; scores joues uniquement."""
import csv, json, math, os, sys, datetime, itertools
import numpy as np
from statistics import NormalDist
RACINE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(RACINE, "data", "football_data", "snapshots")
SAISONS = ["2122", "2223", "2324", "2425", "2526"]
EVT = ["dom", "nul", "ext", "o15", "o25", "o35", "btts"]
MARCHES = ["1X2"] + EVT
FAMILLES = ["P1", "P2", "F"]
K_GRILLE = [2, 5, 10, 20, 40]      # pseudo-matchs de lissage vers la moyenne de la competition (choisis par les donnees passees)
HL_GRILLE = [None, 730, 365]        # demi-vie d'oubli en jours (None = pas d'oubli)
G = 13                              # buts maximum du tableau de Poisson
EPS = 1e-9

def _lire(chemin):
    try: return list(csv.DictReader(open(chemin, encoding="utf-8-sig")))
    except UnicodeDecodeError: return list(csv.DictReader(open(chemin, encoding="latin-1")))

def _date(x):
    for f in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try: return datetime.datetime.strptime(x.strip(), f).date().toordinal()
        except (ValueError, AttributeError): pass
    return None

def charger(code):
    """Matchs joues (avec score) de la competition: liste triee (jour, saison, dom, ext, bd, ba)."""
    out = []
    for s in SAISONS:
        for p in (os.path.join(SNAP, s, "raw", code + ".csv"), os.path.join(SNAP, s, "nouvelles_ligues", "raw", code + ".csv")):
            if not os.path.exists(p): continue
            R = _lire(p)
            if not R: continue
            hk, ak = ("HomeTeam", "AwayTeam") if "HomeTeam" in R[0] else ("Home", "Away")
            gh, ga = ("FTHG", "FTAG") if "FTHG" in R[0] else ("HG", "AG")
            for i, r in enumerate(R):
                try: bd, ba = int(float(r[gh])), int(float(r[ga]))
                except (ValueError, TypeError, KeyError): continue
                d = _date(r.get("Date", ""))
                if d is None or not r[hk] or not r[ak]: continue
                out.append((d, s, r[hk], r[ak], bd, ba))
            break
    out.sort(key=lambda m: (m[0], SAISONS.index(m[1])))
    return out

def evenements(bd, ba):
    return (bd > ba, bd == ba, bd < ba, bd + ba >= 2, bd + ba >= 3, bd + ba >= 4, bd > 0 and ba > 0)

def _poisson(mu):
    """mu: tableau (N,) -> pmf (N,G)."""
    mu = np.maximum(mu, 1e-6)
    pm = np.zeros((len(mu), G)); pm[:, 0] = np.exp(-mu)
    for g in range(1, G): pm[:, g] = pm[:, g - 1] * mu / g
    return pm / pm.sum(axis=1, keepdims=True)

def _probas_poisson(mh, ma):
    ph, pa = _poisson(mh), _poisson(ma)
    M = ph[:, :, None] * pa[:, None, :]
    i = np.arange(G)
    dom = (i[:, None] > i[None, :]); nul = (i[:, None] == i[None, :]); ext = (i[:, None] < i[None, :])
    tot = i[:, None] + i[None, :]
    f = lambda mask: (M * mask[None]).sum(axis=(1, 2))
    return np.stack([f(dom), f(nul), f(ext), f(tot >= 2), f(tot >= 3), f(tot >= 4), f((i[:, None] > 0) & (i[None, :] > 0))], axis=1)

def predire(matchs, famille, k, hl, ret_mu=False):
    """Probabilites (N,7) pour chaque match, calculees en parcourant le temps; NaN si aucune donnee anterieure dans la competition."""
    N = len(matchs); mu = np.full((N, 2), np.nan); P = np.full((N, 7), np.nan)
    lam = 0.0 if hl is None else math.log(2) / hl
    acc = {}                                    # (equipe, lieu) -> [n, S, C, W, D, L, o15, o25, o35, btts, dernier_jour]
    lg = [0] * 10                               # ligue: N, somme dom, somme ext, evenements dom,nul,ext,o15,o25,o35,btts
    def lire(eq, lieu, jour):
        a = acc.get((eq, lieu))
        if a is None: return [0.0] * 10
        f = math.exp(-lam * (jour - a[10])) if lam else 1.0
        return [x * f for x in a[:10]]
    def maj(eq, lieu, jour, vec):
        a = acc.get((eq, lieu))
        if a is None: acc[(eq, lieu)] = vec + [jour]; return
        f = math.exp(-lam * (jour - a[10])) if lam else 1.0
        acc[(eq, lieu)] = [a[i] * f + vec[i] for i in range(10)] + [jour]
    i = 0
    while i < N:
        j = i
        while j < N and matchs[j][0] == matchs[i][0]: j += 1
        jour = matchs[i][0]
        for t in range(i, j):                   # predictions de la journee AVANT toute mise a jour
            _, _, h, a, _, _ = matchs[t]
            n = lg[0]
            if n == 0: continue
            Lh, La = lg[1] / n, lg[2] / n
            H1, H0, A1, A0 = lire(h, 0, jour), None, lire(a, 1, jour), None
            if famille in ("P1", "P2"):
                if famille == "P2":
                    ah = (H1[1] + k * Lh) / (H1[0] + k); da = (A1[2] + k * Lh) / (A1[0] + k)
                    aa = (A1[1] + k * La) / (A1[0] + k); dh = (H1[2] + k * La) / (H1[0] + k)
                    mu[t] = (ah * da / max(Lh, 1e-6), aa * dh / max(La, 1e-6))
                else:
                    g = (lg[1] + lg[2]) / (2 * n)
                    Ha, Aa = lire(h, 1, jour), lire(a, 0, jour)          # autres lieux de chaque equipe
                    att_h = (H1[1] + Ha[1] + k * g) / (H1[0] + Ha[0] + k); def_h = (H1[2] + Ha[2] + k * g) / (H1[0] + Ha[0] + k)
                    att_a = (A1[1] + Aa[1] + k * g) / (A1[0] + Aa[0] + k); def_a = (A1[2] + Aa[2] + k * g) / (A1[0] + Aa[0] + k)
                    mu[t] = (att_h * def_a / max(g, 1e-6) * Lh / max(g, 1e-6), att_a * def_h / max(g, 1e-6) * La / max(g, 1e-6))
            else:
                lr = [lg[3 + e] / n for e in range(7)]
                rh = [(H1[3 + e] + k * lr[e]) / (H1[0] + k) for e in range(7)]   # equipe a domicile: ses taux a domicile
                ra = [(A1[3 + e] + k * lr[e]) / (A1[0] + k) for e in range(7)]   # equipe a l'exterieur: ses taux a l'exterieur
                # evenements "equipe" -> evenements de match: rh=(vict,nul,def,o15,o25,o35,btts) pour l'equipe locale; ra idem pour la visiteuse
                P[t] = [(rh[0] + ra[2]) / 2, (rh[1] + ra[1]) / 2, (rh[2] + ra[0]) / 2, (rh[3] + ra[3]) / 2, (rh[4] + ra[4]) / 2, (rh[5] + ra[5]) / 2, (rh[6] + ra[6]) / 2]
        for t in range(i, j):                   # mises a jour apres la journee
            _, _, h, a, bd, ba = matchs[t]
            e = evenements(bd, ba)
            maj(h, 0, jour, [1.0, bd, ba, float(bd > ba), float(bd == ba), float(bd < ba), float(e[3]), float(e[4]), float(e[5]), float(e[6])])
            maj(a, 1, jour, [1.0, ba, bd, float(ba > bd), float(bd == ba), float(ba < bd), float(e[3]), float(e[4]), float(e[5]), float(e[6])])
            lg[0] += 1; lg[1] += bd; lg[2] += ba
            for q, v in enumerate((e[0], e[1], e[2], e[3], e[4], e[5], e[6])): lg[3 + q] += v
        i = j
    if famille in ("P1", "P2"):
        ok = ~np.isnan(mu[:, 0])
        if ok.any(): P[ok] = _probas_poisson(mu[ok, 0], mu[ok, 1])
    P = np.clip(P, EPS, 1 - EPS)
    return (P, mu) if ret_mu else P

def reference(matchs):
    """Frequence historique expansive de la competition (Laplace), mises a jour apres chaque journee."""
    N = len(matchs); P = np.full((N, 7), np.nan); cnt = np.zeros(7); n = 0; i = 0
    while i < N:
        j = i
        while j < N and matchs[j][0] == matchs[i][0]: j += 1
        if n > 0:
            p = np.empty(7); p[:3] = (cnt[:3] + 1) / (n + 3); p[3:] = (cnt[3:] + 1) / (n + 2)
            P[i:j] = p
        for t in range(i, j): cnt += np.array(evenements(*matchs[t][4:6]), float); n += 1
        i = j
    return np.clip(P, EPS, 1 - EPS)

def issues(matchs):
    return np.array([evenements(m[4], m[5]) for m in matchs], float)

def pertes(P, Y):
    """Pertes par match et marche: matrice (N,8) = [logloss 1X2 multiclasse, logloss binaire x7]; et Brier (N,8)."""
    L = np.zeros((len(P), 8)); B = np.zeros((len(P), 8))
    L[:, 0] = -np.log(np.sum(P[:, :3] * Y[:, :3], axis=1))
    B[:, 0] = np.sum((P[:, :3] - Y[:, :3]) ** 2, axis=1)
    L[:, 1:] = -(Y * np.log(P) + (1 - Y) * np.log(1 - P)); B[:, 1:] = (P - Y) ** 2
    return L, B

def succes(P, Y):
    """Taux de reussite: 1X2 = issue la plus probable; binaire = (p>0.5) == realise."""
    H = np.zeros((len(P), 8))
    H[:, 0] = (np.argmax(P[:, :3], axis=1) == np.argmax(Y[:, :3], axis=1))
    H[:, 1:] = ((P > 0.5) == (Y > 0.5)); return H

def analyser(code, matchs=None):
    matchs = charger(code) if matchs is None else matchs
    if len(matchs) < 50: return None
    S = np.array([SAISONS.index(m[1]) for m in matchs]); Y = issues(matchs)
    ref = reference(matchs); Lr, Br = pertes(ref, Y); Hr = succes(ref, Y)
    valide = ~np.isnan(ref[:, 0])
    cfgs = {f: [(k, hl) for k in K_GRILLE for hl in HL_GRILLE] for f in FAMILLES}
    pred = {}
    for f in FAMILLES:
        for k, hl in cfgs[f]:
            P = predire(matchs, f, k, hl); L, B = pertes(np.nan_to_num(P, nan=0.5), Y); pred[(f, k, hl)] = (P, L, B, succes(np.nan_to_num(P, nan=0.5), Y))
    res = {}
    for f in FAMILLES:
        for mi, mk in enumerate(MARCHES):
            diffs, diffs_b, hs, hr, n_s, par_saison, choix = [], [], [], [], [], {}, {}
            for st in range(1, 5):                           # saisons test 2223..2526
                tr = valide & (S < st); te = valide & (S == st)
                if not te.any() or not tr.any(): continue
                # choix de la configuration: perte moyenne sur les saisons anterieures UNIQUEMENT
                best = min(cfgs[f], key=lambda c: pred[(f,) + c][1][tr, mi].mean())
                P, L, B, H = pred[(f,) + best]
                d = Lr[te, mi] - L[te, mi]; db = Br[te, mi] - B[te, mi]
                diffs.append(d); diffs_b.append(db); hs.append(H[te, mi]); hr.append(Hr[te, mi])
                par_saison[SAISONS[st]] = round(float(d.mean()), 5); choix[SAISONS[st]] = {"k": best[0], "demi_vie_jours": best[1]}
            if not diffs: continue
            d = np.concatenate(diffs); n = len(d); m = float(d.mean()); se = float(d.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
            res[f"{f}|{mk}"] = {"famille": f, "marche": mk, "n_matchs_test": n, "gain_logloss_moyen": round(m, 5), "ecart_type_moyen": round(se, 5),
                "z": round(m / se, 2) if se and se > 0 else None, "gain_brier_moyen": round(float(np.concatenate(diffs_b).mean()), 5),
                "reussite_methode": round(float(np.concatenate(hs).mean()), 4), "reussite_reference": round(float(np.concatenate(hr).mean()), 4),
                "gain_par_saison_test": par_saison, "saisons_gagnantes": f"{sum(1 for v in par_saison.values() if v > 0)}/{len(par_saison)}",
                "config_retenue": choix}
    return {"n_matchs": len(matchs), "resultats": res}

def verdict(r, z_bonf):
    n_s = len(r["gain_par_saison_test"]); gagn = sum(1 for v in r["gain_par_saison_test"].values() if v > 0)
    z = r["z"]
    if z is None or r["gain_logloss_moyen"] <= 0: return "aucun_avantage"
    if z > z_bonf and gagn == n_s: return "avantage_robuste"
    if z > 1.96 and gagn == n_s: return "avantage"
    return "indetermine"

def main():
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    sortie = {}
    for code in sorted(cl):
        r = analyser(code)
        if r: sortie[code] = r; print(code, r["n_matchs"], flush=True)
    m = sum(len(v["resultats"]) for v in sortie.values()); zb = NormalDist().inv_cdf(1 - 0.05 / m)
    for v in sortie.values():
        for r in v["resultats"].values(): r["verdict"] = verdict(r, zb)
    doc = {"description": "Pouvoir predictif des marches deduits des scores, validation chronologique (voir en-tete de pouvoir_predictif.py). gain_logloss_moyen = perte(reference) - perte(methode) par match; >0 = la methode bat la frequence historique de la competition.",
           "tests_total": m, "z_bonferroni_unilateral_5pct": round(zb, 2), "competitions": sortie}
    json.dump(doc, open(os.path.join(RACINE, "data", "inventaire", "pouvoir_predictif.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ecrire_md(doc)

def ecrire_md(doc):
    C = doc["competitions"]; L = ["# Pouvoir predictif des marches (scores seuls, validation chronologique)", "",
      f"Tests: {doc['tests_total']} (competition x methode x marche); seuil Bonferroni z>{doc['z_bonferroni_unilateral_5pct']}.",
      "Gain = perte log (reference - methode) par match; >0 = bat la frequence historique de la competition. 'avantage' = z>1.96 ET gain>0 dans TOUTES les saisons test; 'avantage_robuste' = idem avec z au-dessus du seuil Bonferroni.", ""]
    L += ["## 1. Par marche et methode (38 competitions)", "", "| Marche | Methode | avantage_robuste | avantage | indetermine | aucun_avantage | gain moyen |", "|---|---|---|---|---|---|---|"]
    for mk in MARCHES:
        for f in FAMILLES:
            rs = [v["resultats"][f"{f}|{mk}"] for v in C.values() if f"{f}|{mk}" in v["resultats"]]
            c = {k: sum(1 for r in rs if r["verdict"] == k) for k in ("avantage_robuste", "avantage", "indetermine", "aucun_avantage")}
            L.append(f"| {mk} | {f} | {c['avantage_robuste']} | {c['avantage']} | {c['indetermine']} | {c['aucun_avantage']} | {np.mean([r['gain_logloss_moyen'] for r in rs]):+.4f} |")
    L += ["", "## 2. Cas avec avantage (tous, sans selection sur le test)", "", "| Comp | Marche | Methode | Matchs test | Gain/match | z | Saisons | Reussite methode | Reussite reference | Verdict |", "|---|---|---|---|---|---|---|---|---|---|"]
    for code, v in sorted(C.items()):
        for r in sorted(v["resultats"].values(), key=lambda r: -(r["z"] or -99)):
            if r["verdict"] in ("avantage", "avantage_robuste"):
                L.append(f"| {code} | {r['marche']} | {r['famille']} | {r['n_matchs_test']} | {r['gain_logloss_moyen']:+.4f} | {r['z']} | {r['saisons_gagnantes']} | {r['reussite_methode']:.3f} | {r['reussite_reference']:.3f} | {r['verdict']} |")
    L += ["", "## 3. Marches sans aucun avantage mesure, par competition", ""]
    for code, v in sorted(C.items()):
        sans = [mk for mk in MARCHES if all(v["resultats"].get(f"{f}|{mk}", {}).get("verdict", "aucun_avantage") in ("aucun_avantage", "indetermine") for f in FAMILLES)]
        L.append(f"- {code}: {', '.join(sans) if sans else 'aucun (au moins un marche avec avantage)'}")
    L += ["", "Limites: archives telles quelles (voir `docs/BILAN_ARCHIVE_FD.md`); formats multi-phases melanges; equipes a libelles variables traitees comme distinctes (aucune fusion); une equipe sans historique retombe sur la moyenne de la competition; pas de cote, pas de ROI. Une frequence stable n'est pas une prevision match par match: seul le gain de perte hors echantillon le mesure."]
    open(os.path.join(RACINE, "data", "inventaire", "pouvoir_predictif.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

if __name__ == "__main__": main()
