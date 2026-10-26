"""Tickets du moteur alpha : gel avant les matchs, résultats et bilan (25/10/2026, demande de Patrick : « finalise le moteur de génération
de tickets »).

Mêmes règles que l'onglet « Traitement séquentiel des tickets » (`af-alpha-tickets.js`, audit validé du 25/10/2026), réécrites ici en
Python pour être gelées et suivies chaque nuit ; un test vérifie que le navigateur et ce module choisissent exactement les mêmes paris.
- Palier 1 : meilleur marché affiché de Buts, Équipes, Calibrés ; admissible si cote ≥ 1,25, pas un remplaçant, valeur ≥ 80 %,
  confirmation sur les matchs des deux équipes ≥ 75 %, au moins 5 matchs comparés ; tranches de 2 heures de 10 h à minuit ; le premier
  de chaque tranche (un marché par match).
- Palier 2 (25/10/2026, Patrick) : les 10 meilleurs pronostics RESTANTS de la journée (10 h – minuit), mêmes règles, même classement,
  un seul pari par match, aucun match du palier 1. Moins de 10 admissibles : le palier en compte moins (rien n'est assoupli).
- Palier 3, en test : les paris de `palier2.py` (« le domicile ne marque pas plus de 2 buts » quand les chiffres battent la cote).
- Page d'accueil (25/10/2026, Patrick) : 3 tickets de 10 matchs au plus, rangés par CLASSEMENT (pas par type de pari : des matchs de
  championnats et de contextes différents n'ont rien en commun du fait de leur marché). Ticket 1 = les 10 paris les mieux classés de
  la journée (10 h – minuit), ticket 2 = les 10 suivants, ticket 3 = les 10 suivants ; mêmes règles que le palier 1, un pari par match,
  un match sur un seul ticket. Moins de 30 admissibles : les derniers tickets en comptent moins (rien n'est assoupli).
  Ticket recommandé (25/10/2026, règle de Patrick : « cote maximum 5 ») : les paris du même classement, pris dans l'ordre, tant que
  la cote totale reste ≤ 5 ; on s'arrête au premier pari qui la ferait dépasser (on ne saute pas un pari mieux classé).
« Plus de 1,5 » à chances maximales (26/10/2026, Patrick : « il doit figurer automatiquement dans le ticket du jour et l'utilisateur doit pouvoir le
  reconnaître ») : le « Plus de 1,5 buts » d'alpha dont le total attendu atteint le palier gelé de `data/alpha_serie/plus15_chances_max.json` (3,4 :
  borne basse de Wilson >= 1/1,25 au réglage ET au contrôle) ET qui compte au plus 1 match passé à 0 ou 1 but dans les séries des deux équipes (`matchs_faibles_max`, même fichier), avec une cote BetPawa connue >= 1,25 (minimum de tous les marchés), devient candidat prioritaire (`chances_max`) : il
  passe devant les autres dans tous les classements (palier 1, palier 2, accueil, ticket recommandé), toujours à raison d'un pari par match. Il est
  marqué dans les tickets gelés (`chances_max`, `total_attendu`) et son taux de réussite réel est suivi (`bilan()["plus15_max"]`). Sans le fichier, rien n'est ajouté.
Gel : chaque nuit, pour le jour courant (Douala), ou pour le lendemain après 22 h (début du dernier créneau), avant le premier match du ticket ; jamais regelé, jamais a posteriori.
Résultats : quand tous les matchs d'un ticket ont un score. Bilan : uniquement sur des tickets gelés avant les matchs.
Bibliothèque standard seulement. Le moteur alpha (`coeur.py`) n'est ni appelé ni modifié.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import parametres as P

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "data" / "alpha_serie" / "tickets_journal.jsonl"
FAMILLES = {"accueil_1": "les mieux classés", "accueil_2": "la suite du classement", "accueil_3": "le troisième groupe"}
PALIERS = ("palier1", "palier2", "palier3") + tuple(FAMILLES) + ("accueil_recommande",)
COTE_RECOMMANDEE_MAX = 5.0         # règle de Patrick, 25/10/2026
ACCUEIL = ROOT / "data" / "alpha_serie" / "tickets_accueil.json"
PLUS15 = ROOT / "data" / "alpha_serie" / "plus15_chances_max.json"
CLE_PLUS15 = ["over_under_1.5", "plus"]


def palier_plus15(chemin: Path = PLUS15) -> float | None:
    """Palier gelé du total attendu pour « Plus de 1,5 » à chances maximales ; None si le fichier est absent (fonction désactivée)."""
    try:
        return float(json.loads(chemin.read_text(encoding="utf-8"))["palier_total_attendu"])
    except (OSError, ValueError, KeyError, TypeError):
        return None

def faibles_max_plus15(chemin: Path = PLUS15) -> int | None:
    """Nombre maximal de matchs passés à 0 ou 1 but toléré pour le « chances maximales » ; None : pas de limite (clé absente du fichier)."""
    try:
        v = json.loads(chemin.read_text(encoding="utf-8")).get("matchs_faibles_max")
        return None if v is None else int(v)
    except (OSError, ValueError, TypeError):
        return None


def matchs_faibles(m: dict) -> int | None:
    """Matchs passés à 0 ou 1 but au total, pour les deux équipes, lus dans les paires publiées d'alpha : domicile = marqués (offensive[0]) + encaissés (défensive[1]) ;
    extérieur = marqués (offensive[1]) + encaissés (défensive[0]). None si les paires manquent."""
    off, de = m.get("scenarios_offensifs") or [], m.get("scenarios_defensifs") or []
    if not off or len(off) != len(de):
        return None
    return sum((o[0] + d[1]) <= 1 for o, d in zip(off, de)) + sum((o[1] + d[0]) <= 1 for o, d in zip(off, de))


COTE_MIN, VALEUR_MIN, CONFIRMATION_MIN, MATCHS_MIN, PAR_TRANCHE, PALIER2_MAX, ACCUEIL_MAX = 1.25, 0.80, 0.75, 5, 2, 10, 10
DEBUT, PAS, FIN = 10 * 60, 120, 24 * 60
DOUALA = timezone(timedelta(hours=1))


# --- Meilleur marché affiché d'une catégorie (même règle que af-alpha-selection.js) ----------------------------------------
def _cote_valide(x: Any) -> bool:
    try:
        return x is not None and x != "" and float(x) > 1
    except (TypeError, ValueError):
        return False


def _lignes(m: dict, cat: str) -> list[dict]:
    source = "buts" if cat == "buts" else cat
    brutes = [s for s in (m.get("onglets") or {}).get(source) or [] if cat != "buts" or not (s.get("cle") or [""])[0] == "multigoals"]
    vus, uniques = set(), []
    for s in brutes:
        k = "|".join(s["cle"]) if isinstance(s.get("cle"), list) else str(s.get("marche") or "")
        if k not in vus:
            vus.add(k)
            uniques.append(s)
    return sorted(uniques, key=lambda s: -(float(s.get("valeur") or 0)))          # tri stable : ordre du fichier à égalité


def meilleur(m: dict, cat: str) -> tuple[dict | None, bool]:
    l = _lignes(m, cat)
    aff = [s for s in l if _cote_valide(s.get("cote"))]
    return (aff[0], bool(l and l[0] is not aff[0])) if aff else (None, False)


def _minutes(h: Any) -> int | None:
    try:
        hh, mm = str(h).split(":")
        return int(hh) * 60 + int(mm)
    except (ValueError, AttributeError):
        return None


def _confirmation(s: dict) -> float | None:
    e = s.get("explication") or {}
    parts = [e[k][0] / e[k][1] for k in ("domicile", "exterieur") if isinstance(e.get(k), list) and len(e[k]) == 2 and e[k][1]]
    return min(parts) if parts else None


def candidats(matchs: list[dict], jour: str) -> list[dict]:
    out = []
    for m in matchs:
        if m.get("statut") != "analyse" or m.get("date") != jour:
            continue
        debut = _minutes(m.get("heure"))
        if debut is None:
            continue
        for cat in ("buts", "equipes", "calibrees"):
            s, rempl = meilleur(m, cat)
            if not s:
                continue
            conf = _confirmation(s)
            n = min(int(m.get("n_domicile") or 0), int(m.get("n_exterieur") or 0))
            c = {"id": f"{m['match_id']}|{cat}", "match_id": m["match_id"], "categorie": cat, "cle": s.get("cle"), "marche": s.get("marche"),
                 "cote": float(s["cote"]), "valeur": float(s.get("valeur") or 0), "confirmation": conf, "matchs": n, "remplacant": rempl,
                 "debut": debut, "heure": m.get("heure"), "domicile": m.get("domicile"), "exterieur": m.get("exterieur"), "competition": m.get("competition")}
            c["admissible"] = (c["cote"] >= P.COTE_MIN - 1e-9 and not rempl and c["valeur"] >= VALEUR_MIN - 1e-9 and conf is not None
                               and conf >= CONFIRMATION_MIN - 1e-9 and n >= MATCHS_MIN)
            out.append(c)
        pm = _plus15(m, debut)
        if pm:
            out.append(pm)
    return out


def _plus15(m: dict, debut: int) -> dict | None:
    """Le « Plus de 1,5 buts » d'alpha à chances maximales (total attendu >= palier gelé, au plus `matchs_faibles_max` matchs passés à 0 ou 1 but, cote connue >= COTE_MIN), sinon None."""
    palier = palier_plus15()
    total = (m.get("niveaux") or {}).get("total")
    if palier is None or total is None or float(total) < palier - 1e-9:
        return None
    limite = faibles_max_plus15()
    faibles = matchs_faibles(m)
    if limite is not None and (faibles is None or faibles > limite):
        return None
    s = next((x for x in (m.get("onglets") or {}).get("buts") or [] if x.get("cle") == CLE_PLUS15), None)
    if not s or not _cote_valide(s.get("cote")) or float(s["cote"]) < P.COTE_MIN - 1e-9:
        return None
    return {"id": f"{m['match_id']}|plus15", "match_id": m["match_id"], "categorie": "plus15", "cle": s.get("cle"), "marche": s.get("marche"),
            "cote": float(s["cote"]), "valeur": float(s.get("valeur") or 0), "confirmation": _confirmation(s),
            "matchs": min(int(m.get("n_domicile") or 0), int(m.get("n_exterieur") or 0)), "remplacant": False, "chances_max": True,
            "total_attendu": round(float(total), 2), "matchs_faibles": faibles, "debut": debut, "heure": m.get("heure"), "domicile": m.get("domicile"),
            "exterieur": m.get("exterieur"), "competition": m.get("competition"), "admissible": True}


