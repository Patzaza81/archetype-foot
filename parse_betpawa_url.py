"""
parse_betpawa_url.py -- convertit le texte d'une page Betpawa RÉCUPÉRÉE PAR
URL (via web_fetch dans le chat) en cotes_manuelles pour panier.json.

Différence structurelle avec parse_betpawa.py (copier-coller depuis le
téléphone) : ici, étiquette et valeur sont COLLÉES sur une seule ligne, sans
séparateur ("11.94" = étiquette "1" + valeur "1.94"), et les libellés de
marché sont en ANGLAIS (page servie sans tenir compte de la langue
demandée). Les deux parseurs sont volontairement séparés plutôt que fusionnés
en un seul avec des branches partout -- deux formats d'entrée réellement
différents valent mieux que du code qui devine lequel des deux il lit.

Ce module est destiné à être exécuté ICI (dans l'environnement d'analyse),
pas déployé sur le site -- c'est Claude qui récupère l'URL et fait tourner
ce parseur à la demande, il n'y a pas de portage JS correspondant.
"""
import re
from datetime import date as _date


def _lignes_non_vides(texte):
    return [l.strip() for l in texte.splitlines() if l.strip()]


def _peler_prefixe(ligne, prefixes):
    """Cherche lequel des préfixes connus commence la ligne, et interprète le
    reste comme la cote (un float positif). Testé du préfixe le plus long au
    plus court pour ne jamais couper un préfixe plus long par erreur."""
    for p in sorted(prefixes, key=len, reverse=True):
        if ligne.startswith(p):
            reste = ligne[len(p):]
            try:
                valeur = float(reste)
                if valeur > 0:
                    return p, valeur
            except ValueError:
                continue
    return None, None


def _lit_bloc(lignes, i, prefixes, arret_sur_titre=True):
    """Lit des lignes concaténées tant qu'un préfixe connu les explique.
    S'arrête à la première ligne qui ne correspond à aucun préfixe --
    délimite naturellement la fin d'une section."""
    resultat = {}
    while i < len(lignes):
        p, v = _peler_prefixe(lignes[i], prefixes)
        if p is None:
            break
        resultat[p] = v
        i += 1
    return resultat, i


LIGNES_OU = [f"{n}.5" for n in range(8)]  # 0.5 .. 7.5
PREFIXES_OU = [f"Over {l}" for l in LIGNES_OU] + [f"Under {l}" for l in LIGNES_OU]
LIGNES_HANDICAP = ["-2.5", "-1.5", "-0.5", "0.5", "1.5", "2.5"]
PREFIXES_HANDICAP = LIGNES_HANDICAP + [f"+{l}" for l in LIGNES_HANDICAP if not l.startswith("-")]
PREFIXES_SCORE = [f"{x}-{y}" for x in range(5) for y in range(5)]
PREFIXES_NB_BUTS = [str(n) for n in range(6)] + ["6+"]


def parse_betpawa_url(texte, nom_domicile, nom_exterieur):
    lignes = _lignes_non_vides(texte)
    cotes = {}
    i = 0

    while i < len(lignes):
        titre = lignes[i]

        if titre == "1X2 | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, ["1", "X", "2"])
            if len(paires) == 3:
                cotes["1x2"] = {"1": paires["1"], "N": paires["X"], "2": paires["2"]}
            continue

        if titre == "Double Chance | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, ["1X", "X2", "12"])
            if len(paires) == 3:
                cotes["double_chance"] = {"1N": paires["1X"], "N2": paires["X2"], "12": paires["12"]}
            continue

        if titre == "Both Teams To Score | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, ["Yes", "No"])
            if len(paires) == 2:
                cotes["btts"] = {"Oui": paires["Yes"], "Non": paires["No"]}
            continue

        if titre == "Over/Under | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, PREFIXES_OU)
            for label, valeur in paires.items():
                sens, ligne = label.split(" ")
                cle_sel = "plus" if sens == "Over" else "moins"
                cotes.setdefault(f"over_under_{ligne}", {})[cle_sel] = valeur
            continue

        m_equipe = re.match(r"^Over/Under \| (.+) \| Full Time$", titre)
        if m_equipe:
            nom = m_equipe.group(1)
            prefixe = ("over_under_domicile" if nom == nom_domicile
                       else "over_under_exterieur" if nom == nom_exterieur else None)
            paires, i = _lit_bloc(lignes, i + 1, PREFIXES_OU)
            if prefixe:
                for label, valeur in paires.items():
                    sens, ligne = label.split(" ")
                    cle_sel = "plus" if sens == "Over" else "moins"
                    cotes.setdefault(f"{prefixe}_{ligne}", {})[cle_sel] = valeur
            continue

        if titre == "2-Way Handicap | Full Time":
            i += 1
            if i < len(lignes) and lignes[i] == "- 1":
                i += 1
            if i < len(lignes) and lignes[i] == "- 2":
                i += 1
            while i + 1 < len(lignes):
                pd, vd = _peler_prefixe(lignes[i], PREFIXES_HANDICAP)
                pe, ve = _peler_prefixe(lignes[i + 1], PREFIXES_HANDICAP)
                if pd is None or pe is None:
                    break
                cle_ligne = pd[1:] if pd.startswith("+") else pd
                cotes[f"handicap_{cle_ligne}"] = {"domicile": vd, "exterieur": ve}
                i += 2
            continue

        if titre == "Odd/Even | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, ["Odd", "Even"])
            if len(paires) == 2:
                cotes["pair_impair"] = {"pair": paires["Even"], "impair": paires["Odd"]}
            continue

        m_cages = re.match(r"^Clean Sheet \| (.+) \| Full Time$", titre)
        if m_cages:
            nom = m_cages.group(1)
            paires, i = _lit_bloc(lignes, i + 1, ["Yes", "No"])
            if len(paires) == 2:
                if nom == nom_domicile:
                    cotes["cages_inviolees_domicile"] = {"oui": paires["Yes"], "non": paires["No"]}
                elif nom == nom_exterieur:
                    cotes["cages_inviolees_exterieur"] = {"oui": paires["Yes"], "non": paires["No"]}
            continue

        if titre == "Correct Score | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, PREFIXES_SCORE + ["Other"])
            scores = {k: v for k, v in paires.items() if k != "Other"}
            if scores:
                cotes["score_exact"] = scores
            continue

        if titre == "Total Goals Exact | Full Time":
            paires, i = _lit_bloc(lignes, i + 1, PREFIXES_NB_BUTS)
            if paires:
                cotes["nombre_exact_buts"] = paires
            continue

        i += 1  # section non reconnue -- ignorée sans message, c'est voulu

    return cotes


