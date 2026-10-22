"""Règles pures de l'onglet « Meilleures sélections » (22/10/2026). Aucune lecture de fichier ici : tout est testable.

Même base que l'étude des indicateurs affichés : un PARI = dict(moteur "V2"|"V3", date, match_id, marche, indice + sur (indice affiché x/sur),
pct (pourcentage AFFICHÉ sur le site, entier), etoiles (étoiles affichées), gagne 0|1). Ni cote ni rendement : seule la réussite réelle compte.

Principe : le classement se recalibre seul. Une RÈGLE = « indice affiché >= i ET pourcentage affiché >= p ET étoiles affichées >= e ».
À chaque recalibrage, toutes les règles possibles sont testées par moteur ; on retient celle dont la réussite garantie est la plus haute (borne basse de l'intervalle à 95 % de la réussite).
  - i : les niveaux de l'indice (0, 1/4, 1/2, 3/4, 1) ; p : les paliers du pourcentage affiché (0, 60, 70, 80, 90, les tranches des tableaux de
    l'étude) ; e : les niveaux d'étoiles du moteur (V2 : 1 à 3, V3 : 1 à 4) ;
  - la référence d'une règle = la réussite de tous les autres paris du même moteur ; le test = probabilité (test exact de Fisher) d'obtenir au
    moins autant de paris gagnés dans la règle par pur hasard ; la règle doit aussi dépasser la référence dans CHAQUE moitié
    chronologique (précédent alpha_serie) ;
  - les seuils de probabilité viennent du NOMBRE de règles possibles (m, fixé par la structure et non par la quantité de données) :
    « confirmé » = risque global de fausse admission d'au plus 5 % (p <= 0,05/m) ; « en observation » = au plus une fausse admission
    attendue sur l'ensemble (p <= 1/m).
Quand les données changent, la règle retenue change toute seule.
"""
from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

PERIODE_JOURS = 7  # recalibrage hebdomadaire (demande de Patrick)
ALPHA = 0.05       # niveau de confiance 95 %, le même que les intervalles des tableaux de l'étude
MOTEURS = ("V2", "V3")
NIVEAUX_INDICE = (0.0, 0.25, 0.5, 0.75, 1.0)    # indice affiché / sur : 4 scénarios (deux équipes) ou 2 (une équipe)
PALIERS_POURCENTAGE = (0, 60, 70, 80, 90)       # tranches du pourcentage affiché, celles des tableaux de l'étude
ETOILES_MAX = {"V2": 3, "V3": 4}                # V2 : catégories C/B/A ; V3 : 4 paliers de taille d'échantillon


def nb_tests_possibles() -> int:
    """Nombre de règles possibles, fixé par la structure (niveaux d'indice x paliers de pourcentage x niveaux d'étoiles, par moteur)."""
    return sum(len(NIVEAUX_INDICE) * len(PALIERS_POURCENTAGE) * e for e in ETOILES_MAX.values())


def famille(marche: str | None) -> str | None:
    """Famille d'un marché (nom V3), utilisée pour ne compter qu'un pari par match et par famille. None si le marché n'est pas reconnu."""
    s = str(marche or "")
    if re.fullmatch(r"under_\d_\d", s):
        return "total_moins"
    if re.fullmatch(r"over_\d_\d", s):
        return "total_plus"
    if re.fullmatch(r"(home|away)_under_\d_\d", s):
        return "equipe_moins"
    if re.fullmatch(r"(home|away)_over_\d_\d", s):
        return "equipe_plus"
    if s.startswith("handicap_"):
        return "handicap"
    if s.startswith("dc_"):
        return "double_chance"
    if s in ("1x2_1", "1x2_2"):
        return "victoire"
    if s == "1x2_x":
        return "nul"
    if s == "btts_yes":
        return "btts_oui"
    if s == "btts_no":
        return "btts_non"
    if s.startswith("clean_"):
        return "cage"
    return None


def niveau(p: Mapping[str, Any]) -> float | None:
    """Part des scénarios validés (indice affiché / sur), entre 0 et 1. None si pas d'indice."""
    i, s = p.get("indice"), p.get("sur")
    if not isinstance(i, int) or not isinstance(s, int) or s <= 0:
        return None
    return i / s


def _jour(p: Mapping[str, Any]) -> str:
    return str(p.get("date") or "")[:10]