def _ordre(c: dict) -> tuple:
    return (not c.get("chances_max"), -c["valeur"], -(c["confirmation"] or 0), -c["matchs"], c["cote"], c["debut"], c["id"])


def tranches(cands: list[dict]) -> list[dict]:
    out = []
    for d in range(DEBUT, FIN, PAS):
        admis = sorted([c for c in cands if c["admissible"] and d <= c["debut"] < d + PAS], key=_ordre)
        ticket, vus = [], set()
        for c in admis:
            if c["match_id"] in vus or len(ticket) >= PAR_TRANCHE:
                continue
            ticket.append(c)
            vus.add(c["match_id"])
        out.append({"debut": d, "ticket": ticket})
    return out


def ticket_long(trs: list[dict]) -> list[dict]:
    return [t["ticket"][0] for t in trs if t["ticket"]] + [t["ticket"][1] for t in trs if len(t["ticket"]) > 1]


def palier_2(cands: list[dict], p1: list[dict]) -> list[dict]:
    pris, out = {c["match_id"] for c in p1}, []
    for c in sorted([c for c in cands if c["admissible"] and DEBUT <= c["debut"] < FIN], key=_ordre):
        if c["match_id"] in pris or len(out) >= PALIER2_MAX:
            continue
        out.append(c)
        pris.add(c["match_id"])
    return out


