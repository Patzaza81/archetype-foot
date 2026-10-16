#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moteur v CALIBRÉ (robustesse) -- couche posée sur moteur_v_test.py (cœur : fréquences, k, verrou d'échantillon, musique).
Usage : python3 -I moteur_v_calibre.py --test
        python3 -I moteur_v_calibre.py <archive_dir> <jeu_reglage_ids.json>

Ajouts :
 1. pourcentage CALIBRÉ = logistique(-0.21 + 1.02*logit(1/cote)) (2 paramètres, ajustés sur les 440 matchs du 28/09-14/10)
 2. verrou d'échantillon inchangé (4 matchs mini, k, seuil brut 75/72 selon l'échantillon) -- variante "avec verrou"
 3. seuil de décision sur le pourcentage calibré (0.75 par défaut)
 4. VETO écart de points : 1X2 / double chance, côté parié avec écart de points par match <= -0.9 (soit -0.3 sur 3) -> pas de pari
 5. alertes musique conservées (n'interdisent rien)
 6. contrôle de calibration : gel si réussite réelle < annoncé - 10 points sur >= 50 paris
"""
import importlib.util, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location("mv", os.path.join(HERE, "moteur_v_test.py"))
mv = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(mv)

CAL_A, CAL_B = -0.21, 1.02          # cote seule
CAL2_A, CAL2_B, CAL2_C = -0.18, 0.89, 0.13   # cote + probabilité 'force des adversaires'
PRIOR_FORCE = 3.0
SEUIL_CAL = 0.76          # meilleur seuil mesuré le 16/10/2026 (balayage 0.66-0.78, avec verrou), voir seuil.py
VETO_ECART = -0.30        # écart de points par match / 3, côté parié
VETO_RANG = -0.40         # écart de rang normalisé (rang adverse - rang du côté parié) / nb équipes, côté parié
MIN_EQUIPES_CLASSEMENT = 8
MIN_MATCHS_PTS = 3
GEL_ECART, GEL_MIN_PARIS = 0.10, 50
COTE_MAX_CAL = 99.0


def p_cal(cote):
    q = min(max(1.0 / cote, 1e-3), 1 - 1e-3)
    z = CAL_A + CAL_B * math.log(q / (1 - q))
    return 1.0 / (1.0 + math.exp(-z))


def p_cal2(cote, p_force):
    """Probabilité calibrée = cote + probabilité issue des forces ajustées aux adversaires affrontés."""
    q = min(max(1.0 / cote, 1e-3), 1 - 1e-3); pf = min(max(p_force, 1e-3), 1 - 1e-3)
    z = CAL2_A + CAL2_B * math.log(q / (1 - q)) + CAL2_C * math.log(pf / (1 - pf))
    return 1.0 / (1.0 + math.exp(-z))


def _pois(l, k): return math.exp(-l) * l ** k / math.factorial(k)


def proba_marche(pred, lh, la, n=10):
    ph = [_pois(lh, k) for k in range(n + 1)]; pa = [_pois(la, k) for k in range(n + 1)]
    return sum(ph[i] * pa[j] for i in range(n + 1) for j in range(n + 1) if pred(i, j))


class Forces:
    """Force d'attaque / défense de chaque équipe, ajustée à la force des adversaires affrontés (modèle Poisson multiplicatif,
    rétréci vers 1 par PRIOR_FORCE matchs fictifs), ajustée sur tous les matchs archivés STRICTEMENT avant la date (aucune fuite)."""
    def __init__(self, archive):
        M = {}
        for e in archive.values():
            for t in ("equipe_dom", "equipe_ext"):
                q = e.get(t) or {}
                for m in q.get("matchs") or []:
                    if not (isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)): continue
                    h, a = (q["nom"], m["adversaire"]) if m["domicile"] else (m["adversaire"], q["nom"])
                    g = (m["buts_marques"], m["buts_encaisses"]) if m["domicile"] else (m["buts_encaisses"], m["buts_marques"])
                    M[(m["date"], h, a)] = g
        self.L = sorted((d, h, a, g[0], g[1]) for (d, h, a), g in M.items()); self.cache = {}

    def ajuste(self, avant, it=60):
        if avant in self.cache: return self.cache[avant]
        from collections import defaultdict
        ms = [x for x in self.L if x[0] < avant]
        if not ms:
            self.cache[avant] = ({}, {}, 1.0, 1.0); return self.cache[avant]
        mu = sum(x[3] + x[4] for x in ms) / (2 * len(ms)); gam = 1.2
        att = defaultdict(lambda: 1.0); dfn = defaultdict(lambda: 1.0)
        for _ in range(it):
            na = defaultdict(float); da = defaultdict(float); nd = defaultdict(float); dd = defaultdict(float)
            for d, h, a, gh, ga in ms:
                na[h] += gh; da[h] += mu * gam * dfn[a]; na[a] += ga; da[a] += mu * dfn[h]
                nd[a] += gh; dd[a] += mu * gam * att[h]; nd[h] += ga; dd[h] += mu * att[a]
            att = defaultdict(lambda: 1.0, {t: (na[t] + PRIOR_FORCE) / (da[t] + PRIOR_FORCE) for t in na})
            dfn = defaultdict(lambda: 1.0, {t: (nd[t] + PRIOR_FORCE) / (dd[t] + PRIOR_FORCE) for t in nd})
            gam = sum(x[3] for x in ms) / max(1e-9, sum(mu * att[x[1]] * dfn[x[2]] for x in ms))
        self.cache[avant] = (att, dfn, mu, gam); return self.cache[avant]

    def lambdas(self, e):
        """(lambda dom, lambda ext) ou None si une équipe n'a aucun match connu."""
        att, dfn, mu, gam = self.ajuste(e["date"]); h, a = e["domicile"], e["exterieur"]
        if h not in att or a not in att: return None
        return mu * gam * att[h] * dfn[a], mu * att[a] * dfn[h]


