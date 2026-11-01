"""Couverture réelle de l'Elo (piste B′), mesurée AVANT tout test. Écrit docs/DC_ELO_COUVERTURE.md.

Un match est « couvert » si les deux équipes ont un Elo la veille (rapprochement de noms exact, même pays). Mesuré sur le bloc Football-Data (apprentissage 2025-26, test 2026-27)
et sur l'archive ARCHETYPE (matchs joués analysables, noms matchendirect).
Contrôle d'intégrité : accord avec une 2e copie indépendante de ClubElo (instantané du 01/03/2026 d'un autre dépôt public), si fournie en argument.
"""
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

from . import donnees as D, elo_donnees as ED

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "DC_ELO_COUVERTURE.md"
COMPETITIONS_ARCHIVE = {"angleterre : premier league": "E0", "angleterre : championnat": "E1", "espagne : laliga": "SP1", "espagne : segunda division": "SP2", "italie : serie a": "I1",
                        "italie : série a": "I1", "italie : série b": "I2", "allemagne : bundesliga": "D1", "allemagne : 2. bundesliga": "D2", "france : ligue 1": "F1", "france : ligue 1 mcdonald's": "F1",
                        "france : ligue 2 bkt": "F2"}


def couverture(matchs: list[dict], elo, idx) -> dict[str, dict[str, int]]:
    out: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for m in matchs:
        d = m["division"]
        out[d]["matchs"] += 1
        a = ED.elo_veille(elo, ED.rapprocher(m["dom"], d, idx), m["jour"])
        b = ED.elo_veille(elo, ED.rapprocher(m["ext"], d, idx), m["jour"])
        out[d]["deux"] += a is not None and b is not None
        out[d]["un"] += (a is None) != (b is None)
    return out


def integrite(elo, snapshot: Path) -> list[str]:
    """Compare l'Elo de la 2e copie (instantané du 01/03/2026) à celui de l'historique pour tous les clubs communs."""
    with open(snapshot, encoding="utf-8") as fh:
        snap = {r["Club"]: float(r["Elo"]) for r in csv.DictReader(fh)}
    ecarts = []
    for club, v in elo.items():
        e = ED.elo_veille(elo, club, "2026-03-02")           # la veille = 01/03/2026
        if club in snap and e is not None:
            ecarts.append((abs(e - snap[club]), club, e, snap[club]))
    ecarts.sort(reverse=True)
    if not ecarts:
        return ["aucun club commun"]
    return [f"{len(ecarts)} clubs comparés ; écart absolu moyen {sum(x[0] for x in ecarts) / len(ecarts):.3f} points Elo ; max {ecarts[0][0]:.3f} ({ecarts[0][1]})"]


def main() -> None:
    elo = ED.charger()
    idx = ED.index_noms(elo)
    bloc = [{"division": m["ligue"].split("|")[2], "saison": m["saison"], "dom": m["dom"], "ext": m["ext"], "jour": m["date"]} for m in D.charger_bloc() if m["h"] is not None]
    L = ["# Couverture réelle de l'Elo (piste B′) — mesurée avant tout test", "",
         "Source : copie publique CC BY 4.0 de ClubElo (voir `data/clubelo/SOURCE.md`). 105 clubs. « Couvert » = les deux équipes ont un Elo la veille du match.", ""]
    for saison, titre in (("2526", "Apprentissage 2025-26"), ("2627", "Test 2026-27")):
        c = couverture([m for m in bloc if m["saison"] == saison], elo, idx)
        tot = sum(v["matchs"] for v in c.values())
        deux = sum(v["deux"] for v in c.values())
        L += [f"## Bloc Football-Data, {titre}", "", f"**{tot} matchs, dont {deux} couverts ({deux / tot:.1%}).**", "",
              "| Division | Matchs | Deux équipes avec Elo | Une seule | Couverture |", "|---|---|---|---|---|"]
        for d, v in sorted(c.items()):
            if v["deux"] or v["un"] or d in ED.PAYS_DIVISION:
                L.append(f"| {d} | {v['matchs']} | {v['deux']} | {v['un']} | {v['deux'] / v['matchs']:.0%} |")
        L.append("")
    # archive
    ligues = D.charger_ligues()
    arch = [m for m in D.charger_archive(ligues) if m["h"] is not None]
    rows = [{"division": COMPETITIONS_ARCHIVE.get(m["ligue"], "?"), "dom": m["domicile"], "ext": m["exterieur"], "jour": m["jour"]} for m in arch]
    c = couverture(rows, elo, idx)
    deux = sum(v["deux"] for d, v in c.items() if d != "?")
    L += ["## Archive ARCHETYPE (matchs joués analysables)", "", f"**{len(arch)} matchs, dont {deux} couverts ({deux / len(arch):.1%}).** "
          f"La demande affirmait une couverture de l'archive : elle est de {deux / len(arch):.1%} (noms matchendirect, 5 pays seulement).", ""]
    for d, v in sorted(c.items()):
        if d != "?":
            L.append(f"- {d} : {v['matchs']} matchs, {v['deux']} couverts")
    L += ["", "## Contrôle d'intégrité (2e copie indépendante)", ""]
    if len(sys.argv) > 1:
        L += ["- " + x for x in integrite(elo, Path(sys.argv[1]))]
    else:
        L.append("- non fait (aucune 2e copie fournie)")
    SORTIE.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
