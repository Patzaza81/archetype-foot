"""
corrige_dates_historique.py -- (05/09/2026) rattrapage ponctuel du point
critique #4 de TRANSITION.md : environ 333 matchs archivés entre le 24 et
le 30/08/2026 ont une date enregistrée fausse (bug fuseau horaire corrigé
le 04/09, voir run_pipeline.aujourdhui_france()) et restent sans score
vérifié -- verification_resultats.py cherchait leur score sur la MAUVAISE
page (celle de la date fausse), ne le trouvait jamais, et de toute façon
n'y touche plus (NB_JOURS_MAX_A_VERIFIER=10, ces jours sont maintenant
hors fenêtre).

CE SCRIPT NE CORRIGE QUE LES MATCHS ANALYSÉS (verdict_global GO/NO_GO
déjà présent) -- ce sont les seuls dont le score compte pour le ROI/
calibrage (calcule_roi.py). Les matchs jamais évalués (raison_non_traite)
ne sont pas touchés : leur date fausse n'a aucune conséquence sur rien.

MÉTHODE -- pour chaque match candidat, au lieu de chercher UNIQUEMENT sur
la page de sa date enregistrée (comme verification_resultats.py), on
cherche sur J-1, J, J+1 (la date enregistrée ET les deux jours autour --
le bug ne pouvait décaler que d'un jour, jamais plus). Dès qu'un score
avec statut "TER" (terminé) est trouvé sur l'une des trois pages :
- le score est écrit, exactement comme verification_resultats.py
  (jamais un score sans statut TER confirmé -- même garde-fou)
- le champ "date" du match ET le bucket "jour" qui le contient sont
  corrigés pour refléter la VRAIE date trouvée (pas seulement le score)
- si le nouveau bucket "jour" n'existe pas encore dans l'historique, il
  est créé

Un match resté introuvable sur les 3 jours n'est jamais deviné -- laissé
tel quel, toujours score=None, pour un prochain passage manuel.

Usage : python corrige_dates_historique.py [--dry-run]
--dry-run : affiche ce qui serait changé sans écrire le fichier.
"""
import datetime
import json
import sys

from scraper import parse_matches, url_resultat_foot, fetch_html
from scraper_details import _memes_equipes

FICHIER_HISTORIQUE = "historique_pronostics.json"
DEBUT_FENETRE_BUGUEE = datetime.date(2026, 8, 24)
FIN_FENETRE_BUGUEE = datetime.date(2026, 8, 30)


def charge_historique():
    with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
        return json.load(f)


def sauve_historique(historique):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)


def trouve_score_termine(matchs_page, domicile, exterieur):
    """Identique à verification_resultats.trouve_score() -- ne renvoie un
    score que si le statut scrapé est bien "TER" (terminé). Dupliqué ici
    plutôt qu'importé pour ne jamais risquer de modifier le comportement
    du script de production en cas de refactor futur de l'un des deux."""
    for m in matchs_page:
        if _memes_equipes(m["domicile"], domicile) and _memes_equipes(m["exterieur"], exterieur):
            if m.get("score") is not None and m.get("heure") == "TER":
                return m["score"]
            return None
    return None


def page_du_jour(date_obj, cache_pages):
    """Cache mémoire simple -- plusieurs matchs de jours différents peuvent
    partager le même jour candidat (ex. le 28/08 est à la fois "J" pour un
    match et "J+1" pour un match daté 27/08), pas de raison de retélécharger
    la même page plusieurs fois dans un même passage du script."""
    if date_obj not in cache_pages:
        url = url_resultat_foot(date_obj)
        try:
            html, _ = fetch_html(url)
            cache_pages[date_obj] = parse_matches(html, max_matchs=2000, date_label=date_obj.isoformat())
        except Exception as e:
            print(f"[corrige_dates] échec récupération {url} : {e}", file=sys.stderr)
            cache_pages[date_obj] = []
    return cache_pages[date_obj]


def trouve_jour(historique, date_iso):
    for jour in historique:
        if jour["date"] == date_iso:
            return jour
    return None


def corrige(historique, cache_pages, dry_run):
    total_corriges = 0
    total_introuvables = 0

    # Liste figée des matchs candidats AVANT toute modification -- on va
    # déplacer des matchs entre buckets pendant qu'on itère, donc on
    # construit d'abord la liste complète (jour_original, match) plutôt
    # que de modifier `historique` pendant qu'on le parcourt.
    candidats = []
    for jour in historique:
        date_obj = datetime.date.fromisoformat(jour["date"])
        if not (DEBUT_FENETRE_BUGUEE <= date_obj <= FIN_FENETRE_BUGUEE):
            continue
        for m in jour.get("matchs", []):
            if m.get("verdict_global") and m.get("score") is None:
                candidats.append((jour, m))

    print(f"[corrige_dates] {len(candidats)} match(s) candidat(s) (analysés, sans score, "
          f"datés entre {DEBUT_FENETRE_BUGUEE} et {FIN_FENETRE_BUGUEE}).")

    for jour_original, m in candidats:
        date_enregistree = datetime.date.fromisoformat(m.get("date", jour_original["date"]))
        trouve = False

        for offset in (0, -1, 1):  # date enregistrée d'abord, puis J-1, puis J+1
            date_essai = date_enregistree + datetime.timedelta(days=offset)
            matchs_page = page_du_jour(date_essai, cache_pages)
            score = trouve_score_termine(matchs_page, m["domicile"], m["exterieur"])
            if score is None:
                continue

            trouve = True
            total_corriges += 1
            ancienne_date = m.get("date")
            m["score"] = score
            m["score_verifie_le"] = datetime.datetime.utcnow().isoformat() + "Z"
            m["date"] = date_essai.isoformat()
            m["date_corrigee_le_05_09_2026"] = f"était {ancienne_date}, décalage bug fuseau horaire"

            print(f"[corrige_dates] {'(dry-run) ' if dry_run else ''}"
                  f"{m['domicile']} - {m['exterieur']} : score {score} trouvé sur "
                  f"{date_essai.isoformat()} (enregistré à tort sous {ancienne_date}, "
                  f"décalage {offset:+d} jour(s))")

            if date_essai.isoformat() != jour_original["date"]:
                jour_original["matchs"].remove(m)
                nouveau_jour = trouve_jour(historique, date_essai.isoformat())
                if nouveau_jour is None:
                    nouveau_jour = {"date": date_essai.isoformat(), "matchs": []}
                    historique.append(nouveau_jour)
                nouveau_jour["matchs"].append(m)
            break

        if not trouve:
            total_introuvables += 1
            print(f"[corrige_dates] introuvable (J-1/J/J+1 essayés) : "
                  f"{m['domicile']} - {m['exterieur']} (enregistré {date_enregistree.isoformat()})")

    historique.sort(key=lambda j: j["date"])
    return total_corriges, total_introuvables


def main():
    dry_run = "--dry-run" in sys.argv
    historique = charge_historique()
    cache_pages = {}

    total_corriges, total_introuvables = corrige(historique, cache_pages, dry_run)

    if dry_run:
        print(f"[corrige_dates] DRY-RUN -- {total_corriges} score(s) auraient été corrigés, "
              f"{total_introuvables} toujours introuvables. Fichier NON modifié.")
    else:
        sauve_historique(historique)
        print(f"[corrige_dates] {total_corriges} score(s) corrigé(s) et sauvegardés, "
              f"{total_introuvables} toujours introuvables après ce passage.")


if __name__ == "__main__":
    main()
