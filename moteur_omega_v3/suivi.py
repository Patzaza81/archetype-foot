"""Suivi du moteur Omega V3 (page Gamma depuis le 02/11/2026). Usage : python -m moteur_omega_v3.suivi [pipeline|geler|resultats|page]

Même mécanique que les autres moteurs, code autonome (aucun import d'un autre moteur) :
- geler()     : pour chaque match à venir (coup d'envoi > maintenant), les quatre séquences → exploration (coeur.py) → sélection, puis AJOUT d'une ligne « pronostic »
                horodatée au journal `data/gamma/journal.jsonl` (ajout seul). Nouvelle ligne seulement si la sélection ou les données ont changé ;
                la DERNIÈRE ligne écrite avant le coup d'envoi compte. Un contrôle mathématique raté (§14) EXCLUT le match et fait échouer l'étape : jamais de pari publié sur un calcul faux.
- resultats() : pour les pronostics dont le score est connu, ajoute UNE ligne « resultat » (gagné / perdu / remboursé par pari), jamais modifiée.
- page()      : `data/gamma/pronostics.json` (lecture seule côté navigateur) ; bilan calculé uniquement sur les pronostics gelés avant le match.
Le journal du moteur DC (`data/dc/`) n'est ni lu ni modifié : il reste l'historique gelé de l'ancien Gamma.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import coeur as C, donnees as D, marches as M

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "gamma"
JOURNAL = DOSSIER / "journal.jsonl"
PAGE = DOSSIER / "pronostics.json"
PARAMS = Path(__file__).with_name("parametres.json")
JOURS_REGLES_AFFICHES = 7


def charger_parametres(chemin: Path = PARAMS) -> dict[str, Any] | None:
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None


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
    """Un pari retenu, gelé en entier : de quoi retrouver chaque chiffre à partir des observations d'origine."""
    return {"cle": l["cle"], "famille": l["famille"], "cote": l.get("cote"), "p_implicite": l.get("p_implicite"), "p_implicite_corrigee": l.get("p_implicite_corrigee"),
            "marge": l.get("marge"), "k": l["k"], "n": l["n"], "f": l["f"], "g": l["g"], "niveaux": l["niveaux"], "stabilite": l["stabilite"], "diversite": l["diversite"],
            "contradiction": l["contradiction"], "seuil": l.get("seuil"), "p_calibree": l.get("p_calibree"), "ecart_implicite": l.get("ecart_implicite"), "ev": l.get("ev"),
            "statut": l["statut"], "raison": l["raison"]}


def _compact(m: dict[str, Any]) -> list[Any]:
    """Un marché du tableau « tous les marchés » (§16.D), en ligne positionnelle : [k, remboursés, strict, intermédiaire, élargi, g, f_min, f_max, part max, dépendance, code, cote, seuil].
    L'ordre des marchés est celui de `marches.CLES` (empreinte `ordre_marches` gelée avec la fiche)."""
    nv = m["niveaux"]
    return [m["k"], m["remb"], nv["strict"]["k"], nv["intermediaire"]["k"], nv["elargi"]["k"], m["g"], m["stabilite"]["f_min"], m["stabilite"]["f_max"],
            m["diversite"]["part_max_observation"], int(m["stabilite"]["dependance_unique"]), m["code"], m.get("cote") or 0, m.get("seuil")]


ORDRE = hashlib.sha256("|".join(M.cle_txt(c) for c in M.CLES).encode()).hexdigest()[:12]


