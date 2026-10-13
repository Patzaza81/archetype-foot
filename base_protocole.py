"""base_protocole.py -- couche BASE / SUPER BASE, protocole v4 (docs/PROTOCOLE_BASE.md).

LECTURE SEULE. Ce module ne modifie ni les moteurs (V2.6.10, V3), ni le Journal, ni les indices, ni les fichiers du
pipeline. Il lit les archives à un état Git donné (par défaut `origin/main`) et n'écrit que dans `data/base/`.

Usage :
    python base_protocole.py                      # état courant (lit origin/main), écrit data/base/
    python base_protocole.py --ref <commit>       # même chose à un état Git précis
    python base_protocole.py --reproduction       # chiffres de départ du § 10 (avant le 13/10/2026)
    python base_protocole.py --simulation         # tableau du § 9.5 (200 000 tirages par ligne)

Chaque règle porte le numéro de section du protocole qui la fixe.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np

VERSION_PROTOCOLE = 4

# --- § 2, § 3 : hypothèse et tranches (fixées en v1, inchangées) -------------------------------------------------------
H1_MIN, H1_MAX = 1.27, 1.39
TRANCHES_INFO = {"T-1": (1.20, 1.26), "H1-a": (1.27, 1.33), "H1-b": (1.34, 1.39), "T+1": (1.40, 1.46)}
DEBUT_TEST = dt.datetime(2026, 10, 13, tzinfo=dt.timezone.utc)

# --- § 4.3 : résultats manquants ----------------------------------------------------------------------------------------
DELAI_REGLEMENT = dt.timedelta(days=7)
STATUTS_ANNULE = {"REP", "ANL"}
STATUT_SUSPENDU = "SUS"

# --- § 9 : décisions ----------------------------------------------------------------------------------------------------
SUIVI_MIN_MATCHS, SUIVI_MIN_JOURS = 150, 21
POINTS_DE_CONTROLE = {"C1": (300, 20), "C2": (600, 40)}
ALPHA_UNILATERAL_B0 = 0.0015          # 99,7 % bilatéral (§ 9.3, v4)
ALPHA_UNILATERAL_EXPLO = 0.025        # 95 % bilatéral, affichage (§ 9.4)
PART_MAX_SANS_RESULTAT = 0.05
RISQUE_CIBLE = 0.005
TIRAGES_BOOTSTRAP = 100_000
GRAINE = 20261013
SIMULATIONS_CONTROLE = 200_000

MARCHE_V3 = "under_3_5"
MARCHE_V2 = "over_under_total_3.5_under"
MIN_MATCHS_JOURNAL = 5                # règle d'entrée du Journal (journal_rentabilite.MIN_MATCHS_EQUIPE)

SORTIE = Path("data/base")
FICHIER_ETAT = SORTIE / "etat.json"
FICHIER_EMPREINTES = SORTIE / "empreintes.jsonl"
FICHIER_CONTROLES = SORTIE / "points_de_controle.json"
FICHIER_SIMULATION = SORTIE / "simulation.json"


# =======================================================================================================================
# Lois de Student et bêta sans scipy (le runner du pipeline n'installe pas scipy ; numpy vient avec pandas)
# =======================================================================================================================

def _betacf(a: float, b: float, x: float) -> float:
    """Fraction continue de la fonction bêta incomplète (méthode de Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 10_000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def beta_inc(a: float, b: float, x: float) -> float:
    """Fonction bêta incomplète régularisée I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(ln) * _betacf(a, b, x) / a
    return 1.0 - math.exp(ln) * _betacf(b, a, 1.0 - x) / b


def beta_ppf(q: float, a: float, b: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if beta_inc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def t_cdf(t: float, df: float) -> float:
    p = 0.5 * beta_inc(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - p if t > 0 else p


def t_ppf(q: float, df: float) -> float:
    """Quantile de la loi de Student (bissection sur la fonction de répartition)."""
    if q == 0.5:
        return 0.0
    lo, hi = (0.0, 1.0) if q > 0.5 else (-1.0, 0.0)
    while (t_cdf(hi, df) < q) if q > 0.5 else (t_cdf(lo, df) > q):
        if q > 0.5:
            hi *= 2
        else:
            lo *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# =======================================================================================================================
# Lecture des archives (à un état Git, ou dans un dossier pour les tests)
# =======================================================================================================================

class Source:
    """Lit les fichiers du dépôt. `ref` = état Git (ex. « origin/main ») ; `racine` = dossier (tests)."""

    def __init__(self, ref: str | None = "origin/main", racine: str | Path = "."):
        self.ref, self.racine = ref, Path(racine)

    def _git(self, *args: str) -> bytes:
        return subprocess.run(["git", "-C", str(self.racine), *args], capture_output=True, check=True).stdout

    def lire(self, chemin: str) -> bytes | None:
        if self.ref is None:
            p = self.racine / chemin
            return p.read_bytes() if p.exists() else None
        try:
            return self._git("show", f"{self.ref}:{chemin}")
        except subprocess.CalledProcessError:
            return None

    def lister(self, dossier: str, motif: str) -> list[str]:
        if self.ref is None:
            return sorted(str(p.relative_to(self.racine)) for p in (self.racine / dossier).glob(motif))
        try:
            noms = self._git("ls-tree", "--name-only", f"{self.ref}:{dossier}").decode().split()
        except subprocess.CalledProcessError:
            return []
        rx = re.compile("^" + re.escape(motif).replace(r"\*", ".*") + "$")
        return sorted(f"{dossier}/{n}" for n in noms if rx.match(n))

    def json(self, chemin: str, defaut: Any = None) -> Any:
        b = self.lire(chemin)
        if b is None:
            return defaut
        if chemin.endswith(".gz"):
            b = gzip.decompress(b)
        try:
            return json.loads(b.decode("utf-8"))
        except ValueError:
            return defaut

    def commit(self) -> str | None:
        if self.ref is None:
            return None
        try:
            return self._git("rev-parse", self.ref).decode().strip()
        except subprocess.CalledProcessError:
            return None


def instant(x: Any) -> dt.datetime | None:
    if not x:
        return None
    try:
        t = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def nom_normalise(x: Any) -> str:
    """Même règle que generateur_tickets._nom_normalise (rapprochement par noms, § 6.2)."""
    texte = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


# =======================================================================================================================
# § 4 : admission, doublons, résultats manquants
# =======================================================================================================================

@dataclass
class Match:
    match_id: str
    date: str
    jour: str                       # jour UTC du coup d'envoi (unité du bootstrap)
    coup_d_envoi: dt.datetime
    pris_le: dt.datetime
    cote: float
    cote_plus: float | None
    domicile: str
    exterieur: str
    competition: str
    score: tuple[int, int] | None
    statut: str                     # § 4.3 : REGLE, NON_REGLE, ANNULE, SUSPENDU, RESULTAT_MANQUANT
    brut: Mapping[str, Any] = field(repr=False, default_factory=dict)

    @property
    def gagne(self) -> bool:
        return self.score is not None and self.score[0] + self.score[1] < 3.5

    @property
    def gain(self) -> float:
        return self.cote - 1.0 if self.gagne else -1.0


def cote_moins(m: Mapping[str, Any]) -> tuple[Any, Any]:
    ou = ((m.get("cotes_betpawa") or {}).get("over_under_3.5") or {})
    return ou.get("moins"), ou.get("plus")


def lit_score(m: Mapping[str, Any]) -> tuple[tuple[int, int] | None, bool]:
    """(score, mal_forme). Un score absent n'est pas une erreur ; un score mal formé en est une."""
    s = m.get("score") or {}
    h, a = s.get("buts_dom"), s.get("buts_ext")
    if h is None and a is None:
        return None, False
    try:
        h, a = int(h), int(a)
    except (TypeError, ValueError):
        return None, True
    if h < 0 or a < 0:
        return None, True
    return (h, a), False


def statuts_source(historique: Any) -> dict[str, str]:
    """Statut Matchendirect lu dans le champ « heure » de historique_pronostics.json (§ 4.1)."""
    out: dict[str, str] = {}
    for jour in historique if isinstance(historique, list) else []:
        for m in (jour or {}).get("matchs") or []:
            h = str(m.get("heure") or "").strip().upper()
            if h in STATUTS_ANNULE | {STATUT_SUSPENDU} and m.get("match_id"):
                out[m["match_id"]] = h
    return out


def statut_resultat(score, statut_src: str | None, coup_d_envoi: dt.datetime, maintenant: dt.datetime) -> str:
    """§ 4.3. Une absence de résultat n'est jamais une perte."""
    if score is not None:
        return "REGLE"
    if statut_src in STATUTS_ANNULE:
        return "ANNULE"
    if statut_src == STATUT_SUSPENDU:
        return "SUSPENDU"
    if maintenant - coup_d_envoi < DELAI_REGLEMENT:
        return "NON_REGLE"
    return "RESULTAT_MANQUANT"


@dataclass
class Admission:
    matchs: list[Match]
    exclusions: dict[str, list[str]]
    doublons: list[dict[str, Any]]
    hors_univers: int


def admet(fichiers: Mapping[str, Mapping[str, Mapping[str, Any]]], statuts_src: Mapping[str, str],
          maintenant: dt.datetime, modifies: set[str] = frozenset()) -> Admission:
    """§ 4.2 : règles d'admission dans l'ordre, puis un relevé par match (le plus récent avant le coup d'envoi).
    `fichiers` : {nom de fichier : {match_id : fiche}}. Seuls les matchs dont la cote est dans H1 sont gardés."""
    exclusions: dict[str, list[str]] = defaultdict(list)
    candidats: dict[str, list[Match]] = defaultdict(list)
    hors_univers = 0
    for nom in sorted(fichiers):
        for mid, m in (fichiers[nom] or {}).items():
            o, op = cote_moins(m)
            if o in (None, ""):
                hors_univers += 1
                continue
            try:
                cote = round(float(o), 2)
                cote_plus = float(op) if op not in (None, "") else None
            except (TypeError, ValueError):
                exclusions["ERREUR_COLLECTE"].append(mid)
                continue
            if cote <= 1.0:
                exclusions["ERREUR_COLLECTE"].append(mid)
                continue
            if not (H1_MIN <= cote <= H1_MAX):
                continue
            ko, pris = instant(m.get("coup_d_envoi_utc")), instant((m.get("run") or {}).get("pris_le"))
            if ko is None or pris is None:
                exclusions["HORODATAGE_ABSENT"].append(mid)
                continue
            if pris >= ko:
                exclusions["RELEVE_APRES_COUP_D_ENVOI"].append(mid)
                continue
            score, mal_forme = lit_score(m)
            if mal_forme:
                exclusions["ERREUR_COLLECTE"].append(mid)
                continue
            if mid in modifies:
                exclusions["MODIFICATION_DETECTEE"].append(mid)
                continue
            candidats[mid].append(Match(
                match_id=mid, date=str(m.get("date") or ""), jour=ko.date().isoformat(), coup_d_envoi=ko,
                pris_le=pris, cote=cote, cote_plus=cote_plus, domicile=str(m.get("domicile") or ""),
                exterieur=str(m.get("exterieur") or ""), competition=str(m.get("competition") or ""),
                score=score, statut="", brut=m))
    matchs, doublons = [], []
    for mid, liste in candidats.items():
        scores = {x.score for x in liste if x.score is not None}
        if len(scores) > 1:                                   # même match, deux scores différents
            exclusions["ERREUR_COLLECTE"].append(mid)
            continue
        liste.sort(key=lambda x: x.pris_le)
        garde = liste[-1]
        if garde.score is None and scores:
            garde.score = next(iter(scores))
        if len(liste) > 1:
            doublons.append({"match_id": mid, "releves": len(liste), "garde": garde.pris_le.isoformat()})
        garde.statut = statut_resultat(garde.score, statuts_src.get(mid), garde.coup_d_envoi, maintenant)
        matchs.append(garde)
    matchs.sort(key=lambda x: (x.coup_d_envoi, x.match_id))
    return Admission(matchs, {k: sorted(set(v)) for k, v in exclusions.items()}, doublons, hors_univers)


# =======================================================================================================================
# § 5 : traçabilité (empreintes par match, première observation reconstruite depuis Git)
# =======================================================================================================================

def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def empreintes(m: Mapping[str, Any]) -> tuple[str, str | None]:
    """(avant-match, score). L'empreinte score porte sur le RÉSULTAT (buts_dom, buts_ext) seulement : le pipeline
    réécrit l'horodatage `ecrit_le` sans changer le score (120 cas constatés le 13/10), ce n'est pas une modification
    du résultat. None tant qu'aucun score n'est écrit."""
    avant = _sha({k: v for k, v in m.items() if k != "score"})
    s = m.get("score") or {}
    return avant, (_sha([s.get("buts_dom"), s.get("buts_ext")]) if s.get("buts_dom") is not None else None)


def lit_registre(chemin: Path = FICHIER_EMPREINTES) -> list[dict[str, Any]]:
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def ajoute_registre(lignes: Iterable[dict[str, Any]], chemin: Path = FICHIER_EMPREINTES) -> int:
    """Registre en ajout seul : une ligne n'est jamais modifiée ni supprimée."""
    lignes = list(lignes)
    if lignes:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("a", encoding="utf-8") as f:
            for l in lignes:
                f.write(json.dumps(l, ensure_ascii=False, sort_keys=True) + "\n")
    return len(lignes)


def references(registre: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """(fichier, match_id, type) -> empreinte de référence (la PREMIÈRE ligne « reference » du registre).
    Le fichier fait partie de la clé : un même match peut figurer dans deux fichiers journaliers (§ 4.2)."""
    out: dict[tuple[str, str, str], str] = {}
    for l in registre:
        if l.get("evenement") == "reference":
            out.setdefault((l.get("fichier", ""), l["match_id"], l["type"]), l["sha256"])
    return out


def versions_git(source: Source, chemin: str) -> list[tuple[str, dt.datetime, Any]]:
    """Toutes les versions d'un fichier dans l'historique de `source.ref`, de la plus ancienne à la plus récente."""
    try:
        log = source._git("log", "--reverse", "--format=%H %cI", source.ref or "HEAD", "--", chemin).decode().split("\n")
    except subprocess.CalledProcessError:
        return []
    out = []
    for ligne in filter(None, log):
        h, d = ligne.split(" ", 1)
        try:
            b = source._git("show", f"{h}:{chemin}")
            out.append((h, instant(d), json.loads(gzip.decompress(b).decode("utf-8"))))
        except (subprocess.CalledProcessError, OSError, ValueError):
            continue
    return out


def premieres_observations(versions: list[tuple[str, dt.datetime, Any]], fichier: str = "") -> list[dict[str, Any]]:
    """§ 5.2 : avant-match = premier commit postérieur au coup d'envoi ; score = premier commit où il apparaît."""
    out, vus = [], set()
    for h, date, contenu in versions:
        for mid, m in (contenu or {}).items():
            ko = instant(m.get("coup_d_envoi_utc"))
            avant, score = empreintes(m)
            if ko is not None and date is not None and date > ko and (mid, "avant_match") not in vus:
                vus.add((mid, "avant_match"))
                out.append({"evenement": "reference", "fichier": fichier, "match_id": mid, "type": "avant_match",
                            "sha256": avant, "commit": h, "date_commit": date.isoformat()})
            if score is not None and (mid, "score") not in vus:
                vus.add((mid, "score"))
                out.append({"evenement": "reference", "fichier": fichier, "match_id": mid, "type": "score",
                            "sha256": score, "commit": h, "date_commit": date.isoformat() if date else None})
    return out


def detecte(fichiers: Mapping[str, Mapping[str, Any]], refs: Mapping[tuple[str, str, str], str],
            maintenant: dt.datetime) -> list[dict[str, Any]]:
    """§ 5.3 : empreinte actuelle différente de la référence -> événement MODIFICATION_DETECTEE."""
    out = []
    for nom, contenu in fichiers.items():
        for mid, m in (contenu or {}).items():
            avant, score = empreintes(m)
            for typ, sha in (("avant_match", avant), ("score", score)):
                ref = refs.get((nom, mid, typ))
                if ref is not None and sha != ref:
                    out.append({"evenement": "MODIFICATION_DETECTEE", "match_id": mid, "type": typ,
                                "sha256_reference": ref, "sha256_actuel": sha, "fichier": nom,
                                "detecte_le": maintenant.isoformat()})
    return out


# =======================================================================================================================
# § 6 : configurations B0 à B4 et populations admissibles A(x)
# =======================================================================================================================

@dataclass
class Filtre:
    code: str
    admissible: Callable[[Match], bool]
    retenu: Callable[[Match], bool]


def index_v3(source: Source) -> dict[str, tuple[float, dt.datetime]]:
    """match_id -> (probabilité V3 de « moins de 3,5 », heure du calcul), depuis data/v3/journal/*.json."""
    out: dict[str, tuple[float, dt.datetime]] = {}
    for chemin in source.lister("data/v3/journal", "*.json"):
        for mid, fiche in (source.json(chemin, {}) or {}).items():
            t = instant(fiche.get("calcule_le"))
            for c in (fiche.get("selections") or []) + (fiche.get("candidats") or []) + (fiche.get("apercu_non_calibre") or []):
                if c.get("marche") == MARCHE_V3 and c.get("probabilite") is not None and t is not None:
                    out[mid] = (float(c["probabilite"]), t)
    return out


def index_journal(archive_selection: Any) -> list[tuple[str, str, str, dt.datetime]]:
    """Paris « Match à moins de 3,5 buts » du Journal vus par le générateur : (date, domicile, extérieur, vu_le)."""
    out = []
    for e in (archive_selection or {}).get("executions") or []:
        t = instant(e.get("genere_le"))
        for p in e.get("paris") or []:
            if str(p.get("source") or "").lower() == "journal" and "moins de 3,5" in str(p.get("marche") or "").lower():
                out.append((str(p.get("date") or ""), nom_normalise(p.get("domicile")), nom_normalise(p.get("exterieur")), t))
    return out


def rapproche_journal(m: Match, paris: list[tuple[str, str, str, dt.datetime]]) -> bool:
    """§ 6.2 : même date + mêmes noms normalisés, pari vu avant le coup d'envoi. Équipes inversées = autre match."""
    cle = (m.date, nom_normalise(m.domicile), nom_normalise(m.exterieur))
    return any(p[:3] == cle and p[3] is not None and p[3] < m.coup_d_envoi for p in paris)


def historique_journal(resultats: Iterable[Mapping[str, Any]], nom_ligue: Callable[[str], str]) -> dict[tuple[str, str], list[str]]:
    """(équipe normalisée, ligue) -> dates des matchs terminés de la base du Journal."""
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in resultats:
        lg = r.get("ligue") or ""
        for eq in (r.get("domicile"), r.get("exterieur")):
            out[(nom_normalise(eq), lg)].append(str(r.get("date") or ""))
    return out


def nb_matchs_lieu(m: Match) -> int | None:
    from moteur_v3.model import _latest
    d, e = m.brut.get("equipe_dom"), m.brut.get("equipe_ext")
    if not isinstance(d, Mapping) or not isinstance(e, Mapping) or "matchs" not in d or "matchs" not in e:
        return None
    return min(len(_latest(d.get("matchs") or [], True)), len(_latest(e.get("matchs") or [], False)))


def choix_v2(m: Match) -> tuple[bool, bool]:
    """(V2.6.10 a produit un choix de production, ce choix contient « moins de 3,5 »)."""
    prod = m.brut.get("moteur_en_production") or {}
    if "2_6_10" not in str(prod.get("moteur") or "") or not prod.get("choix"):
        return False, False
    return True, any(MARCHE_V2 in (str(c.get("marche")), str(c.get("marche_moteur")))
                     for c in prod["choix"].values() if isinstance(c, Mapping))


def filtres(v3: Mapping[str, tuple[float, dt.datetime]], paris_journal: list, hist_journal: Mapping, nom_ligue) -> list[Filtre]:
    def v3_adm(m):
        return m.match_id in v3 and v3[m.match_id][1] < m.coup_d_envoi

    def j_adm(m):
        """Le Journal suit UNE équipe : il peut se prononcer dès qu'une des deux a 5 matchs antérieurs du même
        championnat dans sa base. Un pari effectivement proposé est toujours admissible (jamais exclu par cette règle)."""
        lg = nom_ligue(m.competition)
        return rapproche_journal(m, paris_journal) or any(
            sum(1 for d in hist_journal.get((nom_normalise(eq), lg), []) if d < m.date) >= MIN_MATCHS_JOURNAL
            for eq in (m.domicile, m.exterieur))

    return [
        Filtre("B1", v3_adm, lambda m: v3_adm(m) and v3[m.match_id][0] >= 1.0 / m.cote),
        Filtre("B2", j_adm, lambda m: rapproche_journal(m, paris_journal)),
        Filtre("B3", lambda m: choix_v2(m)[0], lambda m: choix_v2(m)[1]),
        Filtre("B4", lambda m: nb_matchs_lieu(m) is not None, lambda m: (nb_matchs_lieu(m) or 0) >= 3),
    ]


# =======================================================================================================================
# § 7 : mesures et intervalles
# =======================================================================================================================

def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d


def par_jour(matchs: list[Match], jours: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """(somme des gains, nombre de paris) par jour, dans l'ordre de `jours` (0 si le jour n'a aucun pari)."""
    pos = {j: i for i, j in enumerate(jours)}
    s, n = np.zeros(len(jours)), np.zeros(len(jours))
    for m in matchs:
        s[pos[m.jour]] += m.gain
        n[pos[m.jour]] += 1
    return s, n


def student_grappes(s: np.ndarray, n: np.ndarray, alpha_unilateral: float) -> tuple[float, float] | None:
    """Intervalle de Student par grappes (jours) : estimateur ratio, linéarisation, J - 1 degrés de liberté (§ 7)."""
    garde = n > 0
    s, n = s[garde], n[garde]
    k = len(n)
    if k < 2:
        return None
    roi = s.sum() / n.sum()
    u = (s - roi * n) / n.mean()
    se = math.sqrt(u.var(ddof=1) / k)
    q = t_ppf(1 - alpha_unilateral, k - 1)
    return roi - q * se, roi + q * se


def tirages_jours(k: int, b: int, graine: int) -> np.ndarray:
    return np.random.default_rng(graine).integers(0, k, size=(b, k))


def bootstrap_roi(s: np.ndarray, n: np.ndarray, alpha_unilateral: float, idx: np.ndarray) -> tuple[float, float] | None:
    """Bootstrap percentile par jour (§ 7). `idx` : tirages de jours partagés entre configurations (§ 8)."""
    if len(n) < 2 or n.sum() == 0:
        return None
    ns = n[idx].sum(1)
    ok = ns > 0
    roi = s[idx].sum(1)[ok] / ns[ok]
    return float(np.quantile(roi, alpha_unilateral)), float(np.quantile(roi, 1 - alpha_unilateral))


def bootstrap_ecart(s1, n1, s2, n2, alpha_unilateral: float, idx: np.ndarray) -> tuple[float, float] | None:
    a, b = n1[idx].sum(1), n2[idx].sum(1)
    ok = (a > 0) & (b > 0)
    if not ok.any():
        return None
    d = s1[idx].sum(1)[ok] / a[ok] - s2[idx].sum(1)[ok] / b[ok]
    return float(np.quantile(d, alpha_unilateral)), float(np.quantile(d, 1 - alpha_unilateral))


def mesures(matchs: list[Match], jours: list[str], alpha_unilateral: float, idx: np.ndarray | None) -> dict[str, Any]:
    regles = [m for m in matchs if m.statut == "REGLE"]
    n = len(regles)
    out: dict[str, Any] = {"matchs": n, "jours": len({m.jour for m in regles})}
    if n == 0:
        return out
    gagnes = sum(m.gagne for m in regles)
    s, nn = par_jour(regles, jours)
    marges = [1 / m.cote + 1 / m.cote_plus - 1 for m in regles if m.cote_plus]
    out.update({
        "roi": round(float(s.sum() / nn.sum()), 6),
        "reussite": round(gagnes / n, 6),
        "reussite_intervalle_95": [round(x, 6) for x in wilson(gagnes, n)],
        "probabilite_implicite_brute_moyenne": round(sum(1 / m.cote for m in regles) / n, 6),
        "cote_moyenne": round(sum(m.cote for m in regles) / n, 4),
        "marge_marche_moyenne": round(sum(marges) / len(marges), 6) if marges else None,
        "niveau_intervalle": round(1 - 2 * alpha_unilateral, 4),
    })
    st = student_grappes(s, nn, alpha_unilateral)
    out["roi_intervalle_student"] = [round(x, 6) for x in st] if st else None
    if idx is not None:
        bs = bootstrap_roi(s, nn, alpha_unilateral, idx)
        out["roi_intervalle_bootstrap"] = [round(x, 6) for x in bs] if bs else None
    return out


# =======================================================================================================================
# § 9.5 : simulation du risque de VALIDÉ à tort
# =======================================================================================================================

def simule_risque(cotes: np.ndarray, jours: tuple[int, int], alpha_unilateral: float, n_sim: int, graine: int,
                  moyenne_par_jour: float = 19.5, decalage_roi: float = 0.0, sens: str = "valide") -> dict[str, float]:
    """Part des simulations où la règle de Student par grappes conclut à l'un des deux contrôles.
    sens = « valide » (borne basse > 0) ou « defavorable » (borne haute < 0). ROI réel = `decalage_roi`."""
    rng = np.random.default_rng(graine)
    k1, k2 = jours
    succes, fait = 0, 0
    while fait < n_sim:
        b = min(20_000, n_sim - fait)
        n = rng.poisson(moyenne_par_jour, size=(b, k2)).clip(3)
        mx = int(n.max())
        o = rng.choice(cotes, size=(b, k2, mx))
        y = rng.random((b, k2, mx)) < np.clip((1 + decalage_roi) / o, 0, 1)
        s = (np.where(y, o - 1, -1.0) * (np.arange(mx)[None, None, :] < n[..., None])).sum(-1)
        conclut = np.zeros(b, bool)
        for k in (k1, k2):
            ss, nk = s[:, :k], n[:, :k]
            roi = ss.sum(1) / nk.sum(1)
            u = (ss - roi[:, None] * nk) / nk.mean(1)[:, None]
            demi = t_ppf(1 - alpha_unilateral, k - 1) * np.sqrt(u.var(1, ddof=1) / k)
            conclut |= (roi - demi > 0) if sens == "valide" else (roi + demi < 0)
        succes += int(conclut.sum())
        fait += b
    p = succes / n_sim
    lo = beta_ppf(0.025, succes, n_sim - succes + 1) if succes else 0.0
    hi = beta_ppf(0.975, succes + 1, n_sim - succes)
    return {"risque": p, "intervalle_95": [float(lo), float(hi)], "simulations": n_sim}


# =======================================================================================================================
# § 9 : points de contrôle et statuts
# =======================================================================================================================

def fenetre(matchs: list[Match], maintenant: dt.datetime) -> list[Match]:
    """Période de test, matchs joués au moins 7 jours avant le calcul (§ 9.2)."""
    return [m for m in matchs if m.coup_d_envoi >= DEBUT_TEST and maintenant - m.coup_d_envoi >= DELAI_REGLEMENT
            and m.statut != "ANNULE"]


def prefixe(matchs: list[Match], min_matchs: int, min_jours: int) -> list[Match] | None:
    """Premiers jours complets (dans l'ordre) qui atteignent les deux minimums ; None s'ils ne sont pas atteints.
    Rend chaque point de contrôle indépendant du jour où le calcul est lancé."""
    jours = sorted({m.jour for m in matchs})
    pris: list[Match] = []
    for i, j in enumerate(jours, 1):
        pris += [m for m in matchs if m.jour == j]
        if sum(m.statut == "REGLE" for m in pris) >= min_matchs and i >= min_jours:
            return pris
    return None


def statut_b0(mes: dict[str, Any]) -> str:
    st, bs = mes.get("roi_intervalle_student"), mes.get("roi_intervalle_bootstrap")
    if not st or not bs:
        return "NEUTRE"
    if st[0] > 0 and bs[0] > 0:
        return "VALIDE"
    if st[1] < 0 and bs[1] < 0:
        return "DEFAVORABLE"
    return "NEUTRE"


def avec_manquants(matchs: list[Match], gagnes: bool) -> list[Match]:
    """Contrôle de sensibilité (§ 4.3) : SUSPENDU et RESULTAT_MANQUANT comptés tous perdus ou tous gagnés."""
    out = []
    for m in matchs:
        if m.statut in ("SUSPENDU", "RESULTAT_MANQUANT", "NON_REGLE"):
            m = Match(**{**m.__dict__, "score": (0, 0) if gagnes else (4, 0), "statut": "REGLE"})
        out.append(m)
    return out


def evalue_controle(nom: str, pris: list[Match], filtres_: list[Filtre], controles_precedents: list[dict[str, Any]],
                    n_sim: int, b: int) -> dict[str, Any]:
    jours = sorted({m.jour for m in pris})
    idx = tirages_jours(len(jours), b, GRAINE)
    b0 = mesures(pris, jours, ALPHA_UNILATERAL_B0, idx)
    statut = statut_b0(b0)
    sans_resultat = sum(m.statut in ("SUSPENDU", "RESULTAT_MANQUANT") for m in pris)
    part = sans_resultat / len(pris) if pris else 0.0
    sens = {f"manquants_{x}": statut_b0(mesures(avec_manquants(pris, x == "gagnes"), jours, ALPHA_UNILATERAL_B0, idx))
            for x in ("perdus", "gagnes")}
    motifs = []
    if part > PART_MAX_SANS_RESULTAT:
        motifs.append("plus de 5 % sans résultat")
    if len(set(sens.values()) | {statut}) > 1:
        motifs.append("le contrôle de sensibilité change la conclusion")
    regles = [m for m in pris if m.statut == "REGLE"]
    cotes = np.array([m.cote for m in regles])
    k_c1 = next((c["jours"] for c in controles_precedents if c["point"] == "C1"), None)
    jours_sim = (len(jours), max(POINTS_DE_CONTROLE["C2"][1], 2 * len(jours))) if nom == "C1" else (k_c1 or POINTS_DE_CONTROLE["C1"][1], len(jours))
    sim = simule_risque(cotes, jours_sim, ALPHA_UNILATERAL_B0, n_sim, GRAINE,
                        moyenne_par_jour=len(regles) / max(1, len(jours))) if len(cotes) else None
    if sim and sim["intervalle_95"][1] > RISQUE_CIBLE and statut == "VALIDE":
        motifs.append("risque simulé au-dessus de 0,5 %")
    if motifs:
        statut = "NON_CONCLUANT"
    explo = evalue_exploration(pris, jours, filtres_, idx)
    return {"point": nom, "version_protocole": VERSION_PROTOCOLE, "jours": len(jours), "premier_jour": jours[0],
            "dernier_jour": jours[-1], "statut_B0": statut, "motifs_non_concluant": motifs, "B0": b0,
            "sensibilite": sens, "part_sans_resultat": round(part, 6), "simulation": sim, "jours_simules": list(jours_sim),
            "exploration": explo}


def evalue_exploration(pris: list[Match], jours: list[str], filtres_: list[Filtre], idx: np.ndarray,
                       au_controle: bool = True) -> dict[str, Any]:
    """§ 8, § 9.4 : intervalles à 95 %, deux comparaisons, jamais de statut VALIDÉ."""
    regles = [m for m in pris if m.statut == "REGLE"]
    s0, n0 = par_jour(regles, jours)
    out = {}
    for f in filtres_:
        adm = [m for m in regles if f.admissible(m)]
        ret = [m for m in adm if f.retenu(m)]
        non = [m for m in adm if not f.retenu(m)]
        mes = mesures(ret, jours, ALPHA_UNILATERAL_EXPLO, idx)
        sr, nr = par_jour(ret, jours)
        sn, nn = par_jour(non, jours)
        gen = bootstrap_ecart(sr, nr, s0, n0, ALPHA_UNILATERAL_EXPLO, idx) if ret else None
        pop = bootstrap_ecart(sr, nr, sn, nn, ALPHA_UNILATERAL_EXPLO, idx) if ret and non else None
        e_gen = (sr.sum() / nr.sum() - s0.sum() / n0.sum()) if ret and n0.sum() else None
        e_pop = (sr.sum() / nr.sum() - sn.sum() / nn.sum()) if ret and non else None
        if mes["matchs"] < SUIVI_MIN_MATCHS or mes["jours"] < SUIVI_MIN_JOURS:
            statut = "NON_EVALUE"
        elif not au_controle:
            statut = "EN_COURS"
        elif (mes.get("roi") or 0) > 0 and (e_gen or 0) > 0 and (e_pop or 0) > 0:
            statut = "SIGNAL_EXPLORATOIRE"
        else:
            statut = "SANS_SIGNAL"
        out[f.code] = {"statut": statut, "admissibles": len(adm), "retenus": mes, "non_retenus": len(non),
                       "ecart_general": None if e_gen is None else round(float(e_gen), 6),
                       "ecart_general_intervalle_95": gen,
                       "ecart_population_egale": None if e_pop is None else round(float(e_pop), 6),
                       "ecart_population_egale_intervalle_95": pop}
    return out


def statut_courant(controles: list[dict[str, Any]], fen: list[Match]) -> str:
    """Un statut ne change qu'à un point de contrôle (§ 9.2)."""
    if controles:
        return controles[-1]["statut_B0"]
    regles = [m for m in fen if m.statut == "REGLE"]
    if len(regles) < SUIVI_MIN_MATCHS or len({m.jour for m in regles}) < SUIVI_MIN_JOURS:
        return "NON_EVALUE"
    return "EN_COURS"


# =======================================================================================================================
# Exécution
# =======================================================================================================================

def charge(source: Source, maintenant: dt.datetime, modifies: set[str] = frozenset()):
    fichiers = {c: source.json(c, {}) for c in source.lister("data/archive_test", "*.json.gz")}
    adm = admet(fichiers, statuts_source(source.json("historique_pronostics.json", [])), maintenant, modifies)
    return fichiers, adm


def resume_admission(adm: Admission, matchs: list[Match]) -> dict[str, Any]:
    st = defaultdict(list)
    for m in matchs:
        st[m.statut].append(m.match_id)
    return {"statuts": {k: len(v) for k, v in sorted(st.items())},
            "liste_sans_resultat": {k: v for k, v in st.items() if k != "REGLE"},
            "exclusions": {k: len(v) for k, v in adm.exclusions.items()}, "liste_exclusions": adm.exclusions,
            "doublons": adm.doublons}


def construit_filtres(source: Source) -> list[Filtre]:
    """La base du Journal est lue au même état Git que l'archive (copie temporaire), jamais dans l'arbre de travail."""
    import tempfile
    import journal_rentabilite as jr
    resultats: list = []
    with tempfile.TemporaryDirectory() as tmp:
        chemins = {}
        for nom in ("data/echantillon_betpawa_501.json", "historique_pronostics.json"):
            contenu = source.lire(nom)
            chemins[nom] = Path(tmp) / Path(nom).name
            chemins[nom].write_bytes(contenu if contenu is not None else b"null")
        try:
            resultats = jr.charge_tous_resultats(str(chemins["data/echantillon_betpawa_501.json"]),
                                                 str(chemins["historique_pronostics.json"]))
        except Exception:  # noqa: BLE001 -- sans base du Journal, B2 n'a aucun match admissible (jamais deviné)
            resultats = []
    return filtres(index_v3(source), index_journal(source.json("data/selection_generateur_historique.json", {})),
                   historique_journal(resultats, jr.nom_ligue), jr.nom_ligue)


def reproduction(source: Source, maintenant: dt.datetime, b: int = TIRAGES_BOOTSTRAP) -> dict[str, Any]:
    """§ 10 : état de départ (coup d'envoi avant le 13/10/2026), description seulement."""
    _, adm = charge(source, maintenant)
    pre = [m for m in adm.matchs if m.coup_d_envoi < DEBUT_TEST]
    regles = [m for m in pre if m.statut == "REGLE"]
    jours = sorted({m.jour for m in regles})
    idx = tirages_jours(len(jours), b, GRAINE)
    out = {"B0": mesures(regles, jours, 0.025, idx),
           "tranches": {k: mesures([m for m in regles if lo <= m.cote <= hi], jours, 0.025, idx)
                        for k, (lo, hi) in TRANCHES_INFO.items() if lo >= H1_MIN and hi <= H1_MAX},
           "admission": resume_admission(adm, pre)}
    out["exploration"] = evalue_exploration(regles, jours, construit_filtres(source), idx, au_controle=False)
    return out


def execute(source: Source, maintenant: dt.datetime, sortie: Path = SORTIE, n_sim: int = SIMULATIONS_CONTROLE,
            b: int = TIRAGES_BOOTSTRAP, reconstruire_empreintes: bool = True) -> dict[str, Any]:
    sortie.mkdir(parents=True, exist_ok=True)
    reg_path, ctl_path = sortie / FICHIER_EMPREINTES.name, sortie / FICHIER_CONTROLES.name
    fichiers = {c: source.json(c, {}) for c in source.lister("data/archive_test", "*.json.gz")}
    # § 5 : références depuis l'historique Git (uniquement ce qui n'est pas déjà au registre), puis détection
    registre = lit_registre(reg_path)
    refs = references(registre)
    if reconstruire_empreintes and source.ref is not None:
        nouvelles = []
        for chemin in fichiers:
            for l in premieres_observations(versions_git(source, chemin), chemin):
                if (chemin, l["match_id"], l["type"]) not in refs:
                    refs[(chemin, l["match_id"], l["type"])] = l["sha256"]
                    nouvelles.append(l)
        ajoute_registre(nouvelles, reg_path)
    evenements = detecte(fichiers, refs, maintenant)
    deja = {(l["match_id"], l["type"], l.get("sha256_actuel")) for l in registre if l.get("evenement") == "MODIFICATION_DETECTEE"}
    ajoute_registre([e for e in evenements if (e["match_id"], e["type"], e["sha256_actuel"]) not in deja], reg_path)
    modifies = {e["match_id"] for e in evenements}
    for l in lit_registre(reg_path):
        if l.get("evenement") == "MODIFICATION_DETECTEE":
            modifies.add(l["match_id"])
    adm = admet(fichiers, statuts_source(source.json("historique_pronostics.json", [])), maintenant, modifies)
    fen = fenetre(adm.matchs, maintenant)
    filtres_ = construit_filtres(source)
    controles = json.loads(ctl_path.read_text(encoding="utf-8")) if ctl_path.exists() else []
    for nom, (mn, mj) in POINTS_DE_CONTROLE.items():
        if any(c["point"] == nom for c in controles):
            continue
        pris = prefixe(fen, mn, mj)
        if pris is None:
            break
        c = evalue_controle(nom, pris, filtres_, controles, n_sim, b)
        c["calcule_le"], c["commit_source"] = maintenant.isoformat(), source.commit()
        controles.append(c)                                   # ajout seul
        ctl_path.write_text(json.dumps(controles, ensure_ascii=False, indent=1), encoding="utf-8")
    jours = sorted({m.jour for m in fen if m.statut == "REGLE"})
    idx = tirages_jours(len(jours), b, GRAINE) if jours else None
    etat = {
        "version_protocole": VERSION_PROTOCOLE, "calcule_le": maintenant.isoformat(), "commit_source": source.commit(),
        "hypothese": {"marche": "Moins de 3,5 buts", "cote_min": H1_MIN, "cote_max": H1_MAX,
                      "debut_test": DEBUT_TEST.isoformat()},
        "statut_B0": statut_courant(controles, fen),
        "points_de_controle_atteints": [c["point"] for c in controles],
        "B0_fenetre": mesures(fen, jours, ALPHA_UNILATERAL_B0, idx) if jours else {"matchs": 0, "jours": 0},
        "tranches_information": {k: mesures([m for m in fen if lo <= m.cote <= hi], jours, ALPHA_UNILATERAL_EXPLO, idx)
                                 for k, (lo, hi) in TRANCHES_INFO.items() if jours and lo >= H1_MIN and hi <= H1_MAX},
        "exploration": evalue_exploration(fen, jours, filtres_, idx, au_controle=False) if jours else {},
        "admission": resume_admission(adm, [m for m in adm.matchs if m.coup_d_envoi >= DEBUT_TEST]),
        "modifications_detectees": sorted(modifies),
        "avertissement": "Historique seulement. Un statut VALIDÉ n'est pas une garantie ; NEUTRE veut dire « avantage non démontré ».",
    }
    (sortie / FICHIER_ETAT.name).write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    return etat


# =======================================================================================================================
# Passage automatique (tâche planifiée) : détecte les seuils C1/C2 et commite data/base/ sur la branche dédiée
# =======================================================================================================================

BRANCHE_BASE = "base-implementation"
BRANCHES_INTERDITES = {"main", "master"}


class RefusAuto(RuntimeError):
    pass


def _g(depot: Path, *args: str, ok: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", "-C", str(depot), *args], capture_output=True, text=True)
    if r.returncode and not ok:
        raise RefusAuto(f"git {' '.join(args)} : {r.stderr.strip()[:300]}")
    return r


def _contenu_utile(chemin: Path) -> Any:
    """Contenu d'un fichier de sortie sans son horodatage de calcul : un passage qui ne change rien ne crée pas de commit."""
    if not chemin.exists():
        return None
    if chemin.suffix != ".json":
        return chemin.read_text(encoding="utf-8")
    d = json.loads(chemin.read_text(encoding="utf-8"))
    if isinstance(d, dict):
        d = {k: v for k, v in d.items() if k != "calcule_le"}
    return d


def passage_automatique(depot: str | Path = ".", branche: str = BRANCHE_BASE, ref_donnees: str = "origin/main",
                        maintenant: dt.datetime | None = None, tentatives: int = 3, n_sim: int = SIMULATIONS_CONTROLE,
                        b: int = TIRAGES_BOOTSTRAP, profondeur: int = 1000) -> dict[str, Any]:
    """Un passage complet, sûr à relancer autant de fois qu'on veut :
    1. se met exactement sur `origin/<branche>` (refuse main, refuse un arbre de travail modifié) ;
    2. lit les données de `origin/main` et déclenche C1 / C2 si et seulement si leur seuil est atteint (§ 9.2) ;
    3. commite UNIQUEMENT data/base/ et pousse sur `<branche>`. Push refusé (passage concurrent) : on repart de la
       version distante et on recommence ; un point de contrôle déjà présent n'est jamais recalculé (ajout seul)."""
    depot = Path(depot)
    if branche in BRANCHES_INTERDITES:
        raise RefusAuto(f"branche interdite : {branche}")
    import fcntl
    import os
    git_dir = Path(_g(depot, "rev-parse", "--absolute-git-dir").stdout.strip())
    verrou = open(git_dir / "base_protocole.lock", "w")      # deux passages simultanés sur la même machine
    try:
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"resultat": "DEJA_EN_COURS"}
    try:
        if _g(depot, "status", "--porcelain").stdout.strip():
            raise RefusAuto("arbre de travail modifié : passage automatique refusé")
        for essai in range(1, tentatives + 1):
            _g(depot, "fetch", "-q", f"--depth={profondeur}", "origin", "main", ok=True)
            _g(depot, "fetch", "-q", "origin", branche)
            _g(depot, "checkout", "-q", "-B", branche, f"origin/{branche}")
            sortie = depot / "data/base"
            avant = {p.name: _contenu_utile(p) for p in sortie.glob("*") if p.is_file()} if sortie.exists() else {}
            moment = maintenant or dt.datetime.now(dt.timezone.utc)
            cwd = Path.cwd()
            try:
                os.chdir(depot)
                etat = execute(Source(ref_donnees, "."), moment, Path("data/base"), n_sim=n_sim, b=b)
            finally:
                os.chdir(cwd)
            apres = {p.name: _contenu_utile(p) for p in sortie.glob("*") if p.is_file()}
            if apres == avant:
                _g(depot, "checkout", "-q", "--", ".", ok=True)
                return {"resultat": "AUCUN_CHANGEMENT", "statut_B0": etat["statut_B0"],
                        "points": etat["points_de_controle_atteints"], "essai": essai}
            _g(depot, "add", "-A", "data/base")
            hors = [f for f in _g(depot, "diff", "--cached", "--name-only").stdout.split() if not f.startswith("data/base/")]
            if hors:
                raise RefusAuto(f"fichiers hors data/base/ : {hors}")
            points = ",".join(etat["points_de_controle_atteints"]) or "aucun"
            _g(depot, "-c", "user.name=archetype-base-bot", "-c", "user.email=bot@users.noreply.github.com", "commit", "-q",
               "-m", f"BASE : passage automatique {moment:%Y-%m-%d %H:%M} UTC (statut {etat['statut_B0']}, points {points})")
            if _g(depot, "push", "-q", "origin", f"HEAD:refs/heads/{branche}", ok=True).returncode == 0:
                return {"resultat": "PUBLIE_SUR_BRANCHE", "statut_B0": etat["statut_B0"],
                        "points": etat["points_de_controle_atteints"], "essai": essai,
                        "commit": _g(depot, "rev-parse", "HEAD").stdout.strip()}
            _g(depot, "reset", "-q", "--hard", f"origin/{branche}")      # passage concurrent : on recommence
        raise RefusAuto(f"push refusé {tentatives} fois")
    finally:
        fcntl.flock(verrou, fcntl.LOCK_UN)
        verrou.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ref", default="origin/main")
    p.add_argument("--maintenant", default=None, help="instant de calcul ISO (par défaut : maintenant)")
    p.add_argument("--reproduction", action="store_true")
    p.add_argument("--simulation", action="store_true")
    p.add_argument("--auto", action="store_true", help="passage automatique : seuils, commit data/base/, push sur la branche dédiée")
    a = p.parse_args(argv)
    maintenant = instant(a.maintenant) if a.maintenant else dt.datetime.now(dt.timezone.utc)
    source = Source(a.ref)
    if a.auto:
        try:
            r = passage_automatique(".", BRANCHE_BASE, a.ref, instant(a.maintenant) if a.maintenant else None)
        except RefusAuto as exc:
            print(json.dumps({"resultat": "REFUS", "raison": str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps(r, ensure_ascii=False))
        return 0
    if a.reproduction:
        print(json.dumps(reproduction(source, maintenant), ensure_ascii=False, indent=1, default=str))
        return 0
    if a.simulation:
        _, adm = charge(source, maintenant)
        cotes = np.array([m.cote for m in adm.matchs if m.coup_d_envoi < DEBUT_TEST])
        lignes = []
        for jours, alpha in (((20, 40), 0.0025), ((25, 50), 0.0025), ((30, 60), 0.0025), ((20, 40), 0.002), ((20, 40), 0.0015)):
            r = simule_risque(cotes, jours, alpha, SIMULATIONS_CONTROLE, GRAINE + jours[0] + int(alpha * 1e5))
            lignes.append({"jours": jours, "niveau": 1 - 2 * alpha, **r})
            print(lignes[-1])
        SORTIE.mkdir(parents=True, exist_ok=True)
        FICHIER_SIMULATION.write_text(json.dumps({"calcule_le": maintenant.isoformat(), "lignes": lignes}, indent=1), encoding="utf-8")
        return 0
    etat = execute(source, maintenant)
    print(json.dumps({k: etat[k] for k in ("statut_B0", "points_de_controle_atteints", "B0_fenetre")}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
