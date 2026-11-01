"""Classement du rejeu Omega / Alpha (LECTURE SEULE). Compare, match par match et marché par marché, les fiches gelées aux rejeux sous trois lectures :
  L  = troncature seule (lignes manquantes ajoutées depuis d'autres blocs du même club, même compétition, identifiant de l'URL équipe),
  S  = auto-références seules (lignes dont l'adversaire est l'équipe elle-même retirées),
  LS = les deux.
Classes : inchangé · probabilité modifiée (Alpha : valeur modifiée) · sélection supprimée · sélection ajoutée · non reproductible · indéterminé.
Usage : python classer.py <dossier_travail> <racine_depot> <sortie_dir>"""
import gzip, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path

W = Path(sys.argv[1]); RACINE = Path(sys.argv[2]); SORTIE = Path(sys.argv[3])
sys.path.insert(0, str(RACINE))
import bilan_reel as BR
from moteur_omega import marches as MO
from alpha_serie import suivi as AS

VARIANTES = ("L", "S", "LS")
commits = json.load(open(W / "commits.json"))


def empreinte(lignes):
    return hashlib.sha1(json.dumps(sorted((str(m.get("date"))[:10], bool(m.get("domicile")), m.get("buts_marques"), m.get("buts_encaisses"), str(m.get("adversaire"))) for m in lignes or []), ensure_ascii=False).encode()).hexdigest()[:12]


def fichier(moteur, ts, v):
    return W / (f"a0_{moteur}_{ts.replace(':', '')}.json" if v == "A0" else f"v_{moteur}_{ts.replace(':', '')}_{v}.json")


_cache = {}
def charge(moteur, ts, v):
    k = (moteur, ts, v)
    if k not in _cache:
        _cache[k] = json.load(open(fichier(moteur, ts, v)))
    return _cache[k]


_infos = {}
def infos(c):
    if c not in _infos:
        _infos[c] = json.load(open(W / f"t_{c}" / "info_blocs.json"))
    return _infos[c]


def cotes_du_bloc(moteur, ts, mid):
    """Drapeaux de blocs du match tels que consommés par le moteur (retrouvés par l'empreinte des lignes lues au rejeu A0)."""
    c = commits[f"{moteur}|{ts}"]
    b = charge(moteur, ts, "A0")["blocs"].get(mid)
    cand = infos(c).get(mid) or []
    if b is None:
        return None
    for x in cand:
        if x["dom"]["empreinte"] == empreinte(b["dom"]) and x["ext"]["empreinte"] == empreinte(b["ext"]):
            return {"dom": {k: x["dom"][k] for k in ("sans_id", "n_lignes", "n_auto_references", "n_manquantes", "n_conflits")},
                    "ext": {k: x["ext"][k] for k in ("sans_id", "n_lignes", "n_auto_references", "n_manquantes", "n_conflits")}}
    return None


# --- paris / marchés d'une fiche -------------------------------------------------------------------------------------------------------------
def paris_omega_fiche(f):
    if not f or f.get("statut") != "analyse":
        return {}
    out = {}
    for rang, p in [("principal", f.get("principal"))] + [("autre", x) for x in f.get("autres") or []]:
        if p:
            out[json.dumps(p["cle"])] = {"rang": rang, "p": p["p"], "p_modele": p["p_modele"], "cote": p["cote"], "cle": p["cle"]}
    return out


def marches_alpha_fiche(onglets):
    out = {}
    for cat, src, i, s, tete in BR.marches_affiches(onglets):
        out[cat + "|" + json.dumps(s["cle"])] = {"cat": cat, "src": src, "i": i, "valeur": s.get("valeur"), "cote": s.get("cote"), "tete": tete, "cle": s["cle"]}
    return out


def etat(gel, var, cle_cmp):
    """Classe d'un marché : inchangé / modifié / supprimé / ajouté."""
    if gel is None:
        return "ajoutée"
    if var is None:
        return "supprimée"
    return "inchangé" if all(gel.get(k) == var.get(k) for k in cle_cmp) else "modifiée"


def classe_match(etats, flags_v, v, sides_ok):
    if "supprimée" in etats:
        return "sélection supprimée"
    if "modifiée" in etats:
        return "probabilité modifiée"
    if "ajoutée" in etats:
        return "sélection ajoutée"
    # aucun écart : on ne peut affirmer « inchangé » que si les deux historiques ont pu être examinés (L et LS exigent un identifiant de club et aucun conflit)
    if "L" in v and not sides_ok:
        return "indéterminé"
    return "inchangé"


