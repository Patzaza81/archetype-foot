# -*- coding: utf-8 -*-
"""Rubrique CORNERS / CARTONS (11/10/2026) — séparée des moteurs V2 et V3, qui ne sont pas touchés.

Les corners et les cartons ne se déduisent PAS des buts (règle de moteur_v3/markets.py) : ils ont leur propre modèle.

FORMULE (choisie par backtest chronologique sans fuite sur la saison 2025-26 de Football-Data : 7 094 matchs, 21 divisions) :

    attendu_dom = L_dom + c * (L_dom * attaque_dom * defense_ext - L_dom)
    attendu_ext = L_ext + c * (L_ext * attaque_ext * defense_dom - L_ext)

  - L_dom, L_ext : moyenne de la division (corners ou cartons du domicile / de l'extérieur), tirée vers la moyenne de
    toutes les divisions avec 20 matchs fictifs tant que la division a peu de matchs ;
  - attaque / défense d'une équipe : moyenne, sur TOUS ses matchs (domicile et extérieur), du rapport « ce qu'elle a
    obtenu / ce qu'une équipe moyenne obtient dans ce lieu », tirée vers 1 avec k matchs fictifs (shrinkage) ;
  - c : facteur de compression des écarts à la moyenne de la division.
  Loi du total et des lignes par équipe : binomiale négative (Poisson si la surdispersion est nulle).
  Carton rouge : probabilité qu'au moins un rouge tombe = 1 - exp(-taux de la division), SANS effet d'équipe
  (le backtest n'a trouvé aucun gain avec un effet d'équipe).

PARAMÈTRES MESURÉS (voir PARAMETRES) :
  corners : k = 40, c = 0,7 ; surdispersion total 0,021, par équipe 0,115
  cartons : k = 40, c = 1,0 ; surdispersion total 0,0163, par équipe 0 (Poisson)
  « cartons » = jaunes + rouges, un rouge compte pour un carton.

LIMITE ASSUMÉE (backtest) : l'ajustement par équipe n'améliore la log-perte que de 0,003 (corners) à 0,005 (cartons)
par rapport à la seule moyenne de la division. Ces marchés dépendent surtout du championnat.
COTES (12/10/2026) : les cotes BetPawa équivalentes à un marché du modèle sont relevées à part (parse_corners_cartons_betpawa.py,
clé `cotes_corners_cartons` du signal) et AFFICHÉES avec leur seuil 1 / cote. Ce module ne calcule toujours ni EV ni pari retenu :
le modèle n'a pas été comparé au marché (voir docs/CORNERS_CARTONS.md).

Données : data/football_data/normalized/<saison la plus récente>/*.jsonl (saison en cours seule, jamais la précédente).
Un match sans corners ou sans cartons publiés est ignoré pour le marché concerné (règle du 24/09/2026).
Rapprochement des noms : data/correspondances/equipes.json (Football-Data <-> Matchendirect).

Sorties (reconstruites ou mises à jour à chaque run) :
  data/corners_cartons.json          — probabilités des matchs à venir + bilan
  data/corners_cartons_archive.json  — prévision de chaque match, règlement dès que Football-Data publie le score

Bibliothèque standard uniquement. Usage : python corners_cartons.py
"""
import datetime
import glob
import json
import math
import os
import re
import unicodedata
from collections import defaultdict

RACINE = os.path.dirname(os.path.abspath(__file__))
DOSSIER_NORMALISE = os.path.join(RACINE, "data", "football_data", "normalized")
FICHIER_CORRESPONDANCES = os.path.join(RACINE, "data", "correspondances", "equipes.json")
FICHIER_PRECALCUL = os.path.join(RACINE, "precalcul.json")
FICHIER_SORTIE = os.path.join(RACINE, "data", "corners_cartons.json")
FICHIER_ARCHIVE = os.path.join(RACINE, "data", "corners_cartons_archive.json")
VERSION = "1.1.0"

