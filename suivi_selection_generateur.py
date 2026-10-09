"""Archive des paris sélectionnés par le générateur de tickets (les « 30 marchés »).

`data/tickets.json` est réécrit à chaque exécution : sans archive, la liste des paris que le générateur a vraiment eus
(V3 + Journal, 15 au maximum par source, par plage de dates) est perdue, et deux exécutions du même jour peuvent différer.
Ce module garde, dans `data/selection_generateur_historique.json` :
- `executions` : une entrée par exécution dont la liste de paris a changé (jamais modifiée après coup), avec chaque pari
  (cote, probabilité, source, rang, plages où il figure) ;
- `resultats` : le score et WIN/LOSS de chaque pari, écrits une seule fois quand le match est terminé ;
- `bilan` : réussite réelle contre probabilité estimée, par source et par jour.

Un match introuvable, un marché non reconnu ou un pari non évaluable restent sans résultat : jamais devinés, jamais comptés
perdus. Une erreur de lecture des scores est écrite dans `derniere_erreur`, jamais masquée.
Lancé par `construit_etat_systeme.py`, après `generateur_tickets.py`. Rattrapage depuis l'historique Git :
`python suivi_selection_generateur.py --rattrapage`."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import generateur_tickets as gt
from selection_adaptative import load_json, norm, num

TICKETS = Path("data/tickets.json")
ARCHIVE = Path("data/selection_generateur_historique.json")
VERSION = 1
CHAMPS = ("match_id", "date", "heure", "competition", "domicile", "exterieur", "marche", "cote", "probabilite_estimee",
          "ev_estime", "marge_modele", "source", "rang", "niveau_confiance", "journal_team", "journal_wins",
          "journal_observations", "probabilite_source")


def pari_id(c: dict[str, Any]) -> str:
    """Identité d'un pari : match (date + équipes), marché canonique, source. La même clé pour le Journal (sans match_id) et V3."""
    return "|".join([gt.match_key(c), gt.marche_canonique(c), norm(c.get("source"))])


def plages_de(tickets: dict[str, Any]) -> list[dict[str, Any]]:
    plages = tickets.get("plages")
    if isinstance(plages, list) and plages:
        return [p for p in plages if isinstance(p, dict)]
    return [{"id": "unique", "pool": tickets.get("pool") or []}]  # anciennes versions de tickets.json


def paris_de(tickets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Tous les paris du générateur pour cette exécution, un par identité, avec les plages où ils figurent."""
    out: dict[str, dict[str, Any]] = {}
    for plage in plages_de(tickets):
        for c in plage.get("pool") or []:
            if not isinstance(c, dict) or not (norm(c.get("domicile")) and norm(c.get("exterieur")) and norm(c.get("marche"))):
                continue
            k = pari_id(c)
            row = out.setdefault(k, {"id": k, **{f: c.get(f) for f in CHAMPS}, "marche_canonique": gt.marche_canonique(c), "plages": []})
            row["plages"].append(plage.get("id"))
    return out


def empreinte(paris: dict[str, dict[str, Any]]) -> str:
    rows = sorted((k, p.get("cote"), p.get("probabilite_estimee"), tuple(p.get("plages") or [])) for k, p in paris.items())
    return hashlib.sha1(json.dumps(rows, default=str).encode("utf-8")).hexdigest()[:16]


def archive_vide() -> dict[str, Any]:
    return {"version": VERSION, "executions": [], "resultats": {}, "bilan": None, "derniere_erreur": None}


def enregistre(archive: dict[str, Any], tickets: dict[str, Any]) -> bool:
    """Ajoute l'exécution si sa liste de paris diffère de la précédente. Renvoie True si une entrée a été ajoutée."""
    paris = paris_de(tickets)
    genere_le = tickets.get("genere_le")
    if not paris or not genere_le:
        return False
    execs = archive["executions"]
    if any(e.get("genere_le") == genere_le for e in execs):
        return False
    emp = empreinte(paris)
    if execs and execs[-1].get("empreinte") == emp:
        return False
    execs.append({"genere_le": genere_le, "jour_present": tickets.get("jour_present"), "empreinte": emp,
                  "plages": {p.get("id"): len(p.get("pool") or []) for p in plages_de(tickets)},
                  "paris": sorted(paris.values(), key=lambda p: (str(p["date"]), str(p["heure"]), p["id"]))})
    execs.sort(key=lambda e: str(e["genere_le"]))
    return True


def index_matchs(matchs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple, dict[str, Any]]]:
    """Matchs terminés : par identifiant, et par (date, domicile, extérieur) normalisés. Équipes inversées = autre match."""
    par_id: dict[str, dict[str, Any]] = {}
    par_nom: dict[tuple, dict[str, Any]] = {}
    for m in matchs:
        if not m.get("buts"):
            continue
        if norm(m.get("match_id")):
            par_id[norm(m["match_id"])] = m
        par_nom[(norm(m.get("date")), gt._nom_normalise(m.get("domicile")), gt._nom_normalise(m.get("exterieur")))] = m
    return par_id, par_nom


def trouve_match(p: dict[str, Any], idx: tuple[dict, dict]) -> dict[str, Any] | None:
    par_id, par_nom = idx
    if norm(p.get("match_id")) in par_id:
        return par_id[norm(p["match_id"])]
    return par_nom.get((norm(p.get("date")), gt._nom_normalise(p.get("domicile")), gt._nom_normalise(p.get("exterieur"))))