def sides_ok(fl):
    return bool(fl) and all(not fl[c]["sans_id"] and fl[c]["n_conflits"] == 0 for c in ("dom", "ext"))


def gagne_omega(cle, score):
    t = MO.test_du_marche(*cle)
    return None if t is None else bool(t(score[0], score[1]))


def gagne_alpha(cle, score):
    return AS._gagne(cle, score["buts_dom"], score["buts_ext"])


def traiter(moteur):
    fich = RACINE / ("data/omega/journal.jsonl" if moteur == "omega" else "data/alpha_serie/journal.jsonl")
    L = BR._lire(fich)
    ko = (lambda l: (l.get("fiche") or {}).get("coup_d_envoi_utc")) if moteur == "omega" else (lambda l: l.get("coup_d_envoi_utc"))
    gels = BR.gels_valides(L, ko)
    toutes = Counter(l["match_id"] for l in L if l.get("type") == "pronostic")
    res = {l["match_id"]: l for l in L if l.get("type") == "resultat"}
    rows = []
    for mid, g in gels.items():
        ts = g["gele_le"]
        if f"{moteur}|{ts}" not in commits:
            rows.append({"mid": mid, "classe": {v: "non reproductible" for v in VARIANTES}, "raison": "gel sans commit retrouvé"}); continue
        a0 = charge(moteur, ts, "A0")["fiches"].get(mid)
        fiche_g = g["fiche"] if moteur == "omega" else {k: g[k] for k in ("match_id", "coup_d_envoi_utc", "date", "competition", "domicile", "exterieur", "k", "onglets")}
        if moteur == "omega":
            repro = a0 is not None and json.dumps(a0, sort_keys=True) == json.dumps(fiche_g, sort_keys=True)
        else:
            repro = a0 is not None and json.dumps({o: a0["onglets"][o] for o in fiche_g["onglets"]}, sort_keys=True) == json.dumps(fiche_g["onglets"], sort_keys=True)
        info = {"mid": mid, "moteur": moteur, "gele_le": ts, "jour": str(fiche_g.get("jour") or fiche_g.get("date"))[:10], "competition": fiche_g.get("competition"),
                "domicile": fiche_g["domicile"], "exterieur": fiche_g["exterieur"], "gels_du_match": toutes[mid], "termine": mid in res, "reproduit_a_l_identique": repro}
        if not repro:
            info["classe"] = {v: "non reproductible" for v in VARIANTES}; rows.append(info); continue
        fl = cotes_du_bloc(moteur, ts, mid)
        info["blocs"] = fl
        ok = sides_ok(fl)
        info["classe"], info["marches"] = {}, {}
        if moteur == "omega":
            base = paris_omega_fiche(fiche_g); cmp_ = ("p", "p_modele", "cote")
        else:
            base = marches_alpha_fiche(fiche_g["onglets"]); cmp_ = ("valeur", "cote", "tete")
        var = {}
        for v in VARIANTES:
            r = charge(moteur, ts, v)["fiches"].get(mid)
            if moteur == "omega":
                var[v] = paris_omega_fiche(r) if r else None
            else:
                var[v] = marches_alpha_fiche({o: r["onglets"][o] for o in fiche_g["onglets"]}) if r else None
        cles = list(base) + [k for v in VARIANTES if var[v] for k in var[v] if k not in base]
        cles = list(dict.fromkeys(cles))
        score = res[mid]["score"] if mid in res else None
        for k in cles:
            ligne = {"g": base.get(k) and {x: base[k][x] for x in cmp_ if x in base[k]}}
            for v in VARIANTES:
                ligne[v] = (var[v] or {}).get(k) and {x: var[v][k][x] for x in cmp_ if x in var[v][k]}
                ligne["etat_" + v] = etat(base.get(k), (var[v] or {}).get(k), cmp_) if var[v] is not None else "indéterminé"
            cle_m = (base.get(k) or next((var[v][k] for v in VARIANTES if var[v] and k in var[v]), None))["cle"]
            if score is not None:
                try:
                    ligne["gagne"] = gagne_omega(cle_m, score) if moteur == "omega" else gagne_alpha(cle_m, score)
                except Exception:                                                  # noqa: BLE001
                    ligne["gagne"] = None
            info["marches"][k] = ligne
        for v in VARIANTES:
            if var[v] is None:
                info["classe"][v] = "indéterminé"
            else:
                info["classe"][v] = classe_match([l["etat_" + v] for l in info["marches"].values()], fl, v, ok)
        rows.append(info)
    return rows