def accueil(cands: list[dict]) -> dict[str, list[dict]]:
    """Les paris admissibles de la journée, un par match, dans l'ordre du classement, coupés en tickets de ACCUEIL_MAX."""
    rang, pris = [], set()
    for c in sorted([c for c in cands if c["admissible"] and DEBUT <= c["debut"] < FIN], key=_ordre):
        if c["match_id"] not in pris:
            rang.append(c)
            pris.add(c["match_id"])
    out = {f: rang[i * ACCUEIL_MAX:(i + 1) * ACCUEIL_MAX] for i, f in enumerate(FAMILLES)}
    rec, cote = [], 1.0
    for c in rang:
        if cote * c["cote"] > COTE_RECOMMANDEE_MAX + 1e-9:
            break
        rec.append(c)
        cote *= c["cote"]
    out["accueil_recommande"] = rec
    return out


def du_jour(matchs: list[dict], jour: str) -> dict[str, Any]:
    cands = candidats(matchs, jour)
    p1 = [t["ticket"][0] for t in tranches(cands) if t["ticket"]]
    p2 = palier_2(cands, p1)
    p3 = sorted([{**s, "match_id": m["match_id"], "categorie": "palier3", "heure": m.get("heure"), "debut": _minutes(m.get("heure")),
                  "domicile": m.get("domicile"), "exterieur": m.get("exterieur"), "competition": m.get("competition")}
                 for m in matchs if m.get("date") == jour and m.get("statut") == "analyse" for s in m.get("palier2") or []
                 if _minutes(m.get("heure")) is not None and DEBUT <= _minutes(m.get("heure")) < FIN], key=lambda x: (x["debut"], x["match_id"]))
    garde = ("match_id", "categorie", "cle", "marche", "cote", "valeur", "heure", "debut", "domicile", "exterieur", "competition")
    garde_max = garde + ("chances_max", "total_attendu")        # le repère « chances maximales » suit le pari jusque dans le journal et l'accueil
    acc = accueil(cands)
    gk = lambda c: {k: c.get(k) for k in (garde_max if c.get("chances_max") else garde)}  # noqa: E731
    return {"jour": jour, "palier1": [gk(c) for c in p1], "palier2": [gk(c) for c in p2],
            "palier3": [{k: c.get(k) for k in garde + ("avantage", "p_estimee", "p_cote")} for c in p3],
            **{f: [gk(c) for c in acc[f]] for f in (*FAMILLES, "accueil_recommande")}}


