"""Données du moteur omega : séries au même lieu, références de championnat, chargement des deux sources de matchs.

Règles (reprises des moteurs déjà construits) :
- Série au MÊME LIEU : matchs à domicile de l'équipe qui reçoit, matchs à l'extérieur de l'autre ; saison en cours et même compétition seulement
  (la saison passée n'entre jamais dans les calculs d'équipe) ; date STRICTEMENT antérieure au jour du match (anti-fuite).
- Minimum 4 matchs par équipe (règle de Patrick) ; sinon le match est exclu. Taille maximale de la fenêtre : apprise sur les données (calibrage).
- Référence de championnat (moyenne de buts à domicile et à l'extérieur) : matchs du même championnat, même saison, strictement antérieurs.
- Sources : bloc Football-Data (calibrage et validation), archive ARCHETYPE `data/archive_test` (validation finale et production).
"""
from __future__ import annotations

import bisect
import glob
import gzip
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BLOC = ROOT / "data" / "bloc_saisons" / "bloc_2526_2627.json.gz"
ARCHIVE = ROOT / "data" / "archive_test"
MIN_MATCHS = 4


def _buts_ok(m: dict) -> bool:
    return isinstance(m.get("buts_marques"), int) and isinstance(m.get("buts_encaisses"), int)


def serie_lieu(matchs: list[dict] | None, domicile: bool, jour: str, fenetre: int | None) -> tuple[list[int], list[int]]:
    """(buts marqués, buts encaissés) au lieu demandé, strictement avant `jour`, du plus ancien au plus récent, `fenetre` derniers au plus."""
    ms = [m for m in (matchs or []) if bool(m.get("domicile")) is bool(domicile) and str(m.get("date"))[:10] < jour and _buts_ok(m)]
    ms.sort(key=lambda m: str(m["date"])[:10])
    if fenetre:
        ms = ms[-fenetre:]
    return [m["buts_marques"] for m in ms], [m["buts_encaisses"] for m in ms]


class References:
    """Moyennes de buts à domicile / à l'extérieur d'un championnat, calculées sur ses matchs strictement antérieurs à une date."""

    def __init__(self) -> None:
        self._brut: dict[str, dict[tuple, tuple[str, int, int]]] = defaultdict(dict)
        self._idx: dict[str, tuple[list[str], list[int], list[int]]] = {}

    def ajouter(self, ligue: str, date: str, equipe_dom: str, buts_dom: int, buts_ext: int) -> None:
        self._brut[ligue][(equipe_dom, date[:10])] = (date[:10], int(buts_dom), int(buts_ext))
        self._idx.pop(ligue, None)

    def avant(self, ligue: str, jour: str) -> tuple[int, float, float]:
        """(nombre de matchs, total buts domicile, total buts extérieur) strictement avant `jour`."""
        if ligue not in self._idx:
            lst = sorted(self._brut.get(ligue, {}).values())
            dates, cum_h, cum_a = [], [0], [0]
            for d, h, a in lst:
                dates.append(d)
                cum_h.append(cum_h[-1] + h)
                cum_a.append(cum_a[-1] + a)
            self._idx[ligue] = (dates, cum_h, cum_a)
        dates, cum_h, cum_a = self._idx[ligue]
        k = bisect.bisect_left(dates, jour)
        return k, float(cum_h[k]), float(cum_a[k])


def _m(date: str, domicile: bool, gm: int, gc: int) -> dict:
    return {"date": date, "domicile": domicile, "buts_marques": gm, "buts_encaisses": gc}