def evalue(p: dict[str, Any], h: int, a: int, evaluer: Callable[[str, int, int], str | None]) -> str | None:
    """Nom tel quel, puis nom canonique (libellés du Journal), puis suffixe de double chance en majuscules."""
    canon = p.get("marche_canonique") or gt.marche_canonique(p)
    essais = [norm(p.get("marche")), canon]
    if canon.startswith("double_chance_"):
        essais.append(canon[:-2] + canon[-2:].upper())
    for nom in essais:
        if nom:
            r = evaluer(nom, h, a)
            if r in ("WIN", "LOSS"):
                return r
    return None


def regle(archive: dict[str, Any], matchs: list[dict[str, Any]], evaluer: Callable[[str, int, int], str | None],
          maintenant: str) -> int:
    """Règle les paris sans résultat dont le match est terminé. Un résultat écrit n'est jamais modifié."""
    idx = index_matchs(matchs)
    deja = archive["resultats"]
    dernier: dict[str, dict[str, Any]] = {}
    for e in archive["executions"]:
        for p in e["paris"]:
            dernier[p["id"]] = p
    regles = 0
    for k, p in dernier.items():
        if k in deja:
            continue
        m = trouve_match(p, idx)
        if not m:
            continue
        h, a = m["buts"]
        r = evalue(p, int(h), int(a), evaluer)
        if r:
            deja[k] = {"score": f"{int(h)}-{int(a)}", "resultat": r, "regle_le": maintenant}
            regles += 1
    return regles


def bilan(archive: dict[str, Any], maintenant: str) -> dict[str, Any]:
    dernier: dict[str, dict[str, Any]] = {}
    for e in archive["executions"]:
        for p in e["paris"]:
            dernier[p["id"]] = p  # dernière version vue : la plus proche du coup d'envoi
    res = archive["resultats"]
    par_source: dict[str, dict[str, Any]] = {}
    par_jour: dict[str, dict[str, Any]] = {}
    for k, p in dernier.items():
        r = res.get(k)
        for table, cle in ((par_source, p.get("source") or "inconnue"), (par_jour, str(p.get("date")))):
            d = table.setdefault(cle, {"paris": 0, "regles": 0, "reussis": 0, "proba": 0.0, "cote": 0.0})
            d["paris"] += 1
            if r:
                d["regles"] += 1
                d["reussis"] += 1 if r["resultat"] == "WIN" else 0
                d["proba"] += num(p.get("probabilite_estimee")) or 0.0
                d["cote"] += num(p.get("cote")) or 0.0

    def fin(t: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return {k: {"paris": d["paris"], "regles": d["regles"], "reussis": d["reussis"],
                    "taux_reussite": round(d["reussis"] / d["regles"], 4) if d["regles"] else None,
                    "proba_moyenne_estimee": round(d["proba"] / d["regles"], 4) if d["regles"] else None,
                    "cote_moyenne": round(d["cote"] / d["regles"], 3) if d["regles"] else None}
                for k, d in sorted(t.items())}
    return {"genere_le": maintenant, "executions": len(archive["executions"]), "paris_distincts": len(dernier),
            "paris_regles": len(res), "par_source": fin(par_source), "par_jour_du_match": fin(par_jour),
            "avertissement": "Petits échantillons : le taux observé n'est significatif qu'avec beaucoup de paris réglés."}


def met_a_jour(archive: dict[str, Any], tickets: dict[str, Any], matchs: list[dict[str, Any]],
               evaluer: Callable[[str, int, int], str | None], maintenant: str) -> tuple[dict[str, Any], bool, int]:
    ajoute = enregistre(archive, tickets)
    regles = regle(archive, matchs, evaluer, maintenant)
    archive["bilan"] = bilan(archive, maintenant)
    return archive, ajoute, regles


def charge_archive(path: Path = ARCHIVE) -> dict[str, Any]:
    a = load_json(path, None)
    if not isinstance(a, dict) or not isinstance(a.get("executions"), list) or not isinstance(a.get("resultats"), dict):
        return archive_vide()
    a.setdefault("version", VERSION)
    return a


def ecrit_archive(archive: dict[str, Any], path: Path = ARCHIVE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def lit_matchs_et_evaluateur() -> tuple[list[dict[str, Any]], Callable[[str, int, int], str | None]]:
    import journal_rentabilite as jr
    import suivi_tickets as st
    return jr.charge_tous_resultats(), st.evaluateur_defaut()


def versions_git() -> list[dict[str, Any]]:
    """Toutes les versions de data/tickets.json dans l'historique Git, de la plus ancienne à la plus récente."""
    commits = subprocess.run(["git", "log", "--reverse", "--format=%H", "--", str(TICKETS)], capture_output=True, text=True, check=True).stdout.split()
    out = []
    for c in commits:
        r = subprocess.run(["git", "show", f"{c}:{TICKETS}"], capture_output=True, text=True)
        if r.returncode == 0:
            try:
                out.append(json.loads(r.stdout))
            except ValueError:
                continue
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat()
    archive = charge_archive()
    versions = []
    if "--rattrapage" in argv:
        versions = versions_git()
    versions.append(load_json(TICKETS, {}) or {})
    ajoutes = sum(1 for t in versions if enregistre(archive, t))
    archive["derniere_erreur"] = None
    regles = 0
    try:
        matchs, evaluer = lit_matchs_et_evaluateur()
        regles = regle(archive, matchs, evaluer, maintenant)
    except Exception as exc:  # noqa: BLE001 - la sélection reste archivée ; l'erreur est écrite et affichée
        archive["derniere_erreur"] = f"{type(exc).__name__}: {exc}"
        print(f"[selection generateur] résultats non mis à jour : {archive['derniere_erreur']}")
    archive["bilan"] = bilan(archive, maintenant)
    ecrit_archive(archive)
    print(json.dumps({"executions": len(archive["executions"]), "ajoutees": ajoutes, "regles_ce_jour": regles,
                      "paris_regles": len(archive["resultats"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
