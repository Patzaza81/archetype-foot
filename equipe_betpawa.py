"""Rattache le nom d'équipe écrit par BetPawa (« AS Saint-Etienne », « Rodez Aveyron Football ») à l'équipe du match
(« Saint-Étienne », « Rodez »). Avant, les parseurs exigeaient l'égalité exacte des noms : les marchés « total de buts
d'une équipe » et « cages inviolées » étaient jetés dès que BetPawa écrivait le nom autrement (10/10/2026, constaté sur
Saint-Étienne – Rodez). Module autonome (aucun import du projet) pour éviter tout import circulaire."""
import re
import unicodedata

# Mots qui ne distinguent pas un club d'un autre.
_BRUIT = {"as", "fc", "ac", "sc", "cf", "afc", "us", "rc", "ss", "ssc", "fk", "sk", "club", "football", "aveyron", "de", "du", "le", "la"}
# Mots qui désignent une AUTRE équipe du même club (réserve, jeunes, féminines).
_RESERVE = {"ii", "iii", "b", "c", "u17", "u18", "u19", "u20", "u21", "u23", "reserve", "reserves", "youth", "jeunes", "women", "feminin", "w"}


def _mots(nom):
    s = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+", s)


def _cle(nom):
    return [m for m in _mots(nom) if m not in _BRUIT]


def memes_equipes(nom_a, nom_b):
    """Vrai si les deux noms désignent la même équipe : mêmes mots significatifs, l'un pouvant contenir l'autre, sans
    mot de réserve/jeunes en trop."""
    if nom_a == nom_b:
        return True
    a, b = _cle(nom_a), _cle(nom_b)
    if not a or not b:
        return False
    if a == b:
        return True
    sa, sb = set(a), set(b)
    if sa <= sb or sb <= sa:
        extra = (sa | sb) - (sa & sb)
        return not (extra & _RESERVE)
    return False


def cote_de_l_equipe(nom, nom_domicile, nom_exterieur):
    """« domicile », « exterieur » ou None. None aussi si le nom correspond aux deux (ambigu)."""
    d, e = memes_equipes(nom, nom_domicile), memes_equipes(nom, nom_exterieur)
    if d and not e:
        return "domicile"
    if e and not d:
        return "exterieur"
    if d and e:      # les deux conviennent (ex. Paris FC / Paris Saint-Germain) : on ne garde que l'égalité exacte des mots
        cle = _cle(nom)
        if cle == _cle(nom_domicile) and cle != _cle(nom_exterieur):
            return "domicile"
        if cle == _cle(nom_exterieur) and cle != _cle(nom_domicile):
            return "exterieur"
    return None
