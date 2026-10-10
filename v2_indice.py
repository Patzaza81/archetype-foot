"""v2_indice.py -- ajoute l'indice de performance (moteur_v3/performance.py) aux marchés du moteur V2.

Pour chaque match de precalcul.json / precalcul_leger.json retrouvé dans l'archive (par match_id), chaque marché du bloc
`moteur_v2_6_10` (sélection P1-P3 et inventaire complet) reçoit `indice_performance`, calculé sur les matchs au même lieu
avec la logique figée (docs/CLAUDE_SELECTION.md). Information seulement : probabilités, cotes, sélection, statuts du V2
ne changent pas. Marchés sans marge continue (nul) : pas d'indice.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Mapping, Sequence

from moteur_v3.model import _latest
from moteur_v3.performance import indice_performance

FICHIERS = ("precalcul.json", "precalcul_leger.json")
CLE_BLOC = "moteur_v2_6_10"

DIRECTS = {"dc_1X": "dc_1X", "dc_X2": "dc_X2", "dc_12": "dc_12", "victoire": "1x2_1", "defaite": "1x2_2",
           "btts_oui": "btts_yes", "btts_non": "btts_no", "clean_sheet_dom": "clean_home", "clean_sheet_ext": "clean_away"}


def marche_v3(mk: str) -> str | None:
    """Nom V2 (marche_moteur) -> nom V3. None si le marché n'a pas de marge continue (nul) ou est inconnu."""
    if mk in DIRECTS:
        return DIRECTS[mk]
    if re.fullmatch(r"(over|under)_\d_\d", mk):
        return mk
    m = re.fullmatch(r"buts_(dom|ext)_(over|under)_(\d_\d)", mk)
    if m:
        return f"{'home' if m[1] == 'dom' else 'away'}_{m[2]}_{m[3]}"
    m = re.fullmatch(r"handicap_(dom|ext)_([+-])(\d)_(\d)", mk)
    if m:
        ligne = float(f"{m[3]}.{m[4]}") * (1 if m[2] == "+" else -1)
        if m[1] == "dom":      # V2 : handicap appliqué au domicile ; V3 : buts à rattraper (signe inverse)
            return f"handicap_{-ligne:g}_1"
        return f"handicap_{ligne:g}_2"
    return None


def indice_du_marche(mk: str, dom: Sequence[Mapping[str, Any]], ext: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    m3 = marche_v3(mk)
    if m3 is None:
        return None
    p = indice_performance(m3, dom, ext)
    if p is None:
        return None
    return {"indice": p["indice"], "sur": p["sur"], "niveau": p["niveau"], "libelle": p["libelle"], "phrase": p["phrase"],
            "marche_moteur": m3, "n_domicile": len(dom), "n_exterieur": len(ext)}


def ajoute_indices(signaux: Sequence[dict[str, Any]], enregs_par_id: Mapping[str, Mapping[str, Any]]) -> int:
    n = 0
    for s in signaux:
        e = enregs_par_id.get(str(s.get("match_id")))
        bloc = s.get(CLE_BLOC)
        if not e or not isinstance(bloc, dict):
            continue
        dom = _latest((e.get("equipe_dom") or {}).get("matchs") or [], True)
        ext = _latest((e.get("equipe_ext") or {}).get("matchs") or [], False)
        cibles = [c for c in (bloc.get("selection") or {}).values() if isinstance(c, dict)]
        cibles += [c for c in bloc.get("inventaire") or [] if isinstance(c, dict)]
        for c in cibles:
            p = indice_du_marche(str(c.get("marche_moteur") or ""), dom, ext)
            if p is not None:
                c["indice_performance"] = p
                n += 1
    return n


def main(*chemins: str) -> None:
    import datetime
    import moteur_v3_pipeline as mp
    limite = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    par_id = {str(e["match_id"]): e for e in mp.lit_archive(mp.DOSSIER_ARCHIVE)
              if e.get("match_id") and str(e.get("date") or "") >= limite}
    for chemin in chemins or FICHIERS:
        try:
            with open(chemin, encoding="utf-8") as f:
                d = json.load(f)
        except FileNotFoundError:
            continue
        n = ajoute_indices(d.get("signaux") or [], par_id)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"[v2 indice] {chemin} : {n} marché(s) avec indice de performance.")


if __name__ == "__main__":
    main(*sys.argv[1:])