PRIOR_LIGUE = 20          # matchs fictifs tirant la moyenne d'une division vers la moyenne de toutes les divisions
MIN_TAUX_ROUGE = 0.02     # plancher : une probabilité de carton rouge nulle n'a pas de sens
MIN_MATCHS_EQUIPE = 3     # matchs publiés (corners ET cartons) minimum par équipe, sinon match écarté

PARAMETRES = {
    "corners": {"k": 40, "c": 0.7, "alpha_total": 0.021, "alpha_equipe": 0.115,
                "lignes_total": (7.5, 8.5, 9.5, 10.5, 11.5, 12.5), "lignes_equipe": (3.5, 4.5, 5.5, 6.5)},
    "cartons": {"k": 40, "c": 1.0, "alpha_total": 0.0163, "alpha_equipe": 0.0,
                "lignes_total": (2.5, 3.5, 4.5, 5.5, 6.5), "lignes_equipe": (0.5, 1.5, 2.5)},
}
# Carton rouge : pas de paramètre d'équipe (voir en-tête).
CHAMPS = {"corners": ("home_corners", "away_corners"),
          "cartons": None,   # jaunes + rouges, voir _comptes
          "rouge": ("home_red_cards", "away_red_cards")}


# ------------------------------------------------------------------------------------------------------------------
# Outils
# ------------------------------------------------------------------------------------------------------------------
def normalise(nom):
    t = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _lire(chemin, defaut):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, doc):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def _date(iso):
    try:
        return datetime.date.fromisoformat(str(iso)[:10])
    except (TypeError, ValueError):
        return None


