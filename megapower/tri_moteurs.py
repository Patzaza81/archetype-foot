"""Tri des moteurs sur leurs résultats RÉELS (`python -m megapower.tri_moteurs`) : paris enregistrés par chaque moteur avant le coup d'envoi, matchs terminés.
Jamais d'archive ni de rejeu. Alpha, Omega, DC et Gamma passent par bilan_reel.py ; les autres par leur propre carnet. Sortie : data/megapower/tri_moteurs.json."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import bilan_reel as B
import verif_pronostic as V

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "data" / "megapower" / "tri_moteurs.json"


def _t(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def ligne(nom: str, paris: list[tuple[str, str, float | None, bool]]) -> dict:
    """paris = (match, jour, cote ou None, gagné). Rendement = gain moyen pour 1 misé, sur les paris qui ont une cote ; marge = ± 2 erreurs types."""
    c = [(k, g) for _, _, k, g in paris if k]
    gains = [(k - 1) if g else -1.0 for k, g in c]
    n = len(gains)
    rend = sum(gains) / n if n else None
    et = math.sqrt(sum((x - rend) ** 2 for x in gains) / n / n) if n > 1 else None
    jours = sorted(j for _, j, _, _ in paris)
    return {"moteur": nom, "paris": len(paris), "matchs": len({m for m, _, _, _ in paris}), "du": jours[0] if jours else None, "au": jours[-1] if jours else None,
            "reussite": round(sum(g for *_, g in paris) / len(paris), 4) if paris else None, "paris_avec_cote": n,
            "cote_moyenne": round(sum(k for k, _ in c) / n, 3) if n else None, "rendement": None if rend is None else round(rend, 4),
            "marge": None if et is None else round(2 * et, 4)}


def _de_bilan(L):
    return [(x["mid"], x["jour"], x["cote"], x["gagne"]) for x in L]


def mesures() -> list[dict]:
    out = []
    al = B.paris_alpha()
    out.append(ligne("Alpha (marchés affichés avec cote)", _de_bilan([x for x in al if x["cote"]])))
    om = B.paris_omega()
    out.append(ligne("Omega (pari principal)", _de_bilan([x for x in om if x["cat"] == "principal"])))
    out.append(ligne("Omega (tous paris)", _de_bilan(om)))
    ga = B.paris_gamma()
    out.append(ligne("Gamma (pari principal)", _de_bilan([x for x in ga if x["cat"] == "principal"])))
    out.append(ligne("Gamma (tous paris)", _de_bilan(ga)))
    out.append(ligne("DC, ancien Gamma (tous paris)", _de_bilan(B.paris_dc())))
    # --- Europe (Europe-Gamma) : même journal qu'Omega/Gamma ---
    f = ROOT / "data" / "europe_gamma" / "journal.jsonl"
    if f.exists():
        out.append(ligne("Europe (tous paris)", _de_bilan(B.paris_gamma(f))))
    # --- Analyse Verdict : journal gelé + scores ---
    sc = {}
    for j in json.loads((ROOT / "historique_pronostics.json").read_text(encoding="utf-8")):
        for m in j["matchs"]:
            if re.fullmatch(r"\d+-\d+", str(m.get("score"))):
                sc[m["match_id"]] = tuple(map(int, m["score"].split("-")))
    par = {}
    for l in V.lire_journal():
        if l.get("coup_d_envoi_utc") and _t(l["gele_le"]) < _t(l["coup_d_envoi_utc"]) and l["match_id"] in sc:
            par[(l["match_id"], l["marche"])] = l                       # dernier gel avant le coup d'envoi
    for v in ("TIENT", "TIENT AVEC RÉSERVE"):
        P = []
        for (mid, mk), l in par.items():
            if l["verdict"] == v:
                h, a = sc[mid]
                P.append((mid, l["date"], l.get("cote"), bool(V.TABLE[min(h, V.CAP), min(a, V.CAP), V.IDX[mk]])))
        out.append(ligne(f"Analyse Verdict ({v.lower()})", P))
    # --- V3 : historique de sélection réglé ---
    h3 = [x for x in json.loads((ROOT / "data" / "v3" / "historique_selection.json").read_text(encoding="utf-8")) if x.get("resultat_statut") == "RESOLVED" and x.get("resultat_marche") in ("WIN", "LOSS")]
    out.append(ligne("V3 (sélections)", [(x["match_id"], x["date"], x.get("cote"), x["resultat_marche"] == "WIN") for x in h3]))
    # --- V et V2R : carnets figés ---
    for nom, chemin in (("V (pari principal)", "data/v/carnet.json"), ("V2R", "data/v2r/carnet.json")):
        P = []
        for mid, m in json.loads((ROOT / chemin).read_text(encoding="utf-8")).items():
            p = m.get("principal") if "principal" in m else m
            if not m.get("fige") or not p or p.get("resultat") not in ("WIN", "LOSS"):
                continue
            if m.get("vu_le") and m.get("coup_d_envoi_utc") and _t(m["vu_le"]) >= _t(m["coup_d_envoi_utc"]):
                continue                                             # vu après le coup d'envoi : écarté
            P.append((mid, m["date"], p.get("cote"), p["resultat"] == "WIN"))
        out.append(ligne(nom, P))
    # --- V2 et Journal : paris retenus par le générateur (une fois chacun), réglés ---
    sel = json.loads((ROOT / "data" / "selection_generateur_historique.json").read_text(encoding="utf-8"))
    cotes = {}
    for e in sel.get("executions") or []:
        for p in e.get("paris") or []:
            cotes[p["id"]] = (p.get("cote"), p.get("date"))
    noms = {"moteur_v2_6_10": "V2 (paris retenus par le générateur)", "journal": "Journal (paris retenus par le générateur)"}
    par_source = {}
    for pid, r in (sel.get("resultats") or {}).items():
        src = pid.rsplit("|", 1)[-1]
        if src in noms and r.get("resultat") in ("WIN", "LOSS") and pid in cotes:
            par_source.setdefault(src, []).append((pid.rsplit("|", 2)[0], cotes[pid][1], cotes[pid][0], r["resultat"] == "WIN"))
    for src, P in sorted(par_source.items()):
        out.append(ligne(noms[src], P))
    return out


def main() -> None:
    L = mesures()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({"genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "regle": "paris enregistrés avant le coup d'envoi, matchs terminés ; jamais d'archive ni de rejeu",
                                  "moteurs": L}, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in L:
        r = "—" if x["rendement"] is None else f"{100 * x['rendement']:+.1f} % (± {100 * (x['marge'] or 0):.1f})"
        print(f"{x['moteur']:42s} {x['paris']:6d} paris {x['matchs']:5d} matchs {x['du']} → {x['au']}  réussite {100 * (x['reussite'] or 0):.1f} %  cote {x['cote_moyenne']}  rendement {r}")


if __name__ == "__main__":
    main()