def synthese(rows, moteur):
    out = {"moteur": moteur, "matchs_avec_gel_valide": len(rows), "termines": sum(1 for r in rows if r.get("termine")),
           "reproduits_a_l_identique": sum(1 for r in rows if r.get("reproduit_a_l_identique")), "periode_gels": None, "lectures": {}}
    jours = sorted(r["jour"] for r in rows if r.get("jour"))
    out["periode_matchs"] = [jours[0], jours[-1]] if jours else None
    avec = [r for r in rows if r.get("blocs")]
    out["exposition"] = {"matchs_avec_blocs_identifies": len(avec),
                         "matchs_avec_au_moins_un_bloc_sans_identifiant_de_club": sum(1 for r in avec if any(r["blocs"][c]["sans_id"] for c in ("dom", "ext"))),
                         "matchs_avec_au_moins_un_bloc_tronque": sum(1 for r in avec if any(r["blocs"][c]["n_manquantes"] > 0 for c in ("dom", "ext"))),
                         "matchs_avec_au_moins_une_auto_reference": sum(1 for r in avec if any(r["blocs"][c]["n_auto_references"] > 0 for c in ("dom", "ext"))),
                         "matchs_avec_conflit_de_scores": sum(1 for r in avec if any(r["blocs"][c]["n_conflits"] > 0 for c in ("dom", "ext")))}
    for v in VARIANTES:
        out["lectures"][v] = {"tous_matchs": dict(Counter(r["classe"][v] for r in rows)), "matchs_termines": dict(Counter(r["classe"][v] for r in rows if r.get("termine")))}
    # bilan des paris réels (matchs terminés) : paris gelés vs paris de chaque lecture
    bil = {}
    for v in ("gelé",) + VARIANTES:
        n = g = 0
        retires = Counter(); ajoutes = Counter()
        mids = set()
        for r in rows:
            if not r.get("termine") or "marches" not in r:
                continue
            for k, l in r["marches"].items():
                if v == "gelé":
                    if l["g"] is not None and l.get("gagne") is not None:
                        n += 1; g += bool(l["gagne"]); mids.add(r["mid"])
                else:
                    if l[v] is not None and l.get("gagne") is not None:
                        n += 1; g += bool(l["gagne"]); mids.add(r["mid"])
                    if l["g"] is not None and l[v] is None and l.get("gagne") is not None:
                        retires["gagnés" if l["gagne"] else "perdus"] += 1
                    if l["g"] is None and l[v] is not None and l.get("gagne") is not None:
                        ajoutes["gagnés" if l["gagne"] else "perdus"] += 1
        bil[v] = {"matchs": len(mids), "paris": n, "gagnes": g, "taux": round(100 * g / n, 1) if n else None, "retires_vs_gele": dict(retires), "ajoutes_vs_gele": dict(ajoutes)}
    out["bilan_termines"] = bil
    # amplitude des changements
    amp = {}
    for v in VARIANTES:
        d = []
        for r in rows:
            for l in (r.get("marches") or {}).values():
                if l["g"] and l[v]:
                    a, b = (l["g"].get("p") if "p" in l["g"] else l["g"].get("valeur")), (l[v].get("p") if "p" in l[v] else l[v].get("valeur"))
                    if a is not None and b is not None and a != b:
                        d.append(abs(b - a))
        amp[v] = {"marches_modifies": len(d), "ecart_moyen": round(sum(d) / len(d), 4) if d else None, "ecart_max": round(max(d), 4) if d else None}
    out["amplitude_modifications"] = amp
    return out


if __name__ == "__main__":
    SORTIE.mkdir(parents=True, exist_ok=True)
    tout = {}
    for moteur in ("omega", "alpha"):
        rows = traiter(moteur)
        tout[moteur] = synthese(rows, moteur)
        with gzip.open(SORTIE / f"rejeu_{moteur}_detail.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
        print(json.dumps(tout[moteur], ensure_ascii=False, indent=1))
    (SORTIE / "rejeu_synthese.json").write_text(json.dumps(tout, ensure_ascii=False, indent=1), encoding="utf-8")