def _utilisable(p: Mapping[str, Any]) -> bool:
    return (famille(p.get("marche")) is not None and niveau(p) is not None and isinstance(p.get("pct"), int)
            and isinstance(p.get("etoiles"), int) and p.get("gagne") in (0, 1, True, False))


def version_courante(paris: Sequence[Mapping[str, Any]], moteur: str = "V2") -> str | None:
    """Version du moteur qui produit les paris les plus récents (celle d'aujourd'hui). None si les paris ne portent aucune version."""
    vus = [(_jour(p), str(p["version"])) for p in paris if p.get("moteur") == moteur and p.get("version")]
    return max(vus)[1] if vus else None


def garde_version_courante(paris: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Retire les paris V2 d'une version de moteur plus ancienne que celle en production : seuls comptent les paris que ce moteur produira.
    V3 et les paris sans information de version restent. Quand une nouvelle version sort, l'échantillon V2 repart donc de ses propres paris."""
    v = version_courante(paris, "V2")
    return [p for p in paris if p.get("moteur") != "V2" or not p.get("version") or v is None or str(p["version"]) == v]


def un_pari_par_match_et_famille(paris: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Les paris d'un même match ne sont pas indépendants : pour un même (moteur, match, famille) on garde UN pari, celui de plus forte
    pourcentage affiché (connu avant le match, donc sans lien avec le résultat). Sans identifiant de match, aucun regroupement."""
    meilleurs: dict[tuple, Mapping[str, Any]] = {}
    sans_id = []

    def rang(p):
        return (-(p.get("pct") or 0), str(p.get("marche")))

    for p in paris:
        f = famille(p.get("marche"))
        if p.get("match_id") in (None, "") or f is None:
            sans_id.append(p)
            continue
        cle = (p.get("moteur"), p["match_id"], f)
        if cle not in meilleurs or rang(p) < rang(meilleurs[cle]):
            meilleurs[cle] = p
    return sans_id + list(meilleurs.values())


def queue_binomiale(k: int, n: int, p: float) -> float:
    """P(X >= k) pour X ~ Binomiale(n, p), calcul exact (somme en logarithmes). p est borné à ]0, 1[."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    p = min(max(p, 1e-12), 1 - 1e-12)
    lp, lq = math.log(p), math.log(1 - p)
    termes = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq for i in range(k, n + 1)]
    m = max(termes)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in termes))


def queue_hypergeometrique(g: int, n: int, k_total: int, n_total: int) -> float:
    """Test exact de Fisher (unilatéral) : P(X >= g) quand on tire n paris parmi n_total dont k_total gagnés, au hasard pur. Tient compte du
    bruit des DEUX côtés (l'ensemble testé ET les autres paris), contrairement à une référence supposée connue."""
    if g <= 0:
        return 1.0
    haut = min(n, k_total)
    if g > haut or n - g > n_total - k_total:
        return 0.0

    def lc(a, b):
        return math.lgamma(a + 1) - math.lgamma(b + 1) - math.lgamma(a - b + 1)

    termes = [lc(k_total, i) + lc(n_total - k_total, n - i) - lc(n_total, n) for i in range(g, haut + 1) if n - i <= n_total - k_total]
    m = max(termes)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in termes))


def borne_basse(gagnes: int, n: int, z: float = 1.96) -> float:
    """Borne basse de l'intervalle de Wilson à 95 % de la réussite (le même intervalle que les tableaux de l'étude)."""
    if n <= 0:
        return 0.0
    p = gagnes / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - marge) / d


def _taux(paris: Sequence[Mapping[str, Any]]) -> float | None:
    return sum(int(bool(p["gagne"])) for p in paris) / len(paris) if paris else None


