"""Suivi du moteur DC en production. Usage : python -m moteur_dc.suivi [pipeline|geler|resultats|page]

Même mécanique que les autres moteurs, code autonome :
- geler()     : pour chaque match à venir (coup d'envoi > maintenant), Modules 1 → 4 (coeur.py), puis AJOUT d'une ligne « pronostic » horodatée au journal
                `data/dc/journal.jsonl` (ajout seul). Nouvelle ligne seulement si la sélection a changé ; la DERNIÈRE ligne écrite avant le coup d'envoi compte.
- resultats() : pour les pronostics dont le score est connu, ajoute UNE ligne « resultat » (gagné / perdu par pari), jamais modifiée.
- page()      : `data/dc/pronostics.json` (lecture seule côté navigateur) ; bilan calculé uniquement sur les pronostics gelés avant le match.
Aucun lien avec V2, V3, V2R, v, Europe, alpha, omega, le Journal ni le générateur de tickets.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as K, coeur, donnees as D, marches as M, module1 as M1

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "dc"
JOURNAL = DOSSIER / "journal.jsonl"
PAGE = DOSSIER / "pronostics.json"
PARAMS = Path(__file__).with_name("parametres.json")
VALIDATION = ROOT / "docs" / "dc_validation.json"
JOURS_REGLES_AFFICHES = 7
JOURS_EMAC = 30                       # Module 4 : EMAC recalculée sur les 30 derniers jours glissants (spécification de Patrick)


def charger_parametres(chemin: Path = PARAMS) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _empreinte(chemin: Path = PARAMS) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:12] if chemin.exists() else "absent"


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "inconnu"
    except Exception:
        return "inconnu"


def _lire(journal: Path) -> list[dict[str, Any]]:
    if not journal.exists():
        return []
    return [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()]


def _ajouter(journal: Path, lignes: list[dict[str, Any]]) -> None:
    if not lignes:
        return
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")


def _ko(x: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return None


def _pari(l: dict[str, Any]) -> dict[str, Any]:
    return {"cle": l["cle"], "marche": l["marche"], "valeur_reelle": l.get("valeur_reelle"), "famille": l["famille"], "cote": l["cote"],
            "p": round(l["p"], 4), "base": l.get("base"), "edge": l.get("edge"), "seuil": l.get("seuil"), "avertissement": l.get("avertissement"),
            "preuve": l.get("preuve"), "decision": l.get("decision")}


def emac_glissante(lignes: list[dict[str, Any]], jour: str, matchs: list[dict], defaut: float) -> tuple[float, str, int]:
    """EMAC du Module 4 : erreur de calibration sur TOUS les marchés des matchs gelés puis terminés dans les 30 jours avant `jour`.
    Sans aucun match terminé dans la fenêtre : valeur hors échantillon du calibrage (Football-Data 2026-27)."""
    scores = {m["id"]: (m["h"], m["a"]) for m in matchs if m.get("h") is not None}
    debut = (datetime.fromisoformat(jour) - timedelta(days=JOURS_EMAC)).date().isoformat()
    P, Y = [], []
    for mid, l in derniers_pronostics(lignes).items():
        f = l["fiche"]
        pm = f.get("p_marches")
        if not pm or mid not in scores or not (debut <= f["jour"] < jour) or len(pm) != len(coeur.CLES):
            continue
        h, a = scores[mid]
        P.extend(pm)
        Y.extend(float(coeur.TESTS[c](h, a)) for c in coeur.CLES)
    if not P:
        return defaut, "calibrage hors échantillon (Football-Data 2026-27)", 0
    return K.emac(np.array(P), np.array(Y)), f"journal gelé, {JOURS_EMAC} derniers jours", len(P) // len(coeur.CLES)


def fiche(m: dict[str, Any], a: dict[str, Any], s: dict[str, Any], matchs: list[dict]) -> dict[str, Any]:
    """Tout ce qui est gelé et affiché pour un match (de quoi auditer la décision)."""
    out = {"match_id": m["id"], "jour": m["jour"], "heure": m.get("heure"), "coup_d_envoi_utc": m.get("coup_d_envoi_utc"),
           "competition": m.get("competition"), "domicile": m["domicile"], "exterieur": m["exterieur"], "statut": a["statut"],
           "n_domicile": a["n_domicile"], "n_exterieur": a["n_exterieur"]}
    if a["statut"] != "analyse":
        return {**out, "raison": a.get("raison"), "principal": None, "autres": []}
    eq = a["parametres_equipes"]
    return {**out, "principal": _pari(s["principal"]) if s["principal"] else None, "autres": [_pari(x) for x in s["autres"]], "raison": s.get("raison"),
            "module4": {"marches_testes": s["m"], "z_seuil_bonferroni": s["z_seuil"], "emac": s["emac"], "emac_source": s.get("emac_source")},
            "buts_attendus": {k: round(v, 3) for k, v in a["buts_attendus"].items()},
            "buts_attendus_avant_effets": {k: round(v, 3) for k, v in a["buts_attendus_avant_effets"].items()},
            "modele": a["modele"], "facteurs": a["facteurs"], "excedents_profil": a["excedents_profil"], "scores_probables": a["scores_probables"],
            "equipes": {k: {x: eq[k].get(x) for x in ("position", "Pts", "J", "PPM", "forme_ppm", "IE", "IE_dom", "IE_ext", "profil", "style_tag",
                                                       "score_modal_dom", "score_modal_ext", "amplitude_dom", "amplitude_ext", "MBM_dom", "MBE_dom", "MBM_ext", "MBE_ext")}
                        for k in ("dom", "ext")},
            "gap": a["contrat"].get("gap"), "p_marches": a["p_marches"],
            "derniers_matchs": {"dom": D.derniers_au_lieu(matchs, m["eq_dom"], True, m["jour"]), "ext": D.derniers_au_lieu(matchs, m["eq_ext"], False, m["jour"])}}


def _cle_selection(f: dict[str, Any]) -> str:
    p = f.get("principal") or {}
    return json.dumps([f.get("statut"), p.get("cle"), p.get("cote"), [(x["cle"], x["cote"]) for x in f.get("autres") or []]], sort_keys=True)


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, ligues: D.Ligues | None = None, matchs: list[dict] | None = None,
          params: dict[str, Any] | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc)
    params = params or charger_parametres()
    if ligues is None:
        ligues = D.charger_ligues()
    if matchs is None:
        matchs = D.charger_archive(ligues)
    lignes = _lire(journal)
    dernier = {l["match_id"]: _cle_selection(l["fiche"]) for l in lignes if l["type"] == "pronostic"}
    caches: dict[tuple, Any] = {}
    emacs: dict[str, tuple] = {}
    nouveaux = []
    for m in matchs:
        ko = _ko(m.get("coup_d_envoi_utc"))
        if ko is None or ko <= maintenant or m.get("h") is not None:
            continue
        liste = ligues.matchs.get(m["ligue"]) or []
        cle = (m["ligue"], m["jour"])
        if cle not in caches:
            t = M1.tableau(liste, m["jour"]) if liste else None
            fit = coeur.ajuster_ligue(liste, m["jour"], params, t) if liste else None
            caches[cle] = (fit, t, coeur.bases_ligue(liste, m["jour"]) if fit else None)
        fit, t, bases = caches[cle]
        if fit is None:
            a = {"id": m["id"], "jour": m["jour"], "domicile": m["domicile"], "exterieur": m["exterieur"], "n_domicile": 0, "n_exterieur": 0,
                 "statut": "exclu", "raison": "championnat sans match connu"}
        else:
            a = coeur.analyser(m, liste, params, fit, t, bases)
        if m["jour"] not in emacs:
            emacs[m["jour"]] = emac_glissante(lignes, m["jour"], matchs, params["emac"])
        e, source, n_e = emacs[m["jour"]]
        s = coeur.selectionner(a, params, e)
        s["emac_source"] = f"{source}" + (f" ({n_e} matchs)" if n_e else "")
        f = fiche(m, a, s, liste)
        if dernier.get(f["match_id"]) == _cle_selection(f):
            continue
        nouveaux.append({"type": "pronostic", "match_id": f["match_id"], "gele_le": maintenant.isoformat(timespec="seconds"),
                         "commit": _commit(), "parametres": _empreinte(), "version": params.get("version"), "fiche": f})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def derniers_pronostics(lignes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pour chaque match, la DERNIÈRE ligne « pronostic » écrite avant le coup d'envoi."""
    out: dict[str, dict] = {}
    for l in lignes:
        if l["type"] != "pronostic":
            continue
        ko, gel = _ko(l["fiche"].get("coup_d_envoi_utc")), _ko(l["gele_le"])
        if ko is None or gel is None or gel >= ko:
            continue
        out[l["match_id"]] = l
    return out


