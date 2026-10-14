"""Variantes « marché modéré » de v2r (ajout 14/10/2026, demande de Patrick).

Principe : v2r choisit le match et le marché (règles figées, inchangées). Chaque variante remplace ce marché par un
marché de la même famille, k crans plus prudent (k = 1 ou 2), puis applique un PLANCHER de cote : si la cote finale est
inférieure à 1,40, on ne propose RIEN (jamais de repli sur le pari d'origine).

Familles avec version modérée : total de buts et buts d'une équipe (Plus de L -> Plus de L-k, Moins de L -> Moins de L+k,
ligne minimale 0,5), handicap (ligne + k), 1X2 victoire -> double chance. Les autres marchés (les deux marquent,
pair/impair, cage inviolée, nul) n'ont pas de version modérée : ils sont gardés tels quels, sous le même plancher.
Si le marché modéré n'est pas coté pour le match, le pari d'origine est gardé (sous le plancher).

Chaque variante a son propre carnet (data/v2r/modere1/carnet.json, data/v2r/modere2/carnet.json), écrit avec les mêmes
règles que le carnet officiel (avant le coup d'envoi, figé ensuite, score ajouté une seule fois). Le carnet officiel et
les règles de v2r ne sont jamais modifiés. Les gains affichés sont des gains de carnet : seuls comptent les paris faits
à l'avance."""
import os
import re

from . import carnet as K

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
    return {"1X2 - 1": "Double chance - 1X", "1X2 - 2": "Double chance - X2"}.get(lib)


def variante(pick, cotes, k, plancher=PLANCHER_COTE):
    """Pari modéré à k crans, ou None si la cote finale est sous le plancher. `cotes` : cotes du match {libellé: cote}."""
    lib, cote = pick["marche"], pick["cote"]
    f = frere(lib, k)
    if f and f in cotes:
        lib, cote = f, cotes[f]
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
            K.enregistre(c, v, maintenant)
        K.sauve(c, d)
        cle = lambda l: (l["coup_d_envoi_utc"], l["match_id"])  # noqa: E731
        sortie[f"{k}_cran" if k == 1 else f"{k}_crans"] = dict(
            bilan=K.bilan(c),
            a_venir=sorted([l for l in c.values() if not l["fige"]], key=cle),
            reglees=sorted([l for l in c.values() if l["resultat"] is not None], key=cle, reverse=True)[:150])
    return sortie
