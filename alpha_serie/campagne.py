"""Moteur alpha — campagne d'optimisation systématique (24/10/2026), construite au-dessus de `robustesse.py` (commit ffb25b0).

But : explorer automatiquement, pour CHAQUE marché précis (famille, ligne) et chaque catégorie de cote, toutes les configurations de la stratégie
par scénarios, retenir celle qui sépare le mieux les gagnants des perdants sur l'apprentissage, puis la vérifier sur des matchs qui n'ont JAMAIS
servi à la choisir. Aucun autre moteur n'est touché ; rien n'est branché au pipeline.

Lecture (inchangée, `robustesse.py`) : séries au même lieu 4 à 7 matchs, paires, défavorable sans « juste au seuil », habituel ;
parts lues après retrait de chaque paire ; combos lus sur leur jambe la plus fragile.

Configuration = (taille minimale de l'échantillon n_min de 4 à 7, marge défavorable, marge habituelle) ; marges = valeurs réellement observées.
Catégories : « toutes » (objectif réussite, cotes absentes comprises), A (cote 1,25 à moins de 1,39, objectif réussite),
B (cote 1,39 et plus, sans limite haute, objectif rendement). Une cote connue sous 1,25 n'est jamais proposable : lecture écartée.

Trois étapes, chronologiques, sans recouvrement de matchs :
  1. APPRENTISSAGE   : Football-Data, matchs avant le 01/07/2026 (coupe par date, corrigée le 24/10). Toutes les configurations sont évaluées ; admissible = apport positif sur les paris non retenus
                       dans chaque moitié chronologique ; retenue = la plus nette (statistique z contre les paris non retenus).
  2. VALIDATION      : Football-Data, matchs du 01/07 au 27/09/2026. La configuration gelée est appliquée telle quelle.
                       Benjamini-Hochberg 5 % sur TOUTES les configurations retenues (tests exacts), puis apport positif dans chaque moitié.
  3. TEST FINAL      : archive ARCHETYPE (28/09–22/10/2026, cotes BetPawa prises avant le coup d'envoi). Jamais utilisée pour choisir ou retoucher.
                       Les candidates sont appliquées une fois ; Benjamini-Hochberg 5 % sur TOUTES les candidates (aucune présélection).
Statuts : exploitable (confirmé au test final), prometteur (positif au test final, non significatif), non confirmé, écarté en validation,
insuffisamment documenté (aucune configuration admissible, ou aucun pari dans une étape).
Cotes : Football-Data = moyenne de clôture du marché (1X2, plus/moins 2,5) et handicap asiatique d'ouverture ; ARCHETYPE = BetPawa avant match.
Combos, multigoals, multiscores : aucune cote archivée, réussite seule, valeur financière non évaluable. Aucune cote n'est inventée.
Usage : python -m alpha_serie.campagne
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import hypergeom

from . import parametres as P
from . import robustesse as R

ROOT = Path(__file__).resolve().parent.parent
RAPPORT = ROOT / "docs" / "alpha_campagne.json"
REGLES = ROOT / "data" / "alpha_serie" / "campagne_regles.json"
DEBUT_ARCHETYPE = "2026-09-28"
N_MIN = (4, 5, 6, 7)
CATEGORIES = ("toutes", "A", "B")
ETAPES = ("apprentissage", "validation", "final")


def objectif(cat: str) -> str:
    return "rendement" if cat == "B" else "reussite"


def categories(cote: float | None) -> list[str]:
    """Catégories d'une lecture. Cote connue sous 1,25 : aucune (non proposable). Sans cote : « toutes » seulement."""
    if cote is None:
        return ["toutes"]
    if cote < P.COTE_MIN:
        return []
    return ["toutes", "A" if cote < R.FRONTIERE_VOIES - 1e-12 else "B"]