def charger_football_data(chemin: Path = BLOC) -> tuple[list[dict[str, Any]], References]:
    """Matchs du bloc Football-Data. Historique d'équipe : même saison ET même division (aucune donnée de la saison passée)."""
    liste = sorted(json.load(gzip.open(chemin))["liste"], key=lambda m: (m["date"], m["id"]))
    equipes: dict[tuple, list] = defaultdict(list)
    refs = References()
    for m in liste:
        cle = (m["saison"], m["division"])
        equipes[cle + (m["domicile"],)].append(_m(m["date"], True, m["buts_dom"], m["buts_ext"]))
        equipes[cle + (m["exterieur"],)].append(_m(m["date"], False, m["buts_ext"], m["buts_dom"]))
        refs.ajouter(f"fd|{m['saison']}|{m['division']}", m["date"], m["domicile"], m["buts_dom"], m["buts_ext"])
    out = []
    for m in liste:
        cle = (m["saison"], m["division"])
        out.append({"id": m["id"], "source": "football-data", "saison": m["saison"], "ligue": f"fd|{m['saison']}|{m['division']}",
                    "competition": m.get("competition"), "jour": m["date"], "domicile": m["domicile"], "exterieur": m["exterieur"],
                    "dom_matchs": equipes[cle + (m["domicile"],)], "ext_matchs": equipes[cle + (m["exterieur"],)],
                    "h": m["buts_dom"], "a": m["buts_ext"], "cotes_fd": m.get("cotes") or {}, "cotes": None})
    return out, refs


def ligue_archetype(competition: Any) -> str:
    return "archetype|" + " ".join(str(competition or "").lower().split())


def _equipes_archive(x: dict) -> tuple[dict | None, dict | None]:
    """Historique d'équipe : assemblage figé (Football-Data + jours manquants), sinon le bloc équipe de l'archive (même règle que l'alpha)."""
    a = x.get("assemblage") or {}
    dom = a.get("equipe_dom") if "matchs" in (a.get("equipe_dom") or {}) else x.get("equipe_dom")
    ext = a.get("equipe_ext") if "matchs" in (a.get("equipe_ext") or {}) else x.get("equipe_ext")
    return dom, ext


def charger_archive(dossier: Path = ARCHIVE, avec_futurs: bool = True) -> tuple[list[dict[str, Any]], References]:
    """Matchs de l'archive ARCHETYPE, sans doublon (match_id, puis jour + équipes ; l'enregistrement le plus récent est gardé).
    Matchs joués : gardés seulement si leurs cotes ont été prises avant le coup d'envoi (aucune cote a posteriori).
    Les références de championnat sont reconstruites à partir des matchs à domicile figurant dans les historiques d'équipes."""
    vus: dict[str, dict] = {}
    refs = References()
    for f in sorted(glob.glob(str(dossier / "*.json.gz"))):
        for k, x in json.load(gzip.open(f)).items():
            dom, ext = _equipes_archive(x)
            ligue = ligue_archetype(x.get("competition"))
            for eq, nom in ((dom, x.get("domicile")), (ext, x.get("exterieur"))):
                for mm in (eq or {}).get("matchs") or []:
                    if mm.get("domicile") and _buts_ok(mm) and mm.get("date"):
                        refs.ajouter(ligue, str(mm["date"])[:10], str(nom), mm["buts_marques"], mm["buts_encaisses"])
            if "matchs" not in (dom or {}) or "matchs" not in (ext or {}):
                continue
            sc = x.get("score") or {}
            joue = sc.get("buts_dom") is not None and sc.get("buts_ext") is not None
            if not joue and not avec_futurs:
                continue
            pris, coup = (x.get("run") or {}).get("pris_le"), x.get("coup_d_envoi_utc")
            if joue and (not pris or not coup or str(pris) >= str(coup)):
                continue
            jour = str(x["date"])[:10]
            cle = str(x.get("match_id") or f"{jour}|{x.get('domicile')}|{x.get('exterieur')}")
            vus[cle] = {"id": f"archetype|{cle}", "match_id": x.get("match_id"), "source": "archetype", "ligue": ligue,
                        "competition": " ".join(str(x.get("competition") or "").split()), "jour": jour, "heure": x.get("heure_cameroun"),
                        "coup_d_envoi_utc": coup, "domicile": x.get("domicile"), "exterieur": x.get("exterieur"),
                        "dom_matchs": dom["matchs"], "ext_matchs": ext["matchs"],
                        "h": sc.get("buts_dom") if joue else None, "a": sc.get("buts_ext") if joue else None,
                        "cotes": x.get("cotes_betpawa") or {}, "cotes_prises_le": pris}
    par_equipes: dict[tuple, dict] = {}
    for m in vus.values():
        par_equipes[(m["jour"], m["domicile"], m["exterieur"])] = m
    return sorted(par_equipes.values(), key=lambda m: (m["jour"], m["id"])), refs
