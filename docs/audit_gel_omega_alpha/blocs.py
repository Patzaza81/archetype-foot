"""Outils communs : lecture des blocs d'équipe de l'archive, identifiant de club indépendant des noms, auto-références, union des historiques."""
import gzip, glob, json, re, unicodedata
from collections import defaultdict
from pathlib import Path


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def id_club(bloc):
    """Identifiant de club tiré de l'URL de la page équipe Matchendirect (…/equipe/<nom>_<id>.html) : indépendant des noms."""
    m = re.search(r"/equipe/[^|]*?_([a-z0-9]{20,30})\.html", str((bloc or {}).get("cle_cache") or ""))
    return m.group(1) if m else None


def cle_club(bloc):
    """(identifiant de club, compétition de la clé de cache) : le bloc dépend de la compétition, la comparaison reste donc à compétition égale."""
    c = id_club(bloc)
    return (c, str((bloc or {}).get("cle_cache") or "").split("||")[-1]) if c else None


def noms_bloc(entree, cote):
    b = (entree.get("assemblage") or {}).get("equipe_" + cote) or {}
    return {norm(x) for x in (b.get("nom_matchendirect"), b.get("nom_football_data"), entree.get("domicile" if cote == "dom" else "exterieur")) if x}


def est_auto_reference(match, noms):
    return norm(match.get("adversaire")) in noms


def cle(m):
    return (str(m["date"])[:10], bool(m.get("domicile")))


def score(m):
    return (m.get("buts_marques"), m.get("buts_encaisses"))


def lire_archive(dossier):
    out = {}
    for f in sorted(glob.glob(str(Path(dossier) / "*.json.gz"))):
        out[Path(f).name] = json.load(gzip.open(f))
    return out


def blocs(entree):
    """(cote, bloc_assemblage) pour les deux équipes, selon la règle des moteurs (assemblage si 'matchs' y figure, sinon bloc de l'archive)."""
    a = entree.get("assemblage") or {}
    res = []
    for cote in ("dom", "ext"):
        b = a.get("equipe_" + cote)
        if "matchs" not in (b or {}):
            b = entree.get("equipe_" + cote)
        res.append((cote, b))
    return res


def union_clubs(archive):
    """Pour chaque club (id) : {clé -> {versions de score -> exemplaire de match}} sur TOUS les blocs de l'archive fournie, auto-références exclues."""
    U = defaultdict(lambda: defaultdict(dict))
    for fichier, d in archive.items():
        for e in d.values():
            for cote, b in blocs(e):
                c = cle_club((e.get("assemblage") or {}).get("equipe_" + cote)) or cle_club(b)
                if not c or not b:
                    continue
                noms = noms_bloc(e, cote)
                for m in b.get("matchs") or []:
                    if not m.get("date") or not isinstance(m.get("buts_marques"), int) or not isinstance(m.get("buts_encaisses"), int):
                        continue
                    if est_auto_reference(m, noms):
                        continue
                    U[c][cle(m)].setdefault(score(m), m)
    return U
