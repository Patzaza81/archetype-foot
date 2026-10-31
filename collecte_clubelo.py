"""Collecte de l'Elo des clubs (clubelo.com, API CSV publique) pour la piste B' du moteur DC (branche moteur-dc-elo).

Un fichier par date : data/clubelo/AAAA-MM-JJ.csv (colonnes Rank, Club, Country, Level, Elo, From, To), une date tous les `--pas` jours (7 par défaut :
le moteur DC réajuste ses forces chaque semaine ; un match du jour J utilisera l'instantané le plus récent daté au plus de J − 1, donc strictement antérieur).
Rien n'est deviné : une réponse qui n'a pas l'en-tête attendu est refusée et comptée en erreur ; 3 échecs consécutifs arrêtent la collecte.
Les fichiers déjà présents ne sont pas retéléchargés. Pause entre deux requêtes (service gratuit : on le ménage). Sortie : data/clubelo/manifest.json.
Usage : python collecte_clubelo.py [--debut 2025-02-27] [--fin AAAA-MM-JJ] [--pas 7] [--pause 1.5]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

DOSSIER = Path(__file__).resolve().parent / "data" / "clubelo"
URL = "https://api.clubelo.com/{jour}"
ENTETE = "Rank,Club,Country,Level,Elo,From,To"
MAX_ECHECS_DE_SUITE = 3
DEBUT_DEFAUT = "2025-02-27"           # la veille du premier match de la saison 2025-26 du bloc Football-Data (2025-02-28)
AGENT = "archetype-foot-collecte/1.0 (recherche personnelle, une requete toutes les quelques secondes)"


def dates(debut: str, fin: str, pas: int) -> list[str]:
    d, f = date.fromisoformat(debut), date.fromisoformat(fin)
    out = []
    while d <= f:
        out.append(d.isoformat())
        d += timedelta(days=pas)
    return out


def valider(texte: str) -> list[dict]:
    """Lignes du CSV ; ValueError si l'en-tête n'est pas celui attendu ou si une ligne est inutilisable."""
    lignes = [l for l in texte.strip().splitlines() if l.strip()]
    if not lignes or lignes[0].strip() != ENTETE:
        raise ValueError(f"en-tête inattendu : {lignes[0][:80] if lignes else 'réponse vide'}")
    if len(lignes) < 2:
        raise ValueError("aucune ligne de club")
    out = []
    for n, l in enumerate(lignes[1:], start=2):
        c = l.split(",")
        if len(c) != 7:
            raise ValueError(f"ligne {n} : {len(c)} colonnes au lieu de 7")
        try:
            elo = float(c[4])
        except ValueError:
            raise ValueError(f"ligne {n} : Elo non numérique ({c[4]!r})") from None
        if not (500 < elo < 3000) or not c[1].strip():
            raise ValueError(f"ligne {n} : club vide ou Elo hors plage ({elo})")
        out.append({"club": c[1], "pays": c[2], "niveau": c[3], "elo": elo, "du": c[5], "au": c[6]})
    return out


def telecharger(jour: str, session) -> str:
    r = session.get(URL.format(jour=jour), timeout=30, headers={"User-Agent": AGENT})
    r.raise_for_status()
    return r.text


def collecter(liste: list[str], dossier: Path, session, pause: float, dormir=time.sleep, log=print) -> dict:
    dossier.mkdir(parents=True, exist_ok=True)
    manifest = {"ok": [], "deja": [], "erreurs": {}, "arret": False}
    suite = 0
    for jour in liste:
        f = dossier / f"{jour}.csv"
        if f.exists():
            manifest["deja"].append(jour)
            continue
        try:
            texte = telecharger(jour, session)
            n = len(valider(texte))
            f.write_text(texte if texte.endswith("\n") else texte + "\n", encoding="utf-8")
            manifest["ok"].append(jour)
            suite = 0
            log(f"{jour} : {n} clubs")
        except Exception as e:                                      # noqa: BLE001 - on garde la raison, jamais d'échec silencieux
            manifest["erreurs"][jour] = f"{type(e).__name__}: {e}"[:200]
            suite += 1
            log(f"{jour} : ERREUR {manifest['erreurs'][jour]}")
            if suite >= MAX_ECHECS_DE_SUITE:
                manifest["arret"] = True
                log(f"{MAX_ECHECS_DE_SUITE} échecs de suite : arrêt")
                break
        dormir(pause)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--debut", default=DEBUT_DEFAUT)
    ap.add_argument("--fin", default=date.today().isoformat())
    ap.add_argument("--pas", type=int, default=7)
    ap.add_argument("--pause", type=float, default=1.5)
    a = ap.parse_args()
    m = collecter(dates(a.debut, a.fin, a.pas), DOSSIER, requests.Session(), a.pause)
    fichiers = sorted(p.name[:-4] for p in DOSSIER.glob("*.csv"))
    (DOSSIER / "manifest.json").write_text(json.dumps({**m, "fichiers": fichiers, "premier": fichiers[0] if fichiers else None,
                                                       "dernier": fichiers[-1] if fichiers else None}, indent=1, ensure_ascii=False))
    print(f"téléchargés : {len(m['ok'])}, déjà là : {len(m['deja'])}, erreurs : {len(m['erreurs'])}")
    return 1 if m["erreurs"] else 0


if __name__ == "__main__":
    sys.exit(main())
