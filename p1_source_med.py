"""Source Matchendirect pour les championnats absents de Football-Data (demande de Patrick, 06/11/2026 : deuxieme ligue des Pays-Bas).
Football-Data ne publie pas l'Eerste Divisie. P1 la lit donc dans l'assemblage Matchendirect (data/assemblage/equipes.json), la meme source que
les moteurs Gamma, Omega et DC pour ce championnat. Identites des equipes = celles du chargeur de l'assemblage (moteur_dc.donnees.Ligues, lecture seule).
Sortie au meme format que integration_calibration.historique : (jour ordinal, saison, domicile, exterieur, buts dom, buts ext)."""
import datetime, os
from moteur_dc import donnees as D

COMPETITIONS_MED = {"N2": "pays-bas : eerste divisie"}      # code interne P1 -> championnat Matchendirect (minuscules)
_NORMALISE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "football_data", "normalized")
_cache = {}

def _ligues(doc=None):
    if doc is not None: return D.Ligues(doc)
    if "ligues" not in _cache: _cache["ligues"] = D.charger_ligues()
    return _cache["ligues"]

def saison_courante():
    """Etiquette de la saison en cours = la plus recente des donnees Football-Data normalisees (ex. « 2627 »)."""
    return max(os.listdir(_NORMALISE))

def historique(code, doc=None, saison=None):
    """Matchs joues du championnat (assemblage Matchendirect, une ligne par match), tries par date. [] si le code n'est pas servi par Matchendirect."""
    comp = COMPETITIONS_MED.get(code)
    if comp is None: return []
    saison = saison or saison_courante()
    return [(datetime.date.fromisoformat(m["date"]).toordinal(), saison, m["dom_nom"], m["ext_nom"], int(m["h"]), int(m["a"])) for m in _ligues(doc).matchs.get(comp, [])]

def division_et_noms(competition, cle_dom, cle_ext, doc=None):
    """(code, nom domicile, nom exterieur) si le match est d'un championnat servi par Matchendirect et que les deux equipes y sont identifiees ; sinon None."""
    nom = " ".join(str(competition or "").lower().split())
    code = next((c for c, n in COMPETITIONS_MED.items() if n == nom), None)
    if code is None: return None
    L = _ligues(doc); a, b = L.equipe(cle_dom or ""), L.equipe(cle_ext or "")
    if a is None or b is None or a == b: return None
    return code, L.noms.get(a), L.noms.get(b)