# --- MODE « MODÈLE SEUL » : le marché est choisi par la probabilité du modèle, la cote n'intervient pas dans le choix -----------
# Fiabilité HONNÊTE par zone de cote, mesurée le 16/10/2026 sur 440 matchs (pari au plus fort score du modèle, 1 par match).
# Le score du modèle lui-même est trop optimiste (il annonçait 74-79 % pour 54-75 % réels) : on affiche la fiabilité mesurée.
FIABILITE_ZONES = [(1.26, 1.37, 0.748, "SÛR"), (1.37, 1.49, 0.655, "MOYEN"), (1.49, 1.81, 0.543, "RISQUÉ")]


def lambdas_simples(rh, ra):
    """Buts attendus par moyennes simples au même lieu (marqués d'une équipe + encaissés de l'autre) / 2."""
    sH = sum(x[0] for x in rh) / len(rh); cH = sum(x[1] for x in rh) / len(rh)
    sA = sum(x[0] for x in ra) / len(ra); cA = sum(x[1] for x in ra) / len(ra)
    return max((sH + cA) / 2, .05), max((sA + cH) / 2, .05)


def zone_fiabilite(cote):
    for lo, hi, p, nom in FIABILITE_ZONES:
        if lo - 1e-9 <= cote < hi + (1e-9 if hi == FIABILITE_ZONES[-1][1] else 0): return p, nom
    return None, "NON CALIBRÉ"


def choisir_modele(cands, lam_force, lam_simple, cote_min=1.26):
    """Choisit le marché au plus fort score du modèle (moyenne force des adversaires + calcul simple). Retourne le pari avec
    sa fiabilité honnête par zone de cote ; None si une des deux estimations manque."""
    if lam_force is None or lam_simple is None: return None
    best = None
    for x in cands:
        if x["cote"] < cote_min - 1e-9: continue
        pm = (proba_marche(x["pred"], *lam_force) + proba_marche(x["pred"], *lam_simple)) / 2
        if best is None or pm > best[0]: best = (pm, x)
    if best is None: return None
    p, nom = zone_fiabilite(best[1]["cote"])
    return dict(best[1], p_modele=best[0], p_honnete=p, niveau=nom)


