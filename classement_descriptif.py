#!/usr/bin/env python3
"""Classement DESCRIPTIF des 38 profils. Trois dimensions separees (couverture, fiabilite, volume), aucun score global,
aucune recommandation de marche, aucun modele predictif. Lit les sorties de l'inventaire et les CSV (structure des saisons)."""
import argparse, csv, json, os, sys
from collections import Counter, defaultdict

VERSION = "1.0.0"
ENTREE = lambda d, n: os.path.join(d, n)


def lire_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def structure_saison(chemin):
    """Par edition: equipes, lignes, paires (dom, ext) manquantes et en double. Observation brute."""
    with open(chemin, "rb") as f:
        brut = f.read()
    try:
        txt = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = brut.decode("latin-1")
    rd = csv.DictReader(txt.splitlines())
    eds = defaultdict(list)
    for r in rd:
        h = (r.get("HomeTeam") or r.get("Home") or "").strip()
        a = (r.get("AwayTeam") or r.get("Away") or "").strip()
        if not h or not a:
            continue
        eds[(r.get("League") or r.get("Div") or "").strip()].append((h, a))
    out = {}
    for ed, paires in sorted(eds.items()):
        eq = sorted({x for p in paires for x in p})
        n = len(eq)
        cnt = Counter(paires)
        manquantes = sum(1 for h in eq for a in eq if h != a and (h, a) not in cnt)
        doubles = sum(1 for v in cnt.values() if v > 1)
        out[ed] = {"equipes": n, "lignes": len(paires), "aller_retour_theorique": n * (n - 1),
                   "paires_manquantes": manquantes, "paires_en_double": doubles,
                   "structure": "ALLER_RETOUR_COMPLET" if (len(paires) == n * (n - 1) and not manquantes and not doubles) else "ECART_STRUCTURE"}
    return out


def statut_completude(code, saison, struct, verifs):
    v = verifs.get((code, saison))
    if not v:
        return "COMPLETUDE_NON_VERIFIEE", None
    eq = sum(e["equipes"] for e in struct.values())
    ml = sum(e["lignes"] for e in struct.values())
    ok = (eq == v["equipes_attendues"] and ml == v["matchs_attendus"])
    return ("COMPLETUDE_VERIFIEE" if ok else "COMPLETUDE_INCOHERENTE"), v["preuves"]


def couverture(prof):
    res = {}
    for nom, cap in prof["capacites"].items():
        taux, non_valides = [], 0
        parsaison = defaultdict(list)
        for col, d in cap["detail"].items():
            for s, x in d["par_saison"].items():
                if x.get("taux") is not None:
                    taux.append(x["taux"])
                parsaison[s].append(x.get("lignes_non_valides", 0))
        non_valides = sum(max(v) for v in parsaison.values())
        res[nom] = {"statut": cap["statut"], "taux_min_observe": min(taux) if taux else None,
                    "lignes_non_renseignees_pire_colonne_par_saison_cumul": non_valides, "usage": cap["usage"]}
    return res