# --- Lectures compactes ----------------------------------------------------------------------------------------------
def lectures(matchs: list[dict], etape_de) -> dict:
    """{(marché, catégorie): {colonne: liste}} ; une ligne par match analysable. `etape_de(match)` -> étape ou None (match écarté)."""
    cat = R.catalogue()
    gr = {cle: R.grilles(p, z) for cle, _, p, z in cat}
    gj = {cle: [R._solide_simple(jp, jz) for jp, jz in p.jambes] for cle, _, p, _ in cat if getattr(p, "jambes", None)}
    out: dict[tuple, dict] = defaultdict(lambda: defaultdict(list))
    infos = {lib: {"cle": cle, "famille": R.famille(cle)} for cle, lib, _, _ in cat}
    for m in matchs:
        etape = etape_de(m)
        if etape is None:
            continue
        prs = R.series(m)
        if len(prs) < P.MIN_MATCHS:
            continue
        for cle, lib, pred, _ in cat:
            d, h = R.parts_marche(prs, cle, gr[cle], gj.get(cle))       # même lecture qu'en production (alpha_serie/calibrees.py)
            cote = R.cote_reelle(m, cle) if cle[0] not in R.ETUDIES_SANS_COTE else None
            for c in categories(cote):
                col = out[(lib, c)]
                col["etape"].append(etape)
                col["jour"].append(m["jour"])
                col["id"].append(m["id"])
                col["n"].append(len(prs))
                col["d"].append(round(d, 4))
                col["h"].append(round(h, 4))
                col["g"].append(bool(pred(m["h"], m["a"])))
                col["cote"].append(np.nan if cote is None else float(cote))
    tab = {}
    for k, col in out.items():
        tab[k] = {"etape": np.array(col["etape"]), "jour": np.array(col["jour"]), "id": col["id"], "n": np.array(col["n"], dtype=np.int8),
                  "d": np.array(col["d"]), "h": np.array(col["h"]), "g": np.array(col["g"], dtype=bool), "cote": np.array(col["cote"])}
    return tab, infos


def _valeurs(cat: str, g: np.ndarray, cote: np.ndarray) -> np.ndarray:
    """Ce que l'objectif mesure, pari par pari : 1/0 (réussite) ou gain à mise égale (rendement)."""
    return np.where(g, cote - 1.0, -1.0) if objectif(cat) == "rendement" else g.astype(float)


# --- Étape 1 : recherche exhaustive ----------------------------------------------------------------------------------
def chercher(cat: str, n: np.ndarray, d: np.ndarray, h: np.ndarray, v: np.ndarray, moitie: np.ndarray) -> tuple[dict | None, int]:
    """Évalue toutes les configurations (n_min, marge défavorable, marge habituelle) sur l'apprentissage SEULEMENT.
    Admissible : sélection non vide, non retenus non vides, apport (sélection moins non retenus) > 0 dans CHAQUE moitié chronologique.
    Retenue : la plus grande statistique z sélection / non retenus. Renvoie (configuration, nombre de configurations évaluées)."""
    N = len(v)
    if N < 4 or moitie.all() or (~moitie).all():
        return None, 0
    best, evaluees = None, 0
    tot_s, tot_q = v.sum(), (v * v).sum()
    tds, ths = np.unique(d), np.unique(h)
    for nm in N_MIN:
        mn = n >= nm
        for td in tds:
            m1 = mn & (d >= td)
            if not m1.any():
                continue
            for th in ths:
                if nm == N_MIN[0] and td == tds[0] and th == ths[0]:
                    continue                                       # « tout prendre » : la référence, pas une configuration
                evaluees += 1
                sel = m1 & (h >= th)
                k = int(sel.sum())
                if k == 0 or k == N:
                    continue
                ok = True
                for half in (moitie, ~moitie):
                    s1, s0 = sel & half, (~sel) & half
                    if not s1.any() or not s0.any() or v[s1].mean() <= v[s0].mean():
                        ok = False
                        break
                if not ok:
                    continue
                s = v[sel].sum()
                q = (v[sel] ** 2).sum()
                m_s, m_r = s / k, (tot_s - s) / (N - k)
                var_s = max(q / k - m_s ** 2, 0.0)
                var_r = max((tot_q - q) / (N - k) - m_r ** 2, 0.0)
                if objectif(cat) == "reussite":
                    pp = tot_s / N
                    se = math.sqrt(max(pp * (1 - pp), 1e-12) * (1 / k + 1 / (N - k)))
                else:
                    se = math.sqrt(var_s / k + var_r / (N - k) + 1e-12)
                z = (m_s - m_r) / se
                if best is None or z > best["z"]:
                    best = {"n_min": nm, "marge_defavorable": float(td), "marge_habituelle": float(th), "z": round(z, 3),
                            "paris": k, "valeur": round(m_s, 4), "valeur_non_retenus": round(m_r, 4)}
    return best, evaluees


