"""Source Matchendirect pour les championnats absents de Football-Data (demande de Patrick, 06/11/2026 : deuxieme ligue des Pays-Bas).
Football-Data ne publie pas l'Eerste Divisie. P1 la lit donc dans l'assemblage Matchendirect (data/assemblage/equipes.json), la meme source que
les moteurs Gamma, Omega et DC pour ce championnat. Identites des equipes = celles du chargeur de l'assemblage (moteur_dc.donnees.Ligues, lecture seule).
Sortie au meme format que integration_calibration.historique : (jour ordinal, saison, domicile, exterieur, buts dom, buts ext)."""
import datetime, json, os
from moteur_dc import donnees as D

COMPETITIONS_MED = {"N2": "pays-bas : eerste divisie", "PT2": "portugal : liga portugal 2", "AU1": "australie : a-ligue", "DE3": "allemagne : ligue 3",
                    "HU1": "hongrie : nb i", "HR1": "croatie : hnl", "CZ1": "république tchèque : ligue tchèque", "RS1": "serbie : super ligue",
                    "BG1": "bulgarie : parva liga", "UA1": "ukraine : première ligue", "CH2": "suisse : challenge ligue", "KE1": "kenya : première ligue"}      # code interne P1 -> championnat Matchendirect (minuscules)
_NORMALISE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "football_data", "normalized")
_DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_FICHIERS = {"N2": os.path.join(_DOSSIER, "eerste_divisie", "matchs.json")}      # les autres : data/historique_med/<CODE>.json
_cache = {}

def _saison_complete(lignes):
    """Une saison n'est utilisee que si chaque rencontre domicile/exterieur possible entre ses equipes a ete jouee et a un score."""
    if any(x[3] is None or x[4] is None for x in lignes): return False
    equipes = {x[1] for x in lignes} | {x[2] for x in lignes}; jouees = {(x[1], x[2]) for x in lignes}
    return len(equipes) >= 2 and all((a, b) in jouees for a in equipes for b in equipes if a != b)

def saisons_passees(code):
    """{etiquette: [(jour ordinal, dom, ext, buts dom, buts ext)]} des saisons passees COMPLETES du championnat (fichiers data/…). Une saison incomplete est ecartee."""
    if code not in COMPETITIONS_MED: return {}
    if code not in _cache:
        with open(_FICHIERS.get(code) or os.path.join(_DOSSIER, "historique_med", code + ".json"), encoding="utf-8") as f: _cache[code] = json.load(f)["saisons"]
    res = {}
    for s, ms in sorted(_cache[code].items()):
        lignes = [(datetime.date.fromisoformat(d).toordinal(), a, b, x, y) for d, a, b, x, y in ms]
        if _saison_complete(lignes): res[s] = lignes
    return res

def _ligues(doc=None):
    if doc is not None: return D.Ligues(doc)
    if "ligues" not in _cache: _cache["ligues"] = D.charger_ligues()
    return _cache["ligues"]

def saison_courante():
    """Etiquette de la saison en cours = la plus recente des donnees Football-Data normalisees (ex. « 2627 »)."""
    return max(os.listdir(_NORMALISE))

# Meme club ecrit autrement dans les fichiers des saisons passees (certain : ce ne sont pas des clubs voisins).
ALIAS = {"AFC Leopards": "Leopards", "Kenya Police FC": "Police", "Mara Sugar FC": "Mara Sugar", "Shabana FC": "Shabana", "Tusker FC": "Tusker", "Ulinzi Stars FC": "Ulinzi"}

def historique(code, doc=None, saison=None):
    """Saisons passees completes + saison en cours (assemblage Matchendirect, une ligne par match), tries par date. [] si le code n'est pas servi par Matchendirect.
    La saison en cours est partielle : elle n'alimente que l'historique, jamais le choix des parametres (voir calibrer_p1_med)."""
    comp = COMPETITIONS_MED.get(code)
    if comp is None: return []
    saison = saison or saison_courante()
    cur = [(datetime.date.fromisoformat(m["date"]).toordinal(), saison, m["dom_nom"], m["ext_nom"], int(m["h"]), int(m["a"])) for m in _ligues(doc).matchs.get(comp, [])]
    # Les fichiers des saisons passees ecrivent « Fc Dordrecht », « Vvv », « Jong Az » ; Matchendirect (saison en cours) « FC Dordrecht », « VVV », « Jong AZ » :
    # meme equipe, donc on reprend l'ecriture de la saison en cours (sinon l'equipe perd tout son historique).
    ecriture = {n.casefold(): n for r in cur for n in (r[2], r[3])}
    nom = lambda n: ecriture.get(ALIAS.get(n, n).casefold(), ALIAS.get(n, n))
    passees = [(j, s, nom(a), nom(b), x, y) for s, ms in saisons_passees(code).items() if s != saison for j, a, b, x, y in ms]
    return sorted(passees + cur, key=lambda r: r[0])

def division_et_noms(competition, cle_dom, cle_ext, doc=None):
    """(code, nom domicile, nom exterieur) si le match est d'un championnat servi par Matchendirect et que les deux equipes y sont identifiees ; sinon None."""
    nom = " ".join(str(competition or "").lower().split())
    code = next((c for c, n in COMPETITIONS_MED.items() if n == nom), None)
    if code is None: return None
    L = _ligues(doc); a, b = L.equipe(cle_dom or ""), L.equipe(cle_ext or "")
    if a is None or b is None or a == b: return None
    return code, L.noms.get(a), L.noms.get(b)
