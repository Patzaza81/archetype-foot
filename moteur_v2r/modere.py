"""Variantes « marché modéré » de v2r (ajout 14/10/2026, demande de Patrick).

Principe : v2r choisit le match et le marché (règles figées, inchangées). Chaque variante remplace ce marché par un
marché de la même famille, k crans plus prudent (k = 1 ou 2), puis applique un PLANCHER de cote : si la cote finale est
inférieure à 1,40, on ne propose RIEN (jamais de repli sur le pari d'origine).

Familles avec version modérée : total de buts et buts d'une équipe (Plus de L -> Plus de L-k, Moins de L -> Moins de L+k,
ligne minimale 0,5), handicap (ligne + k), 1X2 victoire -> double chance, nul -> double chance (domicile ou extérieur),
les deux marquent « oui » -> Plus de 1,5 buts, cage inviolée -> Moins de (0,5+k) buts de l'adversaire. Sans version
modérée (aucun marché plus sûr n'est logiquement équivalent) : les deux marquent « non », pair/impair, « encaisse au
moins 1 but » : ils sont gardés tels quels, sous le même plancher.
Si le marché modéré n'est pas coté pour le match, le pari d'origine est gardé (sous le plancher).

Chaque pari modéré reçoit aussi son indice en % et le statut SUPER FAVORI (>= 75 %, moteur_v2r/super_favori.py).

Chaque variante a son propre carnet (data/v2r/modere1/carnet.json, data/v2r/modere2/carnet.json), écrit avec les mêmes
règles que le carnet officiel (avant le coup d'envoi, figé ensuite, score ajouté une seule fois). Le carnet officiel et
les règles de v2r ne sont jamais modifiés. Les gains affichés sont des gains de carnet : seuls comptent les paris faits
à l'avance."""
import os
import re

from . import carnet as K
from . import super_favori as SF

PLANCHER_COTE = 1.40
CRANS = (1, 2)


def frere(lib, k):
    """Libellé de la même famille, k crans plus prudent. None si la famille n'a pas de version modérée."""
    m = re.fullmatch(r"(Plus|Moins) de (\d+(?:\.\d+)?) buts( - (?:Domicile|Extérieur))?", lib)
    if m:
        sens, ligne, suffixe = m[1], float(m[2]), m[3] or ""
        nouvelle = max(0.5, ligne - k) if sens == "Plus" else ligne + k
        return f"{sens} de {nouvelle:g} buts{suffixe}"
    m = re.fullmatch(r"Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur)", lib)
    if m:
        return f"Handicap {float(m[1]) + k:g} - {m[2]}"
    m = re.fullmatch(r"Cage inviolée - (Domicile|Extérieur)", lib)
    if m:                                    # cage inviolée d'une équipe = l'adversaire marque 0 -> ligne de buts de l'adversaire
        adverse = "Extérieur" if m[1] == "Domicile" else "Domicile"
        return f"Moins de {0.5 + k:g} buts - {adverse}"
    return {"1X2 - 1": "Double chance - 1X", "1X2 - 2": "Double chance - X2",
            "BTTS - oui": "Plus de 1.5 buts"}.get(lib)   # les deux marquent => au moins 2 buts


def candidats(lib, k):
    """Libellés plus prudents (même famille, gagnants dans tous les cas où le pari d'origine gagne). Le nul a deux
    équivalents (double chance avec le domicile ou avec l'extérieur) : le choix se fait dans `variante`."""
    if lib == "1X2 - X":
        return ["Double chance - 1X", "Double chance - X2"]
    f = frere(lib, k)
    return [f] if f else []


def variante(pick, cotes, k, plancher=PLANCHER_COTE):
    """Pari modéré à k crans, ou None si la cote finale est sous le plancher. `cotes` : cotes du match {libellé: cote}.
    Nul : parmi les deux doubles chances cotées, celle dont la cote est la plus proche du plancher en restant au-dessus ;
    aucune au-dessus du plancher -> rien (jamais de repli sur le nul)."""
    lib, cote = pick["marche"], pick["cote"]
    cotes_dispo = [(c, cotes[c]) for c in candidats(lib, k) if c in cotes]
    if lib == "1X2 - X" and cotes_dispo:
        cotes_dispo = sorted((c for c in cotes_dispo if c[1] >= plancher), key=lambda c: (c[1], c[0]))
        if not cotes_dispo:
            return None
    if cotes_dispo:
        lib, cote = cotes_dispo[0]
    if cote < plancher:
        return None
    v = dict(pick)
    v.update(marche=lib, cote=cote, marche_v2r=pick["marche"], cote_v2r=pick["cote"], crans=k)
    return v


def met_a_jour(matchs, carnet_officiel, dossier, maintenant):
    """Règle les paris figés des variantes puis écrit les paris modérés des matchs encore avant le coup d'envoi.
    Retourne {"plancher": ..., "1_cran": {bilan, a_venir, reglees}, "2_crans": {...}}."""
    par_id = {m["id"]: m for m in matchs}
    scores = {m["id"]: (m["h"], m["a"]) for m in matchs if m["h"] is not None}
    sortie = dict(plancher=PLANCHER_COTE)
    for k in CRANS:
        d = os.path.join(dossier, f"modere{k}")
        c = K.charge(d)
        K.fige(c, maintenant)
        K.regle(c, scores)
        for mid, ligne in carnet_officiel.items():
            if ligne["fige"] or mid not in par_id:
                continue
            v = variante(ligne, par_id[mid]["cotes"], k)
            if v is None:
                if mid in c and not c[mid]["fige"]:
                    del c[mid]              # devenu inférieur au plancher avant le coup d'envoi : on ne propose rien
                continue
            v.update(SF.statut(v["marche"], par_id[mid]["hd"], par_id[mid]["he"]))   # indice % + SUPER FAVORI (>= 75 %)
            K.enregistre(c, v, maintenant)
        K.sauve(c, d)
        cle = lambda l: (l["coup_d_envoi_utc"], l["match_id"])  # noqa: E731
        sortie[f"{k}_cran" if k == 1 else f"{k}_crans"] = dict(
            bilan=K.bilan(c),
            a_venir=sorted([l for l in c.values() if not l["fige"]], key=cle),
            en_cours=sorted([l for l in c.values() if l["fige"] and l["resultat"] is None], key=cle),
            reglees=sorted([l for l in c.values() if l["resultat"] is not None], key=cle, reverse=True)[:150])
        sf = {mid: l for mid, l in c.items() if l.get("super_favori")}
        sortie[f"{k}_cran" if k == 1 else f"{k}_crans"]["super_favori"] = dict(
            seuil=SF.SEUIL, bilan=K.bilan(sf), a_venir=sum(1 for l in sf.values() if not l["fige"]))
    return sortie