def resultats(journal: Path = JOURNAL, matchs: list[dict] | None = None, ligues: D.Ligues | None = None) -> int:
    lignes = _lire(journal)
    faits = {l["match_id"] for l in lignes if l["type"] == "resultat"}
    if matchs is None:
        matchs = D.charger_archive(ligues or D.charger_ligues())
    scores = {m["id"]: (m["h"], m["a"]) for m in matchs if m.get("h") is not None}
    nouveaux = []
    for mid, l in derniers_pronostics(lignes).items():
        if mid in faits or mid not in scores:
            continue
        h, a = scores[mid]
        f = l["fiche"]
        paris = ([("principal", f["principal"])] if f.get("principal") else []) + [("autre", x) for x in f.get("autres") or []]
        regles = [{"role": r, "marche": p["marche"], "cle": p["cle"], "cote": p["cote"], "p": p["p"],
                   "gagne": bool(M.test_du_marche(*p["cle"])(h, a))} for r, p in paris]
        nouveaux.append({"type": "resultat", "match_id": mid, "score": [h, a], "regle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "paris": regles})
    _ajouter(journal, nouveaux)
    return len(nouveaux)


def _stats(paris: list[dict[str, Any]]) -> dict[str, Any]:
    if not paris:
        return {"regles": 0}
    g = sum(p["gagne"] for p in paris)
    c = [p for p in paris if p.get("cote")]
    return {"regles": len(paris), "gagnes": g, "reussite": round(g / len(paris), 4), "annonce": round(sum(p["p"] for p in paris) / len(paris), 4),
            "avec_cote": len(c), "cote_moyenne": round(sum(p["cote"] for p in c) / len(c), 3) if c else None}


def bilan(lignes: list[dict[str, Any]]) -> dict[str, Any]:
    res = [l for l in lignes if l["type"] == "resultat"]
    return {"principal": _stats([p for l in res for p in l["paris"] if p["role"] == "principal"]),
            "autres": _stats([p for l in res for p in l["paris"] if p["role"] == "autre"]), "matchs_regles": len(res)}


def _noms_derniers(f: dict[str, Any], noms: dict[str, str] | None) -> dict[str, Any]:
    """Affichage : un adversaire gelé sous son identité interne (lignes gelées avant le 30/10/2026 18 h) reçoit son nom d'équipe."""
    d = f.get("derniers_matchs")
    if not noms or not d:
        return f
    f["derniers_matchs"] = {k: [dict(x, adversaire=noms.get(x.get("adversaire"), x.get("adversaire"))) for x in v] for k, v in d.items()}
    return f


def page(maintenant: datetime | None = None, journal: Path = JOURNAL, sortie: Path = PAGE, noms: dict[str, str] | None = None) -> dict[str, Any]:
    maintenant = maintenant or datetime.now(timezone.utc)
    lignes = _lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    tous = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    gels = derniers_pronostics(lignes)
    a_venir, en_cours, reglees, sans = [], [], [], 0
    for mid, l in tous.items():
        f = _noms_derniers(dict((gels.get(mid) or l)["fiche"]), noms)
        ko = _ko(f.get("coup_d_envoi_utc"))
        if ko is None:
            continue
        if not f.get("principal"):
            sans += ko > maintenant
            continue
        if mid in res:
            if ko < maintenant - timedelta(days=JOURS_REGLES_AFFICHES):
                continue
            r = res[mid]
            f["score"] = r["score"]
            gagnes = {json.dumps(p["cle"]): p["gagne"] for p in r["paris"]}
            for p in [f["principal"]] + f["autres"]:
                p["resultat"] = "WIN" if gagnes.get(json.dumps(p["cle"])) else "LOSS"
            reglees.append(f)
        elif ko > maintenant:
            a_venir.append(f)
        elif ko > maintenant - timedelta(hours=6):
            en_cours.append(f)
    try:
        val = json.loads(VALIDATION.read_text(encoding="utf-8"))
        val = {"matchs_fd_2627": val["validation_fd_2627"]["matchs"], "emac": val["validation_fd_2627"]["emac"], "effets": val["effets"]["final"]}
    except Exception:
        val = None
    p = charger_parametres() if PARAMS.exists() else {}
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "version": p.get("version"), "statut": "observation", "effets": p.get("effets"), "emac_calibrage": p.get("emac"),
           "validation": val, "bilan": bilan(lignes), "sans_pronostic": sans,
           "a_venir": sorted(a_venir, key=lambda f: str(f.get("coup_d_envoi_utc"))), "en_cours": sorted(en_cours, key=lambda f: str(f.get("coup_d_envoi_utc"))),
           "reglees": sorted(reglees, key=lambda f: str(f.get("coup_d_envoi_utc")), reverse=True)}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    ligues = D.charger_ligues()
    matchs = D.charger_archive(ligues)
    n = geler(ligues=ligues, matchs=matchs)
    r = resultats(matchs=matchs)
    p = page(noms=ligues.noms)
    print(f"dc : {n} pronostic(s) gelé(s), {r} résultat(s) réglé(s), {len(p['a_venir'])} pari(s) à venir, {p['sans_pronostic']} match(s) sans pronostic")


if __name__ == "__main__":
    import sys
    {"pipeline": pipeline, "geler": lambda: print(geler()), "resultats": lambda: print(resultats()), "page": lambda: print(len(page()["a_venir"]))}.get(
        sys.argv[1] if len(sys.argv) > 1 else "pipeline", pipeline)()