def classer(dossier_inv, snapshots, cfg):
    man = lire_json(ENTREE(dossier_inv, "manifest_global.json"))
    prof = lire_json(ENTREE(dossier_inv, "profils_capacite.json"))
    ano = lire_json(ENTREE(dossier_inv, "anomalies.json"))["anomalies"]
    vp = ENTREE(dossier_inv, "verifications_completude.json")
    verifs = {(v["competition"], v["saison"]): v for v in lire_json(vp)["verifications"]} if os.path.exists(vp) else {}
    par_comp = defaultdict(list)
    for a in ano:
        par_comp[a.get("competition")].append(a)
    sortie = {"version_classement": VERSION, "version_regles": man["version_regles"], "competitions": {}}
    for code in cfg["competitions_europe"] + cfg["competitions_extra"]:
        eu = code in cfg["competitions_europe"]
        comp = man["competitions"][code]
        p = prof["competitions"][code]
        saisons = {}
        for s in cfg["saisons"]:
            cel = comp["saisons"][s]
            chemin = os.path.join(snapshots, s, "raw" if eu else "nouvelles_ligues/raw", code + ".csv")
            struct = structure_saison(chemin)
            st, preuves = statut_completude(code, s, struct, verifs)
            saisons[s] = {"lignes_mesurees": cel["lignes_mesurees"], "lignes_avec_score": cel["lignes_avec_score"],
                          "structure": struct, "completude": st, "preuves_completude": preuves}
        cat = Counter()
        doublons = 0
        for a in par_comp.get(code, []):
            t = a["type"].split(":")[0]
            if a.get("categorie") in ("erreur_donnee", "code_remplissage"):
                cat[a["categorie"]] += a["nombre"]
            if t.startswith("doublon") or t in ("equipe_deux_matchs_meme_jour",):
                doublons += a["nombre"]
        joues = p["lignes_avec_score"]
        par_saison_matchs = {s: saisons[s]["lignes_avec_score"] for s in cfg["saisons"]}
        indices = []
        if len(set(par_saison_matchs.values())) > 1:
            indices.append("nombre de matchs different selon les saisons: " + json.dumps(par_saison_matchs, sort_keys=True))
        if any(len(saisons[s]["structure"]) > 1 for s in saisons):
            indices.append("plusieurs editions dans un meme fichier: " + json.dumps({s: sorted(saisons[s]["structure"]) for s in saisons if len(saisons[s]["structure"]) > 1}, sort_keys=True))
        libs = {s: comp["saisons"][s]["meta_manifest"].get("competition") for s in cfg["saisons"]}
        if len(set(libs.values())) > 1:
            indices.append("libelle de competition different selon les saisons: " + json.dumps(libs, sort_keys=True))
        ecarts = [s for s in cfg["saisons"] if any(e["structure"] == "ECART_STRUCTURE" for e in saisons[s]["structure"].values())]
        if ecarts:
            indices.append("structure aller-retour simple non respectee: " + ",".join(ecarts))
        comp_st = {s: saisons[s]["completude"] for s in saisons}
        sortie["competitions"][code] = {
            "type": "europe" if eu else "hors_europe",
            "volume": {"matchs_avec_score": joues, "lignes_mesurees": p["lignes_mesurees"],
                       "saisons_avec_matchs": sum(1 for v in par_saison_matchs.values() if v > 0),
                       "matchs_par_saison": par_saison_matchs,
                       "equipes_par_saison": {s: sum(e["equipes"] for e in saisons[s]["structure"].values()) for s in saisons}},
            "couverture": couverture(p),
            "signature_couverture": "".join({"CAPACITE_CONFIRMEE": "C", "CAPACITE_LIMITEE": "L", "CAPACITE_INEXPLOITABLE": "X"}[v["statut"]]
                                            for v in p["capacites"].values()),
            "fiabilite": {"erreurs_donnee_cas": cat["erreur_donnee"], "codes_remplissage_cas": cat["code_remplissage"],
                          "doublons_cas": doublons,
                          "erreurs_et_codes_pour_1000_matchs": round(1000 * (cat["erreur_donnee"] + cat["code_remplissage"]) / joues, 3) if joues else None,
                          "candidats_changement_de_nom_non_fusionnes": sum(a["nombre"] for a in par_comp.get(code, []) if a["type"] == "changement_nom_possible")},
            "indices_segmentation_historique": indices,
            "completude_par_saison": comp_st,
            "comparable_sans_reserve": all(v == "COMPLETUDE_VERIFIEE" for v in comp_st.values()),
        }
    return sortie


