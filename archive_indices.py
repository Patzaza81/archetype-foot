"""archive_indices.py -- archive de l'indice de performance (x/4) des paris de V2, V3 et du Journal.

Pourquoi : l'indice (moteur_v3/performance.py) n'était écrit que dans des fichiers réécrits à chaque exécution
(precalcul.json, journal.json, data/v3/journal/*.json). Aucun historique ne permettait de le suivre ni de le régler.

Ce module écrit data/indices/AAAA-MM-JJ.json.gz (jour du MATCH), une ligne par pari et par moteur :
- v2      : choix de production P1-P3 (archive de test, bloc `moteur_en_production`) ;
- v3      : sélection finale + marchés valides écartés (`alternatives_indice`) de data/v3/journal/AAAA-MM-JJ.json ;
- journal : paris du Journal vus par le générateur (data/selection_generateur_historique.json).

Règles (mêmes que l'archive de test, docs/CLAUDE_ARCHIVE.md) :
- Anti-fuite : l'indice est calculé UNIQUEMENT avec les matchs d'équipe de l'archive de test, déjà figés avant le match.
- Figé au coup d'envoi : tant que le match n'a pas commencé, la ligne reçoit le dernier état ; ensuite plus rien ne
  change sauf le score et le résultat, écrits UNE seule fois et jamais modifiés.
- `origine` : « natif » = écrite avant le coup d'envoi ; « recalcule » = rattrapage après coup (même logique, même
  données figées, mais pas vue en direct).
- `actif` : vrai si le pari était encore proposé au dernier passage avant le coup d'envoi ; faux s'il a été retiré
  (la ligne n'est jamais supprimée). Les bilans ne comptent que les lignes actives.
- Aucune ligne n'est jamais supprimée. `version_indice` suit la version de la logique de l'indice.

Usage : python archive_indices.py [--depuis AAAA-MM-JJ | --tout] [--resultats] [--bilan]
Information seulement : ne modifie ni les moteurs, ni les sélections, ni les cotes.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
from typing import Any, Callable, Mapping

import archive_donnees_test as adt
from moteur_v3.model import _latest
from moteur_v3.performance import indice_performance

SCHEMA_VERSION = 1
DOSSIER = os.path.join("data", "indices")
DOSSIER_ARCHIVE_TEST = adt.DOSSIER
DOSSIER_V3 = os.path.join("data", "v3", "journal")
FICHIER_GENERATEUR = os.path.join("data", "selection_generateur_historique.json")
UTC = datetime.timezone.utc
SOURCES = ("v2", "v3", "journal")


# --- utilitaires ----------------------------------------------------------------------------------------------------

def maintenant_utc() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def iso(t: datetime.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def chemin(dossier: str, date: str) -> str:
    return os.path.join(dossier, f"{date}.json.gz")


def coup_d_envoi(match: Mapping[str, Any]) -> datetime.datetime | None:
    """Coup d'envoi (UTC) : champ de l'archive de test, sinon date + heure du Cameroun. None si inconnu (jamais deviné)."""
    brut = match.get("coup_d_envoi_utc")
    if brut:
        try:
            return datetime.datetime.fromisoformat(str(brut).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    return adt.coup_d_envoi_utc(match.get("date"), match.get("heure_cameroun"))


def matchs_du_jour(date: str, dossier_archive: str = DOSSIER_ARCHIVE_TEST) -> dict[str, dict[str, Any]]:
    return adt.charge_fichier(adt._chemin(dossier_archive, date))


def a_un_score(match: Mapping[str, Any]) -> bool:
    return (match.get("score") or {}).get("buts_dom") is not None


# --- indice ---------------------------------------------------------------------------------------------------------

def calcule_indice(marche_v3: str | None, match: Mapping[str, Any]) -> tuple[dict[str, Any] | None, int, int, str | None]:
    """(indice complet ou None, n matchs domicile, n matchs extérieur, raison si pas d'indice).
    Matchs d'équipe au même lieu, tirés de l'archive de test (figés avant le match) : aucune fuite possible."""
    dom = _latest((match.get("equipe_dom") or {}).get("matchs") or [], True)
    ext = _latest((match.get("equipe_ext") or {}).get("matchs") or [], False)
    if not marche_v3:
        return None, len(dom), len(ext), "marche_sans_indice"
    if not dom or not ext:
        return None, len(dom), len(ext), "historique_domicile_ou_exterieur_absent"
    p = indice_performance(marche_v3, dom, ext)
    if p is None:
        return None, len(dom), len(ext), "marche_sans_indice"
    return p, len(dom), len(ext), None


def construit_ligne(source: str, role: str, rang: str | None, pick: Mapping[str, Any], match: Mapping[str, Any],
                    marche_v3: str | None, marche: str, equipe_suivie: str | None = None) -> dict[str, Any]:
    p, n_dom, n_ext, raison = calcule_indice(marche_v3, match)
    cle = (f"{match['match_id']}|{source}|{marche}" + (f"|{equipe_suivie}" if equipe_suivie else "")
           + ("" if role == "selection" else f"|{role}"))
    ligne = {
        "id": cle, "schema_version": SCHEMA_VERSION, "source": source, "role": role, "rang": rang,
        "date": match.get("date"), "heure_cameroun": match.get("heure_cameroun"),
        "coup_d_envoi_utc": (iso(coup_d_envoi(match)) if coup_d_envoi(match) else None),
        "match_id": match["match_id"], "domicile": match.get("domicile"), "exterieur": match.get("exterieur"),
        "competition": match.get("competition"),
        "marche": marche, "marche_v3": marche_v3, "equipe_suivie": equipe_suivie,
        "cote": pick.get("cote"), "probabilite": pick.get("probabilite"),
        "indice": None if p is None else p.get("indice"), "sur": None if p is None else p.get("sur"),
        "niveau": None if p is None else p.get("niveau"),
        "version_indice": None if p is None else p.get("version"),
        "scenarios": None if p is None else p.get("scenarios"),
        "moyenne_domicile": None if p is None else p.get("moyenne_domicile"),
        "moyenne_exterieur": None if p is None else p.get("moyenne_exterieur"),
        "pire_domicile": None if p is None else p.get("pire_domicile"),
        "pire_exterieur": None if p is None else p.get("pire_exterieur"),
        "indice_raison": raison, "n_domicile": n_dom, "n_exterieur": n_ext,
        "score": None, "resultat": None, "regle_le": None,
    }
    return ligne


# --- extraction des paris de chaque moteur --------------------------------------------------------------------------

def lignes_v2(match: Mapping[str, Any]) -> list[dict[str, Any]]:
    import v2_indice
    choix = (match.get("moteur_en_production") or {}).get("choix") or {}
    out = []
    for rang, c in sorted(choix.items()):
        if not isinstance(c, dict) or not c.get("marche"):
            continue
        out.append(construit_ligne("v2", "selection", rang, c, match,
                                   v2_indice.marche_v3(str(c.get("marche_moteur") or "")), str(c["marche"])))
    return out


def lignes_v3(fiche: Mapping[str, Any], match: Mapping[str, Any]) -> list[dict[str, Any]]:
    out = []
    for i, s in enumerate(fiche.get("selections") or [], 1):
        out.append(construit_ligne("v3", "selection", f"S{i}", s, match, s.get("marche"), str(s["marche"])))
    for a in fiche.get("alternatives_indice") or []:
        mv3 = a.get("marche_moteur") or a.get("marche")
        out.append(construit_ligne("v3", "alternative", None, a, match, mv3, str(mv3)))
    return out


def lignes_journal(paris: list[Mapping[str, Any]], date: str, matchs: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    import journal_indice
    from equipe_betpawa import memes_equipes
    out = []
    for p in paris:
        if p.get("date") != date:
            continue
        m = next((e for e in matchs.values() if memes_equipes(p.get("domicile"), e.get("domicile"))
                  and memes_equipes(p.get("exterieur"), e.get("exterieur"))), None)
        if m is None or not p.get("journal_team"):
            continue
        a_domicile = bool(memes_equipes(p["journal_team"], m.get("domicile")))
        mv3 = journal_indice.marche_moteur(str(p.get("marche") or ""), a_domicile)
        canon = str(p.get("marche_canonique") or p.get("marche"))
        pick = {"cote": p.get("cote"), "probabilite": p.get("probabilite_estimee")}
        l = construit_ligne("journal", "selection", None, pick, m, mv3, canon, equipe_suivie=str(p["journal_team"]))
        l["libelle"] = p.get("marche")
        l["journal_observations"] = p.get("journal_observations")
        l["journal_victoires"] = p.get("journal_wins")
        out.append(l)
    return out


# --- écriture figée -------------------------------------------------------------------------------------------------

def fusionne(doc: dict[str, Any], nouvelles: list[dict[str, Any]], traites: set[tuple[str, str]], date: str,
             matchs: Mapping[str, Mapping[str, Any]], maintenant: datetime.datetime) -> dict[str, int]:
    """Met à jour `doc["lignes"]` en respectant le gel au coup d'envoi.
    `traites` = {(source, match_id)} réellement examinés par ce passage (une ligne d'un match non examiné n'est pas touchée)."""
    lignes = doc.setdefault("lignes", {})
    bilan = {"ecrites": 0, "gelees": 0, "retirees": 0}
    vues = set()
    for n in nouvelles:
        vues.add(n["id"])
        m = matchs.get(n["match_id"]) or {}
        ko = coup_d_envoi(m)
        exist = lignes.get(n["id"])
        if not adt.peut_mettre_a_jour(exist, date, ko, maintenant):
            bilan["gelees"] += 1
            continue
        if exist:
            n["premiere_vue_le"] = exist.get("premiere_vue_le") or iso(maintenant)
        else:
            n["premiere_vue_le"] = iso(maintenant)
        n["derniere_vue_le"] = iso(maintenant)
        n["fige_le"] = iso(maintenant)
        n["origine"] = "natif" if (ko is not None and maintenant < ko) or (ko is None and maintenant.date() <= datetime.date.fromisoformat(date)) else "recalcule"
        n["actif"] = True
        lignes[n["id"]] = n
        bilan["ecrites"] += 1
    for cle, l in lignes.items():
        if cle in vues or (l["source"], l["match_id"]) not in traites or not l.get("actif", True):
            continue
        m = matchs.get(l["match_id"]) or {}
        if adt.peut_mettre_a_jour(l, date, coup_d_envoi(m), maintenant):
            l["actif"] = False
            l["retire_le"] = iso(maintenant)
            bilan["retirees"] += 1
    return bilan


def execute(depuis: str | None = None, dossier: str = DOSSIER, dossier_archive: str = DOSSIER_ARCHIVE_TEST,
            dossier_v3: str = DOSSIER_V3, fichier_generateur: str = FICHIER_GENERATEUR,
            maintenant: datetime.datetime | None = None) -> dict[str, Any]:
    """Un passage : écrit/rafraîchit les lignes des dates >= `depuis` (par défaut : hier, aujourd'hui et la suite)."""
    maintenant = maintenant or maintenant_utc()
    depuis = depuis or (maintenant.date() - datetime.timedelta(days=1)).isoformat()
    paris_journal: list[dict[str, Any]] = []
    try:
        with open(fichier_generateur, encoding="utf-8") as f:
            vus = {}
            for e in json.load(f).get("executions") or []:
                for p in e.get("paris") or []:
                    if p.get("source") == "journal":
                        vus[p["id"]] = p
            paris_journal = list(vus.values())
    except (FileNotFoundError, ValueError):
        pass
    dates = sorted(os.path.basename(p)[:10] for p in glob.glob(os.path.join(dossier_archive, "*.json.gz")))
    total = {"ecrites": 0, "gelees": 0, "retirees": 0, "dates": 0}
    for date in dates:
        if date < depuis:
            continue
        matchs = matchs_du_jour(date, dossier_archive)
        try:
            with open(os.path.join(dossier_v3, f"{date}.json"), encoding="utf-8") as f:
                fiches_v3 = json.load(f)
        except (FileNotFoundError, ValueError):
            fiches_v3 = {}
        doc = adt.charge_fichier(chemin(dossier, date)) or {"schema_version": SCHEMA_VERSION, "date": date, "lignes": {}}
        nouvelles, traites = [], set()
        for mid, m in matchs.items():
            if m.get("date") != date or not m.get("match_id"):
                continue
            if (m.get("moteur_en_production") or {}).get("choix"):
                nouvelles += lignes_v2(m)
            traites.add(("v2", mid))
        for mid, fiche in fiches_v3.items():
            m = matchs.get(mid)
            if not m:
                continue
            nouvelles += lignes_v3(fiche, m)
            traites.add(("v3", mid))
        nj = lignes_journal(paris_journal, date, matchs)
        nouvelles += nj
        traites |= {("journal", m["match_id"]) for m in matchs.values() if m.get("date") == date and m.get("match_id")}
        b = fusionne(doc, nouvelles, traites, date, matchs, maintenant)
        if doc["lignes"]:
            adt.sauve_fichier(chemin(dossier, date), doc)
            total["dates"] += 1
        for k in ("ecrites", "gelees", "retirees"):
            total[k] += b[k]
    return total


# --- résultats ------------------------------------------------------------------------------------------------------

def evaluateur() -> Callable[[dict[str, Any], int, int], str | None]:
    """Règle un pari avec le règlement du pipeline : V3 par moteur_v3.markets.gagne, V2/Journal par le règlement canonique."""
    from moteur_v3.markets import gagne
    import suivi_tickets
    ev = suivi_tickets.evaluateur_defaut()

    def regle(l: dict[str, Any], h: int, a: int) -> str | None:
        if l["source"] == "v3":
            g = gagne(str(l["marche"]), h, a)
            return None if g is None else ("WIN" if g else "LOSS")
        r = ev(str(l["marche"]), h, a)
        if r is None and l.get("libelle"):
            r = ev(str(l["libelle"]), h, a)
        return r if r in ("WIN", "LOSS", "PUSH", "VOID") else None
    return regle


def complete_resultats(dossier: str = DOSSIER, dossier_archive: str = DOSSIER_ARCHIVE_TEST,
                       maintenant: datetime.datetime | None = None, regle: Callable | None = None) -> dict[str, int]:
    """Écrit score + résultat une seule fois pour les lignes dont le match a un score. Un résultat existant n'est jamais modifié."""
    maintenant = maintenant or maintenant_utc()
    regle = regle or evaluateur()
    bilan = {"reglees": 0, "sans_regle": 0}
    for p in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        date = os.path.basename(p)[:10]
        doc = adt.charge_fichier(p)
        matchs = None
        change = False
        for l in doc.get("lignes", {}).values():
            if l.get("resultat") is not None or l.get("score") is not None:
                continue
            if matchs is None:
                matchs = matchs_du_jour(date, dossier_archive)
            s = (matchs.get(l["match_id"]) or {}).get("score") or {}
            if s.get("buts_dom") is None:
                continue
            l["score"] = {"buts_dom": s["buts_dom"], "buts_ext": s["buts_ext"]}
            l["resultat"] = regle(l, s["buts_dom"], s["buts_ext"])
            l["regle_le"] = iso(maintenant)
            change = True
            bilan["reglees" if l["resultat"] else "sans_regle"] += 1
        if change:
            adt.sauve_fichier(p, doc)
    return bilan


# --- bilan ----------------------------------------------------------------------------------------------------------

def lignes_reglees(dossier: str = DOSSIER, roles: tuple[str, ...] = ("selection",), actives: bool = True):
    for p in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        for l in adt.charge_fichier(p).get("lignes", {}).values():
            if l.get("resultat") in ("WIN", "LOSS") and l.get("role") in roles and (l.get("actif", True) or not actives):
                yield l


def bilan(dossier: str = DOSSIER, roles: tuple[str, ...] = ("selection",)) -> str:
    """Taux de réussite par moteur et par indice (+ cote moyenne et rendement à mise plate)."""
    cases: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for l in lignes_reglees(dossier, roles):
        k = "sans indice" if l.get("indice") is None else f"{l['indice']}/{l.get('sur') or 4}"
        cases.setdefault((l["source"], k), []).append(l)
    out = ["moteur   indice        gagnes/paris  taux   cote   rendement"]
    for (src, k), L in sorted(cases.items(), key=lambda kv: (SOURCES.index(kv[0][0]), kv[0][1])):
        w = sum(1 for x in L if x["resultat"] == "WIN")
        cotes = [x["cote"] for x in L if x.get("cote")]
        gain = sum((x["cote"] - 1) if x["resultat"] == "WIN" else -1 for x in L if x.get("cote"))
        out.append(f"{src:8s} {k:12s} {w:5d}/{len(L):<5d} {w / len(L):6.1%} {sum(cotes) / max(1, len(cotes)):5.2f} "
                   f"{gain / max(1, len(cotes)):+7.1%}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Archive de l'indice de performance (V2, V3, Journal).")
    ap.add_argument("--depuis", help="première date de match à (re)traiter, AAAA-MM-JJ (défaut : hier)")
    ap.add_argument("--tout", action="store_true", help="rattrape toutes les dates de l'archive de test")
    ap.add_argument("--resultats", action="store_true", help="écrit seulement score + résultat des lignes existantes")
    ap.add_argument("--bilan", action="store_true", help="affiche le bilan par moteur et par indice")
    a = ap.parse_args(argv)
    if a.bilan:
        print(bilan())
        return 0
    if not a.resultats:
        print(f"[archive indices] {execute('0000-00-00' if a.tout else a.depuis)}")
    print(f"[archive indices] résultats : {complete_resultats()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
