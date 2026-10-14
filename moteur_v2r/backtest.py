"""Test à l'aveugle du VRAI moteur v2r (cellules, regles.py + pronostics.py + modere.py) sur des jours passés.

Ajout 14/10/2026. `moteur_v2r.evaluation` teste l'ANCIEN modèle (calibration/Poisson) : il ne teste pas v2r.
Ici, pour chaque jour D : (1) règles entraînées UNIQUEMENT sur les matchs joués avant D (`regles.entraine(passe, D)`),
(2) choix du pari de chaque match de D avec ces règles (`pronostics.proposer`) et ses variantes modérées 1 et 2 crans
(`modere.variante`, plancher de cote 1,40), (3) règlement avec le vrai score. Aucun match du jour D n'entre dans
l'entraînement. Différence avec la production : les règles sont réapprises chaque jour (la production le fait le lundi).
Usage : python -m moteur_v2r.backtest 2026-10-13 [2026-10-12 ...]"""
import sys

import journal_rentabilite as J

from . import evaluation as E, modere as MOD, pronostics as P, regles as R, super_favori as SF
from .donnees import charge


def profit(libelle, cote, h, a):
    """Profit d'une mise de 1 : cote-1 si gagné, 0 si remboursé, -1 si perdu. None si le marché n'est pas réglable."""
    an = J.analyse_libelle(libelle)
    if an is None or h is None or a is None:
        return None
    r = an[1](h, a)
    if r is None:
        return None
    return (cote - 1) if r == 1 else (0.0 if r == 0 else -1.0)


def _ligne(m, p, marche, cote):
    g = profit(marche, cote, m["h"], m["a"])
    return None if g is None else dict(mid=m["id"], date=m["date"], lib=marche, o=cote, profit=g, r=1 if g > 0 else (0 if g == 0 else -1))


def rejoue(matchs, jours, plancher=MOD.PLANCHER_COTE):
    """{série: [lignes]} pour les jours donnés. Séries : v2r (officiel, tel qu'en production), v2r_plancher (officiel avec
    cote >= plancher), modere1, modere2, sf1, sf2 (paris modérés SUPER FAVORI)."""
    sortie = {k: [] for k in ("v2r", "v2r_plancher", "modere1", "modere2", "sf1", "sf2")}
    for jour in jours:
        passe = [m for m in matchs if m["date"] < jour and m["h"] is not None]
        test = [m for m in matchs if m["date"] == jour and m["h"] is not None]
        reg = R.entraine(passe, jour)
        if reg is None or not test:
            continue
        assert reg["jusqu_au"] < jour, "fuite : règles entraînées avec un match du jour testé"
        tab = R.table(reg)
        for m in test:
            p = P.proposer(m, reg, tab)
            if not p:
                continue
            base = _ligne(m, p, p["marche"], p["cote"])
            if base:
                sortie["v2r"].append(base)
                if p["cote"] >= plancher:
                    sortie["v2r_plancher"].append(base)
            for k in MOD.CRANS:
                v = MOD.variante(p, m["cotes"], k, plancher)
                if not v:
                    continue
                l = _ligne(m, v, v["marche"], v["cote"])
                if not l:
                    continue
                sortie[f"modere{k}"].append(l)
                if SF.statut(v["marche"], m["hd"], m["he"])["super_favori"]:
                    sortie[f"sf{k}"].append(l)
    return sortie


def resume(lignes):
    """Paris, réussite (gagnés / paris non remboursés), cote moyenne, ROI et IC95 par match (si >= 20 paris)."""
    n = len(lignes)
    if n == 0:
        return dict(paris=0, reussite=None, cote_moyenne=None, roi=None, ic95=None)
    jouees = [l for l in lignes if l["r"] != 0]
    ic = E.bootstrap(lignes, 500) if n >= 20 else None
    return dict(paris=n, reussite=(sum(1 for l in jouees if l["r"] == 1) / len(jouees)) if jouees else None,
                cote_moyenne=sum(l["o"] for l in lignes) / n, roi=sum(l["profit"] for l in lignes) / n, ic95=ic)


def main(argv=None):
    jours = list(argv if argv is not None else sys.argv[1:])
    if not jours:
        print(__doc__)
        return 1
    res = rejoue(charge(), jours)
    print(f"Jours testés : {', '.join(jours)} -- règles apprises avant chaque jour, sans fuite.")
    for nom, lignes in res.items():
        r = resume(lignes)
        if not r["paris"]:
            print(f"{nom:14s} 0 pari")
            continue
        ic = f" IC95 [{r['ic95'][0]:+.0%};{r['ic95'][1]:+.0%}]" if r["ic95"] else " (IC95 : moins de 20 paris)"
        rep = "—" if r["reussite"] is None else f"{r['reussite']:.0%}"
        print(f"{nom:14s} {r['paris']:4d} paris | réussite {rep} | cote {r['cote_moyenne']:.2f} | ROI {r['roi']:+.1%}{ic}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
