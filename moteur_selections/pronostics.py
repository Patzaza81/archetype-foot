"""Page « Équipe nationale » : mêmes données que la page Analyse Verdict (format de page_verif.json), méthode Verdict.
Matchs à venir (collecte Matchendirect) + cotes Betpawa (cotes.py) + historique public des sélections.
Un pari n'entre que s'il a une cote Betpawa >= cote minimale ET qu'il tient. Écrit data/selections/page_selections.json.

    python -m moteur_selections.pronostics"""
import datetime, json, os, tempfile
import verif_pronostic as V
from moteur_selections import donnees, noms, verdict

ENTREE = os.path.join(donnees.DOSSIER, "a_venir.json")
COTES = os.path.join(donnees.DOSSIER, "cotes.json")
SORTIE = os.path.join(donnees.DOSSIER, "page_selections.json")
LECTURE = {True: "les buts attendus confirment", "limite": "les buts attendus sont à la limite de la ligne", False: "les buts attendus ne confirment pas", None: ""}


def _utc(date, heure_cameroun):
    try: return (datetime.datetime.fromisoformat(f"{date}T{heure_cameroun}") - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError): return None


def fiche(m, hist, cotes, cfg):
    d, e = noms.FR_EN.get(m["domicile"]), noms.FR_EN.get(m["exterieur"])
    base = {"match_id": m["match_id"], "date": m["date"], "coup_d_envoi_utc": _utc(m["date"], m.get("heure_cameroun") or m.get("heure")),
            "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"], "statut": "a_venir", "resultat": None,
            "xg_source": None, "buts_attendus": None, "equipes": {}, "paris": {"buts": [], "equipes": [], "victoire": [], "combos": []}, "derniers_matchs": {}}
    if not d or not e or not cotes: return base
    match = {"date": m["date"], "domicile": d, "exterieur": e, "neutre": False}
    C = V.cotes_betpawa(cotes)
    for marche, cote in C.items():
        r = verdict.constat(hist, match, marche, cote, cfg)
        if r["verdict"] not in ("TIENT", "TIENT AVEC RÉSERVE"): continue
        A, B = r["A"], r["B"]
        base["paris"][V.groupe(marche)].append({
            "marche": marche, "libelle": r["libelle"].replace(d, m["domicile"]).replace(e, m["exterieur"]), "cote": cote,
            "reussite_dom": [A["reussi"], A["n"]], "reussite_ext": [B["reussi"], B["n"]], "taux": round((A["reussi"] + B["reussi"]) / (A["n"] + B["n"]), 4),
            "verdict": r["verdict"], "lecture_xg": LECTURE.get(r["lecture_buts"], "")})
        av = hist.avantage(m["date"], cfg["fenetre_jours"]); la, lb = r["buts_attendus"]
        base["buts_attendus"] = None if la is None else [round(la + av / 2, 3), round(lb - av / 2, 3)]
        arr = lambda S: {"n": S["n"], "buts_marques": round(S["buts_marques"], 3), "buts_encaisses": round(S["buts_encaisses"], 3), "xg_cree": None, "xg_concede": None, "ecart_xg": None, "surperformance": None, "n_xg": 0, "xg_est": False}
        base["equipes"] = {"dom": arr(A), "ext": arr(B), "championnat": {"buts": None, "xg": None, "xg_est": False, "avantage_dom": round(av, 3), "matchs": None}}
    for L in base["paris"].values(): L.sort(key=lambda p: (-p["taux"], V.ORDRE.index(p["verdict"]), -(p["reussite_dom"][1] + p["reussite_ext"][1])))
    return base


def calcule(a_venir, hist, cotes_par_match, cfg=None):
    cfg = cfg or verdict.config()
    M = [fiche(m, hist, cotes_par_match.get(m["match_id"]), cfg) for m in a_venir]
    M = [f for f in M if any(f["paris"].values())]
    M.sort(key=lambda f: (f["coup_d_envoi_utc"] or "", f["domicile"]))
    return M


def main():
    with open(ENTREE, encoding="utf-8") as f: a_venir = json.load(f)
    try:
        with open(COTES, encoding="utf-8") as f: cotes = json.load(f)
    except (OSError, ValueError): cotes = {}
    csv_tmp = os.path.join(tempfile.gettempdir(), "resultats_selections.csv")   # hors dépôt : le pipeline ne le versionne pas
    donnees.telecharger(csv_tmp)
    hist = donnees.Historique(donnees.charger(csv_tmp)); cfg = verdict.config()
    M = calcule(a_venir, hist, cotes, cfg)
    page = {"genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "cote_min": cfg["cote_min"], "minimum_matchs_meme_lieu": cfg["nmin"],
            "bilan": {}, "nb_matchs": len(M), "matchs": M, "nb_matchs_collectes": len(a_venir), "nb_avec_cotes": len(cotes)}
    with open(SORTIE, "w", encoding="utf-8") as f: json.dump(page, f, ensure_ascii=False, indent=1)
    print(f"selections: {len(a_venir)} matchs collectés, {len(cotes)} avec cotes Betpawa, {len(M)} avec au moins un pari qui tient -> data/selections/page_selections.json")


if __name__ == "__main__":
    main()
