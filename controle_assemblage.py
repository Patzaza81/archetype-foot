"""Contrôle d'intégrité de data/assemblage/equipes.json (enquête du 01/11/2026). LECTURE SEULE : ne modifie aucun fichier.

Pourquoi : le 31/10/2026 l'assemblage a perdu 22 matchs de Série B (Cremonese, Mantova), en a gagné 13 mal attribués, produit « Virtus – Virtus »
et vidé 11 championnats, sans que rien ne bloque la publication (voir docs/ENQUETE_ASSEMBLAGE.md).

Contrôles BLOQUANTS (invariants logiques, aucun seuil choisi) :
  1. auto-rencontre brute : un match d'une équipe dont l'adversaire porte son propre nom (erreur de la source) ;
  2. doublon dans la liste d'une équipe : même date, même adversaire, même score, même lieu, deux fois ;
  3. incohérence croisée : deux équipes du cache se citent à la même date mais avec des scores qui ne sont pas inverses ;
  4. (vue du moteur, via moteur_dc.donnees.Ligues si disponible) auto-rencontre ou doublon de rencontre après reconstruction des identités ;
  5. couverture : un championnat ATTENDU (liste fournie : celui des matchs AVEC cotes BetPawa de la fenêtre du pipeline (precalcul_leger.json)) sans aucun match dans l'assemblage.
Informations (non bloquantes) : volumes avant/après par championnat, championnats passés à zéro, clubs par championnat.

Usage : python controle_assemblage.py [--assemblage chemin] [--avant chemin] [--attendus fichier.json ...] [--verifier]
`--verifier` : code de sortie 1 si un contrôle bloquant échoue (à brancher AVANT la publication, voir la documentation).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent
ASSEMBLAGE = RACINE / "data" / "assemblage" / "equipes.json"


def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s or "").lower()).encode("ascii", "ignore").decode())


def _slug(cle: str) -> str:
    m = re.search(r"/equipe/(.+)_[a-z0-9]{20,}\.html", cle or "")
    return norm(m.group(1)) if m else ""


def _noms_propres(x: dict[str, Any]) -> set[str]:
    return {n for n in (norm(x.get("nom_football_data")), norm(x.get("nom_matchendirect")), _slug(x.get("cle_cache", ""))) if n}


# --- 1 à 3 : données brutes ------------------------------------------------------------------------------------------
def auto_rencontres_brutes(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for x in doc["equipes"]:
        propres = _noms_propres(x)
        for m in x.get("matchs") or []:
            if m.get("adversaire") and norm(m["adversaire"]) in propres:
                out.append({"equipe": x["cle_cache"], "date": str(m.get("date"))[:10], "adversaire": m["adversaire"],
                            "score": [m.get("buts_marques"), m.get("buts_encaisses")]})
    return out


def doublons_par_equipe(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for x in doc["equipes"]:
        c = Counter((str(m.get("date"))[:10], norm(m.get("adversaire")), bool(m.get("domicile")), m.get("buts_marques"), m.get("buts_encaisses"))
                    for m in x.get("matchs") or [])
        out += [{"equipe": x["cle_cache"], "date": k[0], "adversaire": k[1], "fois": n} for k, n in c.items() if n > 1]
    return out


def incoherences_croisees(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """A cite B à une date avec le score g-c ; si B (du cache, même championnat) cite A à la même date, son score doit être c-g."""
    par: dict[tuple, dict[tuple, tuple]] = defaultdict(dict)       # (championnat, date, équipe) -> {(adversaire normalisé): (pour, contre)}
    noms: dict[tuple, str] = {}
    for x in doc["equipes"]:
        for n in _noms_propres(x):
            noms[(x["competition"], n)] = x["cle_cache"]
    out = []
    for x in doc["equipes"]:
        for m in x.get("matchs") or []:
            if isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int):
                par[(x["competition"], str(m.get("date"))[:10], x["cle_cache"])].setdefault(norm(m.get("adversaire")), (m["buts_marques"], m["buts_encaisses"]))
    for (lg, d, t), adv in par.items():
        for nom, (g, c) in adv.items():
            autre = noms.get((lg, nom))
            if not autre or autre == t:
                continue
            retour = par.get((lg, d, autre), {})
            propres = {n for (l2, n), k in noms.items() if l2 == lg and k == t}
            for n in propres:
                if n in retour and retour[n] != (c, g):
                    out.append({"championnat": lg, "date": d, "equipes": [t, autre], "score_vu_par_la_premiere": [g, c], "score_vu_par_la_seconde": list(retour[n])})
                    break
    return out


# --- 4 : vue du moteur -----------------------------------------------------------------------------------------------
def vue_moteur(doc: dict[str, Any], classe: Any = None) -> dict[str, Any]:
    """Ce que verra Gamma : championnats reconstitués par moteur_dc.donnees.Ligues (ou la classe passée)."""
    if classe is None:
        from moteur_dc.donnees import Ligues as classe
    L = classe(doc)
    auto, dup, ident = [], [], {}
    for lg, ms in L.matchs.items():
        auto += [{"championnat": lg, "date": m["date"], "equipe": m["dom"], "score": [m["h"], m["a"]]} for m in ms if m["dom"] == m["ext"]]
        c = Counter((m["date"], frozenset((m["dom"], m["ext"]))) for m in ms)
        dup += [{"championnat": lg, "date": k[0]} for k, n in c.items() if n > 1]
        ident[lg] = len({m[k] for m in ms for k in ("dom", "ext")})
    return {"auto_rencontres": auto, "doublons_rencontre": dup, "identites_par_championnat": ident,
            "matchs_par_championnat": {lg: len(ms) for lg, ms in L.matchs.items()}}


# --- 5 et information : volumes, couverture --------------------------------------------------------------------------
def volumes(doc: dict[str, Any], classe: Any = None) -> dict[str, dict[str, int]]:
    v = vue_moteur(doc, classe)
    eq = Counter(x["competition"] for x in doc["equipes"])
    return {lg: {"equipes": eq.get(lg, 0), "identites": v["identites_par_championnat"].get(lg, 0), "matchs": v["matchs_par_championnat"].get(lg, 0)}
            for lg in sorted(set(eq) | set(v["matchs_par_championnat"]))}


def comparer_volumes(avant: dict[str, dict[str, int]], apres: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Évolution par championnat ; `passes_a_zero` = avait des matchs, n'en a plus."""
    lignes = {lg: {"matchs_avant": avant.get(lg, {}).get("matchs", 0), "matchs_apres": apres.get(lg, {}).get("matchs", 0),
                   "equipes_avant": avant.get(lg, {}).get("equipes", 0), "equipes_apres": apres.get(lg, {}).get("equipes", 0)}
              for lg in sorted(set(avant) | set(apres))}
    return {"total_avant": sum(v["matchs_avant"] for v in lignes.values()), "total_apres": sum(v["matchs_apres"] for v in lignes.values()),
            "passes_a_zero": [lg for lg, v in lignes.items() if v["matchs_avant"] and not v["matchs_apres"]],
            "perdent_des_equipes": [lg for lg, v in lignes.items() if v["equipes_apres"] < v["equipes_avant"]], "par_championnat": lignes}