def fiche(m: dict[str, Any], s: dict[str, Any] | None, a: dict[str, Any] | None, sel: dict[str, Any] | None, raison: str | None = None) -> dict[str, Any]:
    out = {"match_id": m["id"], "jour": m["jour"], "heure": m.get("heure"), "coup_d_envoi_utc": m.get("coup_d_envoi_utc"), "competition": m.get("competition"),
           "domicile": m["domicile"], "exterieur": m["exterieur"], "statut": "analyse" if a else "exclu"}
    if a is None or s is None or sel is None:
        return {**out, "raison": raison, "principal": None, "autres": []}
    ex = a["exploration"]
    return {**out, "n_domicile": s["n_a_total"], "n_exterieur": s["n_b_total"], "raison": sel["raison"],
            "principal": _pari(sel["principal"]) if sel["principal"] else None, "autres": [_pari(x) for x in sel["autres"]],
            "donnees": {"domicile": s["A"], "exterieur": s["B"], "sequences": a["entrees"], "source": "assemblage des équipes (Matchendirect), matchs terminés strictement avant le jour du match"},
            "exploration": {"combinaisons": a["combinaisons"], "scores_distincts": a["scores_distincts"], "top_scores": ex["top_scores"], "concentration_top3": ex["concentration_top3"],
                            "issues": ex["issues"], "buts_a": ex["buts_a"], "buts_b": ex["buts_b"], "totaux": ex["totaux"]},
            "niveaux": a["niveaux"], "verifications": {"total": len(a["verifications"]), "reussies": sum(v["ok"] for v in a["verifications"])},
            "conclusion": a["conclusion"], "empreinte": a["empreinte"], "ordre_marches": ORDRE,
            "tous_marches": [_compact(x) for x in a["marches"]], "a_surveiller": [{"cle": x["cle"], "raison": x["raison"], "g": x["g"], "cote": x.get("cote")}
                                                                                    for x in a["marches"] if x["statut"] == "a_surveiller"],
            "derniers_matchs": {"dom": list(reversed(s["A"])), "ext": list(reversed(s["B"]))}}


def _cle_selection(f: dict[str, Any]) -> str:
    p = f.get("principal") or {}
    return json.dumps([f.get("statut"), f.get("empreinte"), p.get("cle"), p.get("cote"), [(x["cle"], x["cote"]) for x in f.get("autres") or []], f.get("raison")], sort_keys=True)


def analyser_match(m: dict[str, Any], liste: list[dict] | None, calib: dict[str, Any] | None) -> dict[str, Any]:
    """Une fiche gelable pour un match (analysée ou exclue avec sa raison). Lève RuntimeError si un contrôle mathématique échoue."""
    if not liste:
        return fiche(m, None, None, None, "championnat sans match connu")
    try:
        s = D.sequences(liste, m["eq_dom"], m["eq_ext"], m["jour"])
    except ValueError as e:
        return fiche(m, None, None, None, str(e))
    a = C.analyser(s["att_a"], s["def_a"], s["att_b"], s["def_b"], cotes=m.get("cotes"), calib=calib)
    rates = [v["nom"] for v in a["verifications"] if not v["ok"]]
    if rates:
        raise RuntimeError(f"contrôle mathématique échoué pour {m['domicile']} – {m['exterieur']} ({m['jour']}) : {rates}")
    return fiche(m, s, a, C.selection(a))