SEUIL_AUTRES = 0.70   # score modèle minimal pour figurer dans « autres »
MAX_AUTRES = 5


def _signature(pred, n=8):
    return tuple(bool(pred(h, a)) for h in range(n) for a in range(n))


def proposer(cands, lam_force, lam_simple, seuil_autres=SEUIL_AUTRES, max_autres=MAX_AUTRES, cote_min=1.26):
    """Pronostic PRINCIPAL (plus fort score du modèle, la cote ne choisit pas) + rubrique AUTRES (pronostics aussi acceptables).
    « Acceptable » = score modèle >= seuil_autres, cote >= cote_min, et marché différent du principal ET des autres déjà listés
    (deux marchés qui gagnent exactement sur les mêmes scores sont fusionnés : ex. Handicap +0.5 dom = Double chance 1X)."""
    if lam_force is None or lam_simple is None: return None
    liste = []
    for x in cands:
        if x["cote"] < cote_min - 1e-9: continue
        pm = (proba_marche(x["pred"], *lam_force) + proba_marche(x["pred"], *lam_simple)) / 2
        p, nom = zone_fiabilite(x["cote"])
        liste.append(dict(x, p_modele=pm, p_honnete=p, niveau=nom, sig=_signature(x["pred"])))
    if not liste: return None
    liste.sort(key=lambda d: (-round(d["p_modele"], 9), d["cote"]))
    principal = liste[0]; vus = {principal["sig"]}; autres = []
    for d in liste[1:]:
        if d["p_modele"] < seuil_autres - 1e-9 or d["sig"] in vus: continue
        vus.add(d["sig"]); autres.append(d)
        if len(autres) >= max_autres: break
    return {"principal": principal, "autres": autres}


def formater(res):
    if not res: return "Aucun pronostic (échantillon ou forces insuffisants)."
    def l(d): return f"{d['marche']} @ {d['cote']:.2f} | fiabilité {('%.0f %%' % (100 * d['p_honnete'])) if d['p_honnete'] else 'n/d'} ({d['niveau']}) | modèle {100 * d['p_modele']:.0f} %"
    out = ["PRONOSTIC PRINCIPAL : " + l(res["principal"])]
    out += ["AUTRES :"] + (["  - " + l(d) for d in res["autres"]] if res["autres"] else ["  (aucun autre pronostic acceptable)"])
    return "\n".join(out)


def cote_max_pour_seuil(seuil):
    """Cote la plus haute qui atteint encore le seuil calibré (dichotomie)."""
    lo, hi = 1.01, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if p_cal(mid) >= seuil: lo = mid
        else: hi = mid
    return lo


def cote_cote(marche):
    """Côté parié pour un marché 1X2 / double chance : +1 domicile, -1 extérieur, 0 non concerné."""
    return {"1X2 - 1": 1, "1X2 - 2": -1, "Double chance - 1X": 1, "Double chance - X2": -1}.get(marche, 0)


def points_par_match(equipe, date_match):
    ms = [m for m in (equipe.get("matchs") or []) if isinstance(m.get("buts_marques"), int)
          and isinstance(m.get("buts_encaisses"), int) and str(m.get("date") or "") < date_match]
    if len(ms) < MIN_MATCHS_PTS:
        return None
    pts = sum(3 if m["buts_marques"] > m["buts_encaisses"] else 1 if m["buts_marques"] == m["buts_encaisses"] else 0 for m in ms)
    return pts / len(ms)


def ecart_points(e):
    h = points_par_match(e["equipe_dom"], e["date"]); a = points_par_match(e["equipe_ext"], e["date"])
    return None if h is None or a is None else (h - a) / 3.0


