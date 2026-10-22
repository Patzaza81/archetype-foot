"""Choix d'un pari pour un match (à venir ou non) avec des règles figées. Aucune donnée de résultat utilisée."""
import journal_rentabilite as J

from . import integration as I, modele as M, regles as R


def profil(m, regles):
    pri = regles["pri"]
    ld, le = M.lambdas(m["hd"], m["he"], pri, regles["config"]["params"])
    ml = regles["moyenne_ligue"].get(m["ligue"], pri["all"] * 2)
    return (I.classe(ml, tuple(regles["config"]["coupures_ligue"])),
            I.classe(ld + le, tuple(regles["config"]["coupures_match"]))), (ld, le)


NB_FORME = 6        # derniers matchs affichés par équipe (tous lieux), du plus récent au plus ancien


def forme(hist, n=NB_FORME, lieu_dom=None):
    """Derniers matchs d'une équipe pour l'affichage : [{date, adversaire, lieu "D"/"E", bm, be}]. Information seulement."""
    source = [x for x in (hist or []) if lieu_dom is None or bool(x.get("domicile")) == lieu_dom]
    ordre = sorted(source, key=lambda x: x.get("date", ""), reverse=True)[:n]
    return [dict(date=x.get("date"), adversaire=x.get("adversaire"), lieu="D" if x.get("domicile") else "E",
                 bm=x.get("buts_marques"), be=x.get("buts_encaisses")) for x in ordre]


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
    grille = M.grille(ld, le)
    scores = sorted(((grille[h][a], h, a) for h in range(len(grille)) for a in range(len(grille[h]))), reverse=True)[:2]
    proba_marche = M.probas(grille, [lib]).get(lib, (None, None))[0]
    def resume_lieu(hist, lieu_dom):
        liste = forme(hist, n=6, lieu_dom=lieu_dom)
        n = len(liste)
        bm = sum(x["bm"] for x in liste) if n else 0
        be = sum(x["be"] for x in liste) if n else 0
        return dict(matchs=liste, n=n, moyenne_marques=round(bm / n, 2) if n else None,
                    moyenne_encaisses=round(be / n, 2) if n else None)
    return dict(match_id=m["id"], date=m["date"], coup_d_envoi_utc=m.get("kickoff"), competition=m["ligue"],
                domicile=m.get("dom"), exterieur=m.get("ext"), marche=lib, cote=o, roi_cellule=round(roi, 4),
                buts_attendus=[round(ld, 2), round(le, 2)], profil_buts=list(prof), regles_version=regles["version"],
                forme=dict(domicile=forme(m["hd"]), exterieur=forme(m["he"])),
                donnees_lieu=dict(domicile=resume_lieu(m["hd"], True), exterieur=resume_lieu(m["he"], False)),
                classement=dict(domicile=m.get("rang_dom"), exterieur=m.get("rang_ext")),
                probabilites=dict(marche=round(proba_marche, 4) if proba_marche is not None else None,
                                  scores=[dict(score=f"{h}-{a}", probabilite=round(q, 4)) for q, h, a in scores]))
