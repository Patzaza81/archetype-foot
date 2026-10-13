"""Choix d'un pari pour un match (à venir ou non) avec des règles figées. Aucune donnée de résultat utilisée."""
import journal_rentabilite as J

from . import integration as I, modele as M, regles as R


def profil(m, regles):
    pri = regles["pri"]
    ld, le = M.lambdas(m["hd"], m["he"], pri, regles["config"]["params"])
    ml = regles["moyenne_ligue"].get(m["ligue"], pri["all"] * 2)
    return (I.classe(ml, tuple(regles["config"]["coupures_ligue"])),
            I.classe(ld + le, tuple(regles["config"]["coupures_match"]))), (ld, le)


def proposer(m, regles, tab=None):
    """Un pari au maximum (meilleure cellule) ou None."""
    if not m.get("hd") or not m.get("he") or not m.get("cotes"):
        return None
    tab = tab if tab is not None else R.table(regles)
    prof, (ld, le) = profil(m, regles)
    cand = []
    for lib, o in m["cotes"].items():
        if J.analyse_libelle(lib) is None:
            continue
        k = I.cle(dict(lib=lib, o=o, profil=prof))
        if k in tab:
            cand.append((tab[k], lib, o))
    if not cand:
        return None
    roi, lib, o = sorted(cand, key=lambda t: (-t[0], t[1]))[0]
    return dict(match_id=m["id"], date=m["date"], coup_d_envoi_utc=m.get("kickoff"), competition=m["ligue"],
                domicile=m.get("dom"), exterieur=m.get("ext"), marche=lib, cote=o, roi_cellule=round(roi, 4),
                buts_attendus=[round(ld, 2), round(le, 2)], profil_buts=list(prof), regles_version=regles["version"])
