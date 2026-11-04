"""Integration INDEPENDANTE de la calibration de P1 dans le flux de production (mode PARALLELE par defaut).

Ce que ce module est : un lecteur du flux commun + un enregistreur. Il ne modifie ni les moteurs, ni leurs sorties, ni les JSON existants.
  1. Flux commun lu : data/archive_test/<jour>.json.gz (ecrit chaque nuit par archive_donnees_test.py ; c'est aussi la source de alpha_serie et du banc d'essai).
     Chaque match y porte la division Football-Data et le nom Football-Data des deux equipes, deja resolus par assemblage_equipes.py : aucune table de correspondance n'est recreee ici.
  2. P1 : calcule par pouvoir_predictif.predire(famille "P1") sur l'historique de la competition (archives 2122-2526 + saison courante data/football_data/normalized/<saison>/<CODE>.jsonl),
     avec les parametres de la configuration (k, demi-vie). Aucun calcul n'est duplique : c'est la fonction de recherche elle-meme. Un match futur est ajoute en fin d'historique avec un score fictif ;
     la prediction d'un jour est faite AVANT toute mise a jour de ce jour (propriete verifiee par tests/test_pouvoir_predictif.py), donc le score fictif n'a aucun effet.
  3. Calibration : calibration_p1.appliquer (config_calibration.json). Statut P1 CONSERVE -> probabilite originale renvoyee telle quelle (identite exacte).
  4. Sortie (seule ecriture) : data/calibration_p1/parallele/journal.jsonl (une ligne gelee par match, jamais reecrite) et dernier_rapport.json.
ATTENTION: les calibrations sont apprises sur ce P1 precis. Elles ne s'appliquent PAS aux probabilites des moteurs DC, omega, v2.6.10, etc. (autres modeles, autres donnees).
Mode "parallele": P1 original et P1 calibre sont enregistres, rien n'est publie. Mode "actif": voir docs/CALIBRATION_P1_INTEGRATION.md."""
import datetime, glob, gzip, hashlib, json, os, sys
import numpy as np
import calibration_p1 as cp
import pouvoir_predictif as pp

RACINE = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(RACINE, "data", "calibration_p1", "parallele")
CONFIG_INTEGRATION = os.path.join(RACINE, "data", "calibration_p1", "integration.json")
FLUX = os.path.join(RACINE, "data", "archive_test")
NORMALISE = os.path.join(RACINE, "data", "football_data", "normalized")
MARCHES = cp.MARCHES
MODES = ("parallele", "actif")

def mode(chemin=None):
    try: m = json.load(open(chemin or CONFIG_INTEGRATION, encoding="utf-8")).get("mode", "parallele")
    except (OSError, ValueError): m = "parallele"
    return m if m in MODES else "parallele"

def historique(code, jusqua_jour=None):
    """Matchs joues de la competition (jour ordinal, saison, dom, ext, buts dom, buts ext) triees: archives + saison courante normalisee. jusqua_jour: exclus ce jour et apres."""
    H = list(pp.charger(code))
    for chemin in sorted(glob.glob(os.path.join(NORMALISE, "*", code + ".jsonl"))):
        saison = os.path.basename(os.path.dirname(chemin))
        for l in open(chemin, encoding="utf-8"):
            if not l.strip(): continue
            r = json.loads(l); hg, ag = r.get("full_time_home_goals"), r.get("full_time_away_goals"); d = pp._date(r.get("date") or "")
            if hg is None or ag is None or d is None or not r.get("home_team") or not r.get("away_team"): continue
            H.append((d, saison, r["home_team"], r["away_team"], int(hg), int(ag)))
    H.sort(key=lambda m: m[0])
    return [m for m in H if jusqua_jour is None or m[0] < jusqua_jour]

def p1_matchs(hist, fixtures, cfg_p1):
    """P1 de matchs futurs d'une meme competition. fixtures: liste (jour, dom, ext). Regroupe par jour : un seul jour fictif ajoute a la fois (aucun effet d'un match futur sur un autre)."""
    out = {}
    for jour in sorted({f[0] for f in fixtures}):
        H = [m for m in hist if m[0] < jour]; fx = [f for f in fixtures if f[0] == jour]
        M = H + [(jour, "futur", f[1], f[2], 0, 0) for f in fx]
        P = pp.predire(M, "P1", cfg_p1["k"], cfg_p1["demi_vie_jours"])[len(H):]
        n_hist = len(H)
        for f, row in zip(fx, P):
            out[(f[0], f[1], f[2])] = (None if n_hist == 0 or np.isnan(row).any() else row)
    return out

