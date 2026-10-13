"""Double contrôle + justification pour le moteur Europe (même format que moteur_v3_pipeline.preuves).

Décision 13/10 : le double contrôle est appliqué à l'échantillon MÉLANGÉ (matchs européens + championnat réunis, comme le
modèle 70/30), seuils inchangés. Les contrôles Europe seule et championnat seul sont calculés pour information
(`double_controle_europe`, `double_controle_championnat`), non bloquants."""
from __future__ import annotations

from . import regles as rs
from .rendu import DOUBLE_CONTROLE, groupe_exposition

CONTROLE_CHAMPIONNAT_BLOQUANT = False
MAX_CONTROLE = 12


def _vers_controle(matchs):
    rows = sorted(matchs or [], key=lambda m: str(m.get("date") or ""))[-MAX_CONTROLE:]
    return [{"date": m["date"], "lieu": "D" if m.get("domicile") else "E", "bm": m["buts_marques"],
             "be": m["buts_encaisses"]} for m in rows]


def preuves_europe(europe_dom, europe_ext, ligue_dom, ligue_ext, marches, dom="Domicile", ext="Extérieur"):
    ed, ee = _vers_controle(europe_dom), _vers_controle(europe_ext)
    ld, le = _vers_controle(ligue_dom), _vers_controle(ligue_ext)
    # Échantillon MÉLANGÉ (décision 13/10) : Europe + championnat réunis, comme le modèle (70/30). Seuils inchangés.
    md, me = _vers_controle(list(europe_dom or []) + list(ligue_dom or [])), _vers_controle(list(europe_ext or []) + list(ligue_ext or []))
    out = {}
    for m in marches:
        g = groupe_exposition(m)
        bloc = {"family": g, "exposure_group": g, "double_control_ok": False, "justification": None}
        nom = DOUBLE_CONTROLE.get(m)
        if nom:
            r = rs.double_controle(nom, md, me, dom, ext)
            champ = rs.double_controle(nom, ld, le, dom, ext)
            eur = rs.double_controle(nom, ed, ee, dom, ext)
            ok = bool(r["retenu"])
            raisons = list(r["saison"]["raisons"]) + list(r["recent"]["raisons"])
            bloc.update(double_control_ok=ok, justification=" ; ".join(raisons) if ok else None,
                        double_controle_raisons=raisons, double_controle_championnat=bool(champ["retenu"]), double_controle_europe=bool(eur["retenu"]),
                        raisons_saison=list(r["saison"]["raisons"]), raisons_recent=list(r["recent"]["raisons"]))
        out[m] = bloc
    return out
