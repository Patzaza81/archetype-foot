"""Format commun d'un match, identique pour toutes les sources."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Match:
    source: str                 # « matchendirect », « espn », « openfootball »
    id_source: str              # identifiant du match DANS sa source (jamais comparé entre sources)
    jour: str                   # AAAA-MM-JJ : jour UTC du coup d'envoi quand l'heure est connue, sinon jour annoncé par la source
    domicile: str
    exterieur: str
    coup_d_envoi_utc: str | None = None     # AAAA-MM-JJTHH:MM:SSZ
    competition: str | None = None

    def cle(self) -> tuple[str, str]:
        return self.source, self.id_source

    def en_dict(self) -> dict:
        return asdict(self)


def sans_doublons(matchs: list[Match]) -> list[Match]:
    """Un seul exemplaire par (source, id_source) : le premier rencontré. Une source qui liste un match sur deux jours voisins ne le compte qu'une fois."""
    vus, out = set(), []
    for m in matchs:
        if m.cle() not in vus:
            vus.add(m.cle()); out.append(m)
    return out
