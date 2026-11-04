#!/usr/bin/env python3
"""Inventaire automatise, reproductible et tracable des archives Football-Data.

Aucun modele predictif. Lecture seule des archives. Voir docs/INVENTAIRE_FOOTBALL_DATA.md.
Sorties: manifest_global.json, profils_capacite.json, anomalies.json, rapport_inventaire.md, dernier_run.json
"""
import argparse, csv, hashlib, io, json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

VERSION_SCRIPT = "1.0.0"


# ---------- utilitaires ----------
def sha256_fichier(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def sha256_octets(b):
    return hashlib.sha256(b).hexdigest()


def empreinte_arbre(racine):
    """Empreinte de tous les fichiers sous racine (chemin relatif + sha256)."""
    h = hashlib.sha256()
    n = 0
    for dossier, sous, fichiers in os.walk(racine):
        sous.sort()
        for nom in sorted(fichiers):
            p = os.path.join(dossier, nom)
            h.update(os.path.relpath(p, racine).encode() + b"\0" + sha256_fichier(p).encode() + b"\n")
            n += 1
    return {"sha256": h.hexdigest(), "fichiers": n}


def charger_config(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def normaliser_nom(nom):
    s = (nom or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s, formats):
    s = (s or "").strip()
    for f in formats:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def candidats_changement_de_nom(sortants, entrants, longueur_min):
    """Paires (sortant, entrant) dont les noms normalises sont lies (inclusion ou prefixe commun
    >= longueur_min). Candidats SEULEMENT: aucune fusion."""
    res = []
    for a in sorted(sortants):
        na = normaliser_nom(a)
        for b in sorted(entrants):
            nb = normaliser_nom(b)
            if not na or not nb:
                continue
            pref = os.path.commonprefix([na, nb])
            if na in nb or nb in na or len(pref) >= longueur_min:
                res.append([a, b])
    return res


def lire_csv(chemin):
    with open(chemin, "rb") as f:
        brut = f.read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lecteur = csv.reader(io.StringIO(texte, newline=""))
    lignes = []
    entete = None
    for ligne in lecteur:
        if entete is None:
            entete = ligne
            continue
        lignes.append((lecteur.line_num, ligne))
    return enc, entete or [], lignes


# ---------- analyse d'un fichier ----------
class Cfg:
    def __init__(self, cfg):
        self.c = cfg
        self.vides = set(cfg["valeurs_vides"])
        self.motifs = [re.compile(m) for m in cfg["motifs_cotes"]]
        self.entiers = set(cfg["colonnes_entieres_positives"])

    def est_cote(self, nom):
        return any(m.match(nom) for m in self.motifs)


def _vide(v, vides):
    return v is None or v.strip() in vides


def _entier(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return int(x) if x == int(x) and x >= 0 else None


def _cote(v, mini):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x > mini else None


def canonique_vers_source(entete, alias):
    """nom canonique -> nom source present dans l'entete (ou None)."""
    res = {}
    for can, noms in alias.items():
        res[can] = next((n for n in noms if n in entete), None)
    return res


def analyser_fichier(chemin, cfg, annee_min_max=None, div_attendu=None):
    """Analyse un fichier CSV. Retourne dict (couches 1 a 3 + anomalies locales)."""
    C = Cfg(cfg)
    c = cfg
    enc, entete, lignes = lire_csv(chemin)
    noms = [h.strip() for h in entete]
    nonvides = [h for h in noms if h]
    can = canonique_vers_source(nonvides, c["alias_colonnes"])
    idx = {h: i for i, h in enumerate(noms) if h}
    ex_max = c["exemples_max"]
    anomalies = []

    def anom(type_, sev, nombre, exemples, message, edition=None):
        anomalies.append({"type": type_, "severite": sev, "edition": edition, "nombre": nombre,
                          "exemples": exemples[:ex_max], "message": message})

    out = {
        "encodage": enc, "sha256": sha256_fichier(chemin), "octets": os.path.getsize(chemin),
        "colonnes": nonvides, "colonnes_sans_nom": len(noms) - len(nonvides),
        "colonnes_canoniques": can, "lignes_vides": 0, "lignes_longueur_anormale": 0,
    }
    if not can["FTHG"] or not can["FTAG"]:
        pass
    # regrouper par edition
    ed_col = "League" if "League" in idx else ("Div" if "Div" in idx else None)
    unites = defaultdict(list)
    exl = []
    for num, ligne in lignes:
        if not any(x.strip() for x in ligne):
            out["lignes_vides"] += 1
            continue
        if len(ligne) > len(noms) and any(x.strip() for x in ligne[len(noms):]) or \
           len(ligne) < len(nonvides) and len(ligne) < len(noms) - (len(noms) - len(nonvides)):
            out["lignes_longueur_anormale"] += 1
            exl.append({"ligne": num, "detail": f"{len(ligne)} cellules pour {len(noms)} colonnes"})
        ed = ligne[idx[ed_col]].strip() if ed_col and len(ligne) > idx[ed_col] else ""
        unites[ed].append((num, ligne))
    if out["lignes_longueur_anormale"]:
        anom("ligne_longueur_anormale", "avertissement", out["lignes_longueur_anormale"], exl,
             "lignes dont le nombre de cellules ne correspond pas a l'entete")

    def val(ligne, nom):
        i = idx.get(nom)
        return ligne[i].strip() if i is not None and i < len(ligne) else ""

    editions = {}
    for ed, rows in sorted(unites.items()):
        e, an = _analyser_unite(ed, rows, nonvides, can, C, val, annee_min_max, div_attendu)
        editions[ed] = e
        for a in an:
            a["edition"] = ed
        anomalies.extend(an)
    out["editions"] = editions
    out["lignes_total"] = sum(e["lignes"] for e in editions.values())
    out["lignes_avec_score"] = sum(e["lignes_avec_score"] for e in editions.values())
    return out, anomalies


def _analyser_unite(ed, rows, cols, can, C, val, annee_min_max, div_attendu):
    c = C.c
    ex_max = c["exemples_max"]
    an = []
    hg, ag, fr = can["FTHG"], can["FTAG"], can["FTR"]
    ht, home, away = can["HomeTeam"], can["AwayTeam"], can["AwayTeam"]
    home = can["HomeTeam"]
    cpt = Counter()
    exemples = defaultdict(list)

    def flag(k, num, detail):
        cpt[k] += 1
        if len(exemples[k]) < ex_max:
            exemples[k].append({"ligne": num, "detail": detail})

    stats = {k: {"valides_joues": 0, "valides_total": 0, "invalides": 0} for k in cols}
    coh = {k: {"evaluees": 0, "violations": 0} for k in ("FTR_vs_buts", "mt_inferieur_ft", "cadres_inf_tirs", "HTR_vs_buts_mt")}
    joues = 0
    sans_score_vide = 0
    sans_score_invalide = 0
    equipes = set()
    dates = []
    vus_ligne = Counter()
    cle = defaultdict(list)
    sign_odds = defaultdict(list)
    equipe_jour = defaultdict(list)
    cols_cotes = [k for k in cols if C.est_cote(k)]
    for num, ligne in rows:
        d = {k: val(ligne, k) for k in cols}
        vus_ligne[tuple(ligne)] += 1
        # score
        sh = d.get(hg, "") if hg else ""
        sa = d.get(ag, "") if ag else ""
        ih, ia = (_entier(sh), _entier(sa))
        a_score = ih is not None and ia is not None
        if a_score:
            joues += 1
        elif _vide(sh, C.vides) and _vide(sa, C.vides):
            sans_score_vide += 1
        else:
            sans_score_invalide += 1
            flag("score_invalide", num, f"{sh!r}-{sa!r}")
        # colonnes
        for k in cols:
            v = d[k]
            if _vide(v, C.vides):
                continue
            ok = True
            canon = next((cn for cn, s in can.items() if s == k), k)
            if canon in C.entiers:
                ok = _entier(v) is not None
            elif C.est_cote(k):
                ok = _cote(v, c["cote_minimale_exclue"]) is not None
            if ok:
                stats[k]["valides_total"] += 1
                if a_score:
                    stats[k]["valides_joues"] += 1
            else:
                stats[k]["invalides"] += 1
                flag("valeur_invalide:" + k, num, v)
        # date
        dt = parse_date(d.get("Date", ""), c["formats_date"]) if "Date" in d else None
        if "Date" in d:
            if dt is None:
                flag("date_invalide", num, d.get("Date", ""))
            else:
                dates.append(dt)
                if annee_min_max and not (annee_min_max[0] <= dt.year <= annee_min_max[1]):
                    flag("date_hors_saison", num, d["Date"])
        # equipes
        h = d.get(home, "") if home else ""
        a_ = d.get(can["AwayTeam"], "") if can["AwayTeam"] else ""
        if not h or not a_:
            flag("equipe_vide", num, f"{h!r} vs {a_!r}")
        else:
            equipes.update([h, a_])
            if normaliser_nom(h) == normaliser_nom(a_):
                flag("equipe_contre_elle_meme", num, h)
        if dt and h and a_:
            cle[(dt, normaliser_nom(h), normaliser_nom(a_))].append((num, ih, ia))
            equipe_jour[(dt, normaliser_nom(h))].append(num)
            equipe_jour[(dt, normaliser_nom(a_))].append(num)
            odds = tuple(d[k] for k in cols_cotes if d[k])
            if a_score and odds:
                sign_odds[(normaliser_nom(h), normaliser_nom(a_), ih, ia, odds)].append((num, dt))
        # coherence
        if a_score and fr and d.get(fr, ""):
            coh["FTR_vs_buts"]["evaluees"] += 1
            att = "H" if ih > ia else ("A" if ih < ia else "D")
            if d[fr] != att:
                coh["FTR_vs_buts"]["violations"] += 1
                flag("FTR_incoherent", num, f"{ih}-{ia} FTR={d[fr]}")
        hth, hta = _entier(d.get("HTHG", "")), _entier(d.get("HTAG", ""))
        if a_score and hth is not None and hta is not None:
            coh["mt_inferieur_ft"]["evaluees"] += 1
            if hth > ih or hta > ia:
                coh["mt_inferieur_ft"]["violations"] += 1
                flag("mi_temps_superieure_au_final", num, f"MT {hth}-{hta} FT {ih}-{ia}")
            if d.get("HTR", ""):
                coh["HTR_vs_buts_mt"]["evaluees"] += 1
                att = "H" if hth > hta else ("A" if hth < hta else "D")
                if d["HTR"] != att:
                    coh["HTR_vs_buts_mt"]["violations"] += 1
                    flag("HTR_incoherent", num, f"MT {hth}-{hta} HTR={d['HTR']}")
        for t, s in (("HST", "HS"), ("AST", "AS")):
            vt, vs = _entier(d.get(t, "")), _entier(d.get(s, ""))
            if vt is not None and vs is not None:
                coh["cadres_inf_tirs"]["evaluees"] += 1
                if vt > vs:
                    coh["cadres_inf_tirs"]["violations"] += 1
                    flag("tirs_cadres_superieurs_aux_tirs", num, f"{t}={vt} > {s}={vs}")
        if div_attendu and "Div" in d and d["Div"] and d["Div"] != div_attendu:
            flag("div_inattendu", num, d["Div"])
    # doublons
    dup_exact = [(k, v) for k, v in vus_ligne.items() if v > 1]
    if dup_exact:
        an.append(_a("doublon_ligne_exacte", "avertissement", sum(v - 1 for _, v in dup_exact),
                     [{"detail": " | ".join(k)[:120], "occurrences": v} for k, v in dup_exact], ex_max,
                     "lignes strictement identiques"))
    conf = [(k, v) for k, v in cle.items() if len(v) > 1]
    if conf:
        an.append(_a("doublon_cle_date_equipes", "avertissement", sum(len(v) - 1 for _, v in conf),
                     [{"detail": f"{k[0]} {k[1]} - {k[2]}", "lignes": [x[0] for x in v],
                       "scores": [[x[1], x[2]] for x in v]} for k, v in conf], ex_max,
                     "meme date + memes equipes (score identique ou different)"))
    sus = [(k, v) for k, v in sign_odds.items() if len(v) > 1 and len({x[1] for x in v}) > 1]
    if sus:
        an.append(_a("doublon_probable_equipes_score_cotes", "avertissement", sum(len(v) - 1 for _, v in sus),
                     [{"detail": f"{k[0]} - {k[1]} {k[2]}-{k[3]}", "lignes": [x[0] for x in v]} for k, v in sus], ex_max,
                     "memes equipes, meme score et memes cotes a des dates differentes"))
    deux = [(k, v) for k, v in equipe_jour.items() if len(set(v)) > 1]
    if deux:
        an.append(_a("equipe_deux_matchs_meme_jour", "avertissement", len(deux),
                     [{"detail": f"{k[0]} {k[1]}", "lignes": sorted(set(v))} for k, v in deux], ex_max,
                     "une equipe apparait dans deux matchs le meme jour"))
    inv = {(k[0], k[2], k[1]) for k in cle}
    paires_inv = [k for k in cle if (k[0], k[2], k[1]) in cle and k[1] < k[2]]
    if paires_inv:
        an.append(_a("paire_inversee_meme_jour", "info", len(paires_inv),
                     [{"detail": f"{k[0]} {k[1]} / {k[2]}"} for k in paires_inv], ex_max,
                     "match et son inverse a la meme date"))
    for k, n in sorted(cpt.items()):
        sev = "avertissement"
        an.append({"type": k, "severite": sev, "edition": None, "nombre": n, "exemples": exemples[k][:ex_max],
                   "message": "valeurs ou coherences invalides"})
    if sans_score_vide:
        an.append({"type": "lignes_sans_score_vide", "severite": "info", "edition": None, "nombre": sans_score_vide,
                   "exemples": [], "message": "lignes sans score (non jouees / futures): jamais utilisables pour l'apprentissage du resultat"})
    return {
        "lignes": len(rows), "lignes_avec_score": joues,
        "lignes_sans_score_vide": sans_score_vide, "lignes_sans_score_invalide": sans_score_invalide,
        "premiere_date": min(dates).isoformat() if dates else None,
        "derniere_date": max(dates).isoformat() if dates else None,
        "equipes": sorted(equipes),
        "colonnes": stats, "coherence": coh,
    }, an


def _a(type_, sev, n, ex, ex_max, msg):
    return {"type": type_, "severite": sev, "edition": None, "nombre": n, "exemples": ex[:ex_max], "message": msg}


# ---------- etat d'une colonne ----------
def etat_colonne(analyse_fichier, nom_canonique, cfg):
    """absente | presente_vide | partielle | complete (sur matchs joues, toutes editions)."""
    src = analyse_fichier["colonnes_canoniques"].get(nom_canonique, nom_canonique)
    if src not in analyse_fichier["colonnes"]:
        return "absente"
    joues = analyse_fichier["lignes_avec_score"]
    ok = sum(e["colonnes"][src]["valides_joues"] for e in analyse_fichier["editions"].values())
    if ok == 0:
        return "presente_vide"
    return "complete" if joues and ok == joues else "partielle"


def _taux_cellule(cellule, nom, cfg):
    """(valides_joues, joues) pour un nom canonique ou source dans une cellule analysee."""
    src = cellule["colonnes_canoniques"].get(nom) or nom
    if src not in cellule["colonnes"]:
        return None
    ok = sum(e["colonnes"][src]["valides_joues"] for e in cellule["editions"].values())
    return ok, cellule["lignes_avec_score"]


# ---------- capacites ----------
def evaluer_capacite(nom, definition, cellules, cfg):
    """cellules: liste d'analyses de fichier (une par saison de la fenetre)."""
    st = cfg["statuts"]
    meilleure = None
    for groupe in definition["alternatives"]:
        details = {}
        jamais = False
        parfait = True
        for col in groupe:
            par_saison = {}
            total_ok = 0
            for (saison, cel) in cellules:
                r = _taux_cellule(cel, col, cfg) if cel else None
                if r is None:
                    par_saison[saison] = {"etat": "absente", "taux": None}
                    parfait = False
                else:
                    ok, j = r
                    taux = (ok / j) if j else None
                    par_saison[saison] = {"etat": "presente_vide" if ok == 0 else ("complete" if ok == j else "partielle"),
                                          "taux": None if taux is None else round(taux, 6), "renseignees": ok, "joues": j}
                    total_ok += ok
                    if taux is None or taux < st["taux_confirmee"]:
                        parfait = False
            details[col] = {"par_saison": par_saison, "jamais_renseignee": total_ok == 0}
            if total_ok == 0:
                jamais = True
        score = sum(0 if d["jamais_renseignee"] else 1 for d in details.values())
        cand = {"colonnes": groupe, "details": details, "parfait": parfait and not jamais, "jamais": jamais, "score": score}
        if meilleure is None or (cand["parfait"], cand["score"]) > (meilleure["parfait"], meilleure["score"]):
            meilleure = cand
    # coherence
    coh = {}
    ok_coh = True
    for chk in definition["coherence"]:
        ev = sum(cel["editions"][e]["coherence"][chk]["evaluees"] for _, cel in cellules if cel for e in cel["editions"])
        vi = sum(cel["editions"][e]["coherence"][chk]["violations"] for _, cel in cellules if cel for e in cel["editions"])
        coh[chk] = {"evaluees": ev, "violations": vi}
        if ev == 0 or vi > 0:
            ok_coh = False
    saisons_ok = sum(1 for _, cel in cellules if cel and cel["lignes_avec_score"] > 0)
    if meilleure["jamais"]:
        statut = "CAPACITE_INEXPLOITABLE"
    elif meilleure["parfait"] and ok_coh and saisons_ok >= st["saisons_requises"]:
        statut = "CAPACITE_CONFIRMEE"
    else:
        statut = "CAPACITE_LIMITEE"
    raisons = []
    if statut == "CAPACITE_LIMITEE":
        if saisons_ok < st["saisons_requises"]:
            raisons.append(f"{saisons_ok} saison(s) avec matchs joues sur {st['saisons_requises']} requises")
        if not meilleure["parfait"]:
            taux = [v["taux"] for d in meilleure["details"].values() for v in d["par_saison"].values() if v["taux"] is not None]
            raisons.append("remplissage inferieur a 100% sur au moins une saison" + (f" (minimum observe {min(taux):.4f})" if taux else ""))
        if not ok_coh:
            raisons.append("controle de coherence non evaluable ou violations: " + json.dumps(coh, sort_keys=True))
    elif statut == "CAPACITE_INEXPLOITABLE":
        raisons.append("colonne(s) requise(s) jamais renseignee(s) dans toutes les alternatives")
    return {"statut": statut, "usage": definition["usage"], "marches": definition["marches"],
            "alternative_retenue": meilleure["colonnes"], "coherence": coh, "raisons": raisons,
            "detail": meilleure["details"]}


# ---------- inventaire ----------
def _controle_manifest(entree, chemin_fichier, analyse, id_, controles):
    if entree is None:
        controles.append({"id": id_, "ok": False, "message": "entree absente du manifest du snapshot"})
        return None
    ok = True
    msgs = []
    if "sha256" in entree and entree["sha256"] != analyse["sha256"]:
        ok = False; msgs.append("sha256 different du manifest")
    if "rows" in entree and entree["rows"] != analyse["lignes_total"]:
        ok = False; msgs.append(f"lignes {analyse['lignes_total']} != manifest {entree['rows']}")
    controles.append({"id": id_, "ok": ok, "message": "; ".join(msgs) or "conforme au manifest"})
    return entree


def inventorier(racine, cfg, complements=None):
    c = cfg
    snap = os.path.join(racine, c["chemins"]["snapshots"]) if not os.path.isabs(c["chemins"]["snapshots"]) else c["chemins"]["snapshots"]
    controles, anomalies = [], []
    manifest = {"version_regles": c["version_regles"], "version_script": VERSION_SCRIPT,
                "saisons": c["saisons"], "competitions": {}}
    analyses = {}
    for saison in c["saisons"]:
        dossier = os.path.join(snap, saison)
        marq = os.path.exists(os.path.join(dossier, "_SNAPSHOT_COMPLETE.json"))
        controles.append({"id": f"snapshot_complet:{saison}", "ok": marq,
                          "message": "marqueur _SNAPSHOT_COMPLETE present" if marq else "marqueur absent"})
        mans = {}
        for nom, rel in (("europe", c["chemins"]["europe"]), ("extras", c["chemins"]["extras"])):
            base = dossier if nom == "europe" else os.path.join(dossier, "nouvelles_ligues")
            mp = os.path.join(base, "manifest.json")
            mans[nom] = _json(mp) if os.path.exists(mp) else {}
            if not mans[nom]:
                controles.append({"id": f"manifest:{saison}:{nom}", "ok": False, "message": "manifest.json absent"})
        for type_, codes, rel in (("europe", c["competitions_europe"], c["chemins"]["europe"]),
                                  ("extras", c["competitions_extra"], c["chemins"]["extras"])):
            for code in codes:
                comp = manifest["competitions"].setdefault(code, {"type": type_, "saisons": {}})
                chemin = os.path.join(dossier, rel, code + ".csv")
                ident = f"{code}:{saison}"
                if not os.path.exists(chemin):
                    controles.append({"id": f"archive_presente:{ident}", "ok": False, "message": "fichier absent"})
                    comp["saisons"][saison] = {"presente": False}
                    analyses[(code, saison)] = None
                    continue
                an, anos = analyser_fichier(chemin, c, _annees(saison, mans[type_].get("files", {}).get(code), type_), div_attendu=code if type_ == "europe" else None)
                entree = mans[type_].get("files", {}).get(code)
                _controle_manifest(entree, chemin, an, f"manifest_conforme:{ident}", controles)
                for a in anos:
                    a.update({"competition": code, "saison": saison})
                anomalies.extend(anos)
                meta = {}
                if entree:
                    for k in ("season_label", "season_format", "competition", "country"):
                        if k in entree:
                            meta[k] = entree[k]
                cel = {
                    "presente": True, "chemin": os.path.relpath(chemin, snap), "sha256": an["sha256"], "octets": an["octets"],
                    "encodage": an["encodage"], "lignes_mesurees": an["lignes_total"],
                    "lignes_avec_score": an["lignes_avec_score"],
                    "lignes_sans_score": an["lignes_total"] - an["lignes_avec_score"],
                    "lignes_vides_ignorees": an["lignes_vides"], "colonnes_sans_nom": an["colonnes_sans_nom"],
                    "meta_manifest": meta, "colonnes": an["colonnes"],
                    "editions": {},
                }
                for ed, e in an["editions"].items():
                    cel["editions"][ed] = {k: e[k] for k in ("lignes", "lignes_avec_score", "lignes_sans_score_vide",
                                                            "lignes_sans_score_invalide", "premiere_date", "derniere_date")}
                    cel["editions"][ed]["nb_equipes"] = len(e["equipes"])
                    cel["editions"][ed]["colonnes"] = {k: {"etat": ("absente" if False else
                                                             ("presente_vide" if v["valides_joues"] == 0 else
                                                              ("complete" if v["valides_joues"] == e["lignes_avec_score"] else "partielle"))),
                                                           "valides_joues": v["valides_joues"], "valides_total": v["valides_total"],
                                                           "invalides": v["invalides"]} for k, v in e["colonnes"].items()}
                    cel["editions"][ed]["coherence"] = e["coherence"]
                cel["etat_colonnes"] = {k: etat_colonne(an, k, c) for k in an["colonnes"]}
                if len(an["editions"]) > 1:
                    anomalies.append({"type": "editions_multiples", "severite": "info", "competition": code, "saison": saison,
                                      "edition": None, "nombre": len(an["editions"]), "exemples": [{"detail": k} for k in sorted(an["editions"])],
                                      "message": "plusieurs editions dans un meme fichier: traitees separement, jamais fusionnees"})
                comp["saisons"][saison] = cel
                analyses[(code, saison)] = an
                analyses[(code, saison)]["_equipes"] = {ed: e["equipes"] for ed, e in an["editions"].items()}
    # formats / changements d'identite entre saisons
    for code, comp in manifest["competitions"].items():
        fmt = {}
        prec = None
        for s in c["saisons"]:
            cel = comp["saisons"].get(s)
            if not cel or not cel.get("presente"):
                continue
            eds = sorted(cel["editions"])
            fmt[s] = {"lignes_mesurees": cel["lignes_mesurees"], "lignes_avec_score": cel["lignes_avec_score"],
                      "editions": eds, "nb_equipes": sum(v["nb_equipes"] for v in cel["editions"].values()),
                      "libelle": cel["meta_manifest"].get("competition"), "format_saison": cel["meta_manifest"].get("season_format")}
        vals = list(fmt.values())
        comp["historique_format"] = fmt
        if vals and (len({v["lignes_avec_score"] for v in vals}) > 1 or len({tuple(v["editions"]) for v in vals}) > 1
                     or len({v["libelle"] for v in vals}) > 1):
            anomalies.append({"type": "format_ou_edition_variable", "severite": "info", "competition": code, "saison": None,
                              "edition": None, "nombre": len(vals),
                              "exemples": [{"detail": f"{s}: {v['lignes_avec_score']} matchs, {v['nb_equipes']} equipes, editions={v['editions']}, libelle={v['libelle']}"} for s, v in fmt.items()],
                              "message": "format/edition/libelle different entre saisons: segmentation historique a examiner (aucune fusion automatique)"})
        for s1, s2 in zip(c["saisons"], c["saisons"][1:]):
            a1, a2 = analyses.get((code, s1)), analyses.get((code, s2))
            if not a1 or not a2:
                continue
            e1 = set().union(*a1["_equipes"].values()) if a1["_equipes"] else set()
            e2 = set().union(*a2["_equipes"].values()) if a2["_equipes"] else set()
            cand = candidats_changement_de_nom(e1 - e2, e2 - e1, c["longueur_min_prefixe_nom"])
            if cand:
                anomalies.append({"type": "changement_nom_possible", "severite": "a_verifier", "competition": code,
                                  "saison": f"{s1}->{s2}", "edition": None, "nombre": len(cand),
                                  "exemples": [{"detail": f"{a} -> {b}"} for a, b in cand], "message":
                                  "noms proches entre sortants et entrants: identites NON fusionnees, a confirmer manuellement"})
    # profils
    profils = {"version_regles": c["version_regles"], "version_script": VERSION_SCRIPT, "regle_statuts": c["statuts"],
               "competitions": {}}
    for code, comp in manifest["competitions"].items():
        cellules = [(s, analyses.get((code, s))) for s in c["saisons"]]
        capa = {n: evaluer_capacite(n, d, cellules, c) for n, d in c["capacites"].items()}
        jouees = sum((comp["saisons"].get(s) or {}).get("lignes_avec_score", 0) for s in c["saisons"])
        mesurees = sum((comp["saisons"].get(s) or {}).get("lignes_mesurees", 0) for s in c["saisons"])
        profils["competitions"][code] = {
            "type": comp["type"], "lignes_mesurees": mesurees, "lignes_avec_score": jouees, "lignes_sans_score": mesurees - jouees,
            "capacites": capa,
            "resume": dict(Counter(v["statut"] for v in capa.values())),
            "complements_manuels": [],
        }
    if complements:
        _appliquer_complements(complements, profils, manifest, c, controles)
    return manifest, profils, anomalies, controles


def _json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _annees(saison, entree, type_):
    a = 2000 + int(saison[:2]); b = 2000 + int(saison[2:])
    if type_ == "extras" and entree and entree.get("season_format") == "civile":
        return (a, a)
    return (a, b)


def _appliquer_complements(compl, profils, manifest, cfg, controles):
    """Les complements manuels sont DECLARES et tracables; ils ne modifient ni les archives ni le statut automatique."""
    for i, e in enumerate(compl.get("complements", [])):
        code = e.get("competition")
        ok = code in profils["competitions"] and all(k in e for k in ("saison", "colonnes", "source", "date_ajout"))
        controles.append({"id": f"complement_manuel:{i}", "ok": bool(ok),
                          "message": "declare" if ok else "entree invalide (competition, saison, colonnes, source, date_ajout requis)"})
        if ok:
            profils["competitions"][code]["complements_manuels"].append(e)


# ---------- rapport ----------
def rapport_md(manifest, profils, anomalies, controles, empreintes):
    L = ["# Rapport d'inventaire Football-Data", "",
         f"- Version regles: `{manifest['version_regles']}` | script: `{manifest['version_script']}`",
         f"- Empreinte script: `{empreintes['script_sha256']}`", f"- Empreinte config: `{empreintes['config_sha256']}`",
         f"- Empreinte archives avant: `{empreintes['archives_avant']['sha256']}` ({empreintes['archives_avant']['fichiers']} fichiers)",
         f"- Empreinte archives apres: `{empreintes['archives_apres']['sha256']}`", "",
         "## Controles bloquants", ""]
    ko = [x for x in controles if not x["ok"]]
    L.append(f"- {len(controles)} controles, {len(ko)} en echec")
    for x in ko[:50]:
        L.append(f"  - {x['id']}: {x['message']}")
    L += ["", "## Competitions (lignes mesurees vs lignes avec score)", "",
          "| Code | Mesurees | Avec score | Sans score | Confirmees | Limitees | Inexploitables |", "|---|---|---|---|---|---|---|"]
    for code in sorted(profils["competitions"]):
        p = profils["competitions"][code]; r = p["resume"]
        L.append(f"| {code} | {p['lignes_mesurees']} | {p['lignes_avec_score']} | {p['lignes_sans_score']} | "
                 f"{r.get('CAPACITE_CONFIRMEE',0)} | {r.get('CAPACITE_LIMITEE',0)} | {r.get('CAPACITE_INEXPLOITABLE',0)} |")
    L += ["", "## Statuts par capacite", ""]
    caps = list(next(iter(profils["competitions"].values()))["capacites"]) if profils["competitions"] else []
    L += ["| Code | " + " | ".join(caps) + " |", "|---|" + "---|" * len(caps)]
    abr = {"CAPACITE_CONFIRMEE": "C", "CAPACITE_LIMITEE": "L", "CAPACITE_INEXPLOITABLE": "X"}
    for code in sorted(profils["competitions"]):
        L.append(f"| {code} | " + " | ".join(abr[profils['competitions'][code]['capacites'][k]['statut']] for k in caps) + " |")
    L += ["", "C = confirmee, L = limitee, X = inexploitable. Details et raisons: `profils_capacite.json`.", "",
          "## Anomalies (comptage par type)", ""]
    cnt = Counter((a["type"].split(":")[0], a["severite"]) for a in anomalies)
    for (t, s), n in sorted(cnt.items()):
        L.append(f"- {t} ({s}): {n}")
    L.append("")
    return "\n".join(L)


# ---------- principal ----------
def ecrire_json(chemin, obj):
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=".")
    ap.add_argument("--config", default="config/inventaire_regles.json")
    ap.add_argument("--complements", default="data/inventaire/complements_manuels.json")
    ap.add_argument("--sortie", default="data/inventaire")
    a = ap.parse_args(argv)
    cfg = charger_config(os.path.join(a.racine, a.config))
    compl = None
    cp = os.path.join(a.racine, a.complements)
    if os.path.exists(cp):
        compl = _json(cp)
    snap = os.path.join(a.racine, cfg["chemins"]["snapshots"])
    avant = empreinte_arbre(snap)
    manifest, profils, anomalies, controles = inventorier(a.racine, cfg, compl)
    apres = empreinte_arbre(snap)
    controles.append({"id": "integrite_archives_avant_apres", "ok": avant == apres,
                      "message": "inchangees" if avant == apres else "ARCHIVES MODIFIEES PENDANT L'EXECUTION"})
    n_att = len(cfg["competitions_europe"]) + len(cfg["competitions_extra"])
    controles.append({"id": "couverture_38x5", "ok": sum(1 for c in manifest["competitions"].values() for s in c["saisons"].values() if s.get("presente")) == n_att * len(cfg["saisons"]),
                      "message": f"{n_att} competitions x {len(cfg['saisons'])} saisons attendues"})
    emp = {"script_sha256": sha256_fichier(os.path.abspath(__file__)),
           "config_sha256": sha256_fichier(os.path.join(a.racine, a.config)),
           "archives_avant": avant, "archives_apres": apres}
    anomalies.sort(key=lambda x: (x.get("competition") or "", str(x.get("saison")), x["type"], str(x.get("edition"))))
    echecs = [x for x in controles if not x["ok"]]
    sortie = os.path.join(a.racine, a.sortie)
    os.makedirs(sortie, exist_ok=True)
    ecrire_json(os.path.join(sortie, "anomalies.json"), {"version_regles": cfg["version_regles"], "controles": controles, "anomalies": anomalies})
    publication = not echecs
    if publication:
        manifest["empreintes"] = emp
        profils["empreintes"] = emp
        ecrire_json(os.path.join(sortie, "manifest_global.json"), manifest)
        ecrire_json(os.path.join(sortie, "profils_capacite.json"), profils)
        with open(os.path.join(sortie, "rapport_inventaire.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(rapport_md(manifest, profils, anomalies, controles, emp))
    else:
        for nom in ("manifest_global.json", "profils_capacite.json", "rapport_inventaire.md"):
            p = os.path.join(sortie, nom)
            if os.path.exists(p):
                os.remove(p)
    ecrire_json(os.path.join(sortie, "dernier_run.json"), {
        "execute_le_utc": datetime.now(timezone.utc).isoformat(), "publication": publication,
        "controles_total": len(controles), "controles_en_echec": [x for x in echecs],
        "anomalies_total": len(anomalies), "commit": os.environ.get("GITHUB_SHA"), **emp})
    print(json.dumps({"publication": publication, "echecs": len(echecs), "anomalies": len(anomalies)}))
    return 0 if publication else 1


if __name__ == "__main__":
    sys.exit(main())
