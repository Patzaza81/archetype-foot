"""Téléchargement commun à toutes les sources : un seul endroit pour le délai, les essais et l'en-tête."""
from __future__ import annotations

import time

ENTETES = {"User-Agent": "Mozilla/5.0 (compatible; archetype-foot/1.0)", "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}


def telecharger(url: str, essais: int = 3, attente: float = 2.0, delai: float = 25.0) -> bytes:
    """Contenu de l'URL. Lève RuntimeError après `essais` échecs (jamais un contenu vide rendu en silence)."""
    import requests
    erreur = None
    for i in range(essais):
        try:
            r = requests.get(url, headers=ENTETES, timeout=delai)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            erreur = e
            if i + 1 < essais:
                time.sleep(attente)
    raise RuntimeError(f"{url} : {type(erreur).__name__} : {erreur}")
