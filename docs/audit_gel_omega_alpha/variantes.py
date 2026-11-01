"""Construit, pour un arbre extrait (état d'un commit de gel), trois archives modifiées en MÉMOIRE puis écrites dans un dossier à part (l'archive d'origine n'est jamais touchée) :
  L  = troncature seule : on ajoute aux blocs les matchs du même club (identifiant de l'URL équipe, jamais le nom) connus d'autres blocs et antérieurs au match ;
  S  = auto-références seules : on retire des blocs les lignes dont l'adversaire est l'équipe elle-même ;
  LS = les deux.
Usage : python variantes.py <arbre> <union.pkl>"""
import copy, gzip, hashlib, json, pickle, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import blocs as B

arbre = Path(sys.argv[1]); U = pickle.load(open(sys.argv[2], "rb"))
A = B.lire_archive(arbre / "data/archive_test")


def empreinte(lignes):
    return hashlib.sha1(json.dumps(sorted((str(m.get("date"))[:10], bool(m.get("domicile")), m.get("buts_marques"), m.get("buts_encaisses"), str(m.get("adversaire"))) for m in lignes or []), ensure_ascii=False).encode()).hexdigest()[:12]


info = {}
V = {v: {} for v in ("L", "S", "LS")}
for f, d in A.items():
    for v in V:
        V[v][f] = {}
    for k, e in d.items():
        jour = str(e["date"])[:10]
        out = {v: copy.deepcopy(e) for v in V}
        fiche = {"match_id": e.get("match_id"), "fichier": f, "cle": k}
        for cote in ("dom", "ext"):
            asm = (e.get("assemblage") or {}).get("equipe_" + cote)
            utilise_assemblage = "matchs" in (asm or {})
            b = asm if utilise_assemblage else e.get("equipe_" + cote)
            lignes = (b or {}).get("matchs")
            c = B.cle_club(asm) or B.cle_club(e.get("equipe_" + cote))
            noms = B.noms_bloc(e, cote)
            auto = [m for m in lignes or [] if B.est_auto_reference(m, noms)]
            cles_bloc = {B.cle(m): B.score(m) for m in lignes or [] if m.get("date")}
            ajout, conflit = [], 0
            if c and lignes is not None:
                for kk, versions in U.get(c, {}).items():
                    if kk[0] >= jour:
                        continue
                    if len(versions) > 1 or (kk in cles_bloc and cles_bloc[kk] not in versions):
                        conflit += 1; continue
                    if kk not in cles_bloc:
                        ajout.append(next(iter(versions.values())))
            fiche[cote] = {"club": list(c) if c else None, "sans_id": c is None, "bloc_utilise": "assemblage" if utilise_assemblage else "archive", "n_lignes": len(lignes or []),
                           "n_auto_references": len(auto), "n_manquantes": len(ajout), "n_conflits": conflit, "empreinte": empreinte(lignes)}
            if lignes is None:
                continue
            for v in V:
                cible = (out[v].get("assemblage") or {}).get("equipe_" + cote) if utilise_assemblage else out[v].get("equipe_" + cote)
                ms = cible["matchs"]
                if "S" in v:
                    ms = [m for m in ms if not B.est_auto_reference(m, noms)]
                if "L" in v:
                    ms = ms + copy.deepcopy(ajout)
                cible["matchs"] = ms
        info.setdefault(e.get("match_id"), []).append(fiche)
        for v in V:
            V[v][f][k] = out[v]
for v, arch in V.items():
    dossier = arbre / f"var_{v}" / "data" / "archive_test"
    dossier.mkdir(parents=True, exist_ok=True)
    for f, d in arch.items():
        with gzip.open(dossier / f, "wt", encoding="utf-8", compresslevel=3) as fh:
            json.dump(d, fh, ensure_ascii=False)
json.dump(info, open(arbre / "info_blocs.json", "w"), ensure_ascii=False)
print(arbre.name, "variantes écrites")