def veto(marche, ecart, rang=None, use_points=True, use_rang=True):
    """Veto si le côté parié (1X2 / double chance) est très défavorisé aux points OU au classement."""
    c = cote_cote(marche)
    if c == 0: return False
    if use_points and ecart is not None and c * ecart <= VETO_ECART + 1e-9: return True
    if use_rang and rang is not None and c * rang <= VETO_RANG + 1e-9: return True
    return False


class Classements:
    """Classement reconstruit sans fuite depuis les historiques archivés (points par match, puis différence de buts par match).
    En production, le classement réel scrapé (cache_classement.py) doit remplacer cette reconstruction partielle."""
    def __init__(self, archive):
        from collections import defaultdict
        self.t = defaultdict(dict)
        for e in archive.values():
            for k in ("equipe_dom", "equipe_ext"):
                q = e.get(k) or {}
                if q.get("matchs"): self.t[e["competition"]][q["nom"]] = q["matchs"]
        self.cache = {}

    def table(self, comp, d):
        if (comp, d) not in self.cache:
            T = []
            for n, ms in self.t[comp].items():
                ms = [m for m in ms if m["date"] < d and isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)]
                if len(ms) < MIN_MATCHS_PTS: continue
                pts = sum(3 if m["buts_marques"] > m["buts_encaisses"] else 1 if m["buts_marques"] == m["buts_encaisses"] else 0 for m in ms)
                T.append((n, pts / len(ms), sum(m["buts_marques"] - m["buts_encaisses"] for m in ms) / len(ms)))
            T.sort(key=lambda t: (-t[1], -t[2])); self.cache[(comp, d)] = T
        return self.cache[(comp, d)]

    def ecart_rang(self, e):
        """(rang extérieur - rang domicile) / nb équipes : positif = domicile mieux classé. None si classement trop incomplet."""
        T = self.table(e["competition"], e["date"]); noms = [t[0] for t in T]
        if len(T) < MIN_EQUIPES_CLASSEMENT or e["domicile"] not in noms or e["exterieur"] not in noms: return None
        return (noms.index(e["exterieur"]) - noms.index(e["domicile"])) / len(T)


def choisir_calibre(cands, n_min, ecart, seuil=SEUIL_CAL, avec_verrou=True, rang=None, use_points=True, use_rang=True, lam=None):
    ok = []
    for c in cands:
        pc = p_cal(c["cote"]) if lam is None else p_cal2(c["cote"], proba_marche(c["pred"], lam[0], lam[1]))
        if pc < seuil - 1e-9: continue
        if avec_verrou and c["final_moy"] < mv.verrou(n_min) - 1e-9: continue
        if veto(c["marche"], ecart, rang, use_points, use_rang): continue
        ok.append((pc, c))
    if not ok: return None
    pc, best = max(ok, key=lambda t: (round(t[0], 9), round(t[1]["final_moy"], 9)))
    return dict(best, p_cal=pc, statut="ALERTE" if best["alertes"] else "RETENU")


def controle(paris, nom="calibre"):
    """paris = liste {p_cal, gagne}. Gel si réussite < annoncé - 10 pts sur >= 50 paris."""
    if len(paris) < GEL_MIN_PARIS: return "EN OBSERVATION (moins de 50 paris)"
    ann = sum(p["p_cal"] for p in paris) / len(paris); reel = sum(1 for p in paris if p["gagne"]) / len(paris)
    return f"GEL : réel {reel:.1%} < annoncé {ann:.1%} - 10 pts" if reel < ann - GEL_ECART else f"OK : réel {reel:.1%} vs annoncé {ann:.1%}"


