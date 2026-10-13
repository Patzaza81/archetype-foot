"""Double contrôle + justification pour le moteur Europe (même format que moteur_v3_pipeline.preuves).

Décision : le double contrôle (regles_selection) est appliqué à l'HISTORIQUE EUROPÉEN de chaque club (source à 70 %),
qui doit le passer pour que le pari soit retenu. Le même contrôle sur le championnat est calculé et rendu à titre
d'information (`double_controle_championnat`), non bloquant (CONTROLE_CHAMPIONNAT_BLOQUANT = False)."""
from __future__ import annotations

import regles_selection as rs
from moteur_v3_pipeline import DOUBLE_CONTROLE, groupe_exposition

CONTROLE_CHAMPIONNAT_BLOQUANT = False
MAX_CONTROLE = 12


def _vers_controle(matchs):
    rows = sorted(matchs or [], key=lambda m: str(m.get("date") or ""))[-MAX_CONTROLE:]
    return [{"date": m["date"], "lieu": "D" if m.get("domicile") else "E", "bm": m["buts_marques"],
             "be": m["buts_encaisses"]} for m in rows]


def preuves_europe(europe_dom, europe_ext, ligue_dom, ligue_ext, marches, dom="Domicile", ext="Extérieur"):
    ed, ee = _vers_controle(europe_dom), _vers_controle(europe_ext)
    ld, le = _vers_controle(ligue_dom), _vers_controle(ligue_ext)
    out = {}
    for m in marches:
        g = groupe_exposition(m)
        bloc = {"family": g, "exposure_group": g, "double_control_ok": False, "justification": None}
        nom = DOUBLE_CONTROLE.get(m)
        if nom:
            r = rs.double_controle(nom, ed, ee, dom, ext)
            champ = rs.double_controle(nom, ld, le, dom, ext)
            ok = bool(r["retenu"]) and (bool(champ["retenu"]) or not CONTROLE_CHAMPIONNAT_BLOQUANT)
            raisons = list(r["saison"]["raisons"]) + list(r["recent"]["raisons"])
            bloc.update(double_control_ok=ok, justification=" ; ".join(raisons) if ok else None,
                        double_controle_raisons=raisons, double_controle_championnat=bool(champ["retenu"]))
        out[m] = bloc
    return out