def championnats_attendus(fichier: Path = RACINE / "precalcul_leger.json") -> set[str]:
    """Championnats attendus = ceux qui ont au moins un match AVEC cotes BetPawa dans la fenêtre du pipeline (les seuls que Gamma peut pronostiquer)."""
    if not fichier.exists():
        return set()
    d = json.loads(fichier.read_text(encoding="utf-8"))
    matchs = (d.get("matchs") or d.get("signaux") or []) if isinstance(d, dict) else d
    return {" ".join(str(m["competition"]).split()).lower() for m in matchs if isinstance(m, dict) and m.get("competition") and m.get("cotes_manuelles")}


def manquants(doc: dict[str, Any], attendus: set[str], classe: Any = None) -> list[str]:
    """Championnats attendus sans aucun match dans l'assemblage (vue du moteur)."""
    v = volumes(doc, classe)
    return sorted(lg for lg in attendus if not v.get(lg, {}).get("matchs"))


def controler(doc: dict[str, Any], attendus: set[str] | None = None, classe: Any = None, moteur: bool = True) -> dict[str, Any]:
    bloquants = {"auto_rencontres_brutes": auto_rencontres_brutes(doc), "doublons_par_equipe": doublons_par_equipe(doc),
                 "incoherences_croisees": incoherences_croisees(doc)}
    info: dict[str, Any] = {}
    if moteur:
        try:
            vm = vue_moteur(doc, classe)
            bloquants["auto_rencontres_vue_moteur"], bloquants["doublons_rencontre_vue_moteur"] = vm["auto_rencontres"], vm["doublons_rencontre"]
            info["matchs_vue_moteur"] = sum(vm["matchs_par_championnat"].values())
        except ImportError:
            info["vue_moteur"] = "non contrôlée (moteur_dc indisponible)"
    if attendus is not None:
        bloquants["championnats_attendus_sans_match"] = manquants(doc, attendus, classe) if moteur else []
    return {"ok": not any(bloquants.values()), "bloquants": bloquants, "violations": {k: len(v) for k, v in bloquants.items()}, "information": info}


def main(argv: list[str]) -> int:
    chemin = Path(argv[argv.index("--assemblage") + 1]) if "--assemblage" in argv else ASSEMBLAGE
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    attendus = championnats_attendus() if "--attendus" in argv else None
    r = controler(doc, attendus)
    if "--avant" in argv:
        avant = json.loads(Path(argv[argv.index("--avant") + 1]).read_text(encoding="utf-8"))
        r["volumes"] = comparer_volumes(volumes(avant), volumes(doc))
    print(json.dumps({k: v for k, v in r.items() if k != "bloquants"}, ensure_ascii=False, indent=1))
    for k, v in r["bloquants"].items():
        if v:
            print(f"BLOQUANT {k} : {len(v)} -> {json.dumps(v[:3], ensure_ascii=False)}")
    if "--verifier" in argv and not r["ok"]:
        print("Assemblage non conforme : publication à bloquer.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
