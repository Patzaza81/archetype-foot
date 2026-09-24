# -*- coding: utf-8 -*-
"""Test de sources de données externes depuis GitHub Actions (AJOUT 24/09/2026) — LECTURE SEULE.
Pour chaque URL de diagnostic/sources_a_tester.txt : code HTTP, taille, type, signes de blocage (Cloudflare, captcha),
et copie brute dans diagnostic/sources/ (HTML ou CSV) pour analyse. N'écrit que dans diagnostic/."""
import json
import os
import re
import time

import requests

RACINE = os.path.dirname(os.path.abspath(__file__))
LISTE = os.path.join(RACINE, "diagnostic", "sources_a_tester.txt")
DOSSIER = os.path.join(RACINE, "diagnostic", "sources")
SORTIE = os.path.join(RACINE, "diagnostic", "resultat_sources.json")
ENTETES = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0 Safari/537.36", "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}
SIGNES_BLOCAGE = ["cf-chl", "challenge-platform", "captcha", "access denied", "just a moment", "attention required"]


def main():
    os.makedirs(DOSSIER, exist_ok=True)
    out = []
    for url in [l.strip() for l in open(LISTE, encoding="utf-8") if l.strip() and not l.startswith("#")]:
        e = {"url": url}
        try:
            r = requests.get(url, headers=ENTETES, timeout=30)
            e.update(code=r.status_code, url_finale=r.url, octets=len(r.content), type=r.headers.get("content-type"))
            texte = r.text
            bas = texte[:20000].lower()
            e["signes_blocage"] = [s for s in SIGNES_BLOCAGE if s in bas]
            nom = re.sub(r"[^a-z0-9]+", "_", url.lower().split("//", 1)[-1])[:90]
            ext = ".csv" if url.endswith(".csv") else (".txt" if url.endswith(".txt") else ".html")
            with open(os.path.join(DOSSIER, nom + ext), "w", encoding="utf-8") as f:
                f.write(texte)
            e["fichier"] = "diagnostic/sources/" + nom + ext
            if ext == ".csv":
                lignes = texte.splitlines()
                e["csv_colonnes"] = lignes[0].split(",")[:80] if lignes else []
                e["csv_lignes"] = max(0, len(lignes) - 1)
        except Exception as ex:  # noqa: BLE001 -- diagnostic
            e["erreur"] = f"{type(ex).__name__}: {ex}"
        out.append(e)
        time.sleep(2)
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for e in out:
        print(e.get("code"), e.get("octets"), e.get("signes_blocage"), e["url"])


if __name__ == "__main__":
    main()
