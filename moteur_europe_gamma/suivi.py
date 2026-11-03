"""Suivi du moteur Europe-Gamma : gel avant le coup d'envoi, règlement, page. Usage : python -m moteur_europe_gamma.suivi [pipeline|geler|resultats|page]

Même mécanique que Gamma (journal en ajout seul, la DERNIÈRE ligne écrite avant le coup d'envoi compte, résultat réglé une fois) ; code autonome.
Journal `data/europe_gamma/journal.jsonl`, page `data/europe_gamma/pronostics.json`. Entrées : `data/europe/entrees_europe.json` (collecte commune), classements : `cache_classement.json`.
Un contrôle mathématique raté EXCLUT le match et fait échouer l'étape. Un enjeu NUL (zone fixée mathématiquement) exclut le match avec sa raison.
Les paris d'aperçu NON calibré sont étiquetés comme tels et comptés à part dans le bilan.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import coeur as C, donnees as D, enjeu as E, marches as M

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "europe_gamma"
JOURNAL = DOSSIER / "journal.jsonl"
PAGE = DOSSIER / "pronostics.json"
PARAMS = Path(__file__).with_name("parametres.json")
JOURS_REGLES_AFFICHES = 7
ORDRE = hashlib.sha256("|".join(M.cle_txt(c) for c in M.CLES).encode()).hexdigest()[:12]


def charger_parametres(chemin: Path = PARAMS) -> dict[str, Any] | None:
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


def _lire(journal: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()] if journal.exists() else []


def _ajouter(journal: Path, lignes: list[dict[str, Any]]) -> None:
    if lignes:
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as f:
            for l in lignes:
                f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")


def _ko(x: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return None


def charger_matchs(chemin: Path = D.ENTREES) -> list[dict[str, Any]]:
    return json.loads(chemin.read_text(encoding="utf-8"))["matchs"]


def charger_classements(chemin: Path = D.CLASSEMENTS) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _pari(l: dict[str, Any], apercu: bool) -> dict[str, Any]:
    return {"cle": l["cle"], "famille": l["famille"], "cote": l.get("cote"), "p_implicite": l.get("p_implicite"), "p_implicite_corrigee": l.get("p_implicite_corrigee"),
            "marge": l.get("marge"), "k": l["k"], "n": l["n"], "f": l["f"], "g": l["g"], "niveaux": l["niveaux"], "stabilite": l["stabilite"], "diversite": l["diversite"],
            "contradiction": l["contradiction"], "seuil": l.get("seuil"), "p_calibree": l.get("p_calibree"), "statut": l["statut"], "raison": l["raison"], "apercu_non_calibre": apercu}


def _compact(m: dict[str, Any]) -> list[Any]:
    nv = m["niveaux"]
    return [m["k"], m["remb"], nv["strict"]["k"], nv["intermediaire"]["k"], nv["elargi"]["k"], m["g"], m["stabilite"]["f_min"], m["stabilite"]["f_max"],
            m["diversite"]["part_max_observation"], int(m["stabilite"]["dependance_unique"]), m["code"], m.get("cote") or 0, m.get("seuil")]


def _enjeu(m: dict[str, Any], classements: dict[str, Any]) -> dict[str, Any] | None:
    if "phase de ligue" not in str(m.get("competition") or "").lower():
        return None
    cl = (classements.get(D.CLE_CLASSEMENT_EUROPE.get(m.get("competition_code"), "")) or {}).get("resultat")
    d, e = E.enjeu(cl, m["domicile"]), E.enjeu(cl, m["exterieur"])
    return {"domicile": d, "exterieur": e, "ecart_points": E.ecart_points(cl, m["domicile"], m["exterieur"])} if d and e else None


def _recent(src: dict[str, Any], cote: str) -> list[dict[str, Any]]:
    obs = [dict(o, echantillon=z) for z, s in src.items() if s["valide"] for o in s[cote]]
    return sorted(obs, key=lambda o: o["date"], reverse=True)


def fiche(m: dict[str, Any], s: dict[str, Any] | None, a: dict[str, Any] | None, sel: dict[str, Any] | None, enj: dict[str, Any] | None, raison: str | None = None) -> dict[str, Any]:
    out = {"match_id": m["match_id"], "jour": str(m["date"])[:10], "heure": m.get("heure"), "coup_d_envoi_utc": m.get("coup_d_envoi_utc"), "competition": m.get("competition"),
           "domicile": m["domicile"], "exterieur": m["exterieur"], "statut": "analyse" if a else "exclu", "enjeu": enj}
    if a is None or s is None or sel is None:
        return {**out, "raison": raison, "principal": None, "autres": []}
    ex, ap = a["exploration"], sel["apercu_non_calibre"]
    lignes = list(a["conclusion"])
    if enj:
        if enj.get("ecart_points") is not None:
            e = enj["ecart_points"]
            lignes.append(f"Écart de points entre les deux équipes : {abs(e)} point(s)" + (f" en faveur de {m['domicile'] if e > 0 else m['exterieur']}." if e else " (à égalité)."))
        for cote, nom in (("domicile", m["domicile"]), ("exterieur", m["exterieur"])):
            x = enj[cote]
            lignes.append(f"Enjeu {nom} : {x['pts']} pt(s) en {x['j']} match(s), {x['restants']} restant(s) ; à {abs(x['ecart_ligne']['8'])} pt(s) {'au-dessus' if x['ecart_ligne']['8'] >= 0 else 'en dessous'} de la ligne des 1/8e ({x['frontieres']['8']}), à {abs(x['ecart_ligne']['24'])} pt(s) {'au-dessus' if x['ecart_ligne']['24'] >= 0 else 'en dessous'} de la ligne du play-off ({x['frontieres']['24']}) ; enjeu {'réel' if x['reel'] else 'NUL'}.")
    lignes.append(f"Forces en présence : {s['forces']['resolus']} observation(s) pesée(s) par la force réelle de l'adversaire, {s['forces']['neutres']} au poids neutre (adversaire absent du classement de sa compétition).")
    return {**out, "n_domicile": max(v["n_a"] for v in a["echantillons"].values()), "n_exterieur": max(v["n_b"] for v in a["echantillons"].values()), "raison": sel["raison"],
            "apercu_non_calibre": ap, "principal": _pari(sel["principal"], ap) if sel["principal"] else None, "autres": [_pari(x, ap) for x in sel["autres"]],
            "donnees": {"domicile": _recent(s["sources"], "A"), "exterieur": _recent(s["sources"], "B"), "sequences": a["echantillons"],
                        "source": "collecte Europe (Matchendirect) : 3 échantillons au même lieu (20 % saison européenne passée, 30 % championnat en cours, 50 % Europe en cours), matchs strictement avant le jour du match"},
            "exploration": {"combinaisons": a["combinaisons"], "scores_distincts": a["scores_distincts"], "top_scores": ex["top_scores"], "concentration_top3": ex["concentration_top3"],
                            "issues": ex["issues"], "buts_a": ex["buts_a"], "buts_b": ex["buts_b"], "totaux": ex["totaux"]},
            "niveaux": a["niveaux"], "verifications": {"total": len(a["verifications"]), "reussies": sum(v["ok"] for v in a["verifications"])},
            "conclusion": lignes, "empreinte": a["empreinte"], "ordre_marches": ORDRE, "tous_marches": [_compact(x) for x in a["marches"]],
            "a_surveiller": [{"cle": x["cle"], "raison": x["raison"], "g": x["g"], "cote": x.get("cote")} for x in a["marches"] if x["statut"] == "a_surveiller"],
            "derniers_matchs": {"dom": _recent(s["sources"], "A")[:10], "ext": _recent(s["sources"], "B")[:10]}}


def _cle_selection(f: dict[str, Any]) -> str:
    p = f.get("principal") or {}
    return json.dumps([f.get("statut"), f.get("empreinte"), p.get("cle"), p.get("cote"), [(x["cle"], x["cote"]) for x in f.get("autres") or []], f.get("raison")], sort_keys=True)


def analyser_match(m: dict[str, Any], classements: dict[str, Any], calib: dict[str, Any] | None) -> dict[str, Any]:
    enj = _enjeu(m, classements)
    s = D.echantillons(m, classements)
    try:
        a = C.analyser(s["sources"], D.cotes_gamma(m["entree"].get("odds") or {}), calib=calib)
    except C.DonneesInsuffisantes as e:
        return fiche(m, None, None, None, enj, f"données insuffisantes : {e}")
    rates = [v["nom"] for v in a["verifications"] if not v["ok"]]
    if rates:
        raise RuntimeError(f"contrôle mathématique échoué pour {m['domicile']} – {m['exterieur']} ({m['date']}) : {rates}")
    if enj and not (enj["domicile"]["reel"] and enj["exterieur"]["reel"]):
        nul = [n for n, x in ((m["domicile"], enj["domicile"]), (m["exterieur"], enj["exterieur"])) if not x["reel"]]
        return fiche(m, s, a, None, enj, "enjeu nul : zone fixée mathématiquement pour " + ", ".join(nul))
    return fiche(m, s, a, C.selection(a), enj)


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, matchs: list[dict] | None = None, classements: dict | None = None,
          calib: dict[str, Any] | None = None) -> tuple[int, list[str]]:
    maintenant = maintenant or datetime.now(timezone.utc)
    calib = calib if calib is not None else charger_parametres()
    matchs = matchs if matchs is not None else charger_matchs()
    classements = classements if classements is not None else charger_classements()
    dernier = {l["match_id"]: _cle_selection(l["fiche"]) for l in _lire(journal) if l["type"] == "pronostic"}
    nouveaux, erreurs = [], []
    for m in matchs:
        ko = _ko(m.get("coup_d_envoi_utc"))
        if ko is None or ko <= maintenant or (m.get("score") or {}).get("buts_dom") is not None:
            continue
        try:
            f = analyser_match(m, classements, calib)
        except RuntimeError as e:
            erreurs.append(str(e))
            continue
        if dernier.get(f["match_id"]) == _cle_selection(f):
            continue
        nouveaux.append({"type": "pronostic", "match_id": f["match_id"], "gele_le": maintenant.isoformat(timespec="seconds"), "commit": _commit(),
                         "version": (calib or {}).get("version", "sans calibrage"), "fiche": f})
    _ajouter(journal, nouveaux)
    return len(nouveaux), erreurs


def derniers_pronostics(lignes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict] = {}
    for l in lignes:
        if l["type"] != "pronostic":
            continue
        ko, gel = _ko(l["fiche"].get("coup_d_envoi_utc")), _ko(l["gele_le"])
        if ko is None or gel is None or gel >= ko:
            continue
        out[l["match_id"]] = l
    return out


def resultats(journal: Path = JOURNAL, matchs: list[dict] | None = None) -> int:
    lignes = _lire(journal)
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    matchs = matchs if matchs is not None else charger_matchs()
    scores = {m["match_id"]: (m["score"]["buts_dom"], m["score"]["buts_ext"]) for m in matchs if (m.get("score") or {}).get("buts_dom") is not None}
    nouveaux = []
    for mid, l in derniers_pronostics(lignes).items():
        if mid in faits or mid not in scores:
            continue
        h, a = scores[mid]
        f = l["fiche"]
        paris = ([("principal", f["principal"])] if f.get("principal") else []) + [("autre", x) for x in f.get("autres") or []]
        regles = []
        for r, p in paris:
            v = M.resultat((p["cle"][0], p["cle"][1]), h, a)
            regles.append({"role": r, "marche": M.libelle((p["cle"][0], p["cle"][1])), "cle": p["cle"], "cote": p["cote"], "p": p.get("p_calibree"),
                           "apercu_non_calibre": bool(p.get("apercu_non_calibre")), "gagne": None if v == 2 else bool(v), "rembourse": v == 2})
        nouveaux.append({"type": "resultat", "match_id": mid, "score": [h, a], "regle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "paris": regles})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def _stats(paris: list[dict[str, Any]]) -> dict[str, Any]:
    paris = [p for p in paris if not p.get("rembourse")]
    if not paris:
        return {"regles": 0}
    g = sum(bool(p["gagne"]) for p in paris)
    c = [p for p in paris if p.get("cote")]
    pc = [p["p"] for p in paris if p.get("p") is not None]
    return {"regles": len(paris), "gagnes": g, "reussite": round(g / len(paris), 4), "annonce": round(sum(pc) / len(pc), 4) if pc else None,
            "avec_cote": len(c), "cote_moyenne": round(sum(p["cote"] for p in c) / len(c), 3) if c else None}


def bilan(lignes: list[dict[str, Any]]) -> dict[str, Any]:
    res = [l for l in lignes if l["type"] == "resultat"]
    tous = [p for l in res for p in l["paris"]]
    return {"principal": _stats([p for p in tous if p["role"] == "principal" and not p["apercu_non_calibre"]]),
            "autres": _stats([p for p in tous if p["role"] == "autre" and not p["apercu_non_calibre"]]),
            "apercu_non_calibre": _stats([p for p in tous if p["apercu_non_calibre"]]), "matchs_regles": len(res)}


def page(maintenant: datetime | None = None, journal: Path = JOURNAL, sortie: Path = PAGE, derniere_analyse: datetime | None = None) -> dict[str, Any]:
    maintenant = maintenant or datetime.now(timezone.utc)
    lignes = _lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    tous = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    gels = derniers_pronostics(lignes)
    a_venir, en_cours, reglees, sans, exclus = [], [], [], 0, Counter()
    for mid, l in tous.items():
        f = dict((gels.get(mid) or l)["fiche"])
        ko = _ko(f.get("coup_d_envoi_utc"))
        if ko is None:
            continue
        if not f.get("principal"):
            if ko > maintenant:
                if f.get("statut") == "exclu":
                    exclus[str(f.get("raison") or "raison inconnue").split(":")[0].split(" (")[0].strip()] += 1
                else:
                    sans += 1
            continue
        if mid in res:
            if ko < maintenant - timedelta(days=JOURS_REGLES_AFFICHES):
                continue
            r = res[mid]
            f["score"] = r["score"]
            issues = {json.dumps(p["cle"]): p for p in r["paris"]}
            for p in [f["principal"]] + f["autres"]:
                q = issues.get(json.dumps(p["cle"]))
                p["resultat"] = "PUSH" if q and q.get("rembourse") else ("WIN" if q and q.get("gagne") else "LOSS")
            reglees.append(f)
        elif ko > maintenant:
            a_venir.append(f)
        elif ko > maintenant - timedelta(hours=6):
            en_cours.append(f)
    p = charger_parametres() or {}
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "derniere_analyse": (derniere_analyse or maintenant).isoformat(timespec="seconds"), "version": p.get("version", "sans calibrage"),
           "statut": "observation", "calibrage": p.get("echantillon"), "cote_min": p.get("cote_min", C.COTE_MIN), "ordre_marches": ORDRE, "cles_marches": [list(c) for c in M.CLES],
           "bilan": bilan(lignes), "sans_pronostic": sans, "exclus": dict(exclus), "nb_exclus": sum(exclus.values()),
           "a_venir": sorted(a_venir, key=lambda f: str(f.get("coup_d_envoi_utc"))), "en_cours": sorted(en_cours, key=lambda f: str(f.get("coup_d_envoi_utc"))),
           "reglees": sorted(reglees, key=lambda f: str(f.get("coup_d_envoi_utc")), reverse=True)}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    debut = datetime.now(timezone.utc)
    matchs, classements = charger_matchs(), charger_classements()
    n, erreurs = geler(maintenant=debut, matchs=matchs, classements=classements)
    r = resultats(matchs=matchs)
    p = page(derniere_analyse=debut)
    print(f"europe-gamma : {n} pronostic(s) gelé(s), {r} résultat(s) réglé(s), {len(p['a_venir'])} match(s) à venir avec pari, {p['sans_pronostic']} sans pari, {p['nb_exclus']} exclu(s) {p['exclus']}")
    if charger_parametres() is None:
        print("INFO : aucun calibrage (parametres.json absent) : paris d'aperçu NON calibré, comptés à part dans le bilan")
    if erreurs:
        for e in erreurs:
            print("ERREUR :", e)
        raise SystemExit(f"{len(erreurs)} match(s) exclu(s) par un contrôle mathématique")


if __name__ == "__main__":
    import sys
    {"pipeline": pipeline, "geler": lambda: print(geler()), "resultats": lambda: print(resultats()), "page": lambda: print(len(page()["a_venir"]))}.get(sys.argv[1] if len(sys.argv) > 1 else "pipeline", pipeline)()