def _date_iso_depuis_jour_mois(jour_mois, aujourdhui=None):
    """Convertit '29/08' en '2026-08-29'. L'année n'est pas dans le titre
    Betpawa -- on prend l'année en cours, sauf si la date obtenue tombe
    loin dans le passé (>300 jours), auquel cas on bascule sur l'année
    suivante (cas d'un match scrapé fin décembre pour un match de janvier).
    Retourne None si le format est invalide plutôt que de lever une
    exception -- une date de désambiguïsation ratée ne doit jamais faire
    échouer l'extraction de domicile/exterieur/competition, qui reste
    l'essentiel."""
    aujourdhui = aujourdhui or _date.today()
    try:
        jour, mois = (int(x) for x in jour_mois.split("/"))
        candidate = _date(aujourdhui.year, mois, jour)
    except ValueError:
        return None
    if (aujourdhui - candidate).days > 300:
        try:
            candidate = _date(aujourdhui.year + 1, mois, jour)
        except ValueError:
            return None
    return candidate.isoformat()


def extrait_meta(meta_og_title):
    """Extrait domicile/exterieur/competition/date/heure depuis le meta
    og:title, ex. 'Bet on AFC Bournemouth - Everton FC | 3:00 pm Sat 29/08
    | Premier League | England | Football | betPawa Cameroon'.

    'date' sert à désambiguïser un nom d'équipe qui matche plusieurs
    matchs matchendirect à la fois (voir cherche_url_matchendirect_auto()
    dans scraper_betpawa.py). 'heure' est capturée telle quelle (ex.
    '3:00 pm') mais N'EST PAS ENCORE UTILISÉE pour filtrer ou
    désambiguïser -- le fuseau horaire de Betpawa (probablement Cameroun,
    WAT/UTC+1) par rapport à celui de matchendirect (probablement France,
    CEST/UTC+2 en été) n'a jamais été vérifié en conditions réelles. Elle
    est stockée pour permettre la comparaison manuelle sur le prochain run
    réel (voir 'heure' dans matchs_du_jour.json pour le même match) avant
    de décider d'un éventuel filtre par heure.

    Les deux champs peuvent être None si leur format n'a pas été reconnu ;
    le comportement de recherche reste alors identique à avant leur ajout
    (pas de régression possible)."""
    m = re.match(
        r"^Bet on (.+?) - (.+?) \| (\d{1,2}:\d{2} [ap]m) .*?(\d{1,2}/\d{1,2}) \| "
        r"(.+?) \| (.+?) \| Football \|",
        meta_og_title,
    )
    if not m:
        return None
    domicile, exterieur, heure, jour_mois, competition, pays = m.groups()
    return {
        "domicile": domicile.strip(), "exterieur": exterieur.strip(),
        "competition": f"{pays.strip()} : {competition.strip()}",
        "date": _date_iso_depuis_jour_mois(jour_mois),
        "heure": heure.strip(),
    }
