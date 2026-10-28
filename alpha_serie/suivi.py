"""Suivi du moteur alpha « séries » en production : pronostics GELÉS avant le coup d'envoi, résultats, bilan et données de la page.

- geler()     : pour chaque match futur (coup d'envoi > maintenant) analysable, ajoute UNE ligne « pronostic » horodatée au journal en AJOUT SEUL
                (les trois onglets avec cotes, jamais modifiée). Un match déjà gelé n'est jamais regelé ; un match dont le coup d'envoi est passé
                n'est jamais gelé (aucun pronostic a posteriori).
- resultats() : pour les matchs gelés dont le score est connu, ajoute une ligne « resultat » (gagné / perdu par sélection).
- bilan()     : réussite et rendement calculés UNIQUEMENT sur les pronostics gelés avant le match (le vrai test hors échantillon).
- page()      : `data/alpha_serie/pronostics.json`, lu tel quel par `pronostics_comportement.html` (le navigateur ne calcule rien).
Quatrième onglet « calibrees » (24/10/2026) : sélections des règles exploitables de la campagne d'optimisation (`calibrees.py`), gelées,
réglées et comptées dans le bilan comme les trois autres onglets, sans rien changer à ceux-ci.
Aucun lien avec V2, V3, V2R, Europe, le Journal ni le générateur de tickets. Usage : python -m alpha_serie.suivi [pipeline|geler|resultats|bilan|page]
"""
from __future__ import annotations

import glob
import gzip
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import calibrees, coeur, palier2, parametres as P, solidite as SOL, tickets
from .marches import test_du_marche

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "alpha_serie"
JOURNAL = DOSSIER / "journal.jsonl"
BILAN = DOSSIER / "bilan.json"
BANDES = DOSSIER / "bandes_1x2.json"                 # règles candidates 1X2 en validation (26/10/2026)
RAPPORT_BANDES = DOSSIER / "validation_bandes_1x2.json"
PAGE = DOSSIER / "pronostics.json"
CLASSEMENTS = ROOT / "cache_classement.json"
ONGLETS = ("buts", "equipes", "multiscores", "calibrees")   # « calibrees » (24/10/2026) : règles exploitables de la campagne, voir calibrees.py
_REGLES: list | None = None


def _regles() -> list:
    global _REGLES
    if _REGLES is None:
        _REGLES = calibrees.charger_regles()
    return _REGLES


def charger_matchs() -> list[dict[str, Any]]:
    out = []
    for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            sc = x.get("score") or {}
            x["score_final"] = {"buts_dom": sc["buts_dom"], "buts_ext": sc["buts_ext"]} if sc.get("buts_dom") is not None else None
            out.append(x)
    return out


def _lire(journal: Path) -> list[dict[str, Any]]:
    if not journal.exists():
        return []
    return [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()]


def _ajouter(journal: Path, lignes: list[dict[str, Any]]) -> None:
    if not lignes:
        return
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


def _empreinte_params() -> str:
    f = P.FICHIER
    return hashlib.sha256(f.read_bytes()).hexdigest()[:12] if f.exists() else "defaut"


def _coup_d_envoi(m: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(m["coup_d_envoi_utc"]).replace("Z", "+00:00"))
    except Exception:
        return None


