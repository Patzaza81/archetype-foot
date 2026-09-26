# -*- coding: utf-8 -*-
"""Enregistrement des scores réels dans historique_pronostics.json (RÉTABLI le 26/09/2026).

Constat du 26/09/2026 : aucun match joué depuis le 18/09 n'avait son score dans historique_pronostics.json. L'étape
« Vérifier les scores des jours précédents » (verification_resultats.py) avait été retirée du pipeline le 13/09 avec le
panier manuel, puis le fichier supprimé : plus rien n'écrivait le champ `score`. Conséquence : le journal de rentabilité
(journal_rentabilite.py), la page Système et les « équipes à suivre » ne voyaient plus aucun nouveau résultat.

Ce script remet cette écriture en place, avec la méthode déjà éprouvée par archetype_model/learning/resultats.py :
- une seule page par jour : la page des résultats Matchendirect de ce jour (scraper.url_resultat_foot) ;
- un match n'est rempli que si son statut est exactement « TER » (terminé) : un match reporté, suspendu ou en cours
  reste sans score (jamais un score partiel écrit comme définitif) ;
- équipes reconnues avec scraper_details._memes_equipes (même règle que le reste du pipeline) ;
- toutes les entrées d'un même match (il apparaît dans plusieurs jours de l'historique) reçoivent le même score ;
- un score déjà présent n'est jamais modifié.

Rattrapage : sans limite de jours par défaut, tous les jours passés qui ont encore des matchs sans score sont traités
(une page par jour, pause entre deux pages). Usage :
    python enregistre_scores_historique.py                 # tous les jours passés incomplets
    python enregistre_scores_historique.py --jours 10      # seulement les 10 derniers jours (run nocturne)
"""
import argparse
import datetime
import json
import sys
import time

FICHIER_HISTORIQUE = "historique_pronostics.json"
PAUSE_S = 2.0


def _trouve_score(matchs_page, dom, ext, memes_equipes):
    """Score « D-E » du match si la page le donne TERMINÉ, sinon None (même règle que resultats._trouve_score)."""
    for m in matchs_page:
        if memes_equipes(m.get("domicile") or "", dom) and memes_equipes(m.get("exterieur") or "", ext):
            if m.get("score") is not None and m.get("heure") == "TER":
                return m["score"]
            return None
    return None


def jours_a_traiter(historique, aujourdhui, jours_max=None):
    """{date_du_match: [entrées sans score]} pour les jours STRICTEMENT passés."""
    out = {}
    for jour in historique:
        for m in jour.get("matchs", []) or []:
            if m.get("score"):
                continue
            try:
                d = datetime.date.fromisoformat(str(m.get("date") or jour.get("date"))[:10])
            except ValueError:
                continue
            if d >= aujourdhui or (jours_max is not None and (aujourdhui - d).days > jours_max):
                continue
            out.setdefault(d, []).append(m)
    return dict(sorted(out.items()))


def enregistre(historique, aujourdhui, charge_page, memes_equipes, jours_max=None, pause=PAUSE_S):
    """Remplit les scores en place. charge_page(date) -> liste de matchs de la page résultats (domicile, exterieur,
    score, heure). Renvoie le bilan."""
    a_traiter = jours_a_traiter(historique, aujourdhui, jours_max)
    bilan = {"jours": len(a_traiter), "matchs_remplis": 0, "entrees_remplies": 0, "sans_score_termine": 0,
             "pages_en_echec": [], "par_jour": {}}
    # toutes les entrées de chaque match (même match_id sur plusieurs jours de l'historique)
    par_id = {}
    for jour in historique:
        for m in jour.get("matchs", []) or []:
            if m.get("match_id"):
                par_id.setdefault(m["match_id"], []).append(m)
    deja = set()
    for n, (d, entrees) in enumerate(a_traiter.items()):
        try:
            page = charge_page(d)
        except Exception as exc:
            bilan["pages_en_echec"].append(f"{d.isoformat()} : {exc}")
            continue
        remplis = 0
        for m in entrees:
            cle = m.get("match_id") or (m.get("domicile"), m.get("exterieur"), d)
            if cle in deja:
                continue
            score = _trouve_score(page, m.get("domicile") or "", m.get("exterieur") or "", memes_equipes)
            if score is None:
                bilan["sans_score_termine"] += 1
                continue
            cibles = par_id.get(m.get("match_id"), [m]) if m.get("match_id") else [m]
            for e in cibles:
                if not e.get("score"):
                    e["score"] = score
                    bilan["entrees_remplies"] += 1
            deja.add(cle)
            remplis += 1
            bilan["matchs_remplis"] += 1
        bilan["par_jour"][d.isoformat()] = {"sans_score_avant": len(entrees), "remplis": remplis}
        if pause and n < len(a_traiter) - 1:
            time.sleep(pause)
    return bilan


def _charge_page_matchendirect(d):
    from scraper import fetch_html, parse_matches, url_resultat_foot
    html, _ = fetch_html(url_resultat_foot(d))
    return parse_matches(html, max_matchs=2000, date_label=d.isoformat())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours", type=int, default=None, help="ne traiter que les N derniers jours (défaut : tous)")
    args = parser.parse_args()
    from run_pipeline import aujourdhui_france
    from scraper_details import _memes_equipes
    with open(FICHIER_HISTORIQUE, encoding="utf-8") as f:
        historique = json.load(f)
    bilan = enregistre(historique, aujourdhui_france(), _charge_page_matchendirect, _memes_equipes, jours_max=args.jours)
    if bilan["entrees_remplies"]:
        with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
            json.dump(historique, f, ensure_ascii=False, indent=2)
    print(f"[scores] {bilan['jours']} jour(s) à compléter ; {bilan['matchs_remplis']} match(s) rempli(s) "
          f"({bilan['entrees_remplies']} entrée(s)) ; {bilan['sans_score_termine']} sans score terminé sur la page ; "
          f"pages en échec : {len(bilan['pages_en_echec'])}")
    for d, v in bilan["par_jour"].items():
        print(f"  {d} : {v['remplis']} / {v['sans_score_avant']}")
    for e in bilan["pages_en_echec"]:
        print(f"  ÉCHEC {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
