"""indice_corners_cartons.py -- indice x/4 et « choix du match » pour les corners et les cartons (12/10/2026).

Même logique que l'indice de performance des buts (moteur_v3/performance.py), appliquée aux TOTAUX de corners / cartons :
- par équipe, ses derniers matchs au même lieu (domicile pour l'équipe qui reçoit, extérieur pour l'autre), jusqu'à
  N_MATCHS (CHOIX DE CLAUDE, non défini par Patrick) ; total d'un match = pour + contre ;
- profil « moyen » = moyenne des totaux ; profil « pire » = le total qui met le pari le plus en difficulté
  (le plus petit pour un « Plus de », le plus grand pour un « Moins de ») ;
- 4 scénarios (domicile moyen/pire) x (extérieur moyen/pire), total du scénario = moyenne des deux totaux ;
- un scénario valide le pari si sa marge contre la ligne est strictement > 0 ; indice = scénarios validés sur 4.
Information seulement : ne change ni la probabilité ni le bilan. Pas d'indice pour les lignes par équipe ni le carton rouge.

Choix du match : parmi tous les paris Plus/Moins des lignes totales, celui qui a le meilleur indice puis la meilleure
probabilité du modèle. Les paris à plus de 80 % (PROBA_MAX_CHOIX) sont écartés du choix : leur cote juste est sous 1,25. La cote BetPawa,
quand elle est connue, doit être regardée avant de miser.
"""
from collections import defaultdict

N_MATCHS = 5
MIN_MATCHS = 3
PROBA_MAX_CHOIX = 0.80   # CHOIX DE CLAUDE : au-delà, la cote juste est < 1,25 (ligne extrême, rien à gagner)
NIVEAUX = {4: "Sûr", 3: "Recommandé", 2: "Attention", 1: "Risqué", 0: "Très risqué"}


def historique(matchs, comptes):
    """{(division, équipe, lieu): [(date, total du match)]} par genre. `comptes(m)` -> (domicile, extérieur) ou None."""
    h = defaultdict(list)
    for m in matchs:
        v = comptes(m)
        if not v:
            continue
        t = v[0] + v[1]
        h[(m["competition_code"], m["home_team"], "dom")].append((m["date"], t))
        h[(m["competition_code"], m["away_team"], "ext")].append((m["date"], t))
    return h


def _derniers(h, cle):
    return [t for _, t in sorted(h.get(cle, []))[-N_MATCHS:]]


def indice(totaux_dom, totaux_ext, ligne, cote_plus):
    """Nombre de scénarios (sur 4) validant « Plus de ligne » (cote_plus=True) ou « Moins de ligne ». None si peu de matchs."""
    if len(totaux_dom) < MIN_MATCHS or len(totaux_ext) < MIN_MATCHS:
        return None
    pire = min if cote_plus else max
    md, me = sum(totaux_dom) / len(totaux_dom), sum(totaux_ext) / len(totaux_ext)
    pd_, pe = pire(totaux_dom), pire(totaux_ext)
    n = 0
    for sd, se in ((md, me), (pd_, me), (md, pe), (pd_, pe)):
        marge = (sd + se) / 2 - ligne if cote_plus else ligne - (sd + se) / 2
        if marge > 1e-9:
            n += 1
    return n


def indices_et_choix(previsions, hist_genres, division, dom, ext):
    """-> (indices, choix) ; indices[genre][ligne] = {plus, moins} ; choix[genre] = meilleur pari ou absent."""
    indices, choix = {}, {}
    for genre, h in hist_genres.items():
        td, te = _derniers(h, (division, dom, "dom")), _derniers(h, (division, ext, "ext"))
        tot = previsions[genre]["total"]
        ind, cands = {}, []
        for l, p_plus in tot.items():
            ip, im = indice(td, te, float(l), True), indice(td, te, float(l), False)
            if ip is None or im is None:
                continue
            ind[l] = {"plus": ip, "moins": im}
            for n, p, c in ((ip, p_plus, "plus"), (im, 1.0 - p_plus, "moins")):
                if p <= PROBA_MAX_CHOIX:
                    cands.append((n, p, l, c))
        if not cands:
            continue
        indices[genre] = ind
        n, p, l, cote = max(cands, key=lambda c: (c[0], c[1]))
        choix[genre] = {"ligne": l, "cote": cote, "proba": round(p, 4), "indice": n, "niveau": NIVEAUX[n],
                        "matchs_domicile": len(td), "matchs_exterieur": len(te)}
    return indices, choix
