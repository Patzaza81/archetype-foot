"""Variantes « marché modéré » de v2r (ajout 14/10/2026, demande de Patrick).

Principe : v2r choisit le match et le marché (règles figées, inchangées). Chaque variante remplace ce marché par un
marché de la même famille, k crans plus prudent (k = 1 ou 2), puis applique un PLANCHER de cote : si la cote finale est
inférieure à 1,40, on ne propose RIEN (jamais de repli sur le pari d'origine).

Familles avec version modérée : total de buts et buts d'une équipe (Plus de L -> Plus de L-k, Moins de L -> Moins de L+k,
ligne minimale 0,5), handicap (plus sûr de k : ligne + k pour le domicile, - k pour l'extérieur, car la ligne affichée est celle du domicile), 1X2 victoire -> double chance, nul -> handicap +2 (= +1,5) de l'outsider,
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
    if m:       # la ligne affichée est celle du DOMICILE (journal_rentabilite.ligne_propre) : l'extérieur reçoit -L
        return f"Handicap {float(m[1]) + (k if m[2] == 'Domicile' else -k):g} - {m[2]}"
    m = re.fullmatch(r"Cage inviolée - (Domicile|Extérieur)", lib)
    if m:                                    # cage inviolée d'une équipe = l'adversaire marque 0 -> ligne de buts de l'adversaire
        adverse = "Extérieur" if m[1] == "Domicile" else "Domicile"
        return f"Moins de {0.5 + k:g} buts - {adverse}"
    return {"1X2 - 1": "Double chance - 1X", "1X2 - 2": "Double chance - X2",
            "BTTS - oui": "Plus de 1.5 buts"}.get(lib)   # les deux marquent => au moins 2 buts


def outsider(cotes):
    """Équipe à la plus grosse cote 1X2 (« Domicile » ou « Extérieur »). Cotes égales : Domicile. None si une cote manque."""
    d, e = cotes.get("1X2 - 1"), cotes.get("1X2 - 2")
    if d is None or e is None:
        return None
    return "Domicile" if d >= e else "Extérieur"


def handicap_plus_2(cotes):
    """Libellé du handicap « +2 » de l'outsider. Le +2 à trois issues (gagné si l'équipe ne perd pas de 2 buts ou plus)
    est le même pari que le +1,5 : c'est celui coté par BetPawa. Ligne affichée = ligne du domicile : Domicile +1,5,
    ou Extérieur -1,5 (l'extérieur reçoit +1,5)."""
    o = outsider(cotes)
    return None if o is None else ("Handicap 1.5 - Domicile" if o == "Domicile" else "Handicap -1.5 - Extérieur")


def candidats(lib, k, cotes=None):
    """Libellés plus prudents (même famille, gagnants dans tous les cas où le pari d'origine gagne). Le nul a pour
    équivalent le handicap +2 (= +1,5) de l'équipe à la plus grosse cote (décision de Patrick, 14/10), identique à 1 et 2 crans."""
    if lib == "1X2 - X":
        h = handicap_plus_2(cotes or {})
        return [h] if h else []
    f = frere(lib, k)
    return [f] if f else []


def variante(pick, cotes, k, plancher=PLANCHER_COTE):
    """Pari modéré à k crans, ou None si la cote finale est sous le plancher. `cotes` : cotes du match {libellé: cote}.
    Nul : handicap +2 (= +1,5) de l'outsider ; cote sous le plancher -> rien (jamais de repli sur le nul ni sur la double chance)."""
    lib, cote = pick["marche"], pick["cote"]
    cotes_dispo = [(c, cotes[c]) for c in candidats(lib, k, cotes) if c in cotes]
    if cotes_dispo:
        lib, cote = cotes_dispo[0]
    if cote < plancher:
        return None
    v = dict(pick)
    v.pop("forme", None)                # l'affichage des derniers scores se fait sur le pari officiel : pas de copie dans les carnets modérés
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