def lire_flux(jour_min, maintenant=None):
    """Matchs a venir du flux commun (score absent, date >= jour_min, coup d'envoi futur): liste de dict (match_id, date, competition, division, dom, ext, noms FD)."""
    res = {}
    for f in sorted(glob.glob(os.path.join(FLUX, "*.json.gz"))):
        if os.path.basename(f)[:10] < jour_min: continue
        for x in json.load(gzip.open(f)).values():
            if x.get("score") is not None and (x["score"] or {}).get("buts_dom") is not None: continue
            if maintenant and x.get("coup_d_envoi_utc") and x["coup_d_envoi_utc"] <= maintenant: continue
            a = x.get("assemblage") or {}; ed, ee = a.get("equipe_dom") or {}, a.get("equipe_ext") or {}
            res[x["match_id"]] = {"match_id": x["match_id"], "date": x["date"], "coup_d_envoi_utc": x.get("coup_d_envoi_utc"), "competition": x.get("competition"), "domicile": x.get("domicile"), "exterieur": x.get("exterieur"),
                                  "division": ed.get("division_football_data") if ed.get("couverte_par_football_data") and ee.get("couverte_par_football_data") and ed.get("division_football_data") == ee.get("division_football_data") else None,
                                  "fd_dom": ed.get("nom_football_data"), "fd_ext": ee.get("nom_football_data")}
    return list(res.values())

def traiter(matchs, config, mode_="parallele", ref_jour=None):
    """-> liste d'enregistrements (un par match). Aucune ecriture."""
    par_div = {}
    for m in matchs: par_div.setdefault(m["division"], []).append(m)
    out = []
    for code, L in sorted(par_div.items(), key=lambda kv: str(kv[0])):
        if code is None or code not in config["competitions"]:
            for m in L: out.append({**_base(m), "statut": "HORS_PERIMETRE", "raison": "competition ou equipes non couvertes par Football-Data / non configurees"})
            continue
        ccfg = config["competitions"][code]; jours = {pp._date(m["date"]) for m in L}; hist = historique(code, jusqua_jour=max(j for j in jours if j) if jours else None)
        fx = [(pp._date(m["date"]), m["fd_dom"], m["fd_ext"]) for m in L]; P = p1_matchs(hist, fx, ccfg["p1"])
        hist_elo = [(m[0], m[2], m[3], m[4], m[5]) for m in hist]
        for m, f in zip(L, fx):
            row = P.get(f)
            if row is None: out.append({**_base(m), "statut": "SANS_P1", "raison": "aucun historique anterieur dans la competition"}); continue
            orig = {mk: float(row[i]) for i, mk in enumerate(MARCHES)}; elo = None
            if any(ccfg[mk]["statut"] == "CORRECTION VALIDEE" and ccfg[mk]["methode"] in ("ELO", "ELO_PALIER") for mk in MARCHES):
                elo = cp.elo_diff_depuis_historique([h for h in hist_elo if h[0] < f[0]], ccfg["p1"]["K_elo"], m["fd_dom"], m["fd_ext"])
            cal, stat = {}, {}
            for mk in MARCHES:
                q, info = cp.appliquer(config, code, mk, orig[mk], elo); cal[mk] = float(q); stat[mk] = info["methode"]
            c1 = cp.appliquer_1x2(config, code, orig["dom"], orig["nul"], orig["ext"], elo)
            if any(stat[k] != "P1" for k in ("dom", "nul", "ext")): cal["dom"], cal["nul"], cal["ext"] = (float(x) for x in c1)
            out.append({**_base(m), "statut": "OK", "mode": mode_, "p1_original": orig, "p1_calibre": cal, "methode": stat, "somme_1x2_original": round(sum(orig[k] for k in ("dom", "nul", "ext")), 6),
                        "somme_1x2_calibre": round(sum(cal[k] for k in ("dom", "nul", "ext")), 6), "n_historique_competition": len(hist), "elo_diff": elo,
                        "publie": cal if mode_ == "actif" else orig})
    return out

def _base(m): return {"match_id": m["match_id"], "date": m["date"], "competition": m["competition"], "division": m["division"], "domicile": m["domicile"], "exterieur": m["exterieur"], "coup_d_envoi_utc": m["coup_d_envoi_utc"]}