def rapport(sortie, noms_capacites):
    C = sortie["competitions"]
    L = ["# Classement descriptif des 38 profils", "",
         f"Regles inventaire `{sortie['version_regles']}`. Trois dimensions SEPAREES; aucun score global; aucun statut n'est une recommandation de marche.", "",
         "**Ce classement decrit la disponibilite et la coherence des donnees. Ce n'est PAS un classement de performance predictive.**", "",
         "## Avertissement completude", "",
         "La completude reelle d'une saison (nombre d'equipes et de matchs attendus) n'est verifiee que si une verification externe est enregistree dans `verifications_completude.json`. "
         "Sinon: `COMPLETUDE_NON_VERIFIEE`. Une structure aller-retour complete dans l'archive est coherente mais ne prouve pas qu'aucune equipe n'a ete oubliee.", ""]
    v = [f"{c}:{s}" for c in C for s, st in C[c]["completude_par_saison"].items() if st == "COMPLETUDE_VERIFIEE"]
    L.append(f"- Saisons verifiees: {len(v)} sur {len(C) * 5} ({', '.join(v) or 'aucune'})")
    L.append(f"- **Competitions comparables sans reserve: {sum(1 for c in C.values() if c['comparable_sans_reserve'])} sur {len(C)}**")
    L += ["", "## Volume (tri: matchs avec score decroissant)", "", "| Code | Matchs avec score | Saisons | Matchs/saison (min-max) |", "|---|---|---|---|"]
    for c in sorted(C, key=lambda k: -C[k]["volume"]["matchs_avec_score"]):
        m = C[c]["volume"]["matchs_par_saison"].values()
        L.append(f"| {c} | {C[c]['volume']['matchs_avec_score']} | {C[c]['volume']['saisons_avec_matchs']} | {min(m)}-{max(m)} |")
    L += ["", "## Couverture (signature par capacite; tri: nb de capacites confirmees decroissant, puis signature)", "",
          "Ordre des lettres: " + ", ".join(noms_capacites) + ". C = confirmee, L = limitee, X = inexploitable.", "",
          "| Code | Signature | Capacites C | Taux minimum observe (hors X) |", "|---|---|---|---|"]
    for c in sorted(C, key=lambda k: (-C[k]["signature_couverture"].count("C"), C[k]["signature_couverture"], k)):
        taux = [x["taux_min_observe"] for x in C[c]["couverture"].values() if x["statut"] != "CAPACITE_INEXPLOITABLE" and x["taux_min_observe"] is not None]
        L.append(f"| {c} | {C[c]['signature_couverture']} | {C[c]['signature_couverture'].count('C')} | {min(taux):.4f} |" if taux else f"| {c} | {C[c]['signature_couverture']} | {C[c]['signature_couverture'].count('C')} | - |")
    fam = defaultdict(list)
    for c in C:
        fam[C[c]["signature_couverture"]].append(c)
    L += ["", "## Familles (memes statuts de capacite; regroupement exact, sans seuil)", ""]
    for sig, cs in sorted(fam.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        L.append(f"- `{sig}` : {', '.join(sorted(cs))}")
    L += ["", "## Fiabilite (cas d'erreurs de donnees + codes de remplissage pour 1000 matchs, croissant)", "",
          "| Code | Erreurs de donnees | Codes de remplissage | Doublons | Pour 1000 matchs | Noms a verifier |", "|---|---|---|---|---|---|"]
    for c in sorted(C, key=lambda k: (C[k]["fiabilite"]["erreurs_et_codes_pour_1000_matchs"] or 0, k)):
        f = C[c]["fiabilite"]
        L.append(f"| {c} | {f['erreurs_donnee_cas']} | {f['codes_remplissage_cas']} | {f['doublons_cas']} | {f['erreurs_et_codes_pour_1000_matchs']} | {f['candidats_changement_de_nom_non_fusionnes']} |")
    L += ["", "## Indices de segmentation historique (a examiner; aucune fusion d'editions ni d'identites)", ""]
    for c in sorted(C):
        for i in C[c]["indices_segmentation_historique"]:
            L.append(f"- {c}: {i}")
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--racine", default=".")
    ap.add_argument("--config", default="config/inventaire_regles.json")
    ap.add_argument("--inventaire", default="data/inventaire")
    a = ap.parse_args(argv)
    cfg = lire_json(os.path.join(a.racine, a.config))
    inv = os.path.join(a.racine, a.inventaire)
    sortie = classer(inv, os.path.join(a.racine, cfg["chemins"]["snapshots"]), cfg)
    noms = list(cfg["capacites"])
    with open(os.path.join(inv, "classement_descriptif.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=1, sort_keys=True); f.write("\n")
    with open(os.path.join(inv, "classement_descriptif.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(rapport(sortie, noms))
    inco = [f"{c}:{s}" for c, v in sortie["competitions"].items() for s, st in v["completude_par_saison"].items() if st == "COMPLETUDE_INCOHERENTE"]
    print(json.dumps({"competitions": len(sortie["competitions"]), "completude_incoherente": inco}))
    return 1 if inco else 0


if __name__ == "__main__":
    sys.exit(main())