def _entier(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _comptes(m, genre):
    """(domicile, extérieur) du genre « corners » / « cartons » / « rouge » pour un match normalisé, ou None si une
    donnée nécessaire manque (jamais remplacée par zéro)."""
    if genre == "cartons":
        vals = [_entier(m.get(c)) for c in ("home_yellow_cards", "home_red_cards", "away_yellow_cards", "away_red_cards")]
        if None in vals:
            return None
        return vals[0] + vals[1], vals[2] + vals[3]
    cd, ca = CHAMPS[genre]
    h, a = _entier(m.get(cd)), _entier(m.get(ca))
    return None if h is None or a is None else (h, a)


# ------------------------------------------------------------------------------------------------------------------
# Lois de probabilité
# ------------------------------------------------------------------------------------------------------------------
def proba_plus_de(mu, alpha, ligne):
    """P(Y > ligne), Y de moyenne mu : binomiale négative de variance mu + alpha*mu² (Poisson si alpha ~ 0)."""
    if mu <= 0:
        return 0.0
    kmax = int(math.floor(ligne))
    if alpha < 1e-9:
        terme = math.exp(-mu)
        cumul = terme
        for k in range(kmax):
            terme *= mu / (k + 1)
            cumul += terme
    else:
        r = 1.0 / alpha
        q = mu / (r + mu)                      # 1 - p
        terme = (r / (r + mu)) ** r
        cumul = terme
        for k in range(kmax):
            terme *= (k + r) / (k + 1) * q
            cumul += terme
    return min(max(1.0 - cumul, 0.0), 1.0)


# ------------------------------------------------------------------------------------------------------------------
# Modèle (attendu corners / cartons)
# ------------------------------------------------------------------------------------------------------------------
class ModeleComptage:
    """Rejoue les matchs dans l'ordre : prédire AVANT d'observer garantit l'absence de fuite (backtest identique)."""

    def __init__(self, k, c, prior_ligue=PRIOR_LIGUE):
        self.k, self.c, self.prior = k, c, prior_ligue
        self.pool = [0.0, 0.0, 0]
        self.div = defaultdict(lambda: [0.0, 0.0, 0])
        self.att = defaultdict(lambda: [0.0, 0])
        self.dfn = defaultdict(lambda: [0.0, 0])

    def _ligue(self, div):
        if not self.pool[2]:
            return None
        d = self.div[div]
        ph, pa = self.pool[0] / self.pool[2], self.pool[1] / self.pool[2]
        return ((d[0] + self.prior * ph) / (d[2] + self.prior), (d[1] + self.prior * pa) / (d[2] + self.prior))

    def _facteur(self, v):
        return (v[0] + self.k) / (v[1] + self.k) if (v[1] + self.k) > 0 else 1.0

    def predit(self, div, dom, ext):
        """(mu_dom, mu_ext, base_dom, base_ext, matchs_dom, matchs_ext) ou None si aucune donnée."""
        ligue = self._ligue(div)
        if ligue is None:
            return None
        lh, la = ligue
        kh, ka = (div, dom), (div, ext)
        mh = lh * self._facteur(self.att[kh]) * self._facteur(self.dfn[ka])
        ma = la * self._facteur(self.att[ka]) * self._facteur(self.dfn[kh])
        return (lh + self.c * (mh - lh), la + self.c * (ma - la), lh, la, self.att[kh][1], self.att[ka][1])

    def observe(self, div, dom, ext, yh, ya):
        d = self.div[div]
        d[0] += yh
        d[1] += ya
        d[2] += 1
        self.pool[0] += yh
        self.pool[1] += ya
        self.pool[2] += 1
        lh = (d[0] + self.prior * self.pool[0] / self.pool[2]) / (d[2] + self.prior)
        la = (d[1] + self.prior * self.pool[1] / self.pool[2]) / (d[2] + self.prior)
        if lh > 0 and la > 0:
            kh, ka = (div, dom), (div, ext)
            self.att[kh][0] += yh / lh
            self.att[kh][1] += 1
            self.dfn[kh][0] += ya / la
            self.dfn[kh][1] += 1
            self.att[ka][0] += ya / la
            self.att[ka][1] += 1
            self.dfn[ka][0] += yh / lh
            self.dfn[ka][1] += 1


def charge_matchs_saison(dossier=DOSSIER_NORMALISE):
    """Matchs joués de la saison la plus récente (saison en cours seule), triés par date."""
    saisons = sorted(d for d in os.listdir(dossier) if os.path.isdir(os.path.join(dossier, d))) if os.path.isdir(dossier) else []
    if not saisons:
        return None, []
    saison = saisons[-1]
    out = []
    for f in sorted(glob.glob(os.path.join(dossier, saison, "*.jsonl"))):
        with open(f, encoding="utf-8") as fh:
            for ligne in fh:
                if not ligne.strip():
                    continue
                try:
                    m = json.loads(ligne)
                except ValueError:
                    continue
                if m.get("home_team") and m.get("away_team") and _date(m.get("date")) and m.get("competition_code") \
                        and _entier(m.get("full_time_home_goals")) is not None:
                    out.append(m)
    out.sort(key=lambda m: (m["date"], m["competition_code"], m["home_team"]))
    return saison, out


def construit_modeles(matchs):
    """Un modèle par genre (corners, cartons), alimenté par les matchs où la donnée existe."""
    modeles = {g: ModeleComptage(PARAMETRES[g]["k"], PARAMETRES[g]["c"]) for g in ("corners", "cartons")}
    pool_rouge = [0, 0]
    div_rouge = defaultdict(lambda: [0, 0])
    for m in matchs:
        for g, mod in modeles.items():
            v = _comptes(m, g)
            if v:
                mod.observe(m["competition_code"], m["home_team"], m["away_team"], v[0], v[1])
        r = _comptes(m, "rouge")
        if r:
            div_rouge[m["competition_code"]][0] += r[0] + r[1]
            div_rouge[m["competition_code"]][1] += 1
            pool_rouge[0] += r[0] + r[1]
            pool_rouge[1] += 1
    return modeles, div_rouge, pool_rouge


def taux_rouge(div, div_rouge, pool_rouge):
    """Rouges par match de la division, tirés vers la moyenne de toutes les divisions (20 matchs fictifs)."""
    if not pool_rouge[1]:
        return None
    d = div_rouge[div]
    return max((d[0] + PRIOR_LIGUE * pool_rouge[0] / pool_rouge[1]) / (d[1] + PRIOR_LIGUE), MIN_TAUX_ROUGE)


# ------------------------------------------------------------------------------------------------------------------
# Marchés d'un match
# ------------------------------------------------------------------------------------------------------------------
def marches_famille(genre, mu_dom, mu_ext):
    p = PARAMETRES[genre]
    return {
        "attendu_domicile": round(mu_dom, 3), "attendu_exterieur": round(mu_ext, 3),
        "attendu_total": round(mu_dom + mu_ext, 3),
        "total": {f"{l:g}": round(proba_plus_de(mu_dom + mu_ext, p["alpha_total"], l), 4) for l in p["lignes_total"]},
        "domicile": {f"{l:g}": round(proba_plus_de(mu_dom, p["alpha_equipe"], l), 4) for l in p["lignes_equipe"]},
        "exterieur": {f"{l:g}": round(proba_plus_de(mu_ext, p["alpha_equipe"], l), 4) for l in p["lignes_equipe"]},
    }


def prevoit_match(modeles, div_rouge, pool_rouge, div, dom, ext):
    """Prévision complète, ou (None, raison) si le match doit être écarté."""
    out = {}
    base = {}
    for genre, mod in modeles.items():
        pr = mod.predit(div, dom, ext)
        if pr is None:
            return None, "aucune_donnee_division"
        mu_d, mu_e, b_d, b_e, n_d, n_e = pr
        if mod.div[div][2] == 0:
            return None, "corners_cartons_non_publies_pour_ce_championnat"
        if min(n_d, n_e) < MIN_MATCHS_EQUIPE:
            return None, "echantillon_insuffisant"
        out[genre] = marches_famille(genre, mu_d, mu_e)
        out[genre]["matchs_domicile"], out[genre]["matchs_exterieur"] = n_d, n_e
        base[genre] = (round(b_d, 3), round(b_e, 3))
    taux = taux_rouge(div, div_rouge, pool_rouge)
    if taux is None:
        return None, "aucune_donnee_division"
    out["rouge"] = {"taux_division": round(taux, 4), "oui": round(1.0 - math.exp(-taux), 4)}
    n_min = min(out["corners"]["matchs_domicile"], out["corners"]["matchs_exterieur"],
                out["cartons"]["matchs_domicile"], out["cartons"]["matchs_exterieur"])
    out["fiabilite"] = "bonne" if n_min >= 12 else "moyenne" if n_min >= 6 else "faible"
    return {"previsions": out, "base_ligue": base}, None


# ------------------------------------------------------------------------------------------------------------------
# Cotes BetPawa (AJOUT 12/10/2026) : affichage d'information. Jamais d'EV, jamais de pari retenu (docs/CORNERS_CARTONS.md).
# ------------------------------------------------------------------------------------------------------------------
def _cote_ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1.0


def _ligne_cotes(p_plus, brut, cles=("plus", "moins")):
    """Une ligne : cotes disponibles, seuil de rentabilité (1 / cote) de chaque côté et côté pour lequel la probabilité du
    modèle dépasse ce seuil (au plus un des deux, car les seuils d'un même marché somment plus de 1)."""
    probas = {"plus": p_plus, "moins": 1.0 - p_plus, "oui": p_plus, "non": 1.0 - p_plus}
    sortie, au_dessus = {}, None
    for c in cles:
        v = brut.get(c)
        if not _cote_ok(v):
            continue
        seuil = 1.0 / v
        sortie[c] = v
        sortie["seuil_" + c] = round(seuil, 4)
        if probas[c] > seuil:
            au_dessus = c
    if not any(c in sortie for c in cles):
        return None
    sortie["modele_au_dessus"] = au_dessus
    return sortie


def cotes_du_match(brutes, previsions):
    """Cotes BetPawa rangées comme les prévisions (genre -> zone -> ligne), seulement pour les lignes que le modèle calcule
    ET pour lesquelles BetPawa publie une cote équivalente (parse_corners_cartons_betpawa.py). None si aucune."""
    if not isinstance(brutes, dict):
        return None
    out = {}
    for genre in ("corners", "cartons"):
        bloc = {}
        p = PARAMETRES[genre]
        for zone, lignes in (("total", p["lignes_total"]), ("domicile", p["lignes_equipe"]), ("exterieur", p["lignes_equipe"])):
            for l in lignes:
                brut = brutes.get(f"{genre}_{zone}_{l:g}")
                p_plus = previsions[genre][zone].get(f"{l:g}")
                if not isinstance(brut, dict) or p_plus is None:
                    continue
                ligne = _ligne_cotes(p_plus, brut)
                if ligne:
                    bloc.setdefault(zone, {})[f"{l:g}"] = ligne
        if bloc:
            out[genre] = bloc
    brut = brutes.get("rouge_match")
    if isinstance(brut, dict):
        ligne = _ligne_cotes(previsions["rouge"]["oui"], brut, cles=("oui", "non"))
        if ligne:
            out["rouge"] = ligne
    return out or None


# ------------------------------------------------------------------------------------------------------------------
# Rapprochement des matchs à venir avec les équipes Football-Data
# ------------------------------------------------------------------------------------------------------------------
def _nom_competition(c):
    """Pays ET compétition (« france ligue 1 mcdonald s ») : le nom seul est ambigu (« Premier League » existe dans
    plusieurs pays)."""
    return normalise(c)


def construit_index(correspondances):
    """(index_competition, index_equipes) :
       index_competition[nom compétition normalisé] -> division (None si deux divisions la revendiquent)
       index_equipes[division][nom Matchendirect normalisé] -> nom Football-Data."""
    idx_comp, idx_eq = {}, {}
    for div, info in (correspondances or {}).get("divisions", {}).items():
        cle = _nom_competition(info.get("competition_matchendirect"))
        if cle:
            idx_comp[cle] = None if cle in idx_comp and idx_comp[cle] != div else div
        idx_eq[div] = {}
        for nom_fd, v in (info.get("equipes") or {}).items():
            n = normalise(v.get("matchendirect"))
            idx_eq[div][n] = None if n in idx_eq[div] else nom_fd      # nom revendiqué deux fois : inutilisable
    return idx_comp, idx_eq


def trouve_equipes(competition, dom, ext, idx_comp, idx_eq):
    """(division, nom_fd_dom, nom_fd_ext) ou None. Le pays + la compétition doivent correspondre exactement à ceux de
    la division, et chaque nom d'équipe doit être relié sans ambiguïté : mieux vaut aucun match qu'un mauvais match."""
    div = idx_comp.get(_nom_competition(competition))
    if not div:
        return None
    a, b = idx_eq.get(div, {}).get(normalise(dom)), idx_eq.get(div, {}).get(normalise(ext))
    return (div, a, b) if a and b and a != b else None


# ------------------------------------------------------------------------------------------------------------------
# Règlement
# ------------------------------------------------------------------------------------------------------------------
def observations(m):
    """Valeurs réelles d'un match normalisé (None par genre si la donnée manque)."""
    return {g: _comptes(m, g) for g in ("corners", "cartons", "rouge")}


def regle_prevision(prev, obs):
    """Chaque ligne de la prévision devient gagné (True : « plus de » réalisé) / perdu. Ligne sans donnée réelle : absente."""
    out = {}
    for genre in ("corners", "cartons"):
        v = obs.get(genre)
        if not v or genre not in prev:
            continue
        res = {"total": {}, "domicile": {}, "exterieur": {}}
        for l in prev[genre]["total"]:
            res["total"][l] = (v[0] + v[1]) > float(l)
        for l in prev[genre]["domicile"]:
            res["domicile"][l] = v[0] > float(l)
            res["exterieur"][l] = v[1] > float(l)
        res["reel"] = {"domicile": v[0], "exterieur": v[1]}
        out[genre] = res
    r = obs.get("rouge")
    if r and "rouge" in prev:
        out["rouge"] = {"oui": (r[0] + r[1]) >= 1, "reel": r[0] + r[1]}
    return out


def _brier_logloss(pairs):
    n = len(pairs)
    if not n:
        return None, None
    br = sum((p - o) ** 2 for p, o in pairs) / n
    ll = sum(-(o * math.log(min(max(p, 1e-6), 1 - 1e-6)) + (1 - o) * math.log(min(max(1 - p, 1e-6), 1 - 1e-6)))
             for p, o in pairs) / n
    return round(br, 4), round(ll, 4)


def bilan(archive):
    """Calibration sur les matchs réglés : taux annoncé contre taux observé, comparés à la simple moyenne de la division."""
    sortie = {"matchs_regles": 0, "familles": {}}
    paires = defaultdict(list)       # (genre, cote) -> [(p, gagné)]
    paires_base = defaultdict(list)
    for e in archive.values():
        if not e.get("reglement"):
            continue
        sortie["matchs_regles"] += 1
        prev, regl, base = e["previsions"], e["reglement"], e.get("base_ligue", {})
        for genre in ("corners", "cartons"):
            if genre not in regl:
                continue
            mu_b = base.get(genre)
            for cote, mu_p in (("total", None), ("domicile", None), ("exterieur", None)):
                for l, gagne in (regl[genre].get(cote) or {}).items():
                    paires[(genre, cote)].append((prev[genre][cote][l], 1.0 if gagne else 0.0))
                    if mu_b:
                        mu = mu_b[0] + mu_b[1] if cote == "total" else mu_b[0] if cote == "domicile" else mu_b[1]
                        p = PARAMETRES[genre]
                        alpha = p["alpha_total"] if cote == "total" else p["alpha_equipe"]
                        paires_base[(genre, cote)].append((proba_plus_de(mu, alpha, float(l)), 1.0 if gagne else 0.0))
        if "rouge" in regl:
            paires[("rouge", "match")].append((prev["rouge"]["oui"], 1.0 if regl["rouge"]["oui"] else 0.0))
    for (genre, cote), pr in sorted(paires.items()):
        br, ll = _brier_logloss(pr)
        bb, lb = _brier_logloss(paires_base.get((genre, cote), []))
        sortie["familles"][f"{genre}_{cote}"] = {
            "lignes_evaluees": len(pr), "proba_moyenne_annoncee": round(sum(p for p, _ in pr) / len(pr), 4),
            "taux_observe": round(sum(o for _, o in pr) / len(pr), 4), "brier": br, "logloss": ll,
            "logloss_moyenne_division_seule": lb}
    return sortie


# ------------------------------------------------------------------------------------------------------------------
def main(aujourdhui=None):
    saison, matchs = charge_matchs_saison(DOSSIER_NORMALISE)
    if not matchs:
        print("[corners_cartons] aucune donnée Football-Data : rien à produire.")
        return 0
    aujourdhui = aujourdhui or datetime.datetime.now(datetime.timezone.utc).date()
    modeles, div_rouge, pool_rouge = construit_modeles(matchs)
    idx_comp, idx_eq = construit_index(_lire(FICHIER_CORRESPONDANCES, {}))
    archive = _lire(FICHIER_ARCHIVE, {}) or {}

    # --- règlement des prévisions déjà archivées (Football-Data publie avec 1 à 4 jours de retard)
    joues = defaultdict(list)
    for m in matchs:
        joues[(m["competition_code"], m["home_team"], m["away_team"])].append(m)
    nb_regles = 0
    for e in archive.values():
        if e.get("reglement"):
            continue
        d0 = _date(e.get("date"))
        for m in joues.get((e["division"], e["nom_fd_domicile"], e["nom_fd_exterieur"]), []):
            dm = _date(m["date"])
            if d0 and dm and abs((dm - d0).days) <= 1:
                regl = regle_prevision(e["previsions"], observations(m))
                if regl:
                    e["reglement"], e["date_reelle"] = regl, m["date"]
                    nb_regles += 1
                break

    # --- prévisions des matchs à venir (signaux du pré-calcul), mises à jour tant que le match n'est pas réglé
    signaux = (_lire(FICHIER_PRECALCUL, {}) or {}).get("signaux", [])
    maintenant = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    liste, refus = [], defaultdict(int)
    for s in signaux:
        if s.get("score") or not s.get("match_id"):
            continue
        d = _date(s.get("date"))
        if not d or d < aujourdhui:
            continue
        eq = trouve_equipes(s.get("competition"), s.get("domicile"), s.get("exterieur"), idx_comp, idx_eq)
        if not eq:
            refus["equipes_non_reliees_a_football_data"] += 1
            continue
        div, nd, ne = eq
        if any(abs((_date(m["date"]) - d).days) <= 1 for m in joues.get((div, nd, ne), [])):
            refus["deja_joue_dans_football_data"] += 1      # jamais de prévision avec le résultat sous les yeux
            continue
        prev, raison = prevoit_match(modeles, div_rouge, pool_rouge, div, nd, ne)
        if prev is None:
            refus[raison] += 1
            continue
        fiche = {"match_id": s["match_id"], "date": s["date"], "heure": s.get("heure_cameroun") or s.get("heure"),
                 "competition": " ".join(str(s.get("competition") or "").split()), "division": div,
                 "domicile": s["domicile"], "exterieur": s["exterieur"], "nom_fd_domicile": nd, "nom_fd_exterieur": ne,
                 "previsions": prev["previsions"], "base_ligue": prev["base_ligue"]}
        cotes = cotes_du_match(s.get("cotes_corners_cartons"), prev["previsions"])
        if cotes:
            fiche["cotes"] = cotes
            fiche["cotes_prises_le"] = s.get("prepared_at")
        liste.append(fiche)
        ancien = archive.get(s["match_id"])
        if not (ancien and ancien.get("reglement")):
            archive[s["match_id"]] = {**fiche, "prevu_le": maintenant}

    liste.sort(key=lambda f: (f["date"], f.get("heure") or "", f["competition"]))
    doc = {"version": VERSION, "genere_le": maintenant, "saison_football_data": saison,
           "matchs_football_data_utilises": len(matchs),
           "parametres": {g: {k: v for k, v in PARAMETRES[g].items() if k.startswith(("k", "c", "alpha"))} for g in PARAMETRES},
           "definition_cartons": "jaunes + rouges (un rouge compte pour un carton)",
           "note": "Cotes BetPawa affichées à titre d'information, quand BetPawa publie un marché équivalent. Aucune espérance de gain, "
                   "aucun pari retenu : le modèle n'a pas encore été comparé au marché.",
           "matchs_avec_cotes": sum(1 for f in liste if f.get("cotes")),
           "refus": dict(refus), "bilan": bilan(archive), "matchs": liste}
    _ecrire(FICHIER_SORTIE, doc)
    _ecrire(FICHIER_ARCHIVE, archive)
    print(f"[corners_cartons] {len(liste)} matchs prévus, {sum(refus.values())} écartés {dict(refus)}, "
          f"{nb_regles} réglés ce run, {doc['bilan']['matchs_regles']} réglés au total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
