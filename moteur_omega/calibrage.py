"""Calibrage et validation du moteur omega. Usage : python -m moteur_omega.calibrage

Protocole (fixé avant tout calcul, leçons des moteurs précédents : les réglages appris sur 3 semaines d'archive ne tenaient pas hors échantillon) :
1. RÉGLAGE sur Football-Data 2025-26 (saison terminée, ~12 000 matchs) :
   - forme des buts attendus (« moyenne » de Patrick ou « multiplicative ») et taille de fenêtre : choisies sur les 30 % de matchs les plus
     récents de 2025-26, après ajustement sur les 70 % plus anciens (aucun regard sur 2026-27 ni sur l'archive) ;
   - rapprochement vers la moyenne (pseudo-matchs équipe et championnat) et paramètre ρ de Dixon-Coles : maximum de vraisemblance sur 2025-26 ;
   - calibrage des probabilités : régression isotone par marché sur 2025-26.
2. VALIDATION sur Football-Data 2026-27 (postérieure, jamais utilisée pour régler) : qualité des probabilités (Brier, perte logarithmique,
   calibrage par tranches), comparaison au taux de base et aux cotes de clôture ; décision sur les filtres de résistance et de stabilité
   (gardés seulement s'ils améliorent la réussite au-delà de la probabilité, test de Welch, p < 0,05).
3. ARCHIVE ARCHETYPE (cotes BetPawa réelles prises avant le coup d'envoi), coupée en deux au 14/10/2026 :
   - développement (avant) : seuil de probabilité appris (meilleure borne basse de Wilson des paris principaux, cote >= 1,39 imposée par
     Patrick) et décision sur l'accord avec la cote (mêmes règles que les autres filtres) ;
   - réserve (à partir du 14/10) : test final, jamais utilisé pour choisir ; réussite des sélections, rendement indicatif.
Sorties : moteur_omega/parametres.json, docs/omega_validation.json.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import ttest_ind

from . import coeur, donnees as D, marches as M, modele as MO

ROOT = Path(__file__).resolve().parent.parent
PARAMS = Path(__file__).with_name("parametres.json")
RAPPORT = ROOT / "docs" / "omega_validation.json"
FENETRES = (5, 6, 7, 8, 10, None)          # None = toute la saison au même lieu
FORMES = ("moyenne", "multiplicative")
COUPE_ARCHIVE = "2026-10-14"              # archive : développement avant, réserve (test final) à partir de ce jour ; fixée avant calcul (même coupe que l'alpha)
SEUILS_CANDIDATS = [round(0.50 + 0.01 * k, 2) for k in range(26)]   # 50 % à 75 % : le seuil retenu est APPRIS (72 % est impossible à 1,39 et plus)
MIN_PARIS_SEUIL = 30                       # en dessous, un seuil n'est pas jugeable (borne de Wilson trop large) : il n'est pas candidat
VERSION = "1.1.0"


def _caracteristiques(ms: list[dict], refs: D.References, fenetre: int | None) -> tuple[np.ndarray, list[dict]]:
    rows, gardes = [], []
    for m in ms:
        s = MO.series(m, fenetre)
        if not MO.admissible(s) or m.get("h") is None:
            continue
        k, sh, sa = refs.avant(m["ligue"], m["jour"])
        rows.append((len(s["dom_marques"]), len(s["ext_marques"]), np.mean(s["dom_marques"]), np.mean(s["dom_encaisses"]),
                     np.mean(s["ext_marques"]), np.mean(s["ext_encaisses"]), k, sh, sa, m["h"], m["a"]))
        gardes.append(m)
    return np.array(rows, float), gardes


def _lambdas(F: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    nd, ne, md, cd, mx, cx, k, sh, sa = (F[:, i] for i in range(9))
    me, ml = p["m_equipe"], p["m_ligue"]
    rd, re_ = (sh + ml * p["global_dom"]) / (k + ml), (sa + ml * p["global_ext"]) / (k + ml)
    r = lambda mo, n, ref: (n * mo + me * ref) / (n + me)
    if p["forme"] == "moyenne":
        n = (nd + ne) / 2
        la, lb = r((md + cx) / 2, n, rd), r((mx + cd) / 2, n, re_)
    else:
        la, lb = r(md, nd, rd) * r(cx, ne, rd) / rd, r(mx, ne, re_) * r(cd, nd, re_) / re_
    return np.maximum(la, 0.05), np.maximum(lb, 0.05)


def _ll(F: np.ndarray, p: dict[str, Any]) -> float:
    la, lb = _lambdas(F, p)
    h, a, rho = F[:, 9], F[:, 10], p["rho"]
    lp = h * np.log(la) - la - gammaln(h + 1) + a * np.log(lb) - lb - gammaln(a + 1)
    tau = np.ones_like(la)
    tau = np.where((h == 0) & (a == 0), 1 - la * lb * rho, tau)
    tau = np.where((h == 0) & (a == 1), 1 + la * rho, tau)
    tau = np.where((h == 1) & (a == 0), 1 + lb * rho, tau)
    tau = np.where((h == 1) & (a == 1), 1 - rho, tau)
    return float((lp + np.log(np.maximum(tau, 1e-9))).sum())


def _ajuster(F: np.ndarray, base: dict[str, Any]) -> dict[str, Any]:
    def f(x):
        return -_ll(F, {**base, "m_equipe": math.exp(x[0]), "m_ligue": math.exp(x[1]), "rho": x[2]})
    best = None
    for x0 in ([math.log(3), math.log(30), -0.05], [math.log(10), math.log(300), 0.0]):
        r = minimize(f, x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-3, "maxiter": 3000})
        if best is None or r.fun < best.fun:
            best = r
    return {**base, "m_equipe": round(math.exp(best.x[0]), 4), "m_ligue": round(math.exp(best.x[1]), 2), "rho": round(float(best.x[2]), 4),
            "log_vraisemblance_par_match": round(float(-best.fun) / len(F), 5)}


def regler(fd: list[dict], refs: D.References) -> tuple[dict[str, Any], dict[str, Any]]:
    tr = [m for m in fd if m["saison"] == "2526"]
    base = {"global_dom": float(np.mean([m["h"] for m in tr])), "global_ext": float(np.mean([m["a"] for m in tr]))}
    choix = []
    for w in FENETRES:
        F, gardes = _caracteristiques(tr, refs, w)
        jours = np.array([g["jour"] for g in gardes])
        coupe = sorted(jours)[int(len(jours) * 0.7)]
        A, B = F[jours < coupe], F[jours >= coupe]
        for forme in FORMES:
            p = _ajuster(A, {**base, "forme": forme, "fenetre": w})
            choix.append({"fenetre": w, "forme": forme, "ll_reglage": p["log_vraisemblance_par_match"], "ll_controle": round(_ll(B, p) / len(B), 5),
                          "matchs_reglage": len(A), "matchs_controle": len(B), "coupe": coupe})
    meilleur = max(choix, key=lambda c: c["ll_controle"])
    F, gardes = _caracteristiques(tr, refs, meilleur["fenetre"])
    p = _ajuster(F, {**base, "forme": meilleur["forme"], "fenetre": meilleur["fenetre"]})
    # constante (aucune information d'équipe) : référence de comparaison
    p_cst = {**p, "m_equipe": 1e9, "m_ligue": 1e9, "rho": 0.0}
    rapport = {"candidats": choix, "retenu": {k: meilleur[k] for k in ("fenetre", "forme")}, "matchs_2526": len(F),
               "ll_modele": round(_ll(F, p) / len(F), 5), "ll_constante": round(_ll(F, p_cst) / len(F), 5)}
    # calibrage isotone par marché
    cles = M.catalogue()
    la, lb = _lambdas(F, p)
    brut = MO.probas(MO.grilles(la, lb, p["rho"]), cles)
    h, a = F[:, 9].astype(int), F[:, 10].astype(int)
    calib, bases = {}, {}
    for k, c in enumerate(cles):
        t = M.test_du_marche(*c)
        y = np.array([t(i, j) for i, j in zip(h, a)], float)
        xs, ys = MO.isotone(brut[:, k], y)
        calib["|".join(c)] = [xs, ys]
        bases["|".join(c)] = round(float(y.mean()), 5)
    p["calibration"] = calib
    p["taux_de_base_2526"] = bases
    return p, rapport


# --- Validation -----------------------------------------------------------------------------------------------------
def _brier_ll(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    q = np.clip(p, 1e-6, 1 - 1e-6)
    return float(np.mean((p - y) ** 2)), float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def _tranches(p: np.ndarray, y: np.ndarray) -> list[dict]:
    out = []
    for lo in np.arange(0.0, 1.0, 0.1):
        k = (p >= lo) & (p < lo + 0.1 + (1e-9 if lo >= 0.9 else 0))
        if k.sum():
            out.append({"tranche": f"{lo:.0%}-{lo + 0.1:.0%}", "n": int(k.sum()), "prevu": round(float(p[k].mean()), 4), "observe": round(float(y[k].mean()), 4)})
    return out


def _cote_fd(m: dict, c: M.Cle) -> float | None:
    """Probabilité implicite des cotes de clôture moyennes Football-Data (marge retirée par normalisation) — évaluation seulement."""
    fd = m.get("cotes_fd") or {}
    if c[0] == "1x2" and "1x2_cloture" in fd and fd["1x2_cloture"].get("moy"):
        o = fd["1x2_cloture"]["moy"]
        inv = [1 / x for x in o]
        return inv[{"1": 0, "N": 1, "2": 2}[c[1]]] / sum(inv)
    if c[0] == "over_under_2.5" and "plus_moins_2_5_cloture" in fd and fd["plus_moins_2_5_cloture"].get("moy"):
        o = fd["plus_moins_2_5_cloture"]["moy"]
        inv = [1 / x for x in o]
        return inv[0 if c[1] == "plus" else 1] / sum(inv)
    return None


def _cote_bp(m: dict, c: M.Cle) -> float | None:
    """Probabilité implicite BetPawa normalisée (1X2, totaux, les deux marquent) — évaluation seulement."""
    g = (m.get("cotes") or {}).get(c[0]) or {}
    sels = {"1x2": ("1", "N", "2"), "btts": ("Oui", "Non")}.get(c[0], ("plus", "moins"))
    if all(isinstance(g.get(s), (int, float)) and g.get(s) > 1 for s in sels):
        inv = {s: 1 / g[s] for s in sels}
        return inv[c[1]] / sum(inv.values())
    return None


def analyser_tous(ms: list[dict], refs: D.References, p: dict[str, Any]) -> list[dict]:
    out = []
    for m in ms:
        if m.get("h") is None:
            continue
        a = coeur.analyser(m, refs, p)
        if a["statut"] != "analyse":
            continue
        for l in a["marches"]:
            t = M.test_du_marche(*l["cle"])
            l["gagne"] = bool(t(m["h"], m["a"]))
        a["_m"] = m
        out.append(a)
    return out


def qualite(analyses: list[dict], p: dict[str, Any], source: str) -> dict[str, Any]:
    cles = M.catalogue()
    res = {}
    for k, c in enumerate(cles):
        pc = np.array([a["marches"][k]["p"] for a in analyses])
        pb = np.array([a["marches"][k]["p_brut"] for a in analyses])
        y = np.array([a["marches"][k]["gagne"] for a in analyses], float)
        base = p["taux_de_base_2526"]["|".join(c)]
        r = {"n": len(y), "taux_observe": round(float(y.mean()), 4)}
        r["brier_calibre"], r["perte_log_calibre"] = (round(v, 5) for v in _brier_ll(pc, y))
        r["brier_brut"], _ = (round(v, 5) for v in _brier_ll(pb, y))
        r["brier_taux_de_base"], _ = (round(v, 5) for v in _brier_ll(np.full_like(y, base), y))
        fn = _cote_fd if source == "football-data" else _cote_bp
        im = [(fn(a["_m"], c), pc[i], y[i]) for i, a in enumerate(analyses)]
        im = [x for x in im if x[0] is not None]
        if len(im) >= 50 and (c[0] in ("1x2", "btts") or c[0].startswith("over_under_") and "_domicile" not in c[0] and "_exterieur" not in c[0]):
            q, mo, yy = (np.array(v, float) for v in zip(*im))
            r["comparaison_cotes"] = {"n": len(yy), "brier_modele": round(_brier_ll(mo, yy)[0], 5), "brier_cotes": round(_brier_ll(q, yy)[0], 5)}
        r["tranches"] = _tranches(pc, y)
        res["|".join(c)] = r
    return res


def apport_filtres(analyses: list[dict], seuil: float) -> dict[str, Any]:
    """Parmi les marchés à probabilité >= seuil : la résistance et la stabilité améliorent-elles la réussite AU-DELÀ de la probabilité ?
    Mesure : résidu (gagné − probabilité) des marchés qui passent le filtre contre ceux qui ne le passent pas (test de Welch)."""
    lignes = [l for a in analyses for l in a["marches"] if l["p"] >= seuil]
    out = {"marches_au_dessus_du_seuil": len(lignes)}
    for nom, f in (("resistance", lambda l: l["resistance"] == "RESISTE"), ("stabilite", lambda l: l["p_min"] >= seuil)):
        oui = [l for l in lignes if f(l)]
        non = [l for l in lignes if not f(l)]
        r = {"passe": len(oui), "ne_passe_pas": len(non)}
        for g, lst in (("passe", oui), ("ne_passe_pas", non)):
            if lst:
                r[f"reussite_{g}"] = round(float(np.mean([l["gagne"] for l in lst])), 4)
                r[f"probabilite_moyenne_{g}"] = round(float(np.mean([l["p"] for l in lst])), 4)
        if len(oui) >= 30 and len(non) >= 30:
            ro = [l["gagne"] - l["p"] for l in oui]
            rn = [l["gagne"] - l["p"] for l in non]
            t = ttest_ind(ro, rn, equal_var=False)
            r["apport_residu"] = round(float(np.mean(ro) - np.mean(rn)), 4)
            r["p_valeur"] = round(float(t.pvalue), 4)
            r["garde"] = bool(np.mean(ro) > np.mean(rn) and t.pvalue < 0.05)
        else:
            r["garde"] = False
            r["raison"] = "effectifs insuffisants pour juger (moins de 30 dans un des deux groupes)"
        out[nom] = r
    return out


def apport_accord_cote(analyses: list[dict], seuil: float) -> dict[str, Any]:
    """Parmi les marchés proposables (modèle >= seuil, cote >= 1,25, probabilité de la cote lisible) : quand la cote BetPawa annonce aussi
    au moins le seuil, la réussite dépasse-t-elle davantage la probabilité du modèle ? (même mesure que les autres filtres)."""
    lignes = [l for a in analyses for l in a["marches"] if l["p"] >= seuil and l["cote"] and l["cote"] >= coeur.COTE_MIN and l.get("p_cote") is not None]
    oui = [l for l in lignes if l["p_cote"] >= seuil]
    non = [l for l in lignes if l["p_cote"] < seuil]
    r: dict[str, Any] = {"marches_proposables": len(lignes), "passe": len(oui), "ne_passe_pas": len(non)}
    for g, lst in (("passe", oui), ("ne_passe_pas", non)):
        if lst:
            r[f"reussite_{g}"] = round(float(np.mean([l["gagne"] for l in lst])), 4)
            r[f"probabilite_modele_{g}"] = round(float(np.mean([l["p"] for l in lst])), 4)
            r[f"probabilite_cote_{g}"] = round(float(np.mean([l["p_cote"] for l in lst])), 4)
    if len(oui) >= 30 and len(non) >= 30:
        ro, rn = [l["gagne"] - l["p"] for l in oui], [l["gagne"] - l["p"] for l in non]
        t = ttest_ind(ro, rn, equal_var=False)
        r["apport_residu"], r["p_valeur"] = round(float(np.mean(ro) - np.mean(rn)), 4), round(float(t.pvalue), 4)
        r["garde"] = bool(np.mean(ro) > np.mean(rn) and t.pvalue < 0.05)
    else:
        r["garde"], r["raison"] = False, "effectifs insuffisants pour juger"
    return r


def _wilson_bas(g: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = g / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def choisir_seuil(analyses: list[dict], sel: dict[str, Any]) -> dict[str, Any]:
    """Seuil de probabilité appris sur le développement : celui dont les paris principaux ont la meilleure borne basse de Wilson (95 %)
    de réussite — la réussite la plus sûre compte tenu du nombre de paris. Aucun seuil fixé à la main."""
    essais = []
    for s in SEUILS_CANDIDATS:
        b = bilan_selection(analyses, {**sel, "seuil": s})["principal"]
        if b["n"] >= MIN_PARIS_SEUIL:
            essais.append({"seuil": s, "n": b["n"], "reussite": b["reussite"], "rendement": b["rendement"],
                           "wilson_bas": round(_wilson_bas(b["gagnes"], b["n"]), 4)})
    meilleur = max(essais, key=lambda e: (e["wilson_bas"], e["n"]))
    return {"retenu": meilleur["seuil"], "essais": essais}


def bilan_selection(analyses: list[dict], sel: dict[str, Any]) -> dict[str, Any]:
    principaux, tous = [], []
    for a in analyses:
        s = coeur.selectionner(a, sel)
        if s["principal"]:
            principaux.append(s["principal"])
            tous += [s["principal"]] + s["autres"]

    def fiche(lst: list[dict]) -> dict[str, Any]:
        if not lst:
            return {"n": 0}
        g = [l["gagne"] for l in lst]
        gain = sum((l["cote"] - 1) if l["gagne"] else -1 for l in lst)
        pr = [l["p_retenue"] if l.get("p_retenue") is not None else l["p"] for l in lst]
        return {"n": len(lst), "gagnes": int(sum(g)), "reussite": round(float(np.mean(g)), 4), "probabilite_modele": round(float(np.mean([l["p"] for l in lst])), 4),
                "probabilite_retenue": round(float(np.mean(pr)), 4),
                "cote_moyenne": round(float(np.mean([l["cote"] for l in lst])), 3), "gain_mise_1": round(gain, 2), "rendement": round(gain / len(lst), 4)}
    fam = {}
    for f in ("buts du match", "buts d'une équipe", "résultat", "combinés"):
        fam[f] = fiche([l for l in tous if l["famille"] == f])
    marches = {}
    for l in tous:
        marches.setdefault(l["marche"], []).append(l)
    return {"matchs_analyses": len(analyses), "matchs_avec_pronostic": len(principaux), "principal": fiche(principaux), "tous_les_retenus": fiche(tous),
            "par_famille": fam, "par_marche": {k: fiche(v) for k, v in sorted(marches.items(), key=lambda kv: -len(kv[1]))}}


def main() -> None:
    fd, refs_fd = D.charger_football_data()
    p, reglage = regler(fd, refs_fd)
    p["version"] = VERSION
    p["regle_le"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sel = {"cote_min": coeur.COTE_MIN, "seuil": None, "exiger_accord_cote": True, "exiger_resistance": False, "exiger_stabilite": False}
    arch, refs_ar = D.charger_archive(avec_futurs=False)
    an_ar = analyser_tous(arch, refs_ar, p)
    dev = [a for a in an_ar if a["jour"] < COUPE_ARCHIVE]
    res = [a for a in an_ar if a["jour"] >= COUPE_ARCHIVE]
    # 1. seuil appris sur le développement (accord avec la cote), 2. l'accord est-il utile à ce seuil ? sinon seuil réappris sans accord
    choix = choisir_seuil(dev, sel)
    sel["seuil"] = choix["retenu"]
    accord = apport_accord_cote(dev, sel["seuil"])
    if not accord["garde"]:
        sel["exiger_accord_cote"] = False
        choix = choisir_seuil(dev, sel)
        sel["seuil"] = choix["retenu"]
    # 3. filtres de résistance et de stabilité jugés sur Football-Data 2026-27 au seuil appris
    va = [m for m in fd if m["saison"] == "2627"]
    an_va = analyser_tous(va, refs_fd, p)
    filtres = apport_filtres(an_va, sel["seuil"])
    sel["exiger_resistance"] = filtres["resistance"]["garde"]
    sel["exiger_stabilite"] = filtres["stabilite"]["garde"]
    p["selection"] = sel
    rapport = {"genere_le": p["regle_le"], "version": VERSION, "protocole": __doc__.split("Protocole", 1)[1].split("Sorties")[0].strip(),
               "reglage_2526": reglage, "parametres": {k: v for k, v in p.items() if k not in ("calibration", "taux_de_base_2526")},
               "validation_2627": {"matchs": len(an_va), "qualite_par_marche": qualite(an_va, p, "football-data"),
                                   "apport_des_filtres": filtres, "frequence_resiste": _freq_resiste(an_va)},
               "test_archive": {"matchs": len(an_ar), "du": arch[0]["jour"] if arch else None, "au": arch[-1]["jour"] if arch else None,
                                "coupe": COUPE_ARCHIVE, "matchs_developpement": len(dev), "matchs_reserve": len(res),
                                "choix_du_seuil_developpement": choix,
                                "accord_cote_developpement": accord, "accord_cote_reserve": apport_accord_cote(res, sel["seuil"]),
                                "qualite_par_marche": qualite(an_ar, p, "archetype"),
                                "selection_reserve": bilan_selection(res, sel),
                                "selection_developpement": bilan_selection(dev, sel),
                                "selection_sans_accord_reserve": bilan_selection(res, {**sel, "exiger_accord_cote": False}),
                                "apport_des_filtres": apport_filtres(an_ar, sel["seuil"])}}
    PARAMS.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    r = rapport["test_archive"]["selection_reserve"]
    print("réglage :", reglage["retenu"], "ll", reglage["ll_modele"], "constante", reglage["ll_constante"])
    print("sélection :", sel)
    print("réserve : principal", r["principal"], "\n tous", r["tous_les_retenus"])


def _freq_resiste(analyses: list[dict]) -> dict[str, float]:
    cles = M.catalogue()
    return {"|".join(c): round(float(np.mean([a["marches"][k]["resistance"] == "RESISTE" for a in analyses])), 4) for k, c in enumerate(cles)}


if __name__ == "__main__":
    main()