# --- Journal : gel, résultats, bilan -----------------------------------------------------------------------------------------
def _lire(journal: Path) -> list[dict]:
    return [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()] if journal.exists() else []


def _ajouter(journal: Path, lignes: list[dict]) -> None:
    if lignes:
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as f:
            for l in lignes:
                f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")


def jour_cible(maintenant: datetime) -> str:
    """Passé le début du dernier créneau (22 h, FIN − PAS), tous les tickets du jour ont commencé : le prochain jour est demain.
    Le pipeline démarre à 21:00 UTC (22 h à Douala) : s'il finit avant minuit, il gèle demain au lieu de ne rien geler."""
    local = maintenant.astimezone(DOUALA)
    return (local + timedelta(days=1) if local.hour * 60 + local.minute >= FIN - PAS else local).strftime("%Y-%m-%d")


def geler(matchs_page: list[dict], maintenant: datetime | None = None, journal: Path = JOURNAL) -> int:
    """Gèle les tickets du jour courant (Douala) si aucun de leurs matchs n'a commencé. Un jour déjà gelé ne l'est jamais deux fois."""
    maintenant = maintenant or datetime.now(timezone.utc)
    local = maintenant.astimezone(DOUALA)
    jour = jour_cible(maintenant)
    if any(l["type"] == "tickets" and l["jour"] == jour for l in _lire(journal)):
        return 0
    t = du_jour(matchs_page, jour)
    tous = [c for p in PALIERS for c in t[p]]
    if not tous:
        return 0
    minute_now = local.hour * 60 + local.minute if jour == local.strftime("%Y-%m-%d") else -1
    if min(c["debut"] for c in tous) <= minute_now:
        return 0                                                  # un match a déjà commencé : aucun gel a posteriori
    _ajouter(journal, [{"type": "tickets", "gele_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), **t}])
    return 1


def regler(matchs_archive: list[dict], journal: Path = JOURNAL) -> int:
    from .suivi import _gagne
    lignes = _lire(journal)
    faits = {l["jour"] for l in lignes if l["type"] == "resultat_tickets"}
    scores = {m["match_id"]: m.get("score_final") for m in matchs_archive if m.get("score_final")}
    nouveaux = []
    for t in (l for l in lignes if l["type"] == "tickets" and l["jour"] not in faits):
        legs = [c for p in PALIERS for c in t.get(p, [])]
        if not all(c["match_id"] in scores for c in legs):
            continue
        res = lambda lst: [_gagne(c["cle"], scores[c["match_id"]]["buts_dom"], scores[c["match_id"]]["buts_ext"]) for c in lst]  # noqa: E731
        nouveaux.append({"type": "resultat_tickets", "jour": t["jour"], **{p: res(t.get(p, [])) for p in PALIERS},
                         "enregistre_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def bilan(journal: Path = JOURNAL) -> dict[str, Any]:
    lignes = _lire(journal)
    res = {l["jour"]: l for l in lignes if l["type"] == "resultat_tickets"}
    gel = {l["jour"]: l for l in lignes if l["type"] == "tickets"}
    out: dict[str, Any] = {"jours_geles": len(gel), "jours_regles": len(res)}
    for nom, partie in ((p, [p]) for p in PALIERS):
        tickets = gagnes = legs = legs_g = 0
        rendement = 0.0
        for j, r in res.items():
            sel = sum((gel[j].get(p, []) for p in partie), [])
            ok = sum((r.get(p, []) for p in partie), [])
            if not sel or any(x is None for x in ok):
                continue
            tickets += 1
            legs += len(ok)
            legs_g += sum(ok)
            cote = 1.0
            for c in sel:
                cote *= c["cote"]
            g = all(ok)
            gagnes += g
            rendement += (cote - 1) if g else -1
        out[nom] = {"tickets": tickets, "gagnes": gagnes, "paris": legs, "paris_gagnes": legs_g,
                    "rendement_par_ticket": round(rendement / tickets, 4) if tickets else None}
    out["plus15_max"] = _bilan_plus15(res, gel)
    return out


def _bilan_plus15(res: dict, gel: dict) -> dict[str, Any]:
    """Réussite RÉELLE des « Plus de 1,5 » à chances maximales gelés avant leur match (un match compté une fois, quel que soit le palier)."""
    vus: dict[tuple, bool | None] = {}
    for j, r in res.items():
        for p in PALIERS:
            for c, ok in zip(gel[j].get(p, []), r.get(p, [])):
                if c.get("chances_max") and ok is not None:
                    vus[(j, c["match_id"])] = bool(ok)
    n, k = len(vus), sum(vus.values())
    return {"paris": n, "gagnes": k, "reussite": round(k / n, 4) if n else None}


def page_accueil(matchs_page: list[dict], maintenant: datetime | None = None, journal: Path = JOURNAL) -> dict[str, Any]:
    """Les 3 tickets de l'accueil : ceux GELÉS pour le jour cible quand ils existent (ce qui est suivi est ce qui est affiché) ;
    sinon calculés sur la page du moment, marqués non gelés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    jour = jour_cible(maintenant)
    gel = next((l for l in reversed(_lire(journal)) if l["type"] == "tickets" and l["jour"] == jour and "accueil_recommande" in l), None)
    t = gel or du_jour(matchs_page, jour)
    b = bilan(journal)
    tickets = []
    for f, nom in FAMILLES.items():
        sel, cote = t.get(f, []), 1.0
        for c in sel:
            cote *= c["cote"]
        tickets.append({"cle": f, "nom": nom, "selection": [{**c, "date": jour} for c in sel], "cote_totale": round(cote, 4) if sel else None,
                        "bilan": b.get(f)})
    sel = t.get("accueil_recommande", [])
    cote = 1.0
    for c in sel:
        cote *= c["cote"]
    recommande = {"cle": "accueil_recommande", "nom": "Ticket recommandé", "cote_max": COTE_RECOMMANDEE_MAX,
                  "selection": [{**c, "date": jour} for c in sel], "cote_totale": round(cote, 4) if sel else None, "bilan": b.get("accueil_recommande")}
    return {"jour": jour, "gele": bool(gel), "recommande": recommande, "gele_le": (gel or {}).get("gele_le"), "max": ACCUEIL_MAX,
            "genere_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "tickets": tickets}


def ecrire_accueil(matchs_page: list[dict], maintenant: datetime | None = None, journal: Path = JOURNAL, sortie: Path = ACCUEIL) -> dict[str, Any]:
    d = page_accueil(matchs_page, maintenant, journal)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d
