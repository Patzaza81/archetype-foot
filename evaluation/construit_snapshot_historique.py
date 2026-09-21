#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construit le jeu d'évaluation HISTORIQUE : tous les matchs déjà joués pour lesquels les runs passés ont enregistré les
cotes (BetPawa) ET l'historique saison en cours des deux équipes.

Sans indice de résultat : pour chaque match, on prend le DERNIER run publié AVANT le coup d'envoi (cotes et historiques tels
qu'ils étaient à ce moment-là), on applique exactement le pipeline du nouveau moteur (pont, règle des 2 matchs, moteur,
justification, sélection) et on fige le tout. Les scores sont récupérés ensuite (evaluation_scores.py), jamais avant.

    python evaluation/construit_snapshot_historique.py SORTIE.json [DATE_MAX AAAA-MM-JJ]
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, "evaluation"))
import branchement_moteur as bm
import pont_moteur
from archetype_model.h2h import h2h_stats
from construit_snapshot import construit_match


def git(*args):
    return subprocess.run(["git", "-C", RACINE, *args], capture_output=True, text=True).stdout


def versions():
    """[(commit, heure UTC)] des publications de precalcul.json, de la plus récente à la plus ancienne."""
    out = []
    for l in git("log", "--format=%H|%aI", "--", "precalcul.json").splitlines():
        h, iso = l.split("|")
        out.append((h, datetime.datetime.fromisoformat(iso).astimezone(datetime.timezone.utc)))
    return out


def coup_d_envoi_utc(signal):
    """Date + heure du Cameroun (UTC+1) -> UTC ; None si l'heure n'est pas un horaire (TER, MT, minute de jeu, REP...)."""
    hc = str(signal.get("heure_cameroun") or "")
    if not re.fullmatch(r"\d{2}:\d{2}", hc):
        return None
    return datetime.datetime.strptime(f"{signal['date']} {hc}", "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(hours=1)


def stats_depuis_fenetres(signal):
    """Statistiques du moteur d'après les fenêtres SAISON EN COURS stockées dans le run (équipe qui reçoit : ses matchs à domicile ;
    visiteuse : ses matchs à l'extérieur). Une fenêtre non utilisable = équipe absente : le match sera refusé."""
    fen = ((signal.get("archetype_model") or {}).get("fenetres")) or {}
    out = {}
    for cle, nom, domicile in (("A", signal["domicile"], True), ("B", signal["exterieur"], False)):
        w = fen.get(cle) or {}
        m = [x for x in (w.get("matchs_retenus") or []) if x.get("domicile") is domicile]
        if w.get("statut") != "UTILISABLE" or not m:
            continue
        lieu = "domicile" if domicile else "exterieur"
        r = {"nb_domicile": 0, "nb_exterieur": 0, "matchs_domicile_bruts": [], "matchs_exterieur_bruts": [], "source": "saison_en_cours_seule"}
        r[f"nb_{lieu}"] = len(m)
        r[f"matchs_{lieu}_bruts"] = m
        r[f"gf_{lieu}"] = sum(x["buts_marques"] for x in m) / len(m)
        r[f"ga_{lieu}"] = sum(x["buts_encaisses"] for x in m) / len(m)
        out[(nom, signal["competition"])] = r
    return out


def construit(date_max="2026-09-20"):
    pris, matchs, exclus = set(), [], Counter()
    for commit, heure_run in versions():
        txt = git("show", f"{commit}:precalcul.json")
        if not txt:
            continue
        try:
            P = json.loads(txt)
            H = json.loads(git("show", f"{commit}:cache_h2h.json") or "{}")
        except ValueError:
            continue
        for s in P["signaux"]:
            if s["match_id"] in pris or not s.get("cotes_manuelles") or s["date"] > date_max:
                continue
            envoi = coup_d_envoi_utc(s)
            if envoi is None:
                exclus["horaire non exploitable (match commencé ou terminé au moment du run)"] += 1
                continue
            if heure_run >= envoi:
                exclus["run publié après le coup d'envoi"] += 1
                continue
            stats = stats_depuis_fenetres(s)

            def h2h(sig, H=H):
                brut = (H.get(sig["url_match"] + "?p=face-a-face") or {}).get("resultat") or []
                norm = [n for n in (h2h_stats._normalise_confrontation(c, sig["domicile"]) for c in brut) if n is not None]
                return h2h_stats.classifie_h2h(norm).get("confrontations_retenues", [])

            signal = {k: v for k, v in s.items() if k in ("match_id", "domicile", "exterieur", "competition", "date", "heure", "cotes_manuelles", "url_match")}
            bloc, _ = bm.analyse_signal(signal, stats, heure_run, h2h)
            if bloc["statut"] != "OK":
                exclus[f"{bloc['statut']} / {bloc.get('raison', '').split(':')[0][:50]}"] += 1
                continue
            match, _ = pont_moteur.match_vers_moteur(signal, stats, heure_run.strftime("%Y-%m-%dT%H:%M:%SZ"))
            match.pop("_ignores", None)
            m = construit_match(match, signal, bloc, heure_run)
            m["donnees_du_run"] = {"commit": commit[:7], "heure_utc": heure_run.strftime("%Y-%m-%dT%H:%M:%SZ")}
            matchs.append(m)
            pris.add(s["match_id"])
    matchs.sort(key=lambda m: (m["date"], m["heure"], m["id"]))
    return {"schema": 1, "moteur": {"nom": bm.NOM_MOTEUR, "version": bm.VERSION_MOTEUR},
            "origine": ("moteur_v2_6_9 (règle D6 des 2 matchs par lieu incluse) appliqué à TOUS les matchs déjà joués dont les runs passés ont enregistré cotes et "
                        "historiques saison en cours des deux équipes ; pour chaque match, données du dernier run publié avant le coup d'envoi ; "
                        "construit avant toute connaissance des scores"),
            "construit_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "nb_matchs": len(matchs), "matchs": matchs}, exclus


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    snap, exclus = construit(sys.argv[2] if len(sys.argv) > 2 else "2026-09-20")
    texte = json.dumps(snap, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    open(sys.argv[1], "w", encoding="utf-8").write(texte)
    open(sys.argv[1] + ".sha256", "w").write(hashlib.sha256(texte.encode("utf-8")).hexdigest() + "\n")
    print(f"{snap['nb_matchs']} matchs écrits dans {sys.argv[1]} ({len(texte)//1024} Ko)")
    print("par date :", dict(sorted(Counter(m["date"] for m in snap["matchs"]).items())))
    print("exclusions :", dict(exclus.most_common()))
