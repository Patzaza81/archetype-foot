"""Historique durable de v, pour analyse. Règle unique : on AJOUTE, on ne réécrit jamais (fichiers .jsonl, une ligne = un fait).
Dossier data/v/historique/ :
  versions/AAAA-MM.jsonl   chaque version d'un pronostic avant le coup d'envoi (écrite seulement si elle change)
  reglements/AAAA-MM.jsonl chaque match réglé, UNE seule fois : pronostic figé + score + résultat de chaque pari + tous les marchés lus
                           avec leurs probabilités (force, simple, mixte), lambdas, contexte, alertes, version des paramètres
  bilans.jsonl             un instantané du bilan par passage (par niveau) : sert à voir la dérive de la calibration dans le temps
Le carnet (carnet.json) reste l'état courant ; l'historique en est la mémoire. Aucune lecture par le moteur pour décider un pronostic."""
import hashlib
import json
import os

RACINE = "historique"


def _dossier(dossier, *p):
    d = os.path.join(dossier, RACINE, *p)
    os.makedirs(os.path.dirname(d) if d.endswith(".jsonl") else d, exist_ok=True)
    return d


def _ajoute(chemin, objets):
    if not objets:
        return 0
    with open(chemin, "a", encoding="utf-8") as f:
        for o in objets:
            f.write(json.dumps(o, ensure_ascii=False, sort_keys=True) + "\n")
    return len(objets)


def lit(chemin):
    if not os.path.exists(chemin):
        return []
    out = []
    for l in open(chemin, encoding="utf-8"):
        l = l.strip()
        if l:
            out.append(json.loads(l))
    return out


def _fichiers(dossier, sous):
    d = os.path.join(dossier, RACINE, sous)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl")) if os.path.isdir(d) else []


def signature(ligne):
    """Ce qui fait qu'un pronostic est « différent » : principal, autres, version des paramètres (pas l'heure de lecture)."""
    p = ligne["principal"]
    base = [p["marche"], p["cote"]] + [[a["marche"], a["cote"]] for a in ligne["autres"]] + [ligne.get("parametres_version")]
    return hashlib.sha1(json.dumps(base, sort_keys=True).encode()).hexdigest()[:12]


def _mois(ts):
    return (ts or "0000-00")[:7]


def ajoute_versions(dossier, carnet, maintenant):
    """Une ligne par pronostic non figé dont la signature diffère de la dernière version archivée du même match."""
    derniere = {}
    for f in _fichiers(dossier, "versions"):
        for o in lit(f):
            derniere[o["match_id"]] = o["signature"]
    par_mois = {}
    for mid, l in carnet.items():
        if l["fige"]:
            continue
        s = signature(l)
        if derniere.get(mid) == s:
            continue
        rec = dict(match_id=mid, signature=s, vu_le=l["vu_le"], date=l["date"], coup_d_envoi_utc=l["coup_d_envoi_utc"], competition=l["competition"],
                   domicile=l["domicile"], exterieur=l["exterieur"], parametres_version=l.get("parametres_version"),
                   principal={k: l["principal"][k] for k in ("marche", "cote", "p_modele", "p_honnete", "niveau")},
                   autres=[{k: a[k] for k in ("marche", "cote", "p_modele", "p_honnete", "niveau")} for a in l["autres"]])
        par_mois.setdefault(_mois(l["vu_le"]), []).append(rec)
    n = 0
    for mois, recs in par_mois.items():
        n += _ajoute(_dossier(dossier, "versions", mois + ".jsonl"), sorted(recs, key=lambda r: r["match_id"]))
    return n


def ajoute_reglements(dossier, carnet):
    """Archive chaque match réglé une seule fois (jamais deux fois le même match_id)."""
    deja = {o["match_id"] for f in _fichiers(dossier, "reglements") for o in lit(f)}
    par_mois = {}
    for mid, l in carnet.items():
        if l["resultat"] is None or mid in deja:
            continue
        par_mois.setdefault(_mois(l["date"]), []).append(dict(l, signature=signature(l)))
    n = 0
    for mois, recs in par_mois.items():
        n += _ajoute(_dossier(dossier, "reglements", mois + ".jsonl"), sorted(recs, key=lambda r: r["match_id"]))
    return n


def ajoute_bilan(dossier, bilan, maintenant, parametres_version):
    """Instantané du bilan. Pas de doublon si le bilan est identique au dernier instantané."""
    chemin = _dossier(dossier, "bilans.jsonl")
    ancien = lit(chemin)
    if ancien and ancien[-1]["bilan"] == bilan and ancien[-1]["parametres_version"] == parametres_version:
        return 0
    return _ajoute(chemin, [dict(le=maintenant.isoformat(), parametres_version=parametres_version, bilan=bilan)])


def enregistre(dossier, carnet, bilan, maintenant, parametres_version):
    return dict(versions=ajoute_versions(dossier, carnet, maintenant), reglements=ajoute_reglements(dossier, carnet),
                bilans=ajoute_bilan(dossier, bilan, maintenant, parametres_version))


def verifie(dossier):
    """Contrôle d'intégrité : lignes lisibles, aucun match réglé deux fois, chaque réglé a score et résultat. Retourne la liste des problèmes."""
    pb = []
    vus = set()
    for f in _fichiers(dossier, "reglements"):
        try:
            for o in lit(f):
                if o["match_id"] in vus:
                    pb.append("réglé deux fois : " + str(o["match_id"]))
                vus.add(o["match_id"])
                if o.get("score") is None or o.get("resultat") not in ("WIN", "LOSS"):
                    pb.append("réglé sans score/résultat : " + str(o["match_id"]))
        except ValueError:
            pb.append("fichier illisible : " + f)
    for f in _fichiers(dossier, "versions"):
        try:
            lit(f)
        except ValueError:
            pb.append("fichier illisible : " + f)
    try:
        lit(os.path.join(dossier, RACINE, "bilans.jsonl"))
    except ValueError:
        pb.append("bilans.jsonl illisible")
    return pb
