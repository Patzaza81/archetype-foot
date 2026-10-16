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
    # lambdas_simples attend les scores de chaque équipe de SON point de vue (marqués, encaissés) : lignes brutes, PAS orientées
    # (corrigé le 16/10/2026 : une version utilisait les lignes orientées et inversait marqués/encaissés de l'équipe extérieure).
    lf = forces.lambdas(m["date"], m["dom"], m["ext"])
    ls = M.lambdas_simples(rd[-C.FENETRE:], re_[-C.FENETRE:])
    r = M.proposer(cands, lf, ls)
    if r is None:
        return None
    if r["principal"] is None:      # aucun pari ne atteint le plancher : le match est listé « sans pronostic fiable », jamais au carnet
        return dict(match_id=m["id"], date=m["date"], coup_d_envoi_utc=m.get("kickoff"), competition=m["ligue"], domicile=m.get("dom"),
                    exterieur=m.get("ext"), sans_pronostic=True, meilleur_score=round(r["meilleur_score"], 4), n_marches=len(r["tous"]),
                    parametres_version=M.PARAMETRES_VERSION)
    ep = M.ecart_points(m["hd"], m["he"], m["date"])
    er = classements.ecart_rang(m["ligue"], m["date"], m["dom"], m["ext"])
    pr = r["principal"]
    alertes = M.alerte_contexte(pr["marche"], ep, er) + ["musique " + a for a in pr["alertes"]]
    return dict(match_id=m["id"], date=m["date"], coup_d_envoi_utc=m.get("kickoff"), competition=m["ligue"], domicile=m.get("dom"),
                exterieur=m.get("ext"), n_matchs_lieu=n_min, principal=_pari(pr), autres=[_pari(d) for d in r["autres"]],
                contexte=dict(ecart_points=None if ep is None else round(ep, 3), ecart_rang=None if er is None else round(er, 3)),
                alertes=alertes, parametres_version=M.PARAMETRES_VERSION,
                lambdas=dict(force=[round(x, 4) for x in lf], simple=[round(x, 4) for x in ls]),
                marches=[dict(m=d["marche"], c=d["cote"], pf=round(d["p_force"], 4), ps=round(d["p_simple"], 4), pm=round(d["p_modele"], 4),
                              sh=round(d["sH"], 4), sa=round(d["sA"], 4), k=d["k"]) for d in r["tous"]],
                forme=dict(domicile=forme(m["hd"]), exterieur=forme(m["he"])))