def statistiques(paris: Sequence[Mapping[str, Any]], autres: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """n, gagnés, réussite observée ; avec les AUTRES paris du moteur : référence (leur réussite) et p = probabilité (test exact de Fisher)
    d'obtenir au moins autant de gagnés dans cet ensemble par pur hasard."""
    n = len(paris)
    g = sum(int(bool(p["gagne"])) for p in paris)
    if not n or not autres:
        return {"n": n, "gagnes": g, "reussite": g / n if n else None, "base": None, "p": 1.0}
    ga = sum(int(bool(p["gagne"])) for p in autres)
    return {"n": n, "gagnes": g, "reussite": g / n, "base": ga / len(autres),
            "p": queue_hypergeometrique(g, n, g + ga, n + len(autres))}


def _moitiés(paris: Sequence[Mapping[str, Any]]) -> tuple[list, list]:
    """Moitiés chronologiques : jours distincts triés, coupe au milieu (un jour n'est jamais coupé en deux)."""
    jours = sorted({_jour(p) for p in paris})
    if len(jours) < 2:
        return list(paris), []
    coupe = jours[len(jours) // 2]
    return [p for p in paris if _jour(p) < coupe], [p for p in paris if _jour(p) >= coupe]


def _tient_dans_le_temps(paris: Sequence[Mapping[str, Any]], reference: float) -> bool:
    premiere, seconde = _moitiés(paris)
    if not premiere or not seconde:
        return False
    return all(_taux(moitie) >= reference for moitie in (premiere, seconde))


def dans_la_regle(p: Mapping[str, Any], r: Mapping[str, Any]) -> bool:
    n = niveau(p)
    return (p.get("moteur") == r["moteur"] and n is not None and n >= r["indice_min"] - 1e-12
            and (p.get("pct") or 0) >= r["pct_min"] and (p.get("etoiles") or 0) >= r["etoiles_min"])


def candidats(paris: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Toutes les règles testées (moteur, indice minimal, pourcentage minimal, étoiles minimales) qui retiennent au moins un pari."""
    utiles = [p for p in paris if _utilisable(p)]
    out = []
    for moteur in MOTEURS:
        lot = [p for p in utiles if p["moteur"] == moteur]
        for i in NIVEAUX_INDICE:
            for pc in PALIERS_POURCENTAGE:
                for e in range(1, ETOILES_MAX[moteur] + 1):
                    r = {"moteur": moteur, "indice_min": i, "pct_min": pc, "etoiles_min": e}
                    ens = [p for p in lot if dans_la_regle(p, r)]
                    if ens:
                        out.append({**r, "paris": ens})
    return out


def _autres(tous_du_moteur: Sequence[Mapping[str, Any]], ens: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Tous les AUTRES paris du moteur (l'ensemble testé n'entre pas dans sa propre référence)."""
    ids = {id(p) for p in ens}
    return [p for p in tous_du_moteur if id(p) not in ids]


CLES_REGLE = ("moteur", "indice_min", "pct_min", "etoiles_min")


def calibrer(paris: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Recalibrage complet à partir des seuls paris fournis (déjà résolus). Retourne la règle retenue par moteur et le détail des tests."""
    paris = un_pari_par_match_et_famille([p for p in paris if _utilisable(p)])
    par_moteur: dict[str, list] = {}
    for p in paris:
        par_moteur.setdefault(p["moteur"], []).append(p)
    cands = candidats(paris)
    m = nb_tests_possibles()
    seuil_confirme = ALPHA / m          # risque global de fausse admission <= 5 % sur l'ensemble des règles testées
    seuil_observation = 1.0 / m         # au plus une fausse admission attendue sur l'ensemble
    tests = []
    for c in cands:
        autres = _autres(par_moteur[c["moteur"]], c["paris"])
        if not autres:                       # aucun autre pari du moteur : rien à comparer
            continue
        s = statistiques(c["paris"], autres)
        ref = s["base"]
        stable = _tient_dans_le_temps(c["paris"], ref)
        ok = s["reussite"] > ref and stable
        statut = "confirme" if ok and s["p"] <= seuil_confirme else "observation" if ok and s["p"] <= seuil_observation else "rejete"
        tests.append({**{k: c[k] for k in CLES_REGLE}, "statut": statut, "stable_dans_le_temps": stable, "borne_basse": borne_basse(s["gagnes"], s["n"]), **s})
    admis = []
    for moteur in MOTEURS:
        propres = [t for t in tests if t["moteur"] == moteur]
        for statut in ("confirme", "observation"):
            ok = [t for t in propres if t["statut"] == statut]
            if ok:
                admis.append(max(ok, key=lambda t: (t["borne_basse"], t["n"], -t["indice_min"], -t["pct_min"], -t["etoiles_min"])))   # meilleure réussite garantie ; à égalité, critères les moins restrictifs
                break
    return {"m_tests": m, "nb_tests_realises": len(cands), "seuil_confirme": seuil_confirme, "seuil_observation": seuil_observation,
            "nb_paris": len(paris), "groupes": admis, "tests": tests}


def groupe_du_pari(pari: Mapping[str, Any], groupes: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Règle retenue qui contient ce pari (une seule par moteur)."""
    ok = [g for g in groupes if dans_la_regle(pari, g)]
    return sorted(ok, key=lambda g: (g["statut"] != "confirme", g["p"]))[0] if ok else None


def classer(selections: Sequence[Mapping[str, Any]], groupes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Garde les sélections du jour qui remplissent la règle retenue de leur moteur. Tri : confirmés d'abord, puis pourcentage affiché,
    indice affiché, étoiles affichées."""
    out = []
    for s in selections:
        g = groupe_du_pari(s, groupes)
        if g is not None:
            out.append({**s, "groupe": {k: g[k] for k in (*CLES_REGLE, "statut", "n", "gagnes", "reussite", "borne_basse", "p")}})
    out.sort(key=lambda x: (x["groupe"]["statut"] != "confirme", -(x.get("pct") or 0), -(niveau(x) or 0.0), -(x.get("etoiles") or 0)))
    for i, x in enumerate(out, 1):
        x["rang"] = i
    return out


def recalibrage_du(historique: Sequence[Mapping[str, Any]], jour: str) -> bool:
    """Vrai si un recalibrage est dû : aucun jusqu'ici, ou le dernier date d'au moins PERIODE_JOURS jours."""
    if not historique:
        return True
    dernier = max(str(h["calibre_le"]) for h in historique)
    return date.fromisoformat(jour) - date.fromisoformat(dernier) >= timedelta(days=PERIODE_JOURS)


def photographie(paris: Sequence[Mapping[str, Any]], jour: str) -> dict[str, Any]:
    """Recalibre sur les paris STRICTEMENT antérieurs à `jour` et retourne l'instantané à archiver."""
    passes = [p for p in paris if _jour(p) < jour and _utilisable(p)]
    c = calibrer(passes)
    return {"calibre_le": jour, "nb_paris": len(passes), "m_tests": c["m_tests"], "seuil_confirme": c["seuil_confirme"],
            "seuil_observation": c["seuil_observation"], "groupes": c["groupes"]}


def _par_moteur(retenus: dict[str, list], autres: dict[str, list]) -> dict[str, dict[str, Any]]:
    """Statistiques par moteur des paris retenus, avec la réussite des paris non retenus du même moteur en référence interne."""
    return {m: statistiques(v, autres.get(m) or []) for m, v in retenus.items() if v}


def bilan_historique(paris: Sequence[Mapping[str, Any]], groupes: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Résultat, par moteur, des paris passés qui remplissent la règle retenue (chaque pari compté une fois). Mesure dans l'échantillon :
    ces paris ont servi à choisir la règle, le chiffre est donc flatteur."""
    utiles = un_pari_par_match_et_famille([p for p in paris if _utilisable(p)])
    dedans: dict[str, list] = {}
    dehors: dict[str, list] = {}
    for p in utiles:
        (dedans if groupe_du_pari(p, groupes) is not None else dehors).setdefault(p["moteur"], []).append(p)
    return _par_moteur(dedans, dehors)


def bilan_hors_echantillon(paris: Sequence[Mapping[str, Any]], historique: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Résultat, par moteur, des paris joués APRÈS le recalibrage qui les aurait retenus (le dernier instantané daté d'avant le pari).
    C'est la seule mesure non biaisée : aucun de ces paris n'a servi à choisir sa règle."""
    snaps = sorted(historique, key=lambda h: h["calibre_le"])
    dedans: dict[str, list] = {}
    dehors: dict[str, list] = {}
    for p in paris:
        if not _utilisable(p):
            continue
        actifs = [h for h in snaps if h["calibre_le"] <= _jour(p)]
        if not actifs:
            continue
        (dedans if groupe_du_pari(p, actifs[-1]["groupes"]) is not None else dehors).setdefault(p["moteur"], []).append(p)
    return _par_moteur(dedans, dehors)


def rejeu(paris: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rejoue l'historique comme si le recalibrage hebdomadaire avait toujours tourné (marche avant, sans regarder l'avenir)."""
    jours = sorted({_jour(p) for p in paris if _utilisable(p)})
    if len(jours) <= PERIODE_JOURS:
        return {"instantanes": [], "bilan": {}}
    debut = date.fromisoformat(jours[0]) + timedelta(days=PERIODE_JOURS)
    fin = date.fromisoformat(jours[-1])
    historique, j = [], debut
    while j <= fin:
        historique.append(photographie(paris, j.isoformat()))
        j += timedelta(days=PERIODE_JOURS)
    return {"instantanes": historique, "bilan": bilan_hors_echantillon(paris, historique)}