def ecrire(enregistrements, config, dossier=DOSSIER, maintenant=None):
    """Journal gele: une ligne par match_id, jamais reecrite. Retourne (nb ajoutes, nb deja geles)."""
    os.makedirs(dossier, exist_ok=True); chemin = os.path.join(dossier, "journal.jsonl"); deja = set()
    if os.path.exists(chemin):
        for l in open(chemin, encoding="utf-8"):
            if l.strip(): deja.add(json.loads(l)["match_id"])
    n = 0
    with open(chemin, "a", encoding="utf-8") as f:
        for r in enregistrements:
            if r["statut"] != "OK" or r["match_id"] in deja: continue
            f.write(json.dumps({**r, "gele_le": maintenant or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}, ensure_ascii=False, separators=(",", ":")) + "\n"); n += 1
    return n, len([r for r in enregistrements if r["statut"] == "OK" and r["match_id"] in deja])

def rapport(enregistrements, config, mode_, maintenant=None):
    ok = [r for r in enregistrements if r["statut"] == "OK"]; ecart = max([abs(r["p1_calibre"][k] - r["p1_original"][k]) for r in ok for k in MARCHES] or [0.0])
    par = {}
    for r in enregistrements: d = par.setdefault(str(r["division"]), {"matchs": 0, "ok": 0}); d["matchs"] += 1; d["ok"] += r["statut"] == "OK"
    return {"genere_le": maintenant or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "mode": mode_, "matchs_du_flux": len(enregistrements), "matchs_avec_p1": len(ok),
            "hors_perimetre": sum(r["statut"] == "HORS_PERIMETRE" for r in enregistrements), "sans_p1": sum(r["statut"] == "SANS_P1" for r in enregistrements),
            "ecart_max_calibre_original": ecart, "identite_exacte": all(r["p1_calibre"] == r["p1_original"] for r in ok), "ecart_max_somme_1x2_a_1": max([abs(r["somme_1x2_calibre"] - 1) for r in ok] or [0.0]),
            "couples_valides_dans_la_config": sum(1 for v in config["competitions"].values() for m in MARCHES if v[m]["statut"] == "CORRECTION VALIDEE"), "par_division": par}

def empreintes(chemins):
    return {c: hashlib.sha256(open(c, "rb").read()).hexdigest() for c in chemins if os.path.exists(c)}

def executer(jour=None, maintenant=None, ecrire_journal=True, config=None, mode_=None):
    config = config or cp.charger(); mode_ = mode_ or mode()
    jour = jour or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    enr = traiter(lire_flux(jour, maintenant), config, mode_); rap = rapport(enr, config, mode_, maintenant)
    if ecrire_journal:
        ajoutes, deja = ecrire(enr, config, maintenant=maintenant); rap["ajoutes_au_journal"] = ajoutes; rap["deja_geles"] = deja
        json.dump(rap, open(os.path.join(DOSSIER, "dernier_rapport.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return enr, rap

def verifier_perimetre(config=None):
    """Verification des 38 competitions: configuration complete (7 marches), P1 calculable sur un match fictif (deux dernieres equipes a domicile / a l'exterieur), 1X2 coherent, identite sur P1 CONSERVE."""
    config = config or cp.charger(); res = {}
    for code, v in sorted(config["competitions"].items()):
        h = historique(code); f = {"marches_configures": sorted(m for m in MARCHES if m in v), "valides": sum(v[m]["statut"] == "CORRECTION VALIDEE" for m in MARCHES if m in v)}
        if len(h) < 50: f["p1"] = "historique insuffisant"; res[code] = f; continue
        jour = h[-1][0] + 1; dom, ext = h[-1][2], h[-1][3]; r = p1_matchs(h, [(jour, dom, ext)], v["p1"])[(jour, dom, ext)]
        if r is None: f["p1"] = "indisponible"; res[code] = f; continue
        orig = {mk: float(r[i]) for i, mk in enumerate(MARCHES)}
        cal = {mk: float(cp.appliquer(config, code, mk, orig[mk], 0.0)[0]) for mk in MARCHES}
        f.update({"p1": "ok", "somme_1x2": round(sum(orig[k] for k in ("dom", "nul", "ext")), 6), "identite": all(orig[k] == cal[k] for k in MARCHES) if f["valides"] == 0 else "n/a", "o15_ge_o25_ge_o35": orig["o15"] >= orig["o25"] >= orig["o35"]})
        res[code] = f
    return res

if __name__ == "__main__":
    a = sys.argv[1:]
    if "--verifier" in a:
        res = verifier_perimetre(); json.dump(res, open(os.path.join(DOSSIER, "verification_38.json") if os.path.isdir(DOSSIER) else "/dev/stdout", "w"), ensure_ascii=False, indent=1) if os.path.isdir(DOSSIER) else print(json.dumps(res)); print(len(res), "competitions verifiees")
    else:
        jour = a[a.index("--jour") + 1] if "--jour" in a else None
        enr, rap = executer(jour=jour); print(json.dumps({k: v for k, v in rap.items() if k != "par_division"}, ensure_ascii=False))
