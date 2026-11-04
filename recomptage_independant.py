#!/usr/bin/env python3
"""Recomptage INDEPENDANT des colonnes, directement depuis les CSV sources.

N'importe rien de inventaire_football_data.py: lecture (csv), classification des valeurs et comptages
sont reecrits ici. Compare ensuite aux comptages de manifest_global.json et liste les ecarts.
Sorties: recomptage_independant.json, recomptage_rapport.md
"""
import csv, json, os, re, sys, argparse

NON_COTES = {"Div", "Date", "Time", "HomeTeam", "AwayTeam", "Home", "Away", "Country", "League", "Season", "Referee",
             "Attendance", "FTR", "HTR", "Res"}
ENTIERES = {"FTHG", "FTAG", "HG", "AG", "HTHG", "HTAG", "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"}
VIDES = {"", "NA", "N/A", "NULL", "-", "NaN"}


def type_colonne(nom):
    if nom in ENTIERES:
        return "entier"
    if nom in NON_COTES:
        return "texte"
    if nom.endswith("AHH") or nom.endswith("AHA"):
        return "cote_handicap"
    if nom.endswith(">2.5") or nom.endswith("<2.5"):
        return "cote_decimale"
    if len(nom) >= 2 and nom[-1] in "HDA" and nom[0].isupper() or (nom[:3] == "1XB" and nom[-1] in "HDA"):
        return "cote_decimale"
    return "autre"


def classer(nom, v):
    """-> 'valide' | 'code' | 'erreur' pour une valeur NON vide."""
    t = type_colonne(nom)
    if t in ("texte", "autre"):
        return "valide"
    try:
        x = float(v)
    except ValueError:
        return "code"
    if t == "entier":
        return "valide" if (x >= 0 and x == round(x)) else "erreur"
    if x == 0:
        return "code"
    if t == "cote_handicap":
        return "valide" if x > 0 else "erreur"
    return "valide" if x > 1 else "erreur"


def entier_ok(v):
    try:
        x = float(v)
    except ValueError:
        return False
    return x >= 0 and x == round(x)


def lire(chemin):
    raw = open(chemin, "rb").read()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = raw.decode("latin-1")
    rd = csv.reader(txt.splitlines())
    ent = next(rd)
    rows = [(i + 2, r) for i, r in enumerate(rd)]
    return [h.strip() for h in ent], rows


def recompter_fichier(chemin):
    ent, rows = lire(chemin)
    pos = {h: i for i, h in enumerate(ent) if h}
    hg = "FTHG" if "FTHG" in pos else "HG"
    ag = "FTAG" if "FTAG" in pos else "AG"
    total = joues = 0
    cols = {h: dict(valides_joues=0, valides_total=0, manquantes_joues=0, manquantes_total=0, code=0, erreur=0,
                    lignes_manquantes_joues=[], lignes_code=[], lignes_erreur=[]) for h in pos}
    for nl, r in rows:
        if not any(c.strip() for c in r):
            continue
        total += 1
        g = lambda h: r[pos[h]].strip() if pos[h] < len(r) else ""
        a_score = entier_ok(g(hg)) and entier_ok(g(ag))
        joues += a_score
        for h in pos:
            v = g(h)
            c = cols[h]
            if v in VIDES:
                c["manquantes_total"] += 1
                if a_score:
                    c["manquantes_joues"] += 1
                    c["lignes_manquantes_joues"].append(nl)
                continue
            k = classer(h, v)
            if k == "valide":
                c["valides_total"] += 1
                c["valides_joues"] += a_score
            elif k == "code":
                c["code"] += 1; c["lignes_code"].append(nl)
            else:
                c["erreur"] += 1; c["lignes_erreur"].append(nl)
    return {"lignes": total, "joues": joues, "colonnes": cols}, ent, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", default="data/football_data/snapshots")
    ap.add_argument("--config", default="config/inventaire_regles.json")
    ap.add_argument("--manifest", default="data/inventaire/manifest_global.json")
    ap.add_argument("--sortie", default="data/inventaire")
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config, encoding="utf-8"))
    man = json.load(open(a.manifest, encoding="utf-8"))
    res, ecarts = {}, []
    n_cmp = 0
    for code in cfg["competitions_europe"] + cfg["competitions_extra"]:
        eu = code in cfg["competitions_europe"]
        for s in cfg["saisons"]:
            p = os.path.join(a.snapshots, s, "raw" if eu else "nouvelles_ligues/raw", code + ".csv")
            rc, ent, rows = recompter_fichier(p)
            res.setdefault(code, {})[s] = {"lignes": rc["lignes"], "joues": rc["joues"],
                                           "colonnes": {h: {k: v for k, v in c.items() if not k.startswith("lignes_")}
                                                        for h, c in rc["colonnes"].items()}}
            cel = man["competitions"][code]["saisons"][s]
            ident = f"{code}:{s}"
            for nom, mine, theirs in (("lignes_mesurees", rc["lignes"], cel["lignes_mesurees"]),
                                      ("lignes_avec_score", rc["joues"], cel["lignes_avec_score"])):
                n_cmp += 1
                if mine != theirs:
                    ecarts.append({"cellule": ident, "colonne": None, "champ": nom, "recompte": mine, "inventaire": theirs})
            inv = {}
            for e in cel["editions"].values():
                for h, st in e["colonnes"].items():
                    d = inv.setdefault(h, dict(valides_joues=0, valides_total=0, invalides=0, manquantes_joues=0))
                    for k in d:
                        d[k] += st.get(k, 0)
            for h, c in rc["colonnes"].items():
                if h not in inv:
                    ecarts.append({"cellule": ident, "colonne": h, "champ": "colonne_absente_de_inventaire"})
                    continue
                for champ, mine, theirs in (("valides_joues", c["valides_joues"], inv[h]["valides_joues"]),
                                            ("valides_total", c["valides_total"], inv[h]["valides_total"]),
                                            ("invalides", c["code"] + c["erreur"], inv[h]["invalides"]),
                                            ("manquantes_joues", c["manquantes_joues"], inv[h].get("manquantes_joues", 0))):
                    n_cmp += 1
                    if mine != theirs:
                        ecarts.append({"cellule": ident, "colonne": h, "champ": champ, "recompte": mine, "inventaire": theirs})
            # verifications ciblees
            if "HST" in rc["colonnes"]:
                idx = {h: i for i, h in enumerate(ent) if h}
                bad = []
                for nl, r in rows:
                    for t, sh in (("HST", "HS"), ("AST", "AS")):
                        try:
                            if float(r[idx[t]]) > float(r[idx[sh]]):
                                bad.append({"ligne": nl, "ligne_source": ",".join(r)[:200], "regle": f"{t}>{sh}"})
                        except (ValueError, IndexError, KeyError):
                            pass
                if bad:
                    res[code][s]["tirs_cadres_superieurs_aux_tirs"] = bad
    out = {"comparaisons": n_cmp, "ecarts": ecarts, "nb_ecarts": len(ecarts), "recomptage": res}
    os.makedirs(a.sortie, exist_ok=True)
    with open(os.path.join(a.sortie, "recomptage_independant.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    print(json.dumps({"comparaisons": n_cmp, "ecarts": len(ecarts)}))
    return 0 if not ecarts else 1


if __name__ == "__main__":
    sys.exit(main())
