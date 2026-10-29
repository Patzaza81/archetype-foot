"""Bilan RÉEL des moteurs alpha et omega (29/10/2026, demande de Patrick : plus jamais de chiffres sur des matchs que le moteur n'a pas tournés).

Seules données admises : les paris des journaux gelés (data/alpha_serie/journal.jsonl, data/omega/journal.jsonl) qui remplissent les TROIS conditions :
  1. gelés AVANT le coup d'envoi (gele_le < coup_d_envoi_utc) ; pour un même match, le dernier gel avant le coup d'envoi ;
  2. match TERMINÉ (une ligne « resultat » existe) ;
  3. alpha : seulement les marchés que la page affiche vraiment (règle d'af-alpha-selection.js : Buts, Équipes, Calibrés exigent une cote ; Multigoals et Multiscores non).
Jamais d'archive, de rejeu, de backtest ni de matchs à venir. Toute sortie annonce le nombre de matchs, de paris et la période, pour se contrôler d'un coup d'œil.
Usage : python bilan_reel.py [--solidite-min 0.78]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALPHA_JOURNAL = ROOT / "data" / "alpha_serie" / "journal.jsonl"
OMEGA_JOURNAL = ROOT / "data" / "omega" / "journal.jsonl"
SANS_COTE_OK = {"multigoals", "multiscores"}


def _t(s: str) -> datetime:
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _lire(chemin: Path) -> list[dict]:
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def gels_valides(lignes: list[dict], ko) -> dict[str, dict]:
    """Dernier gel de chaque match fait AVANT son coup d'envoi (les gels tardifs ou sans coup d'envoi sont écartés)."""
    out: dict[str, dict] = {}
    for l in lignes:
        if l.get("type") != "pronostic":
            continue
        k = ko(l)
        if k and l.get("gele_le") and _t(l["gele_le"]) < _t(k):
            if l["match_id"] not in out or _t(l["gele_le"]) >= _t(out[l["match_id"]]["gele_le"]):
                out[l["match_id"]] = l
    return out


def _signature(s: dict) -> str:
    return "|".join(s["cle"]) if isinstance(s.get("cle"), list) else str(s.get("marche", ""))


def _cat(src: str, s: dict) -> str:
    if src == "buts":
        return "multigoals" if (s["cle"][0] == "multigoals" if isinstance(s.get("cle"), list) else str(s.get("marche", "")).startswith("Multigoals ")) else "buts"
    return src


def marches_affiches(onglets: dict) -> list[tuple[str, str, int, dict, bool]]:
    """(catégorie, onglet source, position, marché, en_tête) : même règle que af-alpha-selection.js (classement par valeur décroissante, doublons retirés, cote exigée sauf Multigoals/Multiscores)."""
    out = []
    for cat in ("buts", "multigoals", "equipes", "multiscores", "calibrees"):
        src = "buts" if cat in ("buts", "multigoals") else cat
        vus, brut = set(), []
        for i, s in enumerate(onglets.get(src) or []):
            if _cat(src, s) != cat or _signature(s) in vus:
                continue
            vus.add(_signature(s)); brut.append((i, s))
        brut.sort(key=lambda x: -(float(x[1].get("valeur") or 0)))             # tri stable : l'ordre du fichier départage les égalités
        ok = [(i, s) for i, s in brut if cat in SANS_COTE_OK or (s.get("cote") is not None and float(s["cote"]) > 1)]
        for n, (i, s) in enumerate(ok):
            out.append((cat, src, i, s, n == 0))
    return out


def paris_alpha(journal: Path = ALPHA_JOURNAL) -> list[dict]:
    L = _lire(journal)
    gels = gels_valides(L, lambda l: l.get("coup_d_envoi_utc"))
    res = {l["match_id"]: l for l in L if l.get("type") == "resultat"}
    out = []
    for mid, g in gels.items():
        r = res.get(mid)
        if not r:
            continue
        for cat, src, i, s, tete in marches_affiches(g["onglets"]):
            gl = (r.get("gagnes") or {}).get(src) or []
            if i >= len(gl):
                continue
            c = s.get("cote")
            out.append({"moteur": "alpha", "mid": mid, "jour": str(g["date"])[:10], "cat": cat, "cle": s["cle"], "tete": tete,
                        "cote": float(c) if c is not None and float(c) > 1 else None, "gagne": bool(gl[i]), "sol": None})
    return out


def paris_omega(journal: Path = OMEGA_JOURNAL) -> list[dict]:
    L = _lire(journal)
    gels = gels_valides(L, lambda l: (l.get("fiche") or {}).get("coup_d_envoi_utc"))
    res = {l["match_id"]: l for l in L if l.get("type") == "resultat"}
    out = []
    for mid, g in gels.items():
        r = res.get(mid)
        f = g["fiche"]
        if not r or not f.get("principal"):
            continue
        gag = {json.dumps(p["cle"]): p for p in r.get("paris") or []}
        for rang, p in [("principal", f["principal"])] + [("autre", x) for x in f.get("autres") or []]:
            q = gag.get(json.dumps(p["cle"]))
            if q is None:
                continue
            out.append({"moteur": "omega", "mid": mid, "jour": f["jour"], "cat": rang, "cle": p["cle"], "tete": rang == "principal",
                        "cote": float(q["cote"]) if q.get("cote") else None, "gagne": bool(q["gagne"]), "sol": None, "_series": f.get("series")})
    return out


def ajouter_solidite(alpha: list[dict], omega: list[dict]) -> None:
    """Solidité recalculée comme sur les pages (poids appris sur l'archive : légèrement avantagée, à dire dans tout rapport)."""
    from alpha_serie import solidite as SA, suivi as AS
    from moteur_omega import solidite as SO
    wa, wo = SA.charger(), SO.charger()
    arch = {m["match_id"]: m for m in AS.charger_matchs()}
    for p in alpha:
        m = arch.get(p["mid"])
        if not m:
            continue
        a, jour = m.get("assemblage") or {}, p["jour"]
        try:
            p["sol"] = SA.probabilite(wa, p["cle"], AS.historique_lieu(a.get("equipe_dom"), True, jour), AS.historique_lieu(a.get("equipe_ext"), False, jour))
        except Exception:                                                          # noqa: BLE001
            p["sol"] = None
    for p in omega:
        try:
            p["sol"] = SO.probabilite(wo, p["cle"], p["_series"])
        except Exception:                                                          # noqa: BLE001
            p["sol"] = None


def resume(titre: str, L: list[dict]) -> str:
    if not L:
        return f"{titre} : aucun pari"
    n, g = len(L), sum(x["gagne"] for x in L)
    c = [x for x in L if x["cote"]]
    rend = sum((x["cote"] - 1) if x["gagne"] else -1 for x in c) / len(c) if c else None
    jours = sorted(x["jour"] for x in L)
    return (f"{titre} : {n} paris sur {len({x['mid'] for x in L})} matchs terminés ({jours[0]} → {jours[-1]}) | gagnés {g} = {100 * g / n:.1f} % | "
            f"avec cote : {len(c)}, rendement {'—' if rend is None else f'{100 * rend:+.1f} %'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solidite-min", type=float, default=None)
    a = ap.parse_args()
    al, om = paris_alpha(), paris_omega()
    if a.solidite_min is not None:
        ajouter_solidite(al, om)
        al = [x for x in al if x["sol"] is not None and x["sol"] >= a.solidite_min]
        om = [x for x in om if x["sol"] is not None and x["sol"] >= a.solidite_min]
    suffixe = "" if a.solidite_min is None else f" · solidité ≥ {a.solidite_min:.0%}"
    print("Données : journaux gelés avant le coup d'envoi, matchs terminés seulement" + suffixe)
    print(resume("ALPHA tous marchés affichés", al)); print(resume("ALPHA jouables (avec cote)", [x for x in al if x["cote"]]))
    print(resume("OMEGA tous paris", om)); print(resume("OMEGA pari principal", [x for x in om if x["cat"] == "principal"]))


if __name__ == "__main__":
    main()