def rejouer(dossier, ids, seuil, avec_verrou, use_points=True, use_rang=True, use_force=True):
    vus = mv.charger(dossier); cls = Classements(vus); frc = Forces(vus) if use_force else None; res = []
    for mid in ids:
        e = vus.get(mid)
        if not e: continue
        sc = mv.score_reel(e); cotes = e.get("cotes_observees") or {}
        if sc is None or not cotes: continue
        n, c = mv.analyse(mv.lignes(e["equipe_dom"], True, e["date"]), mv.lignes(e["equipe_ext"], False, e["date"]), cotes)
        if c is None: continue
        b = choisir_calibre(c, n, ecart_points(e), seuil, avec_verrou, cls.ecart_rang(e), use_points, use_rang, frc.lambdas(e) if frc else None)
        if b: res.append({"date": e["date"], "cote": b["cote"], "p_cal": b["p_cal"], "gagne": bool(b["pred"](*sc)), "marche": b["marche"], "statut": b["statut"]})
    return res


def tests():
    ok = True
    def chk(nom, cond):
        nonlocal ok; print(("OK   " if cond else "ECHEC"), nom); ok = ok and cond
    # p_cal : 3 qui passent / 3 qui échouent le seuil 0.75
    chk("p_cal(1.26) >= 0.75", p_cal(1.26) >= 0.75)
    chk("p_cal(1.27) >= 0.75", p_cal(1.27) >= 0.75)
    chk("p_cal(1.26) bord bas >= 0.75 et 1.277 limite", p_cal(1.277) >= 0.75 - 1e-3)
    chk("p_cal(1.28) < 0.75", p_cal(1.28) < 0.75)
    chk("p_cal(1.35) < 0.75", p_cal(1.35) < 0.75)
    chk("p_cal(1.60) < 0.75", p_cal(1.60) < 0.75)
    chk("p_cal(2.00) < 0.75", p_cal(2.00) < 0.75)
    chk("p_cal décroît avec la cote", p_cal(1.3) > p_cal(1.5) > p_cal(2.0))
    # veto : 3 qui passent (veto actif) / 3 qui ne l'activent pas
    chk("veto 1X2-1, domicile -0.4", veto("1X2 - 1", -0.4))
    chk("veto 1X2-2, extérieur désavantagé (+0.4 pour dom)", veto("1X2 - 2", 0.4))
    chk("veto Double chance 1X, -0.3 (borne incluse)", veto("Double chance - 1X", -0.3))
    chk("pas de veto 1X2-1, domicile favori +0.4", not veto("1X2 - 1", 0.4))
    chk("pas de veto pour un total de buts même avec -0.9", not veto("Moins de 2.5 buts", -0.9))
    chk("pas de veto si écart inconnu", not veto("1X2 - 1", None))
    chk("veto rang 1X2-1, domicile -0.5", veto("1X2 - 1", None, -0.5))
    chk("veto rang 1X2-2, extérieur mal classé (+0.45 pour dom)", veto("1X2 - 2", None, 0.45))
    chk("veto rang Double chance X2, +0.4 (borne incluse)", veto("Double chance - X2", None, 0.4))
    chk("pas de veto rang -0.3", not veto("1X2 - 1", None, -0.3))
    chk("pas de veto rang pour BTTS", not veto("BTTS - oui", None, -0.9))
    chk("pas de veto rang si désactivé", not veto("1X2 - 1", None, -0.9, use_rang=False))
    chk("veto points seul actif / rang désactivé", veto("1X2 - 1", -0.5, None, use_rang=False))
    chk("p_cal2 baisse si la force est faible", p_cal2(1.3, 0.5) < p_cal2(1.3, 0.9))
    chk("p_cal2 baisse quand la cote monte", p_cal2(1.3, 0.8) > p_cal2(1.8, 0.8))
    chk("proba_marche : lambdas 1.5/1.0, 'plus de 0.5 buts' ~ 0.918", abs(proba_marche(lambda h, a: h + a >= 1, 1.5, 1.0) - (1 - math.exp(-2.5))) < 1e-6)
    chk("proba_marche : 1X2 somme à 1", abs(sum(proba_marche(f, 1.4, 1.1) for f in (lambda h, a: h > a, lambda h, a: h == a, lambda h, a: h < a)) - 1) < 1e-6)
    arch_t = {"x": {"equipe_dom": {"nom": "A", "matchs": [{"date": "2026-08-01", "domicile": True, "adversaire": "B", "buts_marques": 3, "buts_encaisses": 0}] * 1},
                    "equipe_ext": {"nom": "B", "matchs": []}}}
    fo = Forces(arch_t)
    chk("Forces : aucune fuite (match du jour exclu)", fo.ajuste("2026-08-01")[0] == {} or "A" not in fo.ajuste("2026-08-01")[0])
    chk("Forces : A plus fort que B après un 3-0", fo.ajuste("2026-08-02")[0]["A"] > fo.ajuste("2026-08-02")[0]["B"])
    chk("Forces : équipe inconnue -> None", fo.lambdas({"date": "2026-08-02", "domicile": "Z", "exterieur": "A"}) is None)
    mk2 = lambda cote, f: {"marche": "x", "cote": cote, "pred": f}
    r = choisir_modele([mk2(1.30, lambda h, a: h + a >= 1), mk2(1.60, lambda h, a: h + a >= 3)], (1.5, 1.2), (1.5, 1.2))
    chk("modèle seul : choisit le marché le plus probable même si la cote est basse", r is not None and r["cote"] == 1.30)
    r = choisir_modele([mk2(1.60, lambda h, a: h + a >= 1), mk2(1.30, lambda h, a: h + a >= 4)], (1.5, 1.2), (1.5, 1.2))
    chk("modèle seul : choisit la cote 1.60 quand elle est la plus probable (la cote n'impose rien)", r is not None and r["cote"] == 1.60 and r["niveau"] == "RISQUÉ")
    chk("modèle seul : ignore cote < 1.26", choisir_modele([mk2(1.10, lambda h, a: True)], (1.5, 1.2), (1.5, 1.2)) is None)
    chk("modèle seul : None si forces absentes", choisir_modele([mk2(1.30, lambda h, a: True)], None, (1.5, 1.2)) is None)
    chk("zone 1.30 = SÛR 74.8 %", zone_fiabilite(1.30) == (0.748, "SÛR"))
    chk("zone 1.81 = RISQUÉ (borne incluse)", zone_fiabilite(1.81)[1] == "RISQUÉ")
    chk("zone 2.20 = NON CALIBRÉ", zone_fiabilite(2.20) == (None, "NON CALIBRÉ"))
    chk("fiabilité honnête décroît avec la cote", zone_fiabilite(1.3)[0] > zone_fiabilite(1.4)[0] > zone_fiabilite(1.6)[0])
    A = lambda m, cote, f: {"marche": m, "cote": cote, "pred": f}
    cs = [A("Plus de 0.5 buts", 1.30, lambda h, a: h + a >= 1), A("Plus de 1.5 buts", 1.50, lambda h, a: h + a >= 2),
          A("Moins de 4.5 buts", 1.28, lambda h, a: h + a <= 4), A("Moins de 4.5 buts (copie)", 1.35, lambda h, a: h + a <= 4),
          A("Plus de 5.5 buts", 6.0, lambda h, a: h + a >= 6), A("Cote trop basse", 1.10, lambda h, a: True)]
    rr = proposer(cs, (1.5, 1.2), (1.5, 1.2))
    chk("proposer : principal = marché le plus probable", rr["principal"]["marche"] == "Plus de 0.5 buts" and rr["principal"]["p_modele"] > rr["autres"][0]["p_modele"])
    chk("proposer : doublon (même signature) fusionné", sum("4.5" in d["marche"] for d in [rr["principal"]] + rr["autres"]) == 1)
    chk("proposer : le principal n'est pas dans autres", all(d["sig"] != rr["principal"]["sig"] for d in rr["autres"]))
    chk("proposer : autres triés par score décroissant", [d["p_modele"] for d in rr["autres"]] == sorted([d["p_modele"] for d in rr["autres"]], reverse=True))
    chk("proposer : pari sous le seuil 0.70 exclu des autres", all(d["p_modele"] >= 0.70 for d in rr["autres"]) and all(d["marche"] != "Plus de 5.5 buts" for d in rr["autres"]))
    chk("proposer : cote < 1.26 exclue", all(d["marche"] != "Cote trop basse" for d in [rr["principal"]] + rr["autres"]))
    chk("proposer : max_autres respecté", len(proposer(cs, (1.5, 1.2), (1.5, 1.2), seuil_autres=0.0, max_autres=1)["autres"]) <= 1)
    chk("proposer : None si forces absentes", proposer(cs, None, (1.5, 1.2)) is None)
    # sélection
    mk = lambda m, cote, fin, al=False: {"marche": m, "cote": cote, "final_moy": fin, "alertes": ["x"] if al else [], "pred": lambda h, a: True}
    chk("choisit cote 1.27 / final 0.85 (verrou 6+ = 0.72)", choisir_calibre([mk("Moins de 3.5 buts", 1.26, 0.85)], 8, None) is not None)
    chk("refuse cote 1.40 (calibré < 0.75)", choisir_calibre([mk("Moins de 3.5 buts", 1.40, 0.95)], 8, None) is None)
    chk("verrou : final 0.70 < 0.72 refusé, mais accepté sans verrou",
        choisir_calibre([mk("Moins de 3.5 buts", 1.26, 0.70)], 8, None) is None and choisir_calibre([mk("Moins de 3.5 buts", 1.26, 0.70)], 8, None, avec_verrou=False) is not None)
    chk("verrou 4-5 matchs : final 0.74 < 0.75 refusé", choisir_calibre([mk("Moins de 3.5 buts", 1.26, 0.74)], 4, None) is None)
    chk("veto bloque 1X2-1 avec écart -0.5", choisir_calibre([mk("1X2 - 1", 1.26, 0.9)], 8, -0.5) is None)
    chk("alerte musique conservée", choisir_calibre([mk("Moins de 3.5 buts", 1.26, 0.9, True)], 8, None)["statut"] == "ALERTE")
    chk("contrôle : 40 paris = observation", controle([{"p_cal": .77, "gagne": True}] * 40).startswith("EN OBS"))
    chk("contrôle : 60 paris à 60 % pour 77 % annoncé = gel", controle([{"p_cal": .77, "gagne": i < 36} for i in range(60)]).startswith("GEL"))
    chk("contrôle : 60 paris à 75 % = OK", controle([{"p_cal": .77, "gagne": i < 45} for i in range(60)]).startswith("OK"))
    print("TOUS LES TESTS OK" if ok else "DES TESTS ECHOUENT"); return ok


if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(0 if tests() else 1)
    ids = json.load(open(sys.argv[2]))
    print("ATTENTION : cote max théorique (formule cote seule) 0.76 -> %.3f | 0.72 -> %.3f ; avec la force des adversaires les paris réels montent jusqu a 1.32 (0.76) et 1.39 (0.72)" % (cote_max_pour_seuil(0.76), cote_max_pour_seuil(0.72)))
    for seuil in (0.75, 0.72):
        for av in (True, False):
            for nom, up, ur, uf in (("cote seule", True, True, False), ("+ force advers.", True, True, True)):
                r = rejouer(sys.argv[1], ids, seuil, av, up, ur, uf)
                if not r: print(f"seuil {seuil:.2f} verrou={'oui' if av else 'non'} {nom}: 0 pari"); continue
                s = mv.resume(r); print(f"seuil {seuil:.2f} verrou={'oui' if av else 'non'} | {nom:<13}| {s['n']:>3} paris, réussite {s['reussite']:.1%} (IC95 {s['ic95'][0]:.0%}-{s['ic95'][1]:.0%}), annoncé {sum(x['p_cal'] for x in r)/len(r):.1%}, ROI {s['roi']:+.1%}")
