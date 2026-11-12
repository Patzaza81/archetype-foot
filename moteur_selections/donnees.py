"""Historique des sélections nationales : résultats internationaux publics et gratuits (dépôt GitHub martj42/international_results, results.csv :
date, équipes, buts, compétition, terrain neutre). La collecte ne calcule rien : elle lit, normalise, transmet.
Seuls les matchs joués sur le terrain de l'une des équipes entrent dans les échantillons « au même lieu » (un match en terrain neutre n'a ni domicile ni extérieur)."""
import bisect, csv, datetime, os, urllib.request

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER = os.path.join(RACINE, "data", "selections")
CHEMIN = os.path.join(DOSSIER, "resultats_selections.csv")
URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
QUALIF = "FIFA World Cup qualification"
AMICAL = "Friendly"


def telecharger(dest=CHEMIN, url=URL):
    """Télécharge le fichier public (gratuit). Lève une erreur claire si le téléchargement échoue : jamais de données inventées."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as r: contenu = r.read()
    if not contenu.startswith(b"date,home_team,away_team"): raise RuntimeError("fichier inattendu : colonnes absentes")
    with open(dest, "wb") as f: f.write(contenu)
    return dest


def charger(chemin=CHEMIN):
    """Matchs joués (score connu), triés par date. -> [{date, domicile, exterieur, buts_dom, buts_ext, competition, neutre}]"""
    M = []
    with open(chemin, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try: hs, as_ = int(r["home_score"]), int(r["away_score"])
            except (ValueError, TypeError): continue
            M.append({"date": r["date"], "domicile": r["home_team"], "exterieur": r["away_team"], "buts_dom": hs, "buts_ext": as_,
                      "competition": r["tournament"], "neutre": str(r["neutral"]).strip().upper() == "TRUE"})
    M.sort(key=lambda m: m["date"])
    return M


class Historique:
    """Index des matchs par équipe et par lieu (« dom » = l'équipe reçoit, « ext » = elle se déplace), terrain neutre exclu, du plus ancien au plus récent."""

    def __init__(self, matchs):
        self.dates = {"dom": {}, "ext": {}}; self.lignes = {"dom": {}, "ext": {}}
        self.q_dates, self.q_dom, self.q_ext = [], [], []        # qualifications (hors terrain neutre) : sert à l'avantage du terrain
        for m in sorted(matchs, key=lambda m: m["date"]):
            if m["neutre"]: continue
            officiel = m["competition"] != AMICAL
            for role, eq, marques, encaisses in (("dom", m["domicile"], m["buts_dom"], m["buts_ext"]), ("ext", m["exterieur"], m["buts_ext"], m["buts_dom"])):
                self.dates[role].setdefault(eq, []).append(m["date"]); self.lignes[role].setdefault(eq, []).append((marques, encaisses, officiel))
            if m["competition"] == QUALIF: self.q_dates.append(m["date"]); self.q_dom.append(m["buts_dom"]); self.q_ext.append(m["buts_ext"])

    @staticmethod
    def _debut(date, fenetre_jours):
        return (datetime.date.fromisoformat(date) - datetime.timedelta(days=fenetre_jours)).isoformat()

    def meme_lieu(self, equipe, role, date, fenetre_jours, officiels_seulement):
        """Matchs de l'équipe dans ce rôle, STRICTEMENT avant `date` (jamais le jour même : pas de fuite), dans la fenêtre. -> [(buts marqués, buts encaissés)]"""
        D = self.dates[role].get(equipe, [])
        i, j = bisect.bisect_left(D, self._debut(date, fenetre_jours)), bisect.bisect_left(D, date)
        return [(mq, en) for (mq, en, off) in self.lignes[role][equipe][i:j] if off or not officiels_seulement] if D else []

    def avantage(self, date, fenetre_jours):
        """Avantage du terrain dans les qualifications de la fenêtre : buts à domicile moins buts à l'extérieur, par match. 0 si aucun match."""
        i, j = bisect.bisect_left(self.q_dates, self._debut(date, fenetre_jours)), bisect.bisect_left(self.q_dates, date)
        n = j - i
        return 0.0 if n <= 0 else (sum(self.q_dom[i:j]) - sum(self.q_ext[i:j])) / n