def geler(maintenant: datetime | None = None, journal: Path = JOURNAL, ligues: D.Ligues | None = None, matchs: list[dict] | None = None,
          calib: dict[str, Any] | None = None) -> tuple[int, list[str]]:
    maintenant = maintenant or datetime.now(timezone.utc)
    calib = calib if calib is not None else charger_parametres()
    if ligues is None:
        ligues = D.charger_ligues()
    if matchs is None:
        matchs = D.charger_archive(ligues)
    dernier = {l["match_id"]: _cle_selection(l["fiche"]) for l in _lire(journal) if l["type"] == "pronostic"}
    nouveaux, erreurs = [], []
    for m in matchs:
        ko = _ko(m.get("coup_d_envoi_utc"))
        if ko is None or ko <= maintenant or m.get("h") is not None:
            continue
        try:
            f = analyser_match(m, ligues.matchs.get(m["ligue"]) or [], calib)
        except RuntimeError as e:
            erreurs.append(str(e))
            continue
        if dernier.get(f["match_id"]) == _cle_selection(f):
            continue
        nouveaux.append({"type": "pronostic", "match_id": f["match_id"], "gele_le": maintenant.isoformat(timespec="seconds"), "commit": _commit(),
                         "parametres": _empreinte(), "version": (calib or {}).get("version", "sans calibrage"), "fiche": f})
    _ajouter(journal, nouveaux)
    return len(nouveaux), erreurs


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
        regles = []
        for r, p in paris:
            v = M.resultat((p["cle"][0], p["cle"][1]), h, a)
            regles.append({"role": r, "marche": M.libelle((p["cle"][0], p["cle"][1])), "cle": p["cle"], "cote": p["cote"], "p": p.get("p_calibree"),
                           "gagne": None if v == 2 else bool(v), "rembourse": v == 2})
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
    return {"principal": _stats([p for l in res for p in l["paris"] if p["role"] == "principal"]),
            "autres": _stats([p for l in res for p in l["paris"] if p["role"] == "autre"]), "matchs_regles": len(res)}


def page(maintenant: datetime | None = None, journal: Path = JOURNAL, sortie: Path = PAGE, derniere_analyse: datetime | None = None) -> dict[str, Any]:
    """`derniere_analyse` = heure de la dernière analyse réussie du moteur (pipeline) ; la page l'affiche : si le pipeline plante, elle reste ancienne."""
    maintenant = maintenant or datetime.now(timezone.utc)
    lignes = _lire(journal)
    res = {l["match_id"]: l for l in lignes if l["type"] == "resultat"}
    tous = {l["match_id"]: l for l in lignes if l["type"] == "pronostic"}
    gels = derniers_pronostics(lignes)
    a_venir, en_cours, reglees, sans = [], [], [], 0
    for mid, l in tous.items():
        f = dict((gels.get(mid) or l)["fiche"])
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
    out = {"genere_le": maintenant.isoformat(timespec="seconds"), "derniere_analyse": (derniere_analyse or maintenant).isoformat(timespec="seconds"),
           "version": p.get("version"), "statut": "observation", "calibrage": p.get("echantillon"), "cote_min": p.get("cote_min"), "ordre_marches": ORDRE,
           "cles_marches": [list(c) for c in M.CLES], "bilan": bilan(lignes), "sans_pronostic": sans,
           "a_venir": sorted(a_venir, key=lambda f: str(f.get("coup_d_envoi_utc"))), "en_cours": sorted(en_cours, key=lambda f: str(f.get("coup_d_envoi_utc"))),
           "reglees": sorted(reglees, key=lambda f: str(f.get("coup_d_envoi_utc")), reverse=True)}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


def pipeline() -> None:
    debut = datetime.now(timezone.utc)
    ligues = D.charger_ligues()
    matchs = D.charger_archive(ligues)
    n, erreurs = geler(maintenant=debut, ligues=ligues, matchs=matchs)
    r = resultats(matchs=matchs)
    p = page(derniere_analyse=debut)
    print(f"gamma (omega v3) : {n} pronostic(s) gelé(s), {r} résultat(s) réglé(s), {len(p['a_venir'])} match(s) à venir avec pari, {p['sans_pronostic']} sans pari")
    if charger_parametres() is None:
        print("ATTENTION : aucun calibrage (parametres.json absent) : le moteur n'évalue aucun marché")
    if erreurs:
        for e in erreurs:
            print("ERREUR :", e)
        raise SystemExit(f"{len(erreurs)} match(s) exclu(s) par un contrôle mathématique : la page est publiée sans eux, l'étape est en échec pour que ce soit visible")


if __name__ == "__main__":
    import sys
    {"pipeline": pipeline, "geler": lambda: print(geler()), "resultats": lambda: print(resultats()), "page": lambda: print(len(page()["a_venir"]))}.get(
        sys.argv[1] if len(sys.argv) > 1 else "pipeline", pipeline)()