def _classements() -> dict[str, list]:
    try:
        d = json.loads(CLASSEMENTS.read_text(encoding="utf-8"))
        return {k: (v or {}).get("resultat") or [] for k, v in d.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _cle_competition(nom: Any) -> str:
    return " ".join(str(nom or "").lower().split())


def analyser(m: dict[str, Any], params: dict, classements: dict[str, list] | None = None) -> dict[str, Any]:
    """Étapes 1 et 2 pour un match de l'archive. Les alertes de graduation (nom d'équipe EXACT) n'ajoutent ni ne retirent aucun marché."""
    a = m.get("assemblage") or {}
    r = coeur.analyser_match(a.get("equipe_dom") or {}, a.get("equipe_ext") or {}, str(m["date"])[:10], params)
    fiche = {"match_id": m["match_id"], "date": m["date"], "heure": m.get("heure_cameroun"), "competition": " ".join(str(m.get("competition") or "").split()),
             "domicile": m["domicile"], "exterieur": m["exterieur"], "coup_d_envoi_utc": m.get("coup_d_envoi_utc"), "statut": r["statut"],
             "n_domicile": r["n_domicile"], "n_exterieur": r["n_exterieur"]}
    if r["statut"] != "analyse":
        return {**fiche, "raison": r["raison"], "onglets": {o: [] for o in ONGLETS}}
    e2 = coeur.choisir(r, m.get("cotes_betpawa") or {})
    grad = coeur.graduation((classements or {}).get(_cle_competition(m.get("competition"))), m["domicile"], m["exterieur"])
    onglets: dict[str, list] = {}
    for onglet, lst in e2["onglets"].items():
        onglets[onglet] = []
        for f in lst:
            ligne = {"cle": list(f["cle"]), "marche": f["marche"], "valeur": f["valeur"], "cote": f.get("cote"), "cote_a_lire": bool(f.get("cote_a_lire"))}
            for c in ("offensive", "defensive", "niveau", "scenarios", "sur"):
                if c in f:
                    ligne[c] = f[c]
            alerte = coeur.alerte_graduation(tuple(f["cle"]), grad)
            if alerte:
                ligne["alerte"] = alerte
            onglets[onglet].append(ligne)
    onglets["calibrees"] = calibrees.selections(a.get("equipe_dom") or {}, a.get("equipe_ext") or {}, str(m["date"])[:10],
                                                m.get("cotes_betpawa") or {}, _regles())
    rejetes = [{"onglet": f["onglet"], "marche": f["marche"], "raison": f["raison"]} for f in r["rejetes"]] + \
              [{"onglet": f["onglet"], "marche": f["marche"], "raison": f["raison"]} for f in e2["ecartes_par_la_cote"]]
    return {**fiche, "k": r["k"], "niveaux": r["niveaux"], "scenarios_offensifs": r["scenarios_offensifs"], "scenarios_defensifs": r["scenarios_defensifs"],
            "onglets": onglets, "rejetes": rejetes, "graduation": grad}


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None, params: dict | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    params = params or P.charger()
    deja = {l["match_id"] for l in _lire(journal) if l["type"] == "pronostic"}
    classements = _classements()
    nouveaux = []
    for m in (matchs if matchs is not None else charger_matchs()):
        ko = _coup_d_envoi(m)
        if ko is None or ko <= maintenant or m["match_id"] in deja or m.get("score_final"):
            continue
        r = analyser(m, params, classements)
        if r["statut"] != "analyse" or not any(r["onglets"].values()):
            continue
        nouveaux.append({"type": "pronostic", "gele_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "code": _commit(), "parametres": _empreinte_params(),
                         **{k: r[k] for k in ("match_id", "coup_d_envoi_utc", "date", "competition", "domicile", "exterieur", "k", "onglets")}})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def _gagne(cle: list[str], h: int, a: int) -> bool | None:
    g, s = cle
    if g == "multigoals":
        lo, hi = (int(x) for x in s.split("-"))
        return lo <= h + a <= hi
    if g == "multiscores":
        return bool(coeur.GROUPES_MULTISCORES[s](h, a))
    if g == "combo":
        return calibrees.gagne(cle, h, a)
    p = test_du_marche(g, s)
    return None if p is None else bool(p(h, a))


def resultats(journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None) -> int:
    lignes = _lire(journal)
    figes = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    nouveaux = []
    for m in (matchs if matchs is not None else charger_matchs()):
        sc = m.get("score_final")
        if m["match_id"] in figes and m["match_id"] not in faits and sc:
            gagnes = {o: [_gagne(s["cle"], sc["buts_dom"], sc["buts_ext"]) for s in figes[m["match_id"]]["onglets"].get(o, [])] for o in ONGLETS}
            nouveaux.append({"type": "resultat", "match_id": m["match_id"], "score": sc, "gagnes": gagnes,
                             "enregistre_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(journal: Path = JOURNAL, ecrire: bool = True) -> dict[str, Any]:
    lignes = _lire(journal)
    figes = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    out: dict[str, Any] = {"pronostics_geles": len(figes), "matchs_termines": len([k for k in res if k in figes]), "onglets": {}}
    for o in ONGLETS:
        cas = [(s, g) for k in res if k in figes for s, g in zip(figes[k]["onglets"].get(o, []), res[k]["gagnes"].get(o, [])) if g is not None]
        cotes = [(s["cote"], g) for s, g in cas if s.get("cote")]
        out["onglets"][o] = {"cas": len(cas), "reussite": round(sum(g for _, g in cas) / len(cas), 4) if cas else None,
                             "cote_moyenne": round(sum(c for c, _ in cotes) / len(cotes), 3) if cotes else None,
                             "rendement": round(sum((c - 1) if g else -1 for c, g in cotes) / len(cotes), 4) if cotes else None}
    out["note"] = "Calculé uniquement sur des pronostics gelés avant le coup d'envoi. Rentabilité nécessaire ≈ 1 / cote moyenne."
    if ecrire:
        BILAN.parent.mkdir(parents=True, exist_ok=True)
        BILAN.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def historique_lieu(equipe: dict | None, domicile: bool, jour: str) -> list[dict[str, Any]]:
    """TOUS les matchs de l'équipe au lieu demandé (domicile ou extérieur), joués strictement avant `jour`, du plus récent au plus ancien.
    Mêmes données figées que le moteur (équipe de l'archive)."""
    ms = [x for x in (equipe or {}).get("matchs") or [] if bool(x.get("domicile")) is bool(domicile) and not x.get("provisoire")
          and str(x.get("date"))[:10] < jour and isinstance(x.get("buts_marques"), int) and isinstance(x.get("buts_encaisses"), int)]
    ms.sort(key=lambda x: str(x["date"]), reverse=True)
    return [{"date": str(x["date"])[:10], "adversaire": x.get("adversaire"), "marques": x["buts_marques"], "encaisses": x["buts_encaisses"]} for x in ms]


def bilan_historique(h: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(h)
    bm, be = sum(x["marques"] for x in h), sum(x["encaisses"] for x in h)
    return {"matchs": n, "marques": bm, "encaisses": be, "marques_par_match": round(bm / n, 2) if n else None,
            "encaisses_par_match": round(be / n, 2) if n else None}


def explication(cle: list[str], h_dom: list[dict], h_ext: list[dict]) -> dict[str, list[int]] | None:
    """Faits seulement : dans combien des matchs affichés le pari aurait gagné. Matchs à domicile de l'équipe qui reçoit lus tels quels
    (domicile = elle) ; matchs à l'extérieur de l'adversaire lus avec l'équipe qui recevait ce jour-là comme « domicile »."""
    kd = [_gagne(cle, x["marques"], x["encaisses"]) for x in h_dom]
    ke = [_gagne(cle, x["encaisses"], x["marques"]) for x in h_ext]
    if any(v is None for v in kd + ke):
        return None
    return {"domicile": [sum(kd), len(kd)], "exterieur": [sum(ke), len(ke)]}


def _pct(x: float) -> str:
    return f"{round(float(x) * 100)} %"


def pourquoi(onglet: str, ligne: dict[str, Any], params: dict, n_paires: int | None = None, dom: str = "l'équipe à domicile",
             ext: str = "l'équipe à l'extérieur") -> str | None:
    """La VRAIE raison de la sélection, en mots de tous les jours (24/10/2026, Patrick : « jargon basique compréhensible par tous »).
    Tirée des seuls critères appliqués par le moteur, rien d'inventé ; donnée manquante -> None (pas de phrase).
    Buts / équipes / multigoals : nombre de fois où le pari passe en comparant les derniers matchs des deux équipes, avec les buts marqués
    puis avec les buts encaissés (le moteur exige au moins la moitié des deux côtés) ; « la moyenne de buts confirme » seulement si le marché
    a une marge de sécurité. Multiscores : nombre de fois où le type de score sort. Calibrés : réussite dans des matchs passés comparables."""
    if onglet == "calibrees":
        r, n, sf = ligne.get("reussite_test_final"), ligne.get("paris_test_final"), ligne.get("reussite_sans_filtre")
        if r is None or n is None or sf is None:
            return None
        return f"Dans {n} matchs passés qui ressemblaient à celui-ci, ce pari a gagné {_pct(r)} du temps (contre {_pct(sf)} en général)."
    debut = f"On a comparé les {n_paires} derniers matchs de {dom} à domicile avec ceux de {ext} à l'extérieur : " if n_paires else None
    if onglet == "multiscores":
        c, n = ligne.get("scenarios"), ligne.get("sur")
        if c is None or n is None or not debut:
            return None
        return f"{debut}ce type de score est sorti {c} fois sur {n}."
    o, d = ligne.get("offensive"), ligne.get("defensive")
    if o is None or d is None or not debut:
        return None
    ko, kd = round(float(o) * n_paires), round(float(d) * n_paires)
    marge = "" if "sans objet" in str(ligne.get("niveau") or "sans objet") else " La moyenne de buts des deux équipes le confirme."
    return f"{debut}ce pari passe {ko} fois sur {n_paires} avec leurs buts marqués et {kd} fois sur {n_paires} avec leurs buts encaissés.{marge}"


def _solidite(poids: dict | None, cle: list[str], hd: list[dict], he: list[dict]) -> dict[str, float]:
    """Solidité du marché (`solidite.py`) : champ ajouté seulement si elle est calculable ; jamais écrite dans le journal gelé, aucune sélection modifiée."""
    try:
        r = SOL.probabilite(poids, cle, hd, he)
    except Exception:                                  # noqa: BLE001
        r = None
    return {} if r is None else {"solidite": round(r, 4)}


def page(matchs: list[dict[str, Any]] | None = None, params: dict | None = None, sortie: Path = PAGE, solidite: dict | None = None) -> dict[str, Any]:
    """Données de la page : tous les matchs de l'archive qui ont une analyse ; le moteur lit les équipes figées avant le coup d'envoi."""
    params = params or P.charger()
    classements = _classements()
    poids_solidite = solidite if solidite is not None else SOL.charger()     # Solidité (28/10/2026) : affichage seulement, aucun poids = aucun champ
    liste = []
    depuis = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")     # la page montre les matchs d'hier, d'aujourd'hui et à venir (fichier léger)
    for m in (matchs if matchs is not None else charger_matchs()):
        if str(m["date"])[:10] < depuis:
            continue
        r = analyser(m, params, classements)
        sc = m.get("score_final")
        fiche = {**r, "score": sc, "heure": m.get("heure_cameroun")}
        if r["statut"] == "analyse":                 # affichage (24/10/2026) : matchs joués au même lieu, buts par match, explication factuelle
            a, jour = m.get("assemblage") or {}, str(m["date"])[:10]
            hd, he = historique_lieu(a.get("equipe_dom"), True, jour), historique_lieu(a.get("equipe_ext"), False, jour)
            fiche["historique"] = {"domicile": hd, "exterieur": he, "bilan_domicile": bilan_historique(hd), "bilan_exterieur": bilan_historique(he)}
            n_paires = len(r.get("scenarios_offensifs") or [])
            fiche["onglets"] = {o: [{**x, "explication": explication(x["cle"], hd, he),
                                     "pourquoi": pourquoi(o, x, params, n_paires, m["domicile"], m["exterieur"]), **_solidite(poids_solidite, x["cle"], hd, he)} for x in lst]
                                for o, lst in r["onglets"].items()}
            fiche.pop("rejetes", None)               # marchés exclus : plus affichés (décision de Patrick)
            # Palier 2 des tickets (25/10/2026) : « le domicile ne marque pas plus de 2 buts » quand les chiffres battent la cote (palier2.py)
            fiche["palier2"] = palier2.selections(a.get("equipe_dom"), a.get("equipe_ext"), jour, m.get("cotes_betpawa") or {})
        liste.append(fiche)
    d = {"moteur": "alpha_serie", "statut": "OK", "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "promotion_allowed": False,
         "cote_min": P.COTE_MIN, "parametres": {"seuil_branche": params["seuil_branche"], "source": params.get("source"), "provisoire": params.get("provisoire", [])},
         "bilan_gele": bilan(ecrire=False), "bilan_tickets": tickets.bilan(), "matchs": liste}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d


# --- Validation des bandes de cotes 1X2 (26/10/2026, Patrick) -------------------------------------------------------------------------------
# Deux règles candidates, sans filtre de probabilité, NON intégrées à Alpha : victoire domicile avec cote BetPawa 1,33–1,50, victoire extérieur
# avec cote BetPawa 1,38–1,70 (bornes incluses). Réutilise le journal gelé : lignes « bande » (gel avant le coup d'envoi, jamais regelées, jamais
# a posteriori) puis « resultat_bande ». Aucune donnée Pinnacle, aucun affichage, aucun effet sur les pronostics ni sur les tickets.

def regles_bandes(fichier: Path = BANDES) -> dict[str, dict[str, Any]]:
    try:
        return json.loads(fichier.read_text(encoding="utf-8")).get("regles") or {}
    except Exception:
        return {}


def _cote_bande(m: dict[str, Any], regle: dict[str, Any]) -> float | None:
    c = ((m.get("cotes_betpawa") or {}).get("1x2") or {}).get(regle["cote_cle"])
    if isinstance(c, bool) or not isinstance(c, (int, float)) or c <= 1:
        return None
    c = round(float(c), 2)
    return c if regle["cote_min"] <= c <= regle["cote_max"] else None


def geler_bandes(maintenant: datetime | None = None, journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None,
                 params: dict | None = None, fichier: Path = BANDES) -> int:
    """Gèle TOUS les matchs admissibles (pertes comprises) dont le coup d'envoi n'a pas eu lieu. Un enregistrement par (match, règle)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    regles = regles_bandes(fichier)
    if not regles:
        return 0
    params = params or P.charger()
    deja = {(l["match_id"], l["regle"]) for l in _lire(journal) if l["type"] == "bande"}
    nouveaux = []
    for m in (matchs if matchs is not None else charger_matchs()):
        ko = _coup_d_envoi(m)
        if ko is None or ko <= maintenant or m.get("score_final"):
            continue
        for nom, regle in regles.items():
            cote = _cote_bande(m, regle)
            if cote is None or (m["match_id"], nom) in deja:
                continue
            a = m.get("assemblage") or {}
            try:
                analyse = coeur.analyser_match(a.get("equipe_dom") or {}, a.get("equipe_ext") or {}, str(m["date"])[:10], params).get("statut") == "analyse"
            except Exception:
                analyse = False
            deja.add((m["match_id"], nom))
            nouveaux.append({"type": "bande", "regle": nom, "gele_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "code": _commit(),
                             "match_id": m["match_id"], "coup_d_envoi_utc": m.get("coup_d_envoi_utc"), "date": str(m["date"])[:10],
                             "competition": " ".join(str(m.get("competition") or "").split()), "domicile": m["domicile"], "exterieur": m["exterieur"],
                             "cote": cote, "bande": [regle["cote_min"], regle["cote_max"]], "analyse_alpha": analyse})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def resultats_bandes(journal: Path = JOURNAL, matchs: list[dict[str, Any]] | None = None) -> int:
    lignes = _lire(journal)
    figes = {(l["match_id"], l["regle"]) for l in lignes if l["type"] == "bande"}
    faits = {(l["match_id"], l["regle"]) for l in lignes if l["type"] == "resultat_bande"}
    nouveaux = []
    for m in (matchs if matchs is not None else charger_matchs()):
        sc = m.get("score_final")
        if not sc:
            continue
        for nom in ("domicile", "exterieur"):
            if (m["match_id"], nom) in figes and (m["match_id"], nom) not in faits:
                h, a = sc["buts_dom"], sc["buts_ext"]
                faits.add((m["match_id"], nom))
                nouveaux.append({"type": "resultat_bande", "match_id": m["match_id"], "regle": nom, "score": sc,
                                 "gagne": bool(h > a) if nom == "domicile" else bool(a > h),
                                 "enregistre_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def wilson_bas(g: int, n: int, z: float = 1.96) -> float | None:
    if n <= 0:
        return None
    p = g / n
    return round((p + z * z / (2 * n) - z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n), 4)


def _bloc(lst: list[bool]) -> dict[str, Any]:
    n, g = len(lst), sum(lst)
    return {"matchs": n, "gagnes": g, "perdus": n - g, "taux": round(g / n, 4) if n else None, "wilson_bas_95": wilson_bas(g, n)}


def bilan_bandes(journal: Path = JOURNAL, ecrire: bool = True, fichier: Path = BANDES, sortie: Path = RAPPORT_BANDES) -> dict[str, Any]:
    lignes = _lire(journal)
    figes = [l for l in lignes if l["type"] == "bande"]
    res = {(l["match_id"], l["regle"]): l for l in lignes if l["type"] == "resultat_bande"}
    cles = [(l["match_id"], l["regle"]) for l in figes]
    ref = {}
    try:
        ref = json.loads(fichier.read_text(encoding="utf-8"))
    except Exception:
        pass
    out: dict[str, Any] = {"statut": ref.get("statut"), "source_cotes": ref.get("source_cotes"), "regles": {}, "controles": {
        "doublons_match_regle": len(cles) - len(set(cles)),
        "gels_non_anterieurs_au_coup_d_envoi": sum(1 for l in figes if not l.get("coup_d_envoi_utc") or l["gele_le"] >= l["coup_d_envoi_utc"]),
        "resultats_sans_gel": sum(1 for k in res if k not in set(cles)),
        "cotes_hors_bande": sum(1 for l in figes if not (l["bande"][0] <= l["cote"] <= l["bande"][1]))}}
    for nom, regle in (ref.get("regles") or {}).items():
        mine = [l for l in figes if l["regle"] == nom]
        reglees = [(l, res[(l["match_id"], nom)]["gagne"]) for l in mine if (l["match_id"], nom) in res]
        sem: dict[str, list[bool]] = {}
        for l, g in reglees:
            a = datetime.fromisoformat(l["date"]).isocalendar()
            sem.setdefault("%d-S%02d" % (a[0], a[1]), []).append(g)
        out["regles"][nom] = {"bande_cote_betpawa": [regle["cote_min"], regle["cote_max"]], "geles": len(mine), "en_attente": len(mine) - len(reglees),
                              "cumule": _bloc([g for _, g in reglees]),
                              "dont_analyses_par_alpha": _bloc([g for l, g in reglees if l.get("analyse_alpha")]),
                              "par_semaine": {k: _bloc(v) for k, v in sorted(sem.items())}}
    out["reference_etude"] = ref.get("reference_etude")
    out["decision"] = ref.get("decision")
    if ecrire:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def pipeline() -> dict[str, Any]:
    """Passage dans le pipeline nocturne : lit l'archive du dossier de travail, sans git. Le commit est fait par le pipeline."""
    matchs = charger_matchs()                        # chargée une seule fois : même archive pour le gel, les résultats et la page
    gele = geler(matchs=matchs)
    resultat = resultats(matchs=matchs)
    sol_info = None
    try:                                             # Solidité (28/10/2026) : poids réappris à chaque passage ; une erreur ne bloque rien (poids précédents gardés)
        sol_info = {k: v for k, v in SOL.ecrire(matchs=matchs).items() if k in ("n_marches", "poids_frequence", "poids_ecart", "brier")}
    except Exception as e:                           # noqa: BLE001
        sol_info = {"erreur": repr(e)}
    d = page(matchs=matchs)
    # Tickets du jour (25/10/2026) : gelés avant le premier match, réglés quand tous leurs matchs ont un score, bilan ajouté à la page.
    t_geles, t_regles = tickets.geler(d["matchs"]), tickets.regler(matchs)
    d["bilan_tickets"] = tickets.bilan()
    PAGE.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tickets.ecrire_accueil(d["matchs"])                 # les 3 tickets de la page d'accueil (25/10/2026)
    b_geles, b_regles = geler_bandes(matchs=matchs), resultats_bandes(matchs=matchs)      # validation des bandes 1X2, sans effet sur la page
    bilan_bandes()
    sortie = {"geles": gele, "resultats": resultat, "page_matchs": len(d["matchs"]), "solidite": sol_info, "bilan": bilan(), "bandes_1x2": {"geles": b_geles, "regles": b_regles},
              "tickets": {"geles": t_geles, "regles": t_regles, "bilan": d["bilan_tickets"]}}
    try:                                                                    # onglet « Indice Alpha » (26/10/2026) : lit les journaux, ne change rien d'autre
        from . import indice_alpha
        r = indice_alpha.construire()
        sortie["indice_alpha"] = {"indices": len(r["indices"]), "alerte_registre": r["alerte_registre"], "paris_distincts": r["global"]["paris_distincts"]["matchs"]}
    except Exception as e:                                                  # l'erreur est affichée dans le résultat du pipeline, elle ne bloque pas le reste
        sortie["indice_alpha"] = {"erreur": repr(e)}
    try:                                                                    # sélection provisoire (26/10/2026) : 8 marchés, gel avant match, page « Sélection »
        from . import selection_provisoire
        sortie["selection_provisoire"] = selection_provisoire.pipeline(matchs)
    except Exception as e:                                                  # l'erreur est affichée dans le résultat du pipeline, elle ne bloque pas le reste
        sortie["selection_provisoire"] = {"erreur": repr(e)}
    return sortie


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    if cmd == "pipeline":
        print(json.dumps(pipeline(), ensure_ascii=False, indent=1))
    elif cmd == "geler":
        print("gelés :", geler())
    elif cmd == "resultats":
        print("résultats ajoutés :", resultats())
    elif cmd == "bilan":
        print(json.dumps(bilan(), ensure_ascii=False, indent=1))
    elif cmd == "page":
        print(len(page()["matchs"]), "matchs écrits")
    else:
        raise SystemExit("commande inconnue : " + cmd)
