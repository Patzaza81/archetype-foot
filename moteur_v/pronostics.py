"""Construction du pronostic d'un match : principal + autres + contexte. Aucune donnée de résultat utilisée."""
from . import coeur as C, modele as M

NB_FORME = 6        # derniers matchs affichés par équipe (tous lieux), du plus récent au plus ancien


def forme(hist, n=NB_FORME):
    """Derniers matchs d'une équipe pour l'affichage : [{date, adversaire, lieu "D"/"E", bm, be}]. Information seulement."""
    ordre = sorted(hist or [], key=lambda x: x.get("date", ""), reverse=True)[:n]
    return [dict(date=x.get("date"), adversaire=x.get("adversaire"), lieu="D" if x.get("domicile") else "E",
                 bm=x.get("buts_marques"), be=x.get("buts_encaisses")) for x in ordre]


def _pari(d):
    return dict(marche=d["marche"], cote=d["cote"], p_modele=round(d["p_modele"], 4), p_honnete=d["p_honnete"], niveau=d["niveau"],
                resultat=None, profit=None)


def proposer(m, forces, classements):
    """Retourne la ligne de pronostic d'un match ou None (match exclu : < 4 matchs au lieu, forces inconnues ou aucun marché lu)."""
    rd = C.lignes(m["hd"], True, m["date"])
    re_ = C.lignes(m["he"], False, m["date"])
    n_min, cands = C.analyse(rd, re_, m["cotes"])
    if not cands:
        return None
    rh, ra = C.orienter(rd[-C.FENETRE:], re_[-C.FENETRE:])
    r = M.proposer(cands, forces.lambdas(m["date"], m["dom"], m["ext"]), M.lambdas_simples(rh, ra))
    if r is None:
        return None
    ep = M.ecart_points(m["hd"], m["he"], m["date"])
    er = classements.ecart_rang(m["ligue"], m["date"], m["dom"], m["ext"])
    pr = r["principal"]
    alertes = M.alerte_contexte(pr["marche"], ep, er) + ["musique " + a for a in pr["alertes"]]
    return dict(match_id=m["id"], date=m["date"], coup_d_envoi_utc=m.get("kickoff"), competition=m["ligue"], domicile=m.get("dom"),
                exterieur=m.get("ext"), n_matchs_lieu=n_min, principal=_pari(pr), autres=[_pari(d) for d in r["autres"]],
                contexte=dict(ecart_points=None if ep is None else round(ep, 3), ecart_rang=None if er is None else round(er, 3)),
                alertes=alertes, parametres_version=M.PARAMETRES_VERSION,
                forme=dict(domicile=forme(m["hd"]), exterieur=forme(m["he"])))