# --- Tests exacts et contrôle des faux positifs ------------------------------------------------------------------------
def p_exacte(cat: str, v: np.ndarray, sel: np.ndarray, g: np.ndarray, tirages: int = 10000) -> float:
    """p unilatérale : sélection meilleure que les paris NON retenus. Réussite : Fisher (hypergéométrique). Rendement : permutation, graine 0."""
    k, N = int(sel.sum()), len(v)
    if k == 0 or k == N:
        return 1.0
    if objectif(cat) == "reussite":
        w1, W = int(g[sel].sum()), int(g.sum())
        return float(hypergeom.sf(w1 - 1, N, W, k))
    rng = np.random.default_rng(0)
    obs = v[sel].mean() - v[~sel].mean()
    tot, cnt = v.sum(), 0
    for _ in range(tirages // 1000):
        idx = np.argsort(rng.random((1000, N)), axis=1)[:, :k]
        ms = v[idx].sum(axis=1)
        cnt += int(((ms / k) - (tot - ms) / (N - k) >= obs - 1e-12).sum())
    return (cnt + 1) / (tirages + 1)


def benjamini_hochberg(pvals: dict, q: float = 0.05) -> set:
    return R.benjamini_hochberg(pvals, q)


def q_valeurs(pvals: dict) -> dict:
    """p-valeurs ajustées de Benjamini-Hochberg (q-valeurs) : une hypothèse est retenue à 5 % si sa q-valeur <= 0,05."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, mini = len(items), {}, 1.0
    for i in range(m, 0, -1):
        k, pv = items[i - 1]
        mini = min(mini, pv * m / i)
        out[k] = round(min(mini, 1.0), 6)
    return out


def evaluer(cat: str, cfg: dict, col: dict, masque: np.ndarray) -> dict | None:
    """Applique une configuration GELÉE aux lignes d'une étape. Ne lit l'issue que pour mesurer, jamais pour choisir."""
    if not masque.any():
        return None
    n, d, h, g, cote = col["n"][masque], col["d"][masque], col["h"][masque], col["g"][masque], col["cote"][masque]
    jour = col["jour"][masque]
    v = _valeurs(cat, g, cote)
    sel = (n >= cfg["n_min"]) & (d >= cfg["marge_defavorable"]) & (h >= cfg["marge_habituelle"])
    k = int(sel.sum())
    if k == 0:
        return {"paris": 0, "references": int(len(v))}
    ordre = np.argsort(jour[sel], kind="stable")
    js = jour[sel][ordre]
    coupe = js[k // 2]
    moities = []
    for half in (jour < coupe, jour >= coupe):
        s1, s0 = sel & half, (~sel) & half
        moities.append(round(float(v[s1].mean() - v[s0].mean()), 4) if s1.any() and s0.any() else None)
    avec = ~np.isnan(cote[sel])
    out = {"paris": k, "gagnes": int(g[sel].sum()), "perdus": int(k - g[sel].sum()), "reussite": round(float(g[sel].mean()), 4),
           "references": int(len(v)), "reussite_sans_filtre": round(float(g.mean()), 4),
           "reussite_non_retenus": round(float(g[~sel].mean()), 4) if (~sel).any() else None,
           "apport": round(float(v[sel].mean() - v.mean()), 4), "ecart_non_retenus": round(float(v[sel].mean() - v[~sel].mean()), 4) if (~sel).any() else None,
           "apport_par_moitie": moities, "p_exacte": round(p_exacte(cat, v, sel, g), 6)}
    if avec.all():
        gn = float(np.where(g[sel], cote[sel] - 1, -1).sum())
        ta = ~np.isnan(cote)
        out |= {"cote_moyenne": round(float(cote[sel].mean()), 3), "gain_net": round(gn, 3), "rendement": round(gn / k, 4),
                "rendement_sans_filtre": round(float(np.where(g[ta], cote[ta] - 1, -1).mean()), 4)}
    elif not avec.any():
        out |= {"valeur_financiere": "non évaluable (cotes absentes)"}
    else:                                                          # cotes partielles : finances mesurées sur les seuls paris qui ont une vraie cote
        cs, gs = cote[sel][avec], g[sel][avec]
        tout_avec = ~np.isnan(cote)
        gn = float(np.where(gs, cs - 1, -1).sum())
        out |= {"valeur_financiere": f"partielle : {int(avec.sum())} paris sur {k} avec cote",
                "sur_paris_avec_cote": {"paris": int(avec.sum()), "reussite": round(float(gs.mean()), 4), "cote_moyenne": round(float(cs.mean()), 3),
                                        "gain_net": round(gn, 3), "rendement": round(gn / int(avec.sum()), 4),
                                        "rendement_sans_filtre": round(float(np.where(g[tout_avec], cote[tout_avec] - 1, -1).mean()), 4)}}
    sem: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for j, w in zip(jour[sel], g[sel]):
        sem[R._semaine(str(j))][0] += int(w)
        sem[R._semaine(str(j))][1] += 1
    out["par_semaine"] = {s: {"paris": c[1], "gagnes": c[0]} for s, c in sorted(sem.items())}
    return out


# --- Campagne ----------------------------------------------------------------------------------------------------------
DEBUT_VALIDATION = "2026-07-01"   # 24/10/2026 : coupe par DATE (début de la saison européenne 2026-27). L'ancienne coupe par étiquette de saison
                                  # (2526 / 2627) mêlait les dates : 1 093 matchs « 2627 » des championnats sur l'année civile (Argentine, Brésil,
                                  # États-Unis, Chine, Irlande, Norvège, Suède, Finlande) étaient datés AVANT la fin de l'apprentissage (01/06/2026).


def etape_fd(m: dict) -> str | None:
    """Découpage strictement chronologique par la date du match : apprentissage avant le 01/07/2026, validation du 01/07 au 27/09/2026,
    rien à partir du 28/09/2026 (période de l'archive ARCHETYPE, test final)."""
    if m["jour"] >= DEBUT_ARCHETYPE:
        return None
    return "apprentissage" if m["jour"] < DEBUT_VALIDATION else "validation"


def campagne(tab: dict, infos: dict) -> dict:
    fiches, total_cfg = [], 0
    for (lib, cat), col in sorted(tab.items()):
        ap = col["etape"] == "apprentissage"
        fiche = {"marche": lib, "famille": infos[lib]["famille"], "categorie": cat, "objectif": objectif(cat),
                 "lectures": {e: int((col["etape"] == e).sum()) for e in ETAPES}}
        if ap.sum() >= 4:
            ja = col["jour"][ap]
            med = np.sort(ja)[len(ja) // 2]
            cfg, nb = chercher(cat, col["n"][ap], col["d"][ap], col["h"][ap], _valeurs(cat, col["g"][ap], col["cote"][ap]), ja < med)
            total_cfg += nb
        else:
            cfg, nb = None, 0
        fiche["configurations_evaluees"] = nb
        fiche["configuration"] = cfg
        if cfg:
            for e in ETAPES:
                fiche[e] = evaluer(cat, cfg, col, col["etape"] == e)
        fiches.append(fiche)
    # Étape 2 : validation. Benjamini-Hochberg sur TOUTES les hypothèses de l'étape (toute configuration retenue à l'apprentissage),
    # sans présélection sur les résultats de validation ; une configuration sans pari en validation compte avec p = 1.
    pv = {i: ((f.get("validation") or {}).get("p_exacte", 1.0) if (f.get("validation") or {}).get("paris") else 1.0)
          for i, f in enumerate(fiches) if f["configuration"]}
    qv = q_valeurs(pv)
    sig_v = benjamini_hochberg(pv)
    cand = {i for i in sig_v if (va := fiches[i]["validation"])["apport"] > 0
            and None not in va["apport_par_moitie"] and min(va["apport_par_moitie"]) > 0}   # exigence supplémentaire APRÈS la correction : ne fait que restreindre
    # Étape 3 : test final. Benjamini-Hochberg sur TOUTES les candidates, qu'elles aient ou non un apport positif au test final (p = 1 si aucun pari).
    pf = {i: ((fiches[i].get("final") or {}).get("p_exacte", 1.0) if (fiches[i].get("final") or {}).get("paris") else 1.0) for i in cand}
    qf = q_valeurs(pf)
    conf = benjamini_hochberg(pf)
    for i, f in enumerate(fiches):
        fi = f.get("final") or {}
        if i in qv:
            f["q_validation"] = qv[i]
        if i in qf:
            f["q_final"] = qf[i]
        if not f["configuration"]:
            f["statut"], f["raison"] = "insuffisamment documenté", "aucune configuration admissible à l'apprentissage"
        elif not (f.get("validation") or {}).get("paris"):
            f["statut"], f["raison"] = "insuffisamment documenté", "aucun pari en validation"
        elif i not in cand:
            f["statut"], f["raison"] = "écarté en validation", ("non significatif après correction sur toutes les hypothèses de validation" if i not in sig_v
                                                                 else "significatif mais apport non positif dans les deux moitiés")
        elif not fi.get("paris"):
            f["statut"], f["raison"] = "insuffisamment documenté", "aucun pari au test final"
        elif i in conf and fi["apport"] > 0:
            f["statut"], f["raison"] = "exploitable", "confirmé au test final, significatif après correction sur toutes les candidates"
        elif fi["apport"] > 0:
            f["statut"], f["raison"] = "prometteur", "apport positif au test final, non significatif après correction"
        else:
            f["statut"], f["raison"] = "non confirmé", "aucun apport au test final"
        if f["statut"] == "exploitable":
            fin = fi if "gain_net" in fi else fi.get("sur_paris_avec_cote")
            f["rentable_au_test_final"] = (fin["gain_net"] > 0) if fin else "non évaluable"
    sig = {}                                                       # marchés qui sont le MÊME événement (ex. 1N = handicap +0,5 domicile)
    for cle, lib, pred, _ in R.catalogue():
        sig.setdefault(tuple(bool(pred(a, b)) for a in range(11) for b in range(11)), []).append(lib)
    for f in fiches:
        for libs in sig.values():
            if f["marche"] in libs and len(libs) > 1:
                f["meme_evenement_que"] = [x for x in libs if x != f["marche"]]
    fiches.sort(key=lambda f: (R.FAMILLES.index(f["famille"]), f["marche"], CATEGORIES.index(f["categorie"])))
    return {"fiches": fiches, "configurations_evaluees": total_cfg, "hypotheses_validation": len(pv), "candidates_validation": len(cand), "tests_finaux": len(pf)}


def preuve_decoupage(tab: dict) -> dict:
    """Dates réelles et identifiants de chaque étape, tirés des lectures effectivement utilisées."""
    ids, jours = defaultdict(set), defaultdict(set)
    for col in tab.values():
        for i, e, j in zip(col["id"], col["etape"], col["jour"]):
            ids[str(e)].add(i)
            jours[str(e)].add(str(j))
    out = {e: {"matchs": len(ids[e]), "premier_jour": min(jours[e]), "dernier_jour": max(jours[e])} for e in ETAPES if ids[e]}
    out["identifiants_communs"] = {"apprentissage/validation": len(ids["apprentissage"] & ids["validation"]),
                                   "apprentissage/final": len(ids["apprentissage"] & ids["final"]), "validation/final": len(ids["validation"] & ids["final"])}
    out["strictement_chronologique"] = (max(jours["apprentissage"]) < min(jours["validation"]) and max(jours["validation"]) < min(jours["final"]))
    return out


def comparer(fiches: list[dict], chemin_git: str = "2dc8e31:docs/alpha_campagne.json") -> dict | None:
    """Comparaison avec la campagne 2dc8e31 (ancien découpage, ancienne correction) : configuration et statut, marché par marché."""
    import subprocess
    try:
        old = json.loads(subprocess.run(["git", "show", chemin_git], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    except Exception:
        return None
    anc = {(f["marche"], f["categorie"]): f for f in old["fiches"]}
    changements, anciens_exploitables = [], []
    for f in fiches:
        o = anc.get((f["marche"], f["categorie"]))
        if not o:
            continue
        f["avant_2dc8e31"] = {"statut": o["statut"], "configuration": o["configuration"]}
        if o["statut"] != f["statut"]:
            changements.append({"marche": f["marche"], "categorie": f["categorie"], "avant": o["statut"], "apres": f["statut"]})
        if o["statut"] == "exploitable":
            fi = f.get("final") or {}
            anciens_exploitables.append({"marche": f["marche"], "categorie": f["categorie"], "statut_apres": f["statut"], "raison": f["raison"],
                                         "configuration_avant": o["configuration"], "configuration_apres": f["configuration"],
                                         "validation_apres": {k: (f.get("validation") or {}).get(k) for k in ("paris", "reussite", "reussite_sans_filtre", "apport", "p_exacte")},
                                         "q_validation": f.get("q_validation"),
                                         "final_apres": {k: fi.get(k) for k in ("paris", "reussite", "reussite_sans_filtre", "apport", "p_exacte")},
                                         "q_final": f.get("q_final")})
    st_old = defaultdict(int)
    for o in old["fiches"]:
        st_old[o["statut"]] += 1
    return {"statuts_avant": dict(st_old), "changements_de_statut": changements, "anciens_exploitables_un_par_un": anciens_exploitables}


def main() -> None:
    R.REJETS_COTES.clear()
    fd = R.charger_bloc()
    arch = R.charger_archive_archetype()
    tab, infos = lectures(fd, etape_fd)
    tab2, _ = lectures(arch, lambda m: "final")
    for k, col in tab2.items():                                   # fusion des colonnes par (marché, catégorie)
        if k in tab:
            for c in col:
                tab[k][c] = (tab[k][c] + col[c]) if c == "id" else np.concatenate([tab[k][c], col[c]])
        else:
            tab[k] = col
    res = campagne(tab, infos)
    preuve = preuve_decoupage(tab)
    comp = comparer(res["fiches"])
    statuts = defaultdict(int)
    for f in res["fiches"]:
        statuts[f["statut"]] += 1
    par_fam = {}
    for fam in R.FAMILLES:
        st = defaultdict(int)
        for f in res["fiches"]:
            if f["famille"] == fam:
                st[f["statut"]] += 1
        par_fam[fam] = dict(st)
    nb = lambda e: len({i for col in tab.values() for i, x in zip(col["id"], col["etape"]) if x == e})
    gele = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rapport = {"gele_le": gele, "methode": __doc__.split("Usage")[0].strip(),
               "donnees": {"apprentissage": {"source": f"Football-Data, matchs avant le {DEBUT_VALIDATION}", "matchs_analysables": nb("apprentissage")},
                           "validation": {"source": f"Football-Data, matchs du {DEBUT_VALIDATION} au jour précédant le {DEBUT_ARCHETYPE}", "matchs_analysables": nb("validation")},
                           "final": {"source": "archive ARCHETYPE, cotes BetPawa avant le coup d'envoi", "matchs_analysables": nb("final"),
                                     "ecartes_cotes_non_anterieures": len(R.REJETS_COTES)},
                           "cotes_combos": "aucune archivée : réussite seule, valeur financière non évaluable"},
               "preuve_decoupage": preuve, "comparaison_2dc8e31": comp,
               "configurations_evaluees": res["configurations_evaluees"], "hypotheses_validation": res["hypotheses_validation"],
               "candidates_apres_validation": res["candidates_validation"],
               "tests_finaux": res["tests_finaux"], "statuts": dict(statuts), "statuts_par_famille": par_fam, "fiches": res["fiches"]}
    RAPPORT.write_text(json.dumps(rapport, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    def _export(f):
        fi = f.get("final") or {}
        fin = fi if "gain_net" in fi else (fi.get("sur_paris_avec_cote") or {})
        return {**f["configuration"], "marche": f["marche"], "categorie": f["categorie"], "statut": f["statut"], "q_final": f.get("q_final"),
                "test_final": {"paris": fi.get("paris"), "gagnes": fi.get("gagnes"), "reussite": fi.get("reussite"), "reussite_sans_filtre": fi.get("reussite_sans_filtre"),
                               "rendement": fin.get("rendement"), "paris_avec_cote": fin.get("paris", fi.get("paris") if "gain_net" in fi else None)},
                "meme_evenement_que": f.get("meme_evenement_que", [])}
    REGLES.write_text(json.dumps({"gele_le": gele, "statut": "configurations apprises sur Football-Data (avant le 01/07/2026) des marchés exploitables ou prometteurs ; "
                                                             "la production (alpha_serie/calibrees.py) n'utilise que les exploitables",
                                  "regles": {f"{f['marche']} | {f['categorie']}": _export(f) for f in res["fiches"] if f["statut"] in ("exploitable", "prometteur")}},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONNEES:", json.dumps(rapport["donnees"], ensure_ascii=False))
    print("PREUVE DECOUPAGE:", json.dumps(preuve, ensure_ascii=False))
    print("CONFIGURATIONS EVALUEES:", res["configurations_evaluees"], "| hypothèses en validation:", res["hypotheses_validation"],
          "| candidates après validation:", res["candidates_validation"], "| tests finaux:", res["tests_finaux"])
    if comp:
        print("AVANT (2dc8e31):", comp["statuts_avant"])
        for x in comp["anciens_exploitables_un_par_un"]:
            print(f"  ancien exploitable -> {x['statut_apres']:<26} {x['marche']:<44} {x['categorie']:<6} q_val {x['q_validation']} q_final {x['q_final']} "
                  f"final {x['final_apres']}")
    print("STATUTS:", dict(statuts))
    for f in res["fiches"]:
        if f["statut"] in ("exploitable", "prometteur", "non confirmé"):
            v, fi = f["validation"], f["final"]
            print(f"  {f['statut']:<13} {f['famille']:<15} {f['marche']:<44} {f['categorie']:<6} cfg n>={f['configuration']['n_min']} "
                  f"d>={f['configuration']['marge_defavorable']} h>={f['configuration']['marge_habituelle']} | val {v['paris']} {v['reussite']} "
                  f"apport {v['apport']} p {v['p_exacte']} | final {fi['paris']} {fi['reussite']} (sans filtre {fi['reussite_sans_filtre']}) "
                  f"apport {fi['apport']} p {fi['p_exacte']} gain {fi.get('gain_net', (fi.get('sur_paris_avec_cote') or {}).get('gain_net'))} "
                  f"rend {fi.get('rendement', (fi.get('sur_paris_avec_cote') or {}).get('rendement'))} (sans filtre {(fi.get('sur_paris_avec_cote') or {}).get('rendement_sans_filtre')})")


if __name__ == "__main__":
    main()
